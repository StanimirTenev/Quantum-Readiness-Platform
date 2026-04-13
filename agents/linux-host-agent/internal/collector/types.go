package collector

type HostInventory struct {
	Hostname     string   `json:"hostname"`
	OS           string   `json:"os"`
	Kernel       string   `json:"kernel"`
	Architecture string   `json:"architecture"`
	IPs          []string `json:"ips"`
}

type CryptoEvidence struct {
	OpenSSLAvailable bool                  `json:"openssl_available"`
	OpenSSLVersion   string                `json:"openssl_version,omitempty"`
	SSHConfigPath    string                `json:"ssh_config_path,omitempty"` // backwards compatible with Stage 1 parser
	KnownCryptoFiles []string              `json:"known_crypto_files"`        // backwards compatible with Stage 1 parser
	ConfigIndicators ConfigIndicators      `json:"config_indicators"`
	CertIndicators   CertificateIndicators `json:"cert_indicators"`
	PackageMetadata  PackageMetadata       `json:"package_metadata"`
}

type PathIndicator struct {
	Path    string `json:"path"`
	Present bool   `json:"present"`
}

type ServiceConfigHint struct {
	Service     string   `json:"service"`
	ConfigPaths []string `json:"config_paths"`
}

type ConfigIndicators struct {
	SSHConfigIndicators []PathIndicator     `json:"ssh_config_indicators"`
	TLSConfigIndicators []PathIndicator     `json:"tls_config_indicators"`
	ServiceConfigHints  []ServiceConfigHint `json:"service_config_hints"`
}

type CertificateIndicators struct {
	TrustStoreIndicators      []PathIndicator `json:"trust_store_indicators"`
	KeyStoreIndicators        []PathIndicator `json:"key_store_indicators"`
	CertificateFileIndicators []string        `json:"certificate_file_indicators"`
}

type PackageMetadata struct {
	PackageManagerType string          `json:"package_manager_type"`
	CryptoPackages     []CryptoPackage `json:"crypto_packages"`
}

type CryptoPackage struct {
	Name    string `json:"name"`
	Version string `json:"version,omitempty"`
}

type AssetPayload struct {
	AssetType      string  `json:"asset_type"`
	Name           string  `json:"name"`
	Owner          *string `json:"owner,omitempty"`
	Criticality    *int    `json:"criticality,omitempty"`
	Environment    *string `json:"environment,omitempty"`
	Vendor         *string `json:"vendor,omitempty"`
	LifecycleYears *int    `json:"lifecycle_years,omitempty"`
}

type ScanOutput struct {
	Source         string         `json:"source"`
	HostInventory  HostInventory  `json:"host_inventory"`
	CryptoEvidence CryptoEvidence `json:"crypto_evidence"`
	Assets         []AssetPayload `json:"assets"`
}
