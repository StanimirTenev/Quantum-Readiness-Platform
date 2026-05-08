package collector

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
)

var standardCertificateLocations = []string{
	"/etc/ssl",
	"/etc/pki",
	"/etc/ca-certificates",
	"/usr/local/share/ca-certificates",
	"/etc/letsencrypt",
	"/etc/nginx",
	"/etc/apache2",
	"/etc/httpd",
	"/etc/haproxy",
	"/etc/openvpn",
	"/etc/ipsec.d",
	"/etc/strongswan",
	"/etc/ssh",
}
var standardConfigIndicatorLocations = []string{
	"/etc/ssh/sshd_config",
	"/etc/ssh/ssh_config",
	"/etc/ssh/sshd_config.d",
	"/etc/ssh/ssh_config.d",
	"/etc/nginx",
	"/etc/apache2",
	"/etc/httpd",
	"/etc/haproxy",
	"/etc/stunnel",
	"/etc/letsencrypt",
	"/etc/openvpn",
	"/etc/ipsec.conf",
	"/etc/ipsec.d",
	"/etc/strongswan",
	"/etc/wireguard",
	"/etc/java",
	"/etc/default",
	"/etc/sysconfig",
}

var standardSSHConfigLocations = []string{
	"/etc/ssh/ssh_config",
	"/etc/ssh/sshd_config",
	"/root/.ssh/config",
}

var standardTLSConfigLocations = []string{
	"/etc/ssl/openssl.cnf",
	"/etc/gnutls/config",
	"/etc/pki/tls/openssl.cnf",
	"/etc/ca-certificates.conf",
}

var standardTrustStoreLocations = []string{
	"/etc/ssl/certs",
	"/etc/pki/ca-trust/extracted",
	"/etc/pki/ca-trust/source/anchors",
	"/usr/local/share/ca-certificates",
}

var standardKeyStoreLocations = []string{
	"/etc/ssl/private",
	"/etc/pki/tls/private",
	"/etc/keystores",
	"/etc/security",
}

const maxCertificateIndicators = 200
const maxCertificateSearchDepth = 3
const maxConfigIndicators = 200
const maxConfigSearchDepth = 3

func Collect() (ScanOutput, error) {
	hostname, err := os.Hostname()
	if err != nil {
		return ScanOutput{}, err
	}

	kernel, _ := runCommand("uname", "-r")
	ips := detectIPs()

	opensslVersion, _ := runCommand("openssl", "version")
	opensslVersion = strings.TrimSpace(opensslVersion)
	opensslAvailable := opensslVersion != ""

	sshConfigPath := ""
	if fileExists("/etc/ssh/ssh_config") {
		sshConfigPath = "/etc/ssh/ssh_config"
	}
	sshConfigIndicators := buildPathIndicators(standardSSHConfigLocations)
	tlsConfigIndicators := buildPathIndicators(standardTLSConfigLocations)
	serviceConfigHints := collectServiceConfigHints()
	trustStoreIndicators := buildPathIndicators(standardTrustStoreLocations)
	keyStoreIndicators := buildPathIndicators(standardKeyStoreLocations)

	knownFiles := collectKnownCryptoFiles()
	certificateFileIndicators := discoverCertificateFileIndicators()
	configFileIndicators := discoverConfigFileIndicators()
	packageMetadata := collectPackageMetadata()

	output := ScanOutput{
		Source: "host",
		HostInventory: HostInventory{
			Hostname:     hostname,
			OS:           runtime.GOOS,
			Kernel:       kernel,
			Architecture: runtime.GOARCH,
			IPs:          ips,
		},
		CryptoEvidence: CryptoEvidence{
			OpenSSLAvailable: opensslAvailable,
			OpenSSLVersion:   opensslVersion,
			SSHConfigPath:    sshConfigPath,
			KnownCryptoFiles: knownFiles,
			ConfigIndicators: ConfigIndicators{
				SSHConfigIndicators: sshConfigIndicators,
				TLSConfigIndicators: tlsConfigIndicators,
				ServiceConfigHints:  serviceConfigHints,
			},
			CertIndicators: CertificateIndicators{
				TrustStoreIndicators:      trustStoreIndicators,
				KeyStoreIndicators:        keyStoreIndicators,
				CertificateFileIndicators: certificateFileIndicators,
				ConfigFileIndicators:      configFileIndicators,
			},
			PackageMetadata: packageMetadata,
		},
		Assets: buildAssets(hostname),
	}

	return output, nil
}

