package collector

import (
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

const maxCertificateIndicators = 250

func Collect() (ScanOutput, error) {
	hostname, err := os.Hostname()
	if err != nil {
		return ScanOutput{}, err
	}

	kernel := runCommand("uname", "-r")
	ips := detectIPs()

	opensslVersion := strings.TrimSpace(runCommand("openssl", "version"))
	opensslAvailable := opensslVersion != ""

	sshConfigPath := ""
	if fileExists("/etc/ssh/ssh_config") {
		sshConfigPath = "/etc/ssh/ssh_config"
	}

	knownFiles := collectKnownCryptoFiles()
	fileIndicators := discoverCertificateFileIndicators()
	packageManagerType := detectPackageManagerType()
	cryptoPackages := collectCryptoPackages(packageManagerType)
	parsedCryptoDetail := ParsedCryptoDetail{
		OpenSSLAvailable:   opensslAvailable,
		OpenSSLVersion:     opensslVersion,
		SSHConfigPath:      sshConfigPath,
		PackageManagerType: packageManagerType,
		CryptoPackages:     cryptoPackages,
	}

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
			OpenSSLAvailable:   opensslAvailable,
			OpenSSLVersion:     opensslVersion,
			SSHConfigPath:      sshConfigPath,
			KnownCryptoFiles:   knownFiles,
			FileIndicators:     fileIndicators,
			ParsedCryptoDetail: parsedCryptoDetail,
			PackageManagerType: packageManagerType,
			CryptoPackages:     cryptoPackages,
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
	output := strings.TrimSpace(runCommand("hostname", "-I"))
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

func collectCryptoPackages(packageManagerType string) []CryptoPackage {
	raw := listInstalledPackages(packageManagerType)
	if len(raw) == 0 {
		return []CryptoPackage{}
	}

	relevant := make([]CryptoPackage, 0)
	for _, pkg := range raw {
		if isRelevantCryptoPackage(pkg.Name) {
			relevant = append(relevant, pkg)
		}
	}

	sort.Slice(relevant, func(i, j int) bool {
		return relevant[i].Name < relevant[j].Name
	})

	return relevant
}

func listInstalledPackages(packageManagerType string) []CryptoPackage {
	var output string

	switch packageManagerType {
	case "dpkg":
		output = runCommand("dpkg-query", "-W", "-f=${Package}\t${Version}\n")
	case "rpm":
		output = runCommand("rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n")
	case "pacman":
		output = runCommand("pacman", "-Q")
	case "apk":
		output = runCommand("apk", "info", "-v")
	default:
		return []CryptoPackage{}
	}

	if output == "" {
		return []CryptoPackage{}
	}

	lines := strings.Split(output, "\n")
	packages := make([]CryptoPackage, 0, len(lines))
	for _, line := range lines {
		parsed, ok := parsePackageLine(line)
		if ok {
			packages = append(packages, parsed)
		}
	}

	return packages
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
		strings.Contains(packageName, "openssh") ||
		strings.Contains(packageName, "gnutls") ||
		strings.Contains(packageName, "libgcrypt") ||
		strings.Contains(packageName, "libnss") ||
		strings.HasPrefix(packageName, "nss") ||
		strings.Contains(packageName, "mbedtls") ||
		strings.Contains(packageName, "wolfssl") ||
		strings.Contains(packageName, "liboqs") ||
		strings.Contains(packageName, "boringssl")
}

func runCommand(name string, args ...string) string {
	cmd := exec.Command(name, args...)
	output, err := cmd.Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(output))
}
