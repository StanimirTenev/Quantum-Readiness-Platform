package scanner

import (
	"crypto/rand"
	"encoding/binary"
	"fmt"
	"net"
	"time"
)

// IKEv2 (RFC 7296) wire-format constants used to build a single IKE_SA_INIT
// request and parse the response. Read-only algorithm negotiation, same
// "single probe, non-aggressive" posture as ScanTLS/ScanSSH: no IKE_AUTH is
// ever attempted, no real Diffie-Hellman math is performed (the KE payload
// carries random bytes of the correct length -- responders select a
// transform, and reject on a KE-payload/group mismatch, before validating
// the DH value itself).
const (
	ikeVersion2       = 0x20 // major=2, minor=0
	ikeExchangeSAInit = 34
	ikeFlagInitiator  = 0x08
	ikeFlagResponse   = 0x20
	ikeHeaderLength   = 28

	ikePayloadNone   = 0
	ikePayloadSA     = 33
	ikePayloadKE     = 34
	ikePayloadNonce  = 40
	ikePayloadNotify = 41

	ikeTransformTypeEncr  = 1
	ikeTransformTypePRF   = 2
	ikeTransformTypeInteg = 3
	ikeTransformTypeDH    = 4

	ikeAttrKeyLengthTV = 0x800E

	ikeDefaultDHGroup = 14 // 2048-bit MODP; used for the KE payload's (fake) public value
	ikeKEPublicBytes  = 256
	ikeNonceBytes     = 32
)

var ikeEncryptionNames = map[uint16]string{
	1: "DES-IV64", 2: "DES", 3: "3DES", 5: "CAST", 6: "BLOWFISH",
	11: "NULL", 12: "AES-CBC", 13: "AES-CTR",
	18: "AES-GCM-16", 19: "AES-GCM-12", 20: "AES-GCM-8",
	23: "CHACHA20-POLY1305",
}

var ikePRFNames = map[uint16]string{
	1: "HMAC-MD5", 2: "HMAC-SHA1", 4: "AES128-XCBC",
	5: "HMAC-SHA2-256", 6: "HMAC-SHA2-384", 7: "HMAC-SHA2-512",
}

var ikeIntegrityNames = map[uint16]string{
	0: "NONE", 1: "HMAC-MD5-96", 2: "HMAC-SHA1-96", 3: "DES-MAC",
	4: "KPDK-MD5", 5: "AES-XCBC-96",
	12: "HMAC-SHA2-256-128", 13: "HMAC-SHA2-384-192", 14: "HMAC-SHA2-512-256",
}

var ikeDHGroupNames = map[uint16]string{
	1: "768-bit MODP", 2: "1024-bit MODP", 5: "1536-bit MODP",
	14: "2048-bit MODP", 15: "3072-bit MODP", 16: "4096-bit MODP",
	19: "256-bit random ECP", 20: "384-bit random ECP", 21: "521-bit random ECP",
	31: "Curve25519",
}

var ikeNotifyNames = map[uint16]string{
	14: "NO_PROPOSAL_CHOSEN",
	17: "INVALID_KE_PAYLOAD",
	24: "AUTHENTICATION_FAILED",
	34: "TEMPORARY_FAILURE",
}