func buildAssets(hostname string) []AssetPayload {
	criticality := 3
	environment := "unknown"
	lifecycleYears := 5

	return []AssetPayload{
		{
			AssetType:      "server",
			Name:           hostname,
			Criticality:    &criticality,
			Environment:    &environment,
			LifecycleYears: &lifecycleYears,
		},
	}
}

func detectIPs() []string {
	output, _ := runCommand("hostname", "-I")
	output = strings.TrimSpace(output)
	if output == "" {
		return []string{}
	}

	parts := strings.Fields(output)
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		if part != "" {
			result = append(result, part)
		}
	}
	return result
}

func collectKnownCryptoFiles() []string {
	candidates := []string{
		"/etc/ssl/openssl.cnf",
		"/etc/ssh/ssh_config",
		"/etc/ssh/sshd_config",
		"/etc/ssl/certs",
	}

	found := make([]string, 0, len(candidates))
	for _, path := range candidates {
		if fileExists(path) {
			found = append(found, filepath.Clean(path))
		}
	}
	return found
}

func discoverCertificateFileIndicators() CertificateFileIndicators {
	return discoverCertificateFileIndicatorsInPaths(standardCertificateLocations, maxCertificateIndicators)
}

func discoverCertificateFileIndicatorsInPaths(paths []string, maxIndicators int) CertificateFileIndicators {
	result := emptyCertificateFileIndicators()
	if maxIndicators <= 0 {
		return result
	}

	result.Collected = true
	seen := make(map[string]struct{})
	result.Files = make([]CertificateIndicatorFile, 0, maxIndicators)

	addFile := func(path string, entryName string) {
		indicatorType, extension, ok := classifyCertificateFileIndicator(entryName)
		if !ok {
			return
		}
		cleaned := filepath.Clean(path)
		if _, exists := seen[cleaned]; exists {
			return
		}
		seen[cleaned] = struct{}{}
		readable := fileIsReadable(cleaned)
		result.Files = append(result.Files, CertificateIndicatorFile{Path: cleaned, Type: indicatorType, Extension: extension, Readable: readable, Source: "standard_path"})
		incrementCertificateTypeCount(&result.Counts, indicatorType)
	}

	for _, location := range paths {
		if len(result.Files) >= maxIndicators {
			break
		}
		result.SearchedPaths = append(result.SearchedPaths, filepath.Clean(location))

		info, err := os.Stat(location)
		if err != nil {
			if !os.IsNotExist(err) {
				result.Errors = append(result.Errors, shortDiscoveryError(location, err))
			}
			continue
		}

		if !info.IsDir() {
			addFile(location, filepath.Base(location))
			continue
		}
		walkErr := filepath.WalkDir(location, func(path string, d os.DirEntry, walkErr error) error {
			if walkErr != nil {
				result.Errors = append(result.Errors, shortDiscoveryError(path, walkErr))
				if d != nil && d.IsDir() {
					return filepath.SkipDir
				}
				return nil
			}
			relPath, relErr := filepath.Rel(location, path)
			if relErr == nil && relPath != "." {
				depth := strings.Count(relPath, string(filepath.Separator)) + 1
				if depth > maxCertificateSearchDepth {
					if d.IsDir() {
						return filepath.SkipDir
					}
					return nil
				}
			}
			if d.IsDir() {
				return nil
			}
			if len(result.Files) >= maxIndicators {
				return fmt.Errorf("indicator_limit_reached")
			}
			addFile(path, d.Name())
			return nil
		})
		if walkErr != nil && walkErr.Error() != "indicator_limit_reached" {
			result.Errors = append(result.Errors, shortDiscoveryError(location, walkErr))
		}
	}

	sort.Slice(result.Files, func(i, j int) bool {
		return result.Files[i].Path < result.Files[j].Path
	})
	return result
}

func emptyCertificateFileIndicators() CertificateFileIndicators {
	return CertificateFileIndicators{Collected: false, SearchedPaths: []string{}, Files: []CertificateIndicatorFile{}, Counts: CertificateIndicatorFileCounts{}, Errors: []string{}}
}

