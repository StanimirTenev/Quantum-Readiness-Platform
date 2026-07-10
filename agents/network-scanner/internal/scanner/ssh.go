package scanner

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"strconv"
	"strings"
	"time"
)

const (
	sshMsgKexInit       = 20
	sshMaxBannerLines   = 20
	sshMaxPacketLength  = 256 * 1024 // generous upper bound; a real KEXINIT is a few KB at most
	sshClientIdentifier = "SSH-2.0-QRP-network-scanner\r\n"
)

// ScanSSH performs a single, read-only SSH protocol handshake: it reads the
// server's identification banner and its SSH_MSG_KEXINIT packet (both sent
// in plaintext before any key exchange, per RFC 4253) to observe which
// algorithms the server offers. It never completes key exchange or attempts
// authentication -- same "single dial, non-aggressive" posture as ScanTLS.
func ScanSSH(target string, timeoutSeconds int) (ScanOutput, error) {
	host, rawPort, err := net.SplitHostPort(target)
	if err != nil {
		return ScanOutput{}, fmt.Errorf("invalid target %q: %w", target, err)
	}

	port, err := strconv.Atoi(rawPort)
	if err != nil {
		return ScanOutput{}, fmt.Errorf("invalid target %q: invalid port %q", target, rawPort)
	}

	baseOutput := ScanOutput{
		Source:      "network",
		TLSMetadata: emptyTLSMetadata(host, port),
		SSHMetadata: emptySSHMetadata(),
		Assets:      buildAssets(target),
	}
	baseOutput.SSHMetadata.Target = host
	baseOutput.SSHMetadata.Port = port

	dialer := &net.Dialer{Timeout: time.Duration(timeoutSeconds) * time.Second}
	conn, err := dialer.Dial("tcp", target)
	if err != nil {
		baseOutput.SSHMetadata.Errors = []string{fmt.Sprintf("tcp dial failed: %v", err)}
		return baseOutput, nil
	}
	defer conn.Close()

	deadline := time.Now().Add(time.Duration(timeoutSeconds) * time.Second)
	_ = conn.SetDeadline(deadline)

	reader := bufio.NewReader(conn)

	banner, err := readSSHBanner(reader)
	if err != nil {
		baseOutput.SSHMetadata.Errors = []string{fmt.Sprintf("failed to read SSH identification banner: %v", err)}
		return baseOutput, nil
	}
	baseOutput.SSHMetadata.ServerBanner = banner

	if _, err := conn.Write([]byte(sshClientIdentifier)); err != nil {
		baseOutput.SSHMetadata.Errors = []string{fmt.Sprintf("failed to send client identification: %v", err)}
		return baseOutput, nil
	}

	payload, err := readSSHBinaryPacket(reader)
	if err != nil {
		baseOutput.SSHMetadata.Errors = []string{fmt.Sprintf("failed to read SSH_MSG_KEXINIT packet: %v", err)}
		return baseOutput, nil
	}

	kexInit, err := parseKexInit(payload)
	if err != nil {
		baseOutput.SSHMetadata.Errors = []string{fmt.Sprintf("failed to parse SSH_MSG_KEXINIT: %v", err)}
		return baseOutput, nil
	}

	baseOutput.SSHMetadata.Collected = true
	baseOutput.SSHMetadata.KexAlgorithms = kexInit.kexAlgorithms
	baseOutput.SSHMetadata.ServerHostKeyAlgorithms = kexInit.serverHostKeyAlgorithms
	baseOutput.SSHMetadata.EncryptionAlgorithmsClientToServer = kexInit.encryptionClientToServer
	baseOutput.SSHMetadata.EncryptionAlgorithmsServerToClient = kexInit.encryptionServerToClient
	baseOutput.SSHMetadata.MACAlgorithmsClientToServer = kexInit.macClientToServer
	baseOutput.SSHMetadata.MACAlgorithmsServerToClient = kexInit.macServerToClient

	return baseOutput, nil
}

