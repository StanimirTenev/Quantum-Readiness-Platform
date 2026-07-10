package scanner

import (
	"encoding/binary"
	"net"
	"testing"
	"time"
)

// buildKexInitPacket constructs a full Binary Packet Protocol frame carrying
// an SSH_MSG_KEXINIT payload with the given name-lists (kex, host key, enc
// c2s/s2c, mac c2s/s2c; compression and languages are left empty).
func buildKexInitPacket(kex, hostKey, encC2S, encS2C, macC2S, macS2C []string) []byte {
	payload := []byte{sshMsgKexInit}
	payload = append(payload, make([]byte, 16)...) // cookie

	lists := [][]string{kex, hostKey, encC2S, encS2C, macC2S, macS2C, {}, {}, {}, {}}
	for _, list := range lists {
		joined := ""
		for i, name := range list {
			if i > 0 {
				joined += ","
			}
			joined += name
		}
		lengthBuf := make([]byte, 4)
		binary.BigEndian.PutUint32(lengthBuf, uint32(len(joined)))
		payload = append(payload, lengthBuf...)
		payload = append(payload, []byte(joined)...)
	}
	payload = append(payload, 0)          // first_kex_packet_follows = false
	payload = append(payload, 0, 0, 0, 0) // reserved

	paddingLen := 8
	packetLength := 1 + len(payload) + paddingLen

	frame := make([]byte, 4)
	binary.BigEndian.PutUint32(frame, uint32(packetLength))
	frame = append(frame, byte(paddingLen))
	frame = append(frame, payload...)
	frame = append(frame, make([]byte, paddingLen)...)
	return frame
}

func startFakeSSHServer(t *testing.T, banner string, kexPacket []byte) string {
	t.Helper()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("failed to start fake SSH server: %v", err)
	}
	t.Cleanup(func() { listener.Close() })

	go func() {
		conn, err := listener.Accept()
		if err != nil {
			return
		}
		defer conn.Close()

		conn.Write([]byte(banner))

		// Drain the client's identification line before sending KEXINIT,
		// mirroring real server behavior.
		buf := make([]byte, 256)
		conn.SetReadDeadline(time.Now().Add(2 * time.Second))
		conn.Read(buf)

		if kexPacket != nil {
			conn.Write(kexPacket)
		}
	}()

	return listener.Addr().String()
}