func classifyCertificateFileIndicator(fileName string) (string, string, bool) {
	lower := strings.ToLower(strings.TrimSpace(fileName))
	if lower == "" {
		return "", "", false
	}
	ext := strings.ToLower(filepath.Ext(lower))
	if ext == ".crt" || ext == ".cer" || ext == ".pem" || ext == ".der" {
		return "certificate", ext, true
	}
	if ext == ".key" || lower == "id_rsa" || lower == "id_ecdsa" || lower == "id_ed25519" {
		return "key", ext, true
	}
	if ext == ".jks" || ext == ".p12" || ext == ".pfx" || lower == "keystore" {
		return "keystore", ext, true
	}
	if lower == "cacerts" || lower == "truststore" {
		return "truststore", ext, true
	}
	if strings.Contains(lower, "cert") || strings.Contains(lower, "key") || strings.Contains(lower, "trust") || strings.Contains(lower, "crypto") {
		return "unknown", ext, true
	}
	return "", "", false
}

func incrementCertificateTypeCount(counts *CertificateIndicatorFileCounts, indicatorType string) {
	switch indicatorType {
	case "certificate":
		counts.Certificate++
	case "key":
		counts.Key++
	case "keystore":
		counts.Keystore++
	case "truststore":
		counts.Truststore++
	default:
		counts.Unknown++
	}
}

func discoverConfigFileIndicators() ConfigFileIndicators {
	return discoverConfigFileIndicatorsInPaths(standardConfigIndicatorLocations, maxConfigIndicators)
}

func discoverConfigFileIndicatorsInPaths(paths []string, maxIndicators int) ConfigFileIndicators {
	result := emptyConfigFileIndicators()
	if maxIndicators <= 0 {
		return result
	}
	result.Collected = true
	seen := make(map[string]struct{})
	result.Files = make([]ConfigIndicatorFile, 0, maxIndicators)

	addFile := func(path string) {
		indicatorType, ok := classifyConfigFileIndicator(path)
		if !ok {
			return
		}
		cleaned := filepath.Clean(path)
		if _, exists := seen[cleaned]; exists {
			return
		}
		seen[cleaned] = struct{}{}
		result.Files = append(result.Files, ConfigIndicatorFile{
			Path:     cleaned,
			Type:     indicatorType,
			Readable: fileIsReadable(cleaned),
			Source:   "standard_path",
		})
		incrementConfigTypeCount(&result.Counts, indicatorType)
	}

	for _, location := range paths {
		if len(result.Files) >= maxIndicators {
			break
		}
		result.SearchedPaths = append(result.SearchedPaths, filepath.Clean(location))
		info, err := os.Stat(location)
		if err != nil {
			if !os.IsNotExist(err) {
				result.Errors = append(result.Errors, shortDiscoveryError(location, err))
			}
			continue
		}
		if !info.IsDir() {
			addFile(location)
			continue
		}
		walkErr := filepath.WalkDir(location, func(path string, d os.DirEntry, walkErr error) error {
			if walkErr != nil {
				result.Errors = append(result.Errors, shortDiscoveryError(path, walkErr))
				if d != nil && d.IsDir() {
					return filepath.SkipDir
				}
				return nil
			}
			relPath, relErr := filepath.Rel(location, path)
			if relErr == nil && relPath != "." {
				depth := strings.Count(relPath, string(filepath.Separator)) + 1
				if depth > maxConfigSearchDepth {
					if d.IsDir() {
						return filepath.SkipDir
					}
					return nil
				}
			}
			if d.IsDir() {
				return nil
			}
			if len(result.Files) >= maxIndicators {
				return fmt.Errorf("indicator_limit_reached")
			}
			addFile(path)
			return nil
		})
		if walkErr != nil && walkErr.Error() != "indicator_limit_reached" {
			result.Errors = append(result.Errors, shortDiscoveryError(location, walkErr))
		}
	}
	sort.Slice(result.Files, func(i, j int) bool {
		return result.Files[i].Path < result.Files[j].Path
	})
	return result
}

func emptyConfigFileIndicators() ConfigFileIndicators {
	return ConfigFileIndicators{
		Collected:     false,
		SearchedPaths: []string{},
		Files:         []ConfigIndicatorFile{},
		Counts:        ConfigIndicatorFileCounts{},
		Errors:        []string{},
	}
}

