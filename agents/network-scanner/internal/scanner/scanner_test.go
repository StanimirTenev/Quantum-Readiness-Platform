package scanner

import (
	"crypto/ecdsa"
	"crypto/ed25519"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
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
