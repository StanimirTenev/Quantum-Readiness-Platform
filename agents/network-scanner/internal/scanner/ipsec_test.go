package scanner

import (
	"encoding/binary"
	"net"
	"testing"
)

// buildFakeAcceptResponse constructs a minimal, well-formed IKE_SA_INIT
// response (header + SA payload selecting one transform per type) echoing
// the given initiator SPI, mirroring what a real responder like strongSwan
// sends when it accepts a proposal.
func buildFakeAcceptResponse(initSPI []byte, encrID, prfID, integID, dhID uint16) []byte {
	transforms := [][]byte{
		buildTransform(false, ikeTransformTypeEncr, encrID, keyLengthAttribute(256)),
		buildTransform(false, ikeTransformTypeInteg, integID, nil),
		buildTransform(false, ikeTransformTypePRF, prfID, nil),
		buildTransform(true, ikeTransformTypeDH, dhID, nil),
	}
	var transformBytes []byte
	for _, t := range transforms {
		transformBytes = append(transformBytes, t...)
	}
	proposal := []byte{0, 0}
	proposal = append(proposal, putU16(uint16(8+len(transformBytes)))...)
	proposal = append(proposal, 1, 1, 0, byte(len(transforms)))
	proposal = append(proposal, transformBytes...)

	saPayload := append([]byte{ikePayloadNone, 0}, putU16(uint16(4+len(proposal)))...)
	saPayload = append(saPayload, proposal...)

	return buildFakeIKEHeader(initSPI, ikePayloadSA, saPayload)
}

// buildFakeRejectResponse constructs an IKE_SA_INIT response carrying a
// single NOTIFY payload (e.g. NO_PROPOSAL_CHOSEN), mirroring a responder
// declining every offered transform.
func buildFakeRejectResponse(initSPI []byte, notifyType uint16) []byte {
	notifyBody := []byte{0, 0} // protocol=none, spi-size=0
	notifyBody = append(notifyBody, putU16(notifyType)...)
	notifyPayload := append([]byte{ikePayloadNone, 0}, putU16(uint16(4+len(notifyBody)))...)
	notifyPayload = append(notifyPayload, notifyBody...)

	return buildFakeIKEHeader(initSPI, ikePayloadNotify, notifyPayload)
}

func buildFakeIKEHeader(initSPI []byte, firstPayload byte, body []byte) []byte {
	header := make([]byte, ikeHeaderLength)
	copy(header[0:8], initSPI)
	// responder SPI (bytes 8:16) left as fixed test bytes
	copy(header[8:16], []byte{1, 2, 3, 4, 5, 6, 7, 8})
	header[16] = firstPayload
	header[17] = ikeVersion2
	header[18] = ikeExchangeSAInit
	header[19] = ikeFlagResponse
	binary.BigEndian.PutUint32(header[24:28], uint32(ikeHeaderLength+len(body)))
	return append(header, body...)
}

func startFakeIKEServer(t *testing.T, respond func(request []byte) []byte) string {
	t.Helper()
	conn, err := net.ListenPacket("udp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("failed to start fake IKE server: %v", err)
	}
	t.Cleanup(func() { conn.Close() })

	go func() {
		buf := make([]byte, 4096)
		n, addr, err := conn.ReadFrom(buf)
		if err != nil {
			return
		}
		response := respond(buf[:n])
		if response != nil {
			conn.WriteTo(response, addr)
		}
	}()

	return conn.LocalAddr().String()
}