// ScanIPsec sends a single IKEv2 IKE_SA_INIT request (RFC 7296) offering a
// spread of encryption/PRF/integrity/DH-group transforms -- including
// deliberately weak/legacy ones (3DES, 1024-bit MODP) alongside modern ones
// -- and reports whichever single transform combination the responder
// selects, or the rejection reason if it declines. Never proceeds past
// IKE_SA_INIT (no authentication, no tunnel is ever established).
func ScanIPsec(target string, timeoutSeconds int) (ScanOutput, error) {
	host, rawPort, err := net.SplitHostPort(target)
	if err != nil {
		return ScanOutput{}, fmt.Errorf("invalid target %q: %w", target, err)
	}
	port, err := parsePort(rawPort, target)
	if err != nil {
		return ScanOutput{}, err
	}

	baseOutput := ScanOutput{
		Source:        "network",
		TLSMetadata:   emptyTLSMetadata(host, port),
		SSHMetadata:   emptySSHMetadata(),
		IPsecMetadata: emptyIPsecMetadata(),
		Assets:        buildAssets(target),
	}
	baseOutput.IPsecMetadata.Target = host
	baseOutput.IPsecMetadata.Port = port

	request, initSPI, err := buildIKESAInitRequest()
	if err != nil {
		baseOutput.IPsecMetadata.Errors = []string{fmt.Sprintf("failed to build IKE_SA_INIT request: %v", err)}
		return baseOutput, nil
	}

	conn, err := net.DialTimeout("udp", target, time.Duration(timeoutSeconds)*time.Second)
	if err != nil {
		baseOutput.IPsecMetadata.Errors = []string{fmt.Sprintf("udp dial failed: %v", err)}
		return baseOutput, nil
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(time.Duration(timeoutSeconds) * time.Second))

	if _, err := conn.Write(request); err != nil {
		baseOutput.IPsecMetadata.Errors = []string{fmt.Sprintf("failed to send IKE_SA_INIT request: %v", err)}
		return baseOutput, nil
	}

	response := make([]byte, 4096)
	n, err := conn.Read(response)
	if err != nil {
		baseOutput.IPsecMetadata.Errors = []string{fmt.Sprintf("no IKE_SA_INIT response received: %v", err)}
		return baseOutput, nil
	}

	parsed, err := parseIKESAInitResponse(response[:n], initSPI)
	if err != nil {
		baseOutput.IPsecMetadata.Errors = []string{fmt.Sprintf("failed to parse IKE_SA_INIT response: %v", err)}
		return baseOutput, nil
	}

	baseOutput.IPsecMetadata.Collected = true
	baseOutput.IPsecMetadata.IKEVersion = parsed.ikeVersion
	baseOutput.IPsecMetadata.SelectedEncryption = parsed.selectedEncryption
	baseOutput.IPsecMetadata.SelectedPRF = parsed.selectedPRF
	baseOutput.IPsecMetadata.SelectedIntegrity = parsed.selectedIntegrity
	baseOutput.IPsecMetadata.SelectedDHGroup = parsed.selectedDHGroup
	baseOutput.IPsecMetadata.RejectedNotify = parsed.rejectedNotify

	return baseOutput, nil
}

func parsePort(rawPort, target string) (int, error) {
	port := 0
	if _, err := fmt.Sscanf(rawPort, "%d", &port); err != nil || port <= 0 {
		return 0, fmt.Errorf("invalid target %q: invalid port %q", target, rawPort)
	}
	return port, nil
}

// --- Request construction -------------------------------------------------

func putU16(v uint16) []byte {
	b := make([]byte, 2)
	binary.BigEndian.PutUint16(b, v)
	return b
}

// buildTransform encodes one Transform substructure (RFC 7296 SS3.3.2).
func buildTransform(last bool, transformType byte, transformID uint16, attrs []byte) []byte {
	lastByte := byte(3) // "more transforms follow"
	if last {
		lastByte = 0
	}
	length := 8 + len(attrs)
	buf := make([]byte, 0, length)
	buf = append(buf, lastByte, 0)
	buf = append(buf, putU16(uint16(length))...)
	buf = append(buf, transformType, 0)
	buf = append(buf, putU16(transformID)...)
	buf = append(buf, attrs...)
	return buf
}

// keyLengthAttribute encodes a Key Length transform attribute in TV form
// (RFC 7296 SS3.3.5) -- required alongside variable-key-length ciphers like AES.
func keyLengthAttribute(bits uint16) []byte {
	buf := make([]byte, 0, 4)
	buf = append(buf, putU16(ikeAttrKeyLengthTV)...)
	buf = append(buf, putU16(bits)...)
	return buf
}

