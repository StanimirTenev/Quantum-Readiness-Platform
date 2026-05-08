package scanner

import (
	"crypto/ecdsa"
	"crypto/ed25519"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/tls"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/json"
	"encoding/hex"
	"math/big"
	"strings"
	"testing"
	"time"
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
	if tlsVersionString(0x0304) != "TLS 1.3" {
		t.Fatal("expected TLS 1.3")
	}
}

func TestCipherSuiteMappingReturnsReadableName(t *testing.T) {
	if got := tls.CipherSuiteName(tls.TLS_AES_256_GCM_SHA384); got != "TLS_AES_256_GCM_SHA384" {
		t.Fatalf("expected readable cipher suite name, got %q", got)
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

func TestCertificateSHA256FingerprintUsesLowercaseHex(t *testing.T) {
	raw := []byte("certificate-bytes")
	sum := sha256.Sum256(raw)
	expected := hex.EncodeToString(sum[:])
	if got := certificateSHA256Fingerprint(raw); got != expected {
		t.Fatalf("expected %q, got %q", expected, got)
	}
}

func TestCertificateSHA256FingerprintEmptyForMissingData(t *testing.T) {
	if got := certificateSHA256Fingerprint(nil); got != "" {
		t.Fatalf("expected empty fingerprint, got %q", got)
	}
}

func TestFailureResultContainsStableTLSMetadataFields(t *testing.T) {
	out, err := ScanTLS("127.0.0.1:1", false, 1)
	if err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if out.TLSMetadata.Collected {
		t.Fatal("expected collected=false")
	}
	if out.TLSMetadata.ProtocolVersion != "" || out.TLSMetadata.CipherSuite != "" {
		t.Fatal("expected empty protocol and cipher suite")
	}
	if out.TLSMetadata.Certificate != nil {
		t.Fatal("expected nil certificate on failure")
	}
	if out.TLSMetadata.CertificateChain.Available {
		t.Fatal("expected certificate chain to be unavailable")
	}
	if out.TLSMetadata.CertificateChain.Length != 0 || len(out.TLSMetadata.CertificateChain.Certificates) != 0 {
		t.Fatal("expected empty unavailable certificate chain")
	}
	if len(out.TLSMetadata.CertificateChain.Errors) == 0 {
		t.Fatal("expected non-empty certificate chain errors")
	}
	if len(out.TLSMetadata.Errors) == 0 {
		t.Fatal("expected at least one error")
	}
}

func TestScanOutputJSONContainsTLSMetadata(t *testing.T) {
	out := ScanOutput{Source: "network", TLSMetadata: TLSMetadata{Collected: false, Target: "example.com", Port: 443, ServerName: "example.com", Errors: []string{}}}
	payload, err := json.Marshal(out)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}
	if !strings.Contains(string(payload), `"tls_metadata"`) {
		t.Fatalf("expected tls_metadata field in JSON: %s", string(payload))
	}
	if !strings.Contains(string(payload), `"certificate_chain"`) {
		t.Fatalf("expected certificate_chain field in JSON: %s", string(payload))
	}
}


func TestFailureJSONContractIncludesTLSMetadataCertificateAndChain(t *testing.T) {
	out, err := ScanTLS("127.0.0.1:1", false, 1)
	if err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}

	payload, err := json.Marshal(out)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}

	var decoded map[string]any
	if err := json.Unmarshal(payload, &decoded); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}

	tlsMetadata, ok := decoded["tls_metadata"].(map[string]any)
	if !ok {
		t.Fatalf("expected tls_metadata object, got %T", decoded["tls_metadata"])
	}

	if _, ok := tlsMetadata["certificate"]; !ok {
		t.Fatal("expected tls_metadata.certificate field")
	}
	if tlsMetadata["certificate"] != nil {
		t.Fatal("expected tls_metadata.certificate to be null on failure")
	}

	chain, ok := tlsMetadata["certificate_chain"].(map[string]any)
	if !ok {
		t.Fatalf("expected tls_metadata.certificate_chain object, got %T", tlsMetadata["certificate_chain"])
	}
	if _, ok := chain["certificates"]; !ok {
		t.Fatal("expected tls_metadata.certificate_chain.certificates field")
	}
	certificates, ok := chain["certificates"].([]any)
	if !ok {
		t.Fatalf("expected certificates array, got %T", chain["certificates"])
	}
	if len(certificates) != 0 {
		t.Fatalf("expected empty certificates array, got %d", len(certificates))
	}

	errorsField, ok := tlsMetadata["errors"]
	if !ok {
		t.Fatal("expected tls_metadata.errors field")
	}
	errors, ok := errorsField.([]any)
	if !ok {
		t.Fatalf("expected tls_metadata.errors array, got %T", errorsField)
	}
	if len(errors) == 0 {
		t.Fatal("expected non-empty tls_metadata.errors on failure")
	}
}

