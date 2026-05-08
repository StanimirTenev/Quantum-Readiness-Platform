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

	if result.CryptoEvidence.PackageMetadata.PackageManager == "" {
		t.Fatal("expected package manager to be populated")
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

func TestIsRelevantCryptoPackageReturnsOnlyRelevantEntries(t *testing.T) {
	packages := []CryptoPackage{
		{Name: "openssl", Version: "3.0.2"},
		{Name: "bash", Version: "5.0.0"},
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

func TestCollectPackageMetadataReturnsUnknownWhenPackageManagerMissing(t *testing.T) {
	metadata := collectPackageMetadataWithFunctions(
		func() string { return "unknown" },
		func(string) ([]CryptoPackage, error) { return []CryptoPackage{}, nil },
	)

	if metadata.PackageManager != "unknown" {
		t.Fatalf("expected package manager unknown, got %s", metadata.PackageManager)
	}
	if !metadata.Collected {
		t.Fatal("expected metadata to be marked as collected when manager is unknown")
	}
	if len(metadata.Packages) != 0 {
		t.Fatalf("expected empty packages for unknown manager, got %d", len(metadata.Packages))
	}
	if len(metadata.Errors) != 0 {
		t.Fatalf("expected no errors for unknown manager, got %v", metadata.Errors)
	}
}

func TestCollectPackageMetadataReturnsErrorWhenListingFails(t *testing.T) {
	metadata := collectPackageMetadataWithFunctions(
		func() string { return "dpkg" },
		func(string) ([]CryptoPackage, error) { return nil, os.ErrPermission },
	)

	if metadata.PackageManager != "unknown" {
		t.Fatalf("expected package manager unknown on failure, got %s", metadata.PackageManager)
	}
	if metadata.Collected {
		t.Fatal("expected collected=false when listing fails")
	}
	if len(metadata.Packages) != 0 {
		t.Fatalf("expected no packages on failure, got %d", len(metadata.Packages))
	}
	if len(metadata.Errors) != 1 {
		t.Fatalf("expected one error on failure, got %v", metadata.Errors)
	}
}

func TestDiscoverCertificateFileIndicatorsInPathsClassifiesCertificateFiles(t *testing.T) {
	tempDir := t.TempDir()
	certFile := filepath.Join(tempDir, "service.crt")
	pemFile := filepath.Join(tempDir, "service.pem")

	if err := os.WriteFile(certFile, []byte("cert"), 0o600); err != nil {
		t.Fatalf("failed to create cert file: %v", err)
	}
	if err := os.WriteFile(pemFile, []byte("pem"), 0o600); err != nil {
		t.Fatalf("failed to create pem file: %v", err)
	}

	indicators := discoverCertificateFileIndicatorsInPaths([]string{tempDir}, 20)
	if len(indicators.Files) != 2 {
		t.Fatalf("expected 2 file indicators, got %d: %v", len(indicators.Files), indicators.Files)
	}
	if indicators.Counts.Certificate != 2 {
		t.Fatalf("expected 2 certificate indicators, got %#v", indicators.Counts)
	}
	if indicators.Files[0].Path != certFile || indicators.Files[1].Path != pemFile {
		t.Fatalf("expected certificate paths %s and %s, got %#v", certFile, pemFile, indicators.Files)
	}
}

func TestDiscoverCertificateFileIndicatorsInPathsClassifiesKeyFiles(t *testing.T) {
	tempDir := t.TempDir()
	keyFile := filepath.Join(tempDir, "service.key")
	idRsa := filepath.Join(tempDir, "id_rsa")
	if err := os.WriteFile(keyFile, []byte("k"), 0o600); err != nil {
		t.Fatalf("failed to create key file: %v", err)
	}
	if err := os.WriteFile(idRsa, []byte("k"), 0o600); err != nil {
		t.Fatalf("failed to create id_rsa file: %v", err)
	}

	indicators := discoverCertificateFileIndicatorsInPaths([]string{tempDir}, 20)
	if indicators.Counts.Key != 2 {
		t.Fatalf("expected 2 key indicators, got %#v", indicators.Counts)
	}
}

func TestDiscoverCertificateFileIndicatorsInPathsClassifiesKeyStoreAndTrustStoreFiles(t *testing.T) {
	tempDir := t.TempDir()
	_ = os.WriteFile(filepath.Join(tempDir, "bundle.jks"), []byte("x"), 0o600)
	_ = os.WriteFile(filepath.Join(tempDir, "bundle.p12"), []byte("x"), 0o600)
	_ = os.WriteFile(filepath.Join(tempDir, "cacerts"), []byte("x"), 0o600)

	indicators := discoverCertificateFileIndicatorsInPaths([]string{tempDir}, 20)
	if indicators.Counts.Keystore != 2 {
		t.Fatalf("expected 2 keystore indicators, got %#v", indicators.Counts)
	}
	if indicators.Counts.Truststore != 1 {
		t.Fatalf("expected 1 truststore indicator, got %#v", indicators.Counts)
	}
}

func TestDiscoverCertificateFileIndicatorsInPathsMissingPathsDoNotFailCollection(t *testing.T) {
	indicators := discoverCertificateFileIndicatorsInPaths([]string{"/path/that/does/not/exist"}, 20)
	if !indicators.Collected {
		t.Fatal("expected collection to remain true for missing standard paths")
	}
	if len(indicators.Files) != 0 {
		t.Fatalf("expected no files, got %#v", indicators.Files)
	}
}

func TestDiscoverCertificateFileIndicatorsInPathsReturnsStableEmptyCounts(t *testing.T) {
	indicators := discoverCertificateFileIndicatorsInPaths([]string{t.TempDir()}, 20)
	if indicators.Counts != (CertificateIndicatorFileCounts{}) {
		t.Fatalf("expected empty counts, got %#v", indicators.Counts)
	}
}

func TestDiscoverCertificateFileIndicatorsInPathsRespectsMaxFileLimit(t *testing.T) {
	tempDir := t.TempDir()
	for i := 0; i < 10; i++ {
		_ = os.WriteFile(filepath.Join(tempDir, "cert"+string(rune('a'+i))+".crt"), []byte("x"), 0o600)
	}

	indicators := discoverCertificateFileIndicatorsInPaths([]string{tempDir}, 3)
	if len(indicators.Files) != 3 {
		t.Fatalf("expected file limit 3, got %d", len(indicators.Files))
	}
}

func TestBuildPathIndicatorsMarksPresenceByPath(t *testing.T) {
	tempDir := t.TempDir()
	existingPath := filepath.Join(tempDir, "openssl.cnf")
	if err := os.WriteFile(existingPath, []byte("test"), 0o600); err != nil {
		t.Fatalf("failed to create test file: %v", err)
	}
	missingPath := filepath.Join(tempDir, "missing.cnf")

	indicators := buildPathIndicators([]string{existingPath, missingPath})
	if len(indicators) != 2 {
		t.Fatalf("expected 2 indicators, got %d", len(indicators))
	}
	if indicators[0].Path != existingPath || !indicators[0].Present {
		t.Fatalf("expected existing path to be present, got %#v", indicators[0])
	}
	if indicators[1].Path != missingPath || indicators[1].Present {
		t.Fatalf("expected missing path to be absent, got %#v", indicators[1])
	}
}

func TestCollectServiceConfigHintsWithProbeReturnsExpectedHints(t *testing.T) {
	commandProbe := func(name string) bool {
		return name == "nginx" || name == "java"
	}
	fileProbe := func(path string) bool {
		return path == "/etc/ssh/sshd_config"
	}

	hints := collectServiceConfigHintsWithProbe(commandProbe, fileProbe)
	if len(hints) != 3 {
		t.Fatalf("expected 3 hints, got %d: %#v", len(hints), hints)
	}

	if hints[0].Service != "sshd" {
		t.Fatalf("expected first hint for sshd, got %s", hints[0].Service)
	}
	if hints[1].Service != "nginx" {
		t.Fatalf("expected second hint for nginx, got %s", hints[1].Service)
	}
	if hints[2].Service != "java" {
		t.Fatalf("expected third hint for java, got %s", hints[2].Service)
	}
}
