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
	"/etc/ssl/certs",
	"/etc/ssl/private",
	"/usr/local/share/ca-certificates",
	"/etc/ca-certificates",
	"/etc/pki/tls/certs",
	"/etc/pki/tls/private",
	"/etc/pki/ca-trust/source/anchors",
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

const maxCertificateIndicators = 250

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

func discoverCertificateFileIndicators() []string {
	return discoverCertificateFileIndicatorsInPaths(standardCertificateLocations, maxCertificateIndicators)
}

func discoverCertificateFileIndicatorsInPaths(paths []string, maxIndicators int) []string {
	if maxIndicators <= 0 {
		return []string{}
	}

	seen := make(map[string]struct{})
	indicators := make([]string, 0, maxIndicators)

	addIfIndicator := func(path string, entryName string) {
		if !looksLikeCertificateOrKeyFile(entryName) {
			return
		}
		cleaned := filepath.Clean(path)
		if _, exists := seen[cleaned]; exists {
			return
		}
		seen[cleaned] = struct{}{}
		indicators = append(indicators, cleaned)
	}

	for _, location := range paths {
		if len(indicators) >= maxIndicators {
			break
		}

		info, err := os.Stat(location)
		if err != nil {
			continue
		}

		if !info.IsDir() {
			addIfIndicator(location, filepath.Base(location))
			continue
		}

		entries, err := os.ReadDir(location)
		if err != nil {
			continue
		}

		for _, entry := range entries {
			if len(indicators) >= maxIndicators {
				break
			}
			if entry.IsDir() {
				continue
			}
			addIfIndicator(filepath.Join(location, entry.Name()), entry.Name())
		}
	}

	sort.Strings(indicators)
	return indicators
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

func looksLikeCertificateOrKeyFile(fileName string) bool {
	lower := strings.ToLower(strings.TrimSpace(fileName))
	if lower == "" {
		return false
	}

	extensions := []string{
		".crt",
		".cer",
		".pem",
		".key",
		".p12",
		".pfx",
		".jks",
		".keystore",
	}
	for _, extension := range extensions {
		if strings.HasSuffix(lower, extension) {
			return true
		}
	}

	return strings.Contains(lower, "cert") ||
		strings.Contains(lower, "ca") ||
		strings.Contains(lower, "key")
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