func classifyConfigFileIndicator(path string) (string, bool) {
	cleaned := filepath.Clean(path)
	base := strings.ToLower(filepath.Base(cleaned))
	parent := strings.ToLower(filepath.Base(filepath.Dir(cleaned)))
	full := strings.ToLower(cleaned)

	if strings.HasSuffix(full, "/sshd_config") || strings.Contains(full, "/sshd_config.d/") {
		return "ssh_server_config", true
	}
	if strings.HasSuffix(full, "/ssh_config") || strings.Contains(full, "/ssh_config.d/") {
		return "ssh_client_config", true
	}
	if base == "nginx.conf" || base == "apache2.conf" || base == "httpd.conf" || base == "haproxy.cfg" || base == "stunnel.conf" {
		return "tls_server_config", true
	}
	if parent == "sites-enabled" || parent == "conf.d" || parent == "vhosts.d" || strings.Contains(full, "/letsencrypt/renewal/") {
		return "tls_server_config", true
	}
	if base == "ipsec.conf" || base == "strongswan.conf" || base == "swanctl.conf" || (strings.HasPrefix(base, "wg") && strings.HasSuffix(base, ".conf")) || strings.HasSuffix(base, ".ovpn") || strings.HasSuffix(base, ".conf") && strings.Contains(full, "/openvpn/") {
		return "vpn_config", true
	}
	if base == "keystore" || base == "truststore" || base == "cacerts" || base == "java.security" {
		return "keystore_config", true
	}
	if strings.Contains(base, "keystore") || strings.Contains(base, "truststore") {
		return "keystore_config", true
	}
	if looksLikeConfigFile(base) {
		return "unknown", true
	}
	return "", false
}

func looksLikeConfigFile(base string) bool {
	return strings.HasSuffix(base, ".conf") || strings.HasSuffix(base, ".cfg") || strings.HasSuffix(base, ".cnf")
}

func incrementConfigTypeCount(counts *ConfigIndicatorFileCounts, indicatorType string) {
	switch indicatorType {
	case "ssh_server_config":
		counts.SSHServerConfig++
	case "ssh_client_config":
		counts.SSHClientConfig++
	case "tls_server_config":
		counts.TLSServerConfig++
	case "vpn_config":
		counts.VPNConfig++
	case "keystore_config":
		counts.KeystoreConfig++
	default:
		counts.Unknown++
	}
}

func fileIsReadable(path string) bool {
	file, err := os.Open(path)
	if err != nil {
		return false
	}
	_ = file.Close()
	return true
}

func shortDiscoveryError(path string, err error) string {
	return fmt.Sprintf("%s: %v", filepath.Clean(path), err)
}

func buildPathIndicators(paths []string) []PathIndicator {
	indicators := make([]PathIndicator, 0, len(paths))
	for _, path := range paths {
		indicators = append(indicators, PathIndicator{
			Path:    filepath.Clean(path),
			Present: fileExists(path),
		})
	}
	return indicators
}

func collectServiceConfigHints() []ServiceConfigHint {
	return collectServiceConfigHintsWithProbe(commandExists, fileExists)
}