// buildIKESAInitRequest builds a full IKE_SA_INIT request (header + SA + KE
// + Nonce payloads) offering AES-CBC-256/128 and 3DES encryption,
// SHA2-256/SHA1 PRF and integrity, and 2048-bit/1024-bit MODP DH groups --
// deliberately spanning modern and legacy/weak options so the responder's
// selection is informative. Returns the request bytes and the initiator SPI
// (needed to validate the response echoes it back).
func buildIKESAInitRequest() ([]byte, []byte, error) {
	transforms := [][]byte{
		buildTransform(false, ikeTransformTypeEncr, 12, keyLengthAttribute(256)), // AES-CBC-256
		buildTransform(false, ikeTransformTypeEncr, 12, keyLengthAttribute(128)), // AES-CBC-128
		buildTransform(false, ikeTransformTypeEncr, 3, nil),                      // 3DES (weak, deliberately offered)
		buildTransform(false, ikeTransformTypePRF, 5, nil),                       // HMAC-SHA2-256
		buildTransform(false, ikeTransformTypePRF, 2, nil),                       // HMAC-SHA1
		buildTransform(false, ikeTransformTypeInteg, 12, nil),                    // HMAC-SHA2-256-128
		buildTransform(false, ikeTransformTypeInteg, 2, nil),                     // HMAC-SHA1-96
		buildTransform(false, ikeTransformTypeDH, 14, nil),                       // 2048-bit MODP
		buildTransform(true, ikeTransformTypeDH, 2, nil),                         // 1024-bit MODP (weak, last)
	}
	var transformBytes []byte
	for _, t := range transforms {
		transformBytes = append(transformBytes, t...)
	}

	proposal := []byte{0, 0} // last proposal, reserved
	proposal = append(proposal, putU16(uint16(8+len(transformBytes)))...)
	proposal = append(proposal, 1, 1, 0, byte(len(transforms))) // proposal#1, protocol=IKE, spi-size=0, num-transforms
	proposal = append(proposal, transformBytes...)

	saPayload := append([]byte{ikePayloadKE, 0}, putU16(uint16(4+len(proposal)))...)
	saPayload = append(saPayload, proposal...)

	kePublic := make([]byte, ikeKEPublicBytes)
	if _, err := rand.Read(kePublic); err != nil {
		return nil, nil, fmt.Errorf("generate KE payload randomness: %w", err)
	}
	keBody := append(putU16(ikeDefaultDHGroup), 0, 0)
	keBody = append(keBody, kePublic...)
	kePayload := append([]byte{ikePayloadNonce, 0}, putU16(uint16(4+len(keBody)))...)
	kePayload = append(kePayload, keBody...)

	nonce := make([]byte, ikeNonceBytes)
	if _, err := rand.Read(nonce); err != nil {
		return nil, nil, fmt.Errorf("generate nonce: %w", err)
	}
	noncePayload := append([]byte{ikePayloadNone, 0}, putU16(uint16(4+len(nonce)))...)
	noncePayload = append(noncePayload, nonce...)

	body := append(append(saPayload, kePayload...), noncePayload...)

	initSPI := make([]byte, 8)
	if _, err := rand.Read(initSPI); err != nil {
		return nil, nil, fmt.Errorf("generate initiator SPI: %w", err)
	}

	header := make([]byte, ikeHeaderLength)
	copy(header[0:8], initSPI) // responder SPI (bytes 8:16) stays zero
	header[16] = ikePayloadSA
	header[17] = ikeVersion2
	header[18] = ikeExchangeSAInit
	header[19] = ikeFlagInitiator
	binary.BigEndian.PutUint32(header[24:28], uint32(ikeHeaderLength+len(body)))

	return append(header, body...), initSPI, nil
}

// --- Response parsing -------------------------------------------------------

type ikeSAInitResult struct {
	ikeVersion         string
	selectedEncryption string
	selectedPRF        string
	selectedIntegrity  string
	selectedDHGroup    string
	rejectedNotify     string
}