func TestScanIPsecParsesAcceptedProposal(t *testing.T) {
	var capturedSPI []byte
	addr := startFakeIKEServer(t, func(request []byte) []byte {
		capturedSPI = append([]byte{}, request[0:8]...)
		return buildFakeAcceptResponse(capturedSPI, 12, 5, 12, 14) // AES-CBC, SHA2-256 PRF, SHA2-256-128 integ, group14
	})

	result, err := ScanIPsec(addr, 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if !result.IPsecMetadata.Collected {
		t.Fatalf("expected Collected=true, errors=%v", result.IPsecMetadata.Errors)
	}
	if result.IPsecMetadata.IKEVersion != "2.0" {
		t.Fatalf("unexpected IKE version: %q", result.IPsecMetadata.IKEVersion)
	}
	if result.IPsecMetadata.SelectedEncryption != "AES-CBC" {
		t.Fatalf("unexpected encryption: %q", result.IPsecMetadata.SelectedEncryption)
	}
	if result.IPsecMetadata.SelectedPRF != "HMAC-SHA2-256" {
		t.Fatalf("unexpected PRF: %q", result.IPsecMetadata.SelectedPRF)
	}
	if result.IPsecMetadata.SelectedIntegrity != "HMAC-SHA2-256-128" {
		t.Fatalf("unexpected integrity: %q", result.IPsecMetadata.SelectedIntegrity)
	}
	if result.IPsecMetadata.SelectedDHGroup != "2048-bit MODP" {
		t.Fatalf("unexpected DH group: %q", result.IPsecMetadata.SelectedDHGroup)
	}
	if result.IPsecMetadata.RejectedNotify != "" {
		t.Fatalf("expected no rejection notify, got %q", result.IPsecMetadata.RejectedNotify)
	}
	if result.Source != "network" {
		t.Fatalf("expected source=network, got %q", result.Source)
	}
}

func TestScanIPsecParsesWeakSelectionFromLegacyResponder(t *testing.T) {
	addr := startFakeIKEServer(t, func(request []byte) []byte {
		initSPI := request[0:8]
		return buildFakeAcceptResponse(initSPI, 3, 2, 2, 2) // 3DES, SHA1 PRF, SHA1-96 integ, group2 (all weak/legacy)
	})

	result, err := ScanIPsec(addr, 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.IPsecMetadata.SelectedEncryption != "3DES" {
		t.Fatalf("unexpected encryption: %q", result.IPsecMetadata.SelectedEncryption)
	}
	if result.IPsecMetadata.SelectedDHGroup != "1024-bit MODP" {
		t.Fatalf("unexpected DH group: %q", result.IPsecMetadata.SelectedDHGroup)
	}
}

func TestScanIPsecParsesRejectedProposal(t *testing.T) {
	addr := startFakeIKEServer(t, func(request []byte) []byte {
		initSPI := request[0:8]
		return buildFakeRejectResponse(initSPI, 14) // NO_PROPOSAL_CHOSEN
	})

	result, err := ScanIPsec(addr, 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !result.IPsecMetadata.Collected {
		t.Fatal("expected Collected=true (we did get a real response, just a rejection)")
	}
	if result.IPsecMetadata.RejectedNotify != "NO_PROPOSAL_CHOSEN" {
		t.Fatalf("unexpected rejection notify: %q", result.IPsecMetadata.RejectedNotify)
	}
	if result.IPsecMetadata.SelectedEncryption != "" {
		t.Fatalf("expected no selected encryption on a rejection, got %q", result.IPsecMetadata.SelectedEncryption)
	}
}

func TestScanIPsecNoResponseIsGraceful(t *testing.T) {
	conn, err := net.ListenPacket("udp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("failed to reserve a port: %v", err)
	}
	addr := conn.LocalAddr().String()
	conn.Close() // free the port; nothing will ever respond

	result, err := ScanIPsec(addr, 1)
	if err != nil {
		t.Fatalf("ScanIPsec should not return an error for a missing response: %v", err)
	}
	if result.IPsecMetadata.Collected {
		t.Fatal("expected Collected=false when no response arrives")
	}
	if len(result.IPsecMetadata.Errors) == 0 {
		t.Fatal("expected a populated Errors slice")
	}
}

func TestScanIPsecIgnoresResponseWithMismatchedSPI(t *testing.T) {
	addr := startFakeIKEServer(t, func(request []byte) []byte {
		wrongSPI := []byte{9, 9, 9, 9, 9, 9, 9, 9}
		return buildFakeAcceptResponse(wrongSPI, 12, 5, 12, 14)
	})

	result, err := ScanIPsec(addr, 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.IPsecMetadata.Collected {
		t.Fatal("expected Collected=false for an SPI-mismatched response")
	}
	if len(result.IPsecMetadata.Errors) == 0 {
		t.Fatal("expected a populated Errors slice")
	}
}

func TestBuildIKESAInitRequestHasValidHeader(t *testing.T) {
	request, initSPI, err := buildIKESAInitRequest()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(request) < ikeHeaderLength {
		t.Fatalf("request too short: %d bytes", len(request))
	}
	for i, b := range initSPI {
		if request[i] != b {
			t.Fatalf("initiator SPI not present at expected offset")
		}
	}
	if request[17] != ikeVersion2 {
		t.Fatalf("unexpected version byte: 0x%x", request[17])
	}
	if request[18] != ikeExchangeSAInit {
		t.Fatalf("unexpected exchange type: %d", request[18])
	}
	if request[19] != ikeFlagInitiator {
		t.Fatalf("unexpected flags byte: 0x%x", request[19])
	}
	declaredLength := binary.BigEndian.Uint32(request[24:28])
	if int(declaredLength) != len(request) {
		t.Fatalf("declared length %d does not match actual length %d", declaredLength, len(request))
	}
}

func TestParseIKESAInitResponseRejectsWrongExchangeType(t *testing.T) {
	initSPI := []byte{1, 2, 3, 4, 5, 6, 7, 8}
	header := buildFakeIKEHeader(initSPI, ikePayloadNone, nil)
	header[18] = 35 // not IKE_SA_INIT

	_, err := parseIKESAInitResponse(header, initSPI)
	if err == nil {
		t.Fatal("expected an error for an unexpected exchange type")
	}
}

func TestParseIKESAInitResponseRejectsMissingResponseFlag(t *testing.T) {
	initSPI := []byte{1, 2, 3, 4, 5, 6, 7, 8}
	header := buildFakeIKEHeader(initSPI, ikePayloadNone, nil)
	header[19] = 0 // no response flag set

	_, err := parseIKESAInitResponse(header, initSPI)
	if err == nil {
		t.Fatal("expected an error when the response flag is not set")
	}
}

func TestScanIPsecInvalidTargetReturnsError(t *testing.T) {
	_, err := ScanIPsec("not-a-valid-target", 1)
	if err == nil {
		t.Fatal("expected an error for a malformed target")
	}
}