func collectServiceConfigHintsWithProbe(commandProbe func(string) bool, fileProbe func(string) bool) []ServiceConfigHint {
	hints := make([]ServiceConfigHint, 0)

	addHint := func(service string, paths []string) {
		hints = append(hints, ServiceConfigHint{
			Service:     service,
			ConfigPaths: paths,
		})
	}

	if commandProbe("sshd") || fileProbe("/etc/ssh/sshd_config") {
		addHint("sshd", []string{"/etc/ssh/sshd_config"})
	}
	if commandProbe("nginx") || fileProbe("/etc/nginx/nginx.conf") {
		addHint("nginx", []string{"/etc/nginx/nginx.conf", "/etc/nginx/conf.d"})
	}
	if commandProbe("apache2") || commandProbe("httpd") || fileProbe("/etc/apache2/apache2.conf") || fileProbe("/etc/httpd/conf/httpd.conf") {
		addHint("apache", []string{"/etc/apache2/apache2.conf", "/etc/httpd/conf/httpd.conf"})
	}
	if commandProbe("haproxy") || fileProbe("/etc/haproxy/haproxy.cfg") {
		addHint("haproxy", []string{"/etc/haproxy/haproxy.cfg"})
	}
	if commandProbe("stunnel") || fileProbe("/etc/stunnel/stunnel.conf") {
		addHint("stunnel", []string{"/etc/stunnel/stunnel.conf"})
	}
	if commandProbe("java") {
		addHint("java", []string{
			"/etc/ssl/certs/java/cacerts",
			"/usr/lib/jvm/default-java/lib/security/cacerts",
		})
	}

	return hints
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func commandExists(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

func detectPackageManagerType() string {
	switch {
	case commandExists("dpkg-query"):
		return "dpkg"
	case commandExists("rpm"):
		return "rpm"
	case commandExists("pacman"):
		return "pacman"
	case commandExists("apk"):
		return "apk"
	default:
		return "unknown"
	}
}

func collectPackageMetadata() PackageMetadata {
	return collectPackageMetadataWithFunctions(detectPackageManagerType, listInstalledPackages)
}

func collectPackageMetadataWithFunctions(
	detectManager func() string,
	listPackages func(string) ([]CryptoPackage, error),
) PackageMetadata {
	packageManager := detectManager()
	if packageManager == "unknown" {
		return PackageMetadata{
			PackageManager: packageManager,
			Collected:      true,
			Packages:       []CryptoPackage{},
			Errors:         []string{},
		}
	}

	raw, err := listPackages(packageManager)
	if err != nil {
		return PackageMetadata{
			PackageManager: "unknown",
			Collected:      false,
			Packages:       []CryptoPackage{},
			Errors:         []string{err.Error()},
		}
	}

	relevant := make([]CryptoPackage, 0)
	for _, pkg := range raw {
		if isRelevantCryptoPackage(pkg.Name) {
			pkg.Source = packageManager
			relevant = append(relevant, pkg)
		}
	}

	sort.Slice(relevant, func(i, j int) bool {
		return relevant[i].Name < relevant[j].Name
	})

	return PackageMetadata{
		PackageManager: packageManager,
		Collected:      true,
		Packages:       relevant,
		Errors:         []string{},
	}
}

func listInstalledPackages(packageManagerType string) ([]CryptoPackage, error) {
	var output string
	var err error

	switch packageManagerType {
	case "dpkg":
		output, err = runCommand("dpkg-query", "-W", "-f=${Package}\t${Version}\n")
	case "rpm":
		output, err = runCommand("rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n")
	case "pacman":
		output, err = runCommand("pacman", "-Q")
	case "apk":
		output, err = runCommand("apk", "info", "-v")
	default:
		return []CryptoPackage{}, nil
	}

	if err != nil {
		return nil, fmt.Errorf("package collection failed: %s", packageManagerType)
	}
	if output == "" {
		return []CryptoPackage{}, nil
	}

	lines := strings.Split(output, "\n")
	packages := make([]CryptoPackage, 0, len(lines))
	for _, line := range lines {
		parsed, ok := parsePackageLine(line)
		if ok {
			packages = append(packages, parsed)
		}
	}

	return packages, nil
}

func parsePackageLine(line string) (CryptoPackage, bool) {
	line = strings.TrimSpace(line)
	if line == "" {
		return CryptoPackage{}, false
	}

	fields := strings.Fields(line)
	if len(fields) == 0 {
		return CryptoPackage{}, false
	}

	name := fields[0]
	version := ""
	if len(fields) > 1 {
		version = strings.Join(fields[1:], " ")
	}

	return CryptoPackage{
		Name:    name,
		Version: version,
	}, true
}

func isRelevantCryptoPackage(packageName string) bool {
	packageName = strings.ToLower(packageName)
	return strings.Contains(packageName, "openssl") ||
		strings.Contains(packageName, "libssl") ||
		strings.Contains(packageName, "gnutls") ||
		strings.Contains(packageName, "nss") ||
		strings.Contains(packageName, "libgcrypt") ||
		strings.Contains(packageName, "cryptography") ||
		strings.Contains(packageName, "crypto") ||
		strings.Contains(packageName, "openssh") ||
		strings.Contains(packageName, "ssh") ||
		strings.Contains(packageName, "ca-certificates") ||
		strings.Contains(packageName, "curl") ||
		strings.Contains(packageName, "wget") ||
		strings.Contains(packageName, "java") ||
		strings.Contains(packageName, "openjdk") ||
		strings.Contains(packageName, "keytool") ||
		strings.Contains(packageName, "nginx") ||
		strings.Contains(packageName, "apache") ||
		strings.Contains(packageName, "httpd") ||
		strings.Contains(packageName, "haproxy") ||
		strings.Contains(packageName, "stunnel") ||
		strings.Contains(packageName, "strongswan") ||
		strings.Contains(packageName, "openvpn") ||
		strings.Contains(packageName, "wireguard")
}

func runCommand(name string, args ...string) (string, error) {
	cmd := exec.Command(name, args...)
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(output)), nil
}