func TestTLSMetadataJSONContainsCertificateChainCertificatesErrors(t *testing.T) {
	out := ScanOutput{
		Source: "network",
		TLSMetadata: TLSMetadata{
			Collected:       false,
			Target:          "example.com",
			Port:            443,
			ServerName:      "example.com",
			ProtocolVersion: "",
			CipherSuite:     "",
			Certificate:     nil,
			CertificateChain: TLSCertificateChainSummary{
				Available:    false,
				Length:       0,
				Certificates: []TLSCertificateBriefItem{},
				Errors:       []string{"chain details unavailable"},
			},
			Errors: []string{"short error message"},
		},
	}
	payload, err := json.Marshal(out)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}

	jsonOutput := string(payload)
	for _, field := range []string{
		`"tls_metadata"`,
		`"certificate":null`,
		`"certificate_chain"`,
		`"certificates":[]`,
		`"errors":["short error message"]`,
	} {
		if !strings.Contains(jsonOutput, field) {
			t.Fatalf("expected JSON to contain %q, got %s", field, jsonOutput)
		}
	}
}

func TestCertificateChainSummaryAvailableWithPeerCertificates(t *testing.T) {
	leaf := mustCreateCertificate(t, "leaf.example", nil)
	intermediate := mustCreateCertificate(t, "intermediate.example", nil)

	summary := certificateChainSummary([]*x509.Certificate{leaf, intermediate})
	if !summary.Available {
		t.Fatal("expected available=true")
	}
	if summary.Length != 2 {
		t.Fatalf("expected length=2, got %d", summary.Length)
	}
	if len(summary.Certificates) != 2 {
		t.Fatalf("expected 2 certificates, got %d", len(summary.Certificates))
	}
	if summary.Certificates[0].FingerprintSHA256 != certificateSHA256Fingerprint(leaf.Raw) {
		t.Fatal("expected first chain certificate fingerprint to match leaf")
	}
}

func TestCertificateChainSummaryUnavailableStableShape(t *testing.T) {
	summary := certificateChainSummary(nil)
	if summary.Available {
		t.Fatal("expected available=false")
	}
	if summary.Length != 0 {
		t.Fatalf("expected length=0, got %d", summary.Length)
	}
	if len(summary.Certificates) != 0 {
		t.Fatalf("expected empty certificates, got %d", len(summary.Certificates))
	}
	if len(summary.Errors) == 0 {
		t.Fatal("expected non-empty errors")
	}
}

func mustCreateCertificate(t *testing.T, commonName string, parent *x509.Certificate) *x509.Certificate {
	t.Helper()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("rsa key generation failed: %v", err)
	}

	tpl := &x509.Certificate{
		SerialNumber: big.NewInt(time.Now().UnixNano()),
		Subject:      pkix.Name{CommonName: commonName},
		NotBefore:    time.Now().Add(-time.Hour),
		NotAfter:     time.Now().Add(24 * time.Hour),
		KeyUsage:     x509.KeyUsageDigitalSignature,
	}
	if parent == nil {
		parent = tpl
	}

	der, err := x509.CreateCertificate(rand.Reader, tpl, parent, &key.PublicKey, key)
	if err != nil {
		t.Fatalf("certificate creation failed: %v", err)
	}

	cert, err := x509.ParseCertificate(der)
	if err != nil {
		t.Fatalf("parse certificate failed: %v", err)
	}

	return cert
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
