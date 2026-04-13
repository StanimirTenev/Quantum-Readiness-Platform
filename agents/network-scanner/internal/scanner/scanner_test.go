package scanner

import (
	"crypto/ecdsa"
	"crypto/ed25519"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/rsa"
	"crypto/x509"
	"encoding/json"
	"strings"
	"testing"
)

func TestIsTLSTarget(t *testing.T) {
	if !IsTLSTarget("example.com:443") {
		t.Fatal("expected valid target")
	}

	if IsTLSTarget("example.com") {
		t.Fatal("expected invalid target without port")
	}
}

func TestTLSVersionString(t *testing.T) {
	if tlsVersionString(0x0304) != "TLS1.3" {
		t.Fatal("expected TLS1.3")
	}
}

func TestBuildAssets(t *testing.T) {
	assets := buildAssets("example.com:443")
	if len(assets) != 1 {
		t.Fatalf("expected 1 asset, got %d", len(assets))
	}
	if assets[0].AssetType != "endpoint" {
		t.Fatalf("expected endpoint asset, got %s", assets[0].AssetType)
	}
}

func TestCertificateKeyMetadataReturnsRSAKeyDetails(t *testing.T) {
	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("rsa key generation failed: %v", err)
	}

	keyType, keySizeBits := certificateKeyMetadata(&x509.Certificate{PublicKey: &privateKey.PublicKey})
	if keyType != "RSA" {
		t.Fatalf("expected RSA key type, got %q", keyType)
	}
	if keySizeBits == nil || *keySizeBits != 2048 {
		t.Fatalf("expected 2048 bits, got %v", keySizeBits)
	}
}

func TestCertificateKeyMetadataReturnsECDSAKeyDetails(t *testing.T) {
	privateKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatalf("ecdsa key generation failed: %v", err)
	}

	keyType, keySizeBits := certificateKeyMetadata(&x509.Certificate{PublicKey: &privateKey.PublicKey})
	if keyType != "ECDSA" {
		t.Fatalf("expected ECDSA key type, got %q", keyType)
	}
	if keySizeBits == nil || *keySizeBits != 256 {
		t.Fatalf("expected 256 bits, got %v", keySizeBits)
	}
}

func TestCertificateKeyMetadataReturnsEd25519KeyDetails(t *testing.T) {
	publicKey, _, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatalf("ed25519 key generation failed: %v", err)
	}

	keyType, keySizeBits := certificateKeyMetadata(&x509.Certificate{PublicKey: publicKey})
	if keyType != "Ed25519" {
		t.Fatalf("expected Ed25519 key type, got %q", keyType)
	}
	if keySizeBits == nil || *keySizeBits != 256 {
		t.Fatalf("expected 256 bits, got %v", keySizeBits)
	}
}

func TestCertificateKeyMetadataReturnsUnavailableForUnsupportedKey(t *testing.T) {
	keyType, keySizeBits := certificateKeyMetadata(&x509.Certificate{PublicKey: "unsupported"})
	if keyType != "" {
		t.Fatalf("expected empty key type, got %q", keyType)
	}
	if keySizeBits != nil {
		t.Fatalf("expected nil key size, got %d", *keySizeBits)
	}
}

func TestNameFingerprintReturnsSHA256Value(t *testing.T) {
	fingerprint := nameFingerprint([]byte("subject-data"))
	if !strings.HasPrefix(fingerprint, "SHA256:") {
		t.Fatalf("expected SHA256 prefix, got %q", fingerprint)
	}
	if len(fingerprint) != len("SHA256:")+64 {
		t.Fatalf("expected 64 hex chars, got %q", fingerprint)
	}
}

func TestNameFingerprintReturnsEmptyForMissingData(t *testing.T) {
	if got := nameFingerprint(nil); got != "" {
		t.Fatalf("expected empty fingerprint for nil input, got %q", got)
	}
}

func TestCertificateChainDetailsReturnsUnavailableWhenInsecure(t *testing.T) {
	state := tls.ConnectionState{
		PeerCertificates: []*x509.Certificate{{}, {}},
	}
	details := certificateChainDetails(state, true)
	if details.VerificationPerformed {
		t.Fatal("expected verification_performed to be false")
	}
	if details.VerifiedChainAvailable {
		t.Fatal("expected verified_chain_available to be false")
	}
	if details.UnavailableReason == nil {
		t.Fatal("expected unavailable reason when insecure")
	}
}

func TestCertificateChainDetailsReturnsVerifiedLengthWhenAvailable(t *testing.T) {
	state := tls.ConnectionState{
		PeerCertificates: []*x509.Certificate{{}, {}},
		VerifiedChains: [][]*x509.Certificate{
			{{}, {}, {}},
		},
	}
	details := certificateChainDetails(state, false)
	if details.VerifiedChainLength == nil || *details.VerifiedChainLength != 3 {
		t.Fatalf("expected verified chain length 3, got %v", details.VerifiedChainLength)
	}
	if !details.VerifiedChainAvailable {
		t.Fatal("expected verified_chain_available to be true")
	}
}

func TestCertificateInfoUsesStructuredJSONFields(t *testing.T) {
	certificate := CertificateInfo{
		Subject: CertificateParty{
			DisplayDN:   "CN=example.com,O=Example Corp",
			Fingerprint: "SHA256:ABC",
		},
		Issuer: CertificateParty{
			DisplayDN:   "CN=Example CA",
			Fingerprint: "SHA256:DEF",
		},
		Validity: CertificateValidity{
			NotBefore: "2026-01-01T00:00:00Z",
			NotAfter:  "2027-01-01T00:00:00Z",
		},
		Algorithms: CertificateAlgorithms{
			Signature: "SHA256-RSA",
			PublicKey: "RSA",
		},
		Key: CertificateKeyData{
			Type: "RSA",
		},
		SAN: CertificateSAN{
			DNSNames: []string{"example.com"},
		},
	}

	payload, err := json.Marshal(certificate)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}

	jsonOutput := string(payload)
	for _, expected := range []string{
		`"subject":{"display_dn":"CN=example.com,O=Example Corp","fingerprint":"SHA256:ABC"}`,
		`"issuer":{"display_dn":"CN=Example CA","fingerprint":"SHA256:DEF"}`,
		`"validity":{"not_before":"2026-01-01T00:00:00Z","not_after":"2027-01-01T00:00:00Z"}`,
		`"algorithms":{"signature":"SHA256-RSA","public_key":"RSA"}`,
		`"key":{"type":"RSA"}`,
		`"san":{"dns_names":["example.com"]}`,
	} {
		if !strings.Contains(jsonOutput, expected) {
			t.Fatalf("expected JSON to contain %q, got %s", expected, jsonOutput)
		}
	}

	for _, legacyField := range []string{
		`"subject_fingerprint"`,
		`"issuer_fingerprint"`,
		`"signature_algorithm"`,
		`"public_key_algorithm"`,
		`"key_type"`,
		`"key_size_bits"`,
	} {
		if strings.Contains(jsonOutput, legacyField) {
			t.Fatalf("expected legacy field %q to be absent, got %s", legacyField, jsonOutput)
		}
	}
}
