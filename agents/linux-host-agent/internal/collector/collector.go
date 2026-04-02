package collector

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

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

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func runCommand(name string, args ...string) string {
	cmd := exec.Command(name, args...)
	output, err := cmd.Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(output))
}