func TestScanSSHParsesRealHandshake(t *testing.T) {
	kexPacket := buildKexInitPacket(
		[]string{"curve25519-sha256", "diffie-hellman-group14-sha256"},
		[]string{"rsa-sha2-512", "ssh-ed25519"},
		[]string{"chacha20-poly1305@openssh.com", "aes256-gcm@openssh.com"},
		[]string{"chacha20-poly1305@openssh.com", "aes256-gcm@openssh.com"},
		[]string{"umac-64-etm@openssh.com"},
		[]string{"umac-64-etm@openssh.com"},
	)
	addr := startFakeSSHServer(t, "SSH-2.0-OpenSSH_9.6\r\n", kexPacket)

	result, err := ScanSSH(addr, 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if !result.SSHMetadata.Collected {
		t.Fatalf("expected Collected=true, errors=%v", result.SSHMetadata.Errors)
	}
	if result.SSHMetadata.ServerBanner != "SSH-2.0-OpenSSH_9.6" {
		t.Fatalf("unexpected banner: %q", result.SSHMetadata.ServerBanner)
	}
	if len(result.SSHMetadata.KexAlgorithms) != 2 || result.SSHMetadata.KexAlgorithms[0] != "curve25519-sha256" {
		t.Fatalf("unexpected kex algorithms: %v", result.SSHMetadata.KexAlgorithms)
	}
	if len(result.SSHMetadata.ServerHostKeyAlgorithms) != 2 || result.SSHMetadata.ServerHostKeyAlgorithms[1] != "ssh-ed25519" {
		t.Fatalf("unexpected host key algorithms: %v", result.SSHMetadata.ServerHostKeyAlgorithms)
	}
	if len(result.SSHMetadata.MACAlgorithmsClientToServer) != 1 {
		t.Fatalf("unexpected mac algorithms: %v", result.SSHMetadata.MACAlgorithmsClientToServer)
	}
	if result.Source != "network" {
		t.Fatalf("expected source=network, got %q", result.Source)
	}
	if len(result.Assets) != 1 || result.Assets[0].Name != addr {
		t.Fatalf("unexpected assets: %+v", result.Assets)
	}
}

func TestScanSSHParsesLegacyAlgorithmNames(t *testing.T) {
	kexPacket := buildKexInitPacket(
		[]string{"diffie-hellman-group1-sha1"},
		[]string{"ssh-rsa", "ssh-dss"},
		[]string{"3des-cbc"},
		[]string{"3des-cbc"},
		[]string{"hmac-sha1"},
		[]string{"hmac-sha1"},
	)
	addr := startFakeSSHServer(t, "SSH-2.0-OldServer_1.0\r\n", kexPacket)

	result, err := ScanSSH(addr, 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !result.SSHMetadata.Collected {
		t.Fatalf("expected Collected=true, errors=%v", result.SSHMetadata.Errors)
	}
	if result.SSHMetadata.KexAlgorithms[0] != "diffie-hellman-group1-sha1" {
		t.Fatalf("unexpected kex algorithms: %v", result.SSHMetadata.KexAlgorithms)
	}
	if result.SSHMetadata.ServerHostKeyAlgorithms[0] != "ssh-rsa" || result.SSHMetadata.ServerHostKeyAlgorithms[1] != "ssh-dss" {
		t.Fatalf("unexpected host key algorithms: %v", result.SSHMetadata.ServerHostKeyAlgorithms)
	}
}

func TestScanSSHConnectionRefusedIsGraceful(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("failed to reserve a port: %v", err)
	}
	addr := listener.Addr().String()
	listener.Close() // free the port so the dial below fails with connection refused

	result, err := ScanSSH(addr, 1)
	if err != nil {
		t.Fatalf("ScanSSH should not return an error for a failed connection: %v", err)
	}
	if result.SSHMetadata.Collected {
		t.Fatal("expected Collected=false for a refused connection")
	}
	if len(result.SSHMetadata.Errors) == 0 {
		t.Fatal("expected a populated Errors slice")
	}
}

func TestScanSSHNoBannerIsGraceful(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("failed to start listener: %v", err)
	}
	t.Cleanup(func() { listener.Close() })

	go func() {
		conn, err := listener.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		time.Sleep(2 * time.Second) // never sends a banner within the scan's 1s timeout
	}()

	result, err := ScanSSH(listener.Addr().String(), 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.SSHMetadata.Collected {
		t.Fatal("expected Collected=false when no banner arrives in time")
	}
	if len(result.SSHMetadata.Errors) == 0 {
		t.Fatal("expected a populated Errors slice")
	}
}

func TestParseKexInitRejectsWrongMessageType(t *testing.T) {
	_, err := parseKexInit([]byte{99, 0, 0})
	if err == nil {
		t.Fatal("expected an error for a non-KEXINIT message type")
	}
}

func TestReadNameListParsesCommaSeparatedNames(t *testing.T) {
	payload := []byte{0, 0, 0, 7, 'a', ',', 'b', ',', 'c', 'c', 'c'}
	names, next, err := readNameList(payload, 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if next != 11 {
		t.Fatalf("expected next offset 11, got %d", next)
	}
	if len(names) != 3 || names[2] != "ccc" {
		t.Fatalf("unexpected names: %v", names)
	}
}

func TestReadNameListHandlesEmptyList(t *testing.T) {
	payload := []byte{0, 0, 0, 0}
	names, next, err := readNameList(payload, 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if next != 4 {
		t.Fatalf("expected next offset 4, got %d", next)
	}
	if len(names) != 0 {
		t.Fatalf("expected empty list, got %v", names)
	}
}