func parseIKESAInitResponse(data []byte, initSPI []byte) (ikeSAInitResult, error) {
	if len(data) < ikeHeaderLength {
		return ikeSAInitResult{}, fmt.Errorf("response too short (%d bytes)", len(data))
	}
	for i, b := range initSPI {
		if data[i] != b {
			return ikeSAInitResult{}, fmt.Errorf("initiator SPI mismatch -- not a response to our request")
		}
	}
	if data[18] != ikeExchangeSAInit {
		return ikeSAInitResult{}, fmt.Errorf("unexpected exchange type %d (expected IKE_SA_INIT=34)", data[18])
	}
	if data[19]&ikeFlagResponse == 0 {
		return ikeSAInitResult{}, fmt.Errorf("response flag not set -- not a response packet")
	}

	majorVersion := data[17] >> 4
	minorVersion := data[17] & 0x0F
	result := ikeSAInitResult{ikeVersion: fmt.Sprintf("%d.%d", majorVersion, minorVersion)}

	nextPayload := data[16]
	offset := ikeHeaderLength
	var notifyTypes []uint16

	for nextPayload != ikePayloadNone && offset+4 <= len(data) {
		payloadType := nextPayload
		payloadLength := int(binary.BigEndian.Uint16(data[offset+2 : offset+4]))
		if payloadLength < 4 || offset+payloadLength > len(data) {
			return result, fmt.Errorf("malformed payload at offset %d (length %d)", offset, payloadLength)
		}
		payloadBody := data[offset+4 : offset+payloadLength]
		nextPayload = data[offset]

		switch payloadType {
		case ikePayloadSA:
			applySelectedTransforms(payloadBody, &result)
		case ikePayloadNotify:
			if notifyType, ok := readNotifyType(payloadBody); ok {
				notifyTypes = append(notifyTypes, notifyType)
			}
		}

		offset += payloadLength
	}

	// A response can legitimately carry both an accepted SA proposal and
	// informational Notify payloads (e.g. NAT detection, vendor-specific
	// private-use extensions) -- only surface a notify as a *rejection* when
	// there's no accepted proposal alongside it.
	if result.selectedEncryption == "" && len(notifyTypes) > 0 {
		result.rejectedNotify = lookupOrNumeric(ikeNotifyNames, notifyTypes[0])
	}

	return result, nil
}

// applySelectedTransforms walks the first (and, for an accepted IKE_SA_INIT
// response, only) Proposal in an SA payload and records each transform's
// human-readable name by type.
func applySelectedTransforms(saBody []byte, result *ikeSAInitResult) {
	if len(saBody) < 8 {
		return
	}
	numTransforms := int(saBody[7])
	offset := 8 + int(saBody[6]) // skip past any proposal-level SPI

	for i := 0; i < numTransforms && offset+8 <= len(saBody); i++ {
		transformType := saBody[offset+4]
		transformID := binary.BigEndian.Uint16(saBody[offset+6 : offset+8])
		transformLength := int(binary.BigEndian.Uint16(saBody[offset+2 : offset+4]))
		if transformLength < 8 || offset+transformLength > len(saBody) {
			return
		}

		switch transformType {
		case ikeTransformTypeEncr:
			result.selectedEncryption = lookupOrNumeric(ikeEncryptionNames, transformID)
		case ikeTransformTypePRF:
			result.selectedPRF = lookupOrNumeric(ikePRFNames, transformID)
		case ikeTransformTypeInteg:
			result.selectedIntegrity = lookupOrNumeric(ikeIntegrityNames, transformID)
		case ikeTransformTypeDH:
			result.selectedDHGroup = lookupOrNumeric(ikeDHGroupNames, transformID)
		}

		offset += transformLength
	}
}

// readNotifyType extracts a NOTIFY payload's message type (e.g.
// NO_PROPOSAL_CHOSEN). Whether it represents a rejection or just an
// informational extension is decided by the caller, once the full payload
// chain has been walked.
func readNotifyType(notifyBody []byte) (uint16, bool) {
	if len(notifyBody) < 4 {
		return 0, false
	}
	spiSize := int(notifyBody[1])
	if 4+spiSize > len(notifyBody) {
		return 0, false
	}
	return binary.BigEndian.Uint16(notifyBody[2+spiSize : 4+spiSize]), true
}

func lookupOrNumeric(names map[uint16]string, id uint16) string {
	if name, ok := names[id]; ok {
		return name
	}
	return fmt.Sprintf("unknown(%d)", id)
}
