package scanner

import (
	"crypto/dsa"
	"crypto/ecdsa"
	"crypto/ed25519"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"fmt"
	"net"
	"strconv"
	"strings"
	"time"
)

func ScanTLS(target string, insecure bool, timeoutSeconds int) (ScanOutput, error) {
	host, rawPort, err := net.SplitHostPort(target)
	if err != nil {
		return ScanOutput{}, fmt.Errorf("invalid target %q: %w", target, err)
	}

	port, err := strconv.Atoi(rawPort)
	if err != nil {
		return ScanOutput{}, fmt.Errorf("invalid target %q: invalid port %q", target, rawPort)
	}

	baseOutput := ScanOutput{
		Source: "network",
		TLSMetadata: TLSMetadata{
			Collected:       false,
			Target:          host,
			Port:            port,
			ServerName:      host,
			ProtocolVersion: "",
			CipherSuite:     "",
			Certificate:     nil,
			CertificateChain: unavailableCertificateChainSummary("chain details unavailable"),
			Errors:          []string{},
		},
		Assets: buildAssets(target),
	}

	dialer := &net.Dialer{
		Timeout: time.Duration(timeoutSeconds) * time.Second,
	}

	config := &tls.Config{
		InsecureSkipVerify: insecure, // intended for controlled scanning
		ServerName:         host,
		MinVersion:         tls.VersionTLS12,
	}

	conn, err := tls.DialWithDialer(dialer, "tcp", target, config)
	if err != nil {
		baseOutput.TLSMetadata.Errors = []string{fmt.Sprintf("tls dial failed: %v", err)}
		return baseOutput, nil
	}
	defer conn.Close()

	state := conn.ConnectionState()
	chainSummary := certificateChainSummary(state.PeerCertificates)
	if len(state.PeerCertificates) == 0 {
		baseOutput.TLSMetadata.CertificateChain = chainSummary
		baseOutput.TLSMetadata.Errors = []string{"no peer certificates returned"}
		return baseOutput, nil
	}

	cert := state.PeerCertificates[0]
	keyType, keySizeBits := certificateKeyMetadata(cert)
	chainInfo := certificateChainDetails(state, insecure)
	serverName := state.ServerName
	if strings.TrimSpace(serverName) == "" {
		serverName = host
	}

	evidence := TLSEvidence{
		Target:      target,
		TLSVersion:  tlsVersionString(state.Version),
		CipherSuite: tls.CipherSuiteName(state.CipherSuite),
		ServerName:  serverName,
		Certificate: CertificateInfo{
			Subject: CertificateParty{
				DisplayDN:   cert.Subject.String(),
				Fingerprint: nameFingerprint(cert.RawSubject),
			},
			Issuer: CertificateParty{
				DisplayDN:   cert.Issuer.String(),
				Fingerprint: nameFingerprint(cert.RawIssuer),
			},
			Validity: CertificateValidity{
				NotBefore: cert.NotBefore.Format(time.RFC3339),
				NotAfter:  cert.NotAfter.Format(time.RFC3339),
			},
			Algorithms: CertificateAlgorithms{
				Signature: cert.SignatureAlgorithm.String(),
				PublicKey: cert.PublicKeyAlgorithm.String(),
			},
			Key: CertificateKeyData{
				Type:     keyType,
				SizeBits: keySizeBits,
			},
			SAN: CertificateSAN{
				DNSNames: cert.DNSNames,
			},
		},
		CertificateChainInfo: chainInfo,
	}

	baseOutput.TLSEvidence = &evidence
	baseOutput.TLSMetadata = TLSMetadata{
		Collected:       true,
		Target:          host,
		Port:            port,
		ServerName:      serverName,
		ProtocolVersion: tlsVersionString(state.Version),
		CipherSuite:     tls.CipherSuiteName(state.CipherSuite),
		Certificate: &TLSCertificateBrief{
			Subject:            cert.Subject.String(),
			Issuer:             cert.Issuer.String(),
			NotBefore:          cert.NotBefore.Format(time.RFC3339),
			NotAfter:           cert.NotAfter.Format(time.RFC3339),
			SignatureAlgorithm: cert.SignatureAlgorithm.String(),
			PublicKeyAlgorithm: cert.PublicKeyAlgorithm.String(),
			PublicKeySize:      keySizeOrZero(keySizeBits),
			FingerprintSHA256:  certificateSHA256Fingerprint(cert.Raw),
		},
		CertificateChain: chainSummary,
		Errors: []string{},
	}

	return baseOutput, nil
}

