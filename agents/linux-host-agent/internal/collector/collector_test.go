package collector

import (
	"os"
	"path/filepath"
	"testing"
)

func TestCollect(t *testing.T) {
	result, err := Collect()
	if err != nil {
		t.Fatalf("Collect returned error: %v", err)
	}

	if result.Source != "host" {
		t.Fatalf("expected source host, got %s", result.Source)
	}

	if result.HostInventory.Hostname == "" {
		t.Fatal("expected hostname to be populated")
	}

	if result.HostInventory.OS == "" {
		t.Fatal("expected OS to be populated")
	}

	if len(result.Assets) == 0 {
		t.Fatal("expected at least one asset")
	}

	if result.Assets[0].AssetType != "server" {
		t.Fatalf("expected first asset type server, got %s", result.Assets[0].AssetType)
	}

	if result.CryptoEvidence.PackageManagerType == "" {
		t.Fatal("expected package manager type to be populated")
	}

	if result.CryptoEvidence.ParsedCryptoDetail.PackageManagerType == "" {
		t.Fatal("expected parsed crypto detail package manager type to be populated")
	}
}

func TestParsePackageLineReturnsNameAndVersionWhenBothAreProvided(t *testing.T) {
	parsed, ok := parsePackageLine("openssl\t3.0.2")
	if !ok {
		t.Fatal("expected parsePackageLine to parse valid package line")
	}

	if parsed.Name != "openssl" {
		t.Fatalf("expected package name openssl, got %s", parsed.Name)
	}

	if parsed.Version != "3.0.2" {
		t.Fatalf("expected version 3.0.2, got %s", parsed.Version)
	}
}

func TestParsePackageLineReturnsNameOnlyWhenVersionMissing(t *testing.T) {
	parsed, ok := parsePackageLine("openssl")
	if !ok {
		t.Fatal("expected parsePackageLine to parse line with name only")
	}

	if parsed.Name != "openssl" {
		t.Fatalf("expected package name openssl, got %s", parsed.Name)
	}

	if parsed.Version != "" {
		t.Fatalf("expected empty version, got %s", parsed.Version)
	}
}

func TestCollectCryptoPackagesReturnsOnlyRelevantEntries(t *testing.T) {
	packages := []CryptoPackage{
		{Name: "openssl", Version: "3.0.2"},
		{Name: "curl", Version: "8.0.0"},
		{Name: "openssh-client", Version: "9.6"},
	}

	filtered := make([]CryptoPackage, 0)
	for _, pkg := range packages {
		if isRelevantCryptoPackage(pkg.Name) {
			filtered = append(filtered, pkg)
		}
	}

	if len(filtered) != 2 {
		t.Fatalf("expected 2 relevant packages, got %d", len(filtered))
	}

	if filtered[0].Name != "openssl" {
		t.Fatalf("expected first package openssl, got %s", filtered[0].Name)
	}

	if filtered[1].Name != "openssh-client" {
		t.Fatalf("expected second package openssh-client, got %s", filtered[1].Name)
	}
}

func TestDiscoverCertificateFileIndicatorsInPathsReturnsOnlyCertificateAndKeyLikeFiles(t *testing.T) {
	tempDir := t.TempDir()
	certFile := filepath.Join(tempDir, "service.crt")
	keyFile := filepath.Join(tempDir, "service.key")
	otherFile := filepath.Join(tempDir, "notes.txt")

	if err := os.WriteFile(certFile, []byte("cert"), 0o600); err != nil {
		t.Fatalf("failed to create cert file: %v", err)
	}
	if err := os.WriteFile(keyFile, []byte("key"), 0o600); err != nil {
		t.Fatalf("failed to create key file: %v", err)
	}
	if err := os.WriteFile(otherFile, []byte("notes"), 0o600); err != nil {
		t.Fatalf("failed to create non-indicator file: %v", err)
	}

	indicators := discoverCertificateFileIndicatorsInPaths([]string{tempDir}, 20)
	if len(indicators) != 2 {
		t.Fatalf("expected 2 file indicators, got %d: %v", len(indicators), indicators)
	}

	if indicators[0] != certFile {
		t.Fatalf("expected first indicator %s, got %s", certFile, indicators[0])
	}
	if indicators[1] != keyFile {
		t.Fatalf("expected second indicator %s, got %s", keyFile, indicators[1])
	}
}

func TestDiscoverCertificateFileIndicatorsInPathsDoesNotTraverseNestedDirectories(t *testing.T) {
	tempDir := t.TempDir()
	nestedDir := filepath.Join(tempDir, "nested")
	if err := os.Mkdir(nestedDir, 0o755); err != nil {
		t.Fatalf("failed to create nested dir: %v", err)
	}

	nestedCert := filepath.Join(nestedDir, "deep.crt")
	if err := os.WriteFile(nestedCert, []byte("cert"), 0o600); err != nil {
		t.Fatalf("failed to create nested cert file: %v", err)
	}

	indicators := discoverCertificateFileIndicatorsInPaths([]string{tempDir}, 20)
	if len(indicators) != 0 {
		t.Fatalf("expected no indicators from nested files, got %v", indicators)
	}
}
