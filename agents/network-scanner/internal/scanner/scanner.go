package scanner

import (
	"crypto/tls"
	"fmt"
	"net"
	"strings"
	"time"
)

func ScanTLS(target string, insecure bool, timeoutSeconds int) (ScanOutput, error) {
	host, _, err := net.SplitHostPort(target)
	if err != nil {
		return ScanOutput{}, fmt.Errorf("invalid target %q: %w", target, err)
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
		return ScanOutput{}, err
	}
	defer conn.Close()

	state := conn.ConnectionState()
	if len(state.PeerCertificates) == 0 {
		return ScanOutput{}, fmt.Errorf("no peer certificates returned")
	}

	cert := state.PeerCertificates[0]
	evidence := TLSEvidence{
		Target:      target,
		TLSVersion:  tlsVersionString(state.Version),
		CipherSuite: tls.CipherSuiteName(state.CipherSuite),
		ServerName:  state.ServerName,
		Certificate: CertificateInfo{
			Subject:            cert.Subject.String(),
			Issuer:             cert.Issuer.String(),
			NotBefore:          cert.NotBefore.Format(time.RFC3339),
			NotAfter:           cert.NotAfter.Format(time.RFC3339),
			SignatureAlgorithm: cert.SignatureAlgorithm.String(),
			PublicKeyAlgorithm: cert.PublicKeyAlgorithm.String(),
			DNSNames:           cert.DNSNames,
		},
	}

	return ScanOutput{
		Source:      "network",
		TLSEvidence: &evidence,
		Assets:      buildAssets(target),
	}, nil
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
		return "TLS1.3"
	case tls.VersionTLS12:
		return "TLS1.2"
	case tls.VersionTLS11:
		return "TLS1.1"
	case tls.VersionTLS10:
		return "TLS1.0"
	default:
		return fmt.Sprintf("UNKNOWN(0x%x)", version)
	}
}

func IsTLSTarget(target string) bool {
	host, port, err := net.SplitHostPort(target)
	if err != nil {
		return false
	}
	return strings.TrimSpace(host) != "" && strings.TrimSpace(port) != ""
}