func certificateChainSummary(peerCertificates []*x509.Certificate) TLSCertificateChainSummary {
	if len(peerCertificates) == 0 {
		return unavailableCertificateChainSummary("chain details unavailable")
	}

	certificates := make([]TLSCertificateBriefItem, 0, len(peerCertificates))
	for i, cert := range peerCertificates {
		_, keySizeBits := certificateKeyMetadata(cert)
		certificates = append(certificates, TLSCertificateBriefItem{
			Position:           i,
			Subject:            cert.Subject.String(),
			Issuer:             cert.Issuer.String(),
			NotBefore:          cert.NotBefore.Format(time.RFC3339),
			NotAfter:           cert.NotAfter.Format(time.RFC3339),
			SignatureAlgorithm: cert.SignatureAlgorithm.String(),
			PublicKeyAlgorithm: cert.PublicKeyAlgorithm.String(),
			PublicKeySize:      keySizeOrZero(keySizeBits),
			FingerprintSHA256:  certificateSHA256Fingerprint(cert.Raw),
		})
	}

	return TLSCertificateChainSummary{
		Available:    true,
		Length:       len(certificates),
		Certificates: certificates,
		Errors:       []string{},
	}
}

func unavailableCertificateChainSummary(reason string) TLSCertificateChainSummary {
	return TLSCertificateChainSummary{
		Available:    false,
		Length:       0,
		Certificates: []TLSCertificateBriefItem{},
		Errors:       []string{reason},
	}
}

func buildAssets(target string) []AssetPayload {
	criticality := 3
	environment := "unknown"
	lifecycleYears := 3

	return []AssetPayload{
		{
			AssetType:      "endpoint",
			Name:           target,
			Criticality:    &criticality,
			Environment:    &environment,
			LifecycleYears: &lifecycleYears,
		},
	}
}

func tlsVersionString(version uint16) string {
	switch version {
	case tls.VersionTLS13:
		return "TLS 1.3"
	case tls.VersionTLS12:
		return "TLS 1.2"
	case tls.VersionTLS11:
		return "TLS 1.1"
	case tls.VersionTLS10:
		return "TLS 1.0"
	default:
		return fmt.Sprintf("UNKNOWN(0x%x)", version)
	}
}

func keySizeOrZero(sizeBits *int) int {
	if sizeBits == nil {
		return 0
	}
	return *sizeBits
}

func certificateSHA256Fingerprint(raw []byte) string {
	if len(raw) == 0 {
		return ""
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

func IsTLSTarget(target string) bool {
	host, port, err := net.SplitHostPort(target)
	if err != nil {
		return false
	}
	return strings.TrimSpace(host) != "" && strings.TrimSpace(port) != ""
}

func certificateKeyMetadata(cert *x509.Certificate) (string, *int) {
	switch key := cert.PublicKey.(type) {
	case *rsa.PublicKey:
		bits := key.N.BitLen()
		return "RSA", &bits
	case *ecdsa.PublicKey:
		bits := key.Params().BitSize
		return "ECDSA", &bits
	case ed25519.PublicKey:
		bits := len(key) * 8
		return "Ed25519", &bits
	case *dsa.PublicKey:
		bits := key.P.BitLen()
		return "DSA", &bits
	default:
		return "", nil
	}
}

func nameFingerprint(raw []byte) string {
	if len(raw) == 0 {
		return ""
	}
	sum := sha256.Sum256(raw)
	return "SHA256:" + strings.ToUpper(hex.EncodeToString(sum[:]))
}

func certificateChainDetails(state tls.ConnectionState, insecure bool) CertificateChainDetails {
	presented := len(state.PeerCertificates)
	info := CertificateChainDetails{
		Available:              true,
		Presence:               presented > 0,
		PresentedChainLength:   presented,
		VerificationPerformed:  !insecure,
		VerifiedChainAvailable: false,
	}

	if len(state.VerifiedChains) > 0 {
		length := len(state.VerifiedChains[0])
		info.VerifiedChainLength = &length
		info.VerifiedChainAvailable = true
	}

	switch {
	case presented == 0:
		info.Available = false
		reason := "peer did not present certificates"
		info.UnavailableReason = &reason
		info.Summary = "No certificate chain was presented by the peer."
	case insecure:
		reason := "verification skipped because insecure mode is enabled"
		info.UnavailableReason = &reason
		info.Summary = fmt.Sprintf(
			"Presented chain length: %d. Verified chain unavailable (%s).",
			presented,
			reason,
		)
	case !info.VerifiedChainAvailable:
		reason := "verified chain unavailable from TLS state"
		info.UnavailableReason = &reason
		info.Summary = fmt.Sprintf(
			"Presented chain length: %d. Verified chain unavailable (%s).",
			presented,
			reason,
		)
	default:
		info.Summary = fmt.Sprintf(
			"Presented chain length: %d. Verified chain length: %d.",
			presented,
			*info.VerifiedChainLength,
		)
	}

	return info
}