// readSSHBanner reads lines until it finds the SSH identification string
// (starts with "SSH-"), per RFC 4253 SS4.2: a server MAY send other lines
// before it. Bounded so a misbehaving peer can't stall or exhaust memory.
func readSSHBanner(reader *bufio.Reader) (string, error) {
	for i := 0; i < sshMaxBannerLines; i++ {
		line, err := reader.ReadString('\n')
		if err != nil {
			return "", err
		}
		line = strings.TrimRight(line, "\r\n")
		if strings.HasPrefix(line, "SSH-") {
			return line, nil
		}
	}
	return "", fmt.Errorf("no SSH identification string within %d lines", sshMaxBannerLines)
}

// readSSHBinaryPacket reads one Binary Packet Protocol frame (RFC 4253 SS6)
// and returns its payload. Only valid before encryption is established
// (mac_length is 0), which is the case for the initial KEXINIT exchange.
func readSSHBinaryPacket(reader io.Reader) ([]byte, error) {
	lengthBuf := make([]byte, 4)
	if _, err := io.ReadFull(reader, lengthBuf); err != nil {
		return nil, err
	}
	packetLength := binary.BigEndian.Uint32(lengthBuf)
	if packetLength == 0 || packetLength > sshMaxPacketLength {
		return nil, fmt.Errorf("implausible packet length: %d", packetLength)
	}

	rest := make([]byte, packetLength)
	if _, err := io.ReadFull(reader, rest); err != nil {
		return nil, err
	}

	paddingLength := int(rest[0])
	payloadEnd := len(rest) - paddingLength
	if payloadEnd < 1 {
		return nil, fmt.Errorf("invalid padding length %d for packet length %d", paddingLength, packetLength)
	}

	payload := rest[1:payloadEnd]
	if len(payload) == 0 {
		return nil, fmt.Errorf("empty packet payload")
	}
	return payload, nil
}

type kexInitPayload struct {
	kexAlgorithms            []string
	serverHostKeyAlgorithms  []string
	encryptionClientToServer []string
	encryptionServerToClient []string
	macClientToServer        []string
	macServerToClient        []string
}

// parseKexInit parses an SSH_MSG_KEXINIT payload (RFC 4253 SS7.1): message
// type byte, 16-byte cookie, then 10 name-lists in a fixed order.
func parseKexInit(payload []byte) (kexInitPayload, error) {
	if len(payload) < 1 || payload[0] != sshMsgKexInit {
		return kexInitPayload{}, fmt.Errorf("unexpected message type %v (expected SSH_MSG_KEXINIT=20)", firstByteOrNegative(payload))
	}
	offset := 1 + 16 // type byte + cookie
	if offset > len(payload) {
		return kexInitPayload{}, fmt.Errorf("payload too short for KEXINIT cookie")
	}

	nameLists := make([][]string, 10)
	for i := 0; i < 10; i++ {
		list, next, err := readNameList(payload, offset)
		if err != nil {
			return kexInitPayload{}, fmt.Errorf("name-list %d: %w", i, err)
		}
		nameLists[i] = list
		offset = next
	}

	return kexInitPayload{
		kexAlgorithms:            nameLists[0],
		serverHostKeyAlgorithms:  nameLists[1],
		encryptionClientToServer: nameLists[2],
		encryptionServerToClient: nameLists[3],
		macClientToServer:        nameLists[4],
		macServerToClient:        nameLists[5],
	}, nil
}

// readNameList reads a uint32-length-prefixed, comma-separated ASCII name-list
// starting at offset, returning the parsed names and the offset just past it.
func readNameList(payload []byte, offset int) ([]string, int, error) {
	if offset+4 > len(payload) {
		return nil, 0, fmt.Errorf("truncated before length prefix")
	}
	length := int(binary.BigEndian.Uint32(payload[offset : offset+4]))
	offset += 4
	if length < 0 || offset+length > len(payload) {
		return nil, 0, fmt.Errorf("truncated name-list body (length %d)", length)
	}
	raw := string(payload[offset : offset+length])
	offset += length

	if raw == "" {
		return []string{}, offset, nil
	}
	return strings.Split(raw, ","), offset, nil
}

func firstByteOrNegative(payload []byte) int {
	if len(payload) == 0 {
		return -1
	}
	return int(payload[0])
}
