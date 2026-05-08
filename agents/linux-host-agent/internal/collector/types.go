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
	TrustStoreIndicators      []PathIndicator           `json:"trust_store_indicators"`
	KeyStoreIndicators        []PathIndicator           `json:"key_store_indicators"`
	CertificateFileIndicators CertificateFileIndicators `json:"certificate_file_indicators"`
	ConfigFileIndicators      ConfigFileIndicators      `json:"config_file_indicators"`
}

type CertificateFileIndicators struct {
	Collected     bool                           `json:"collected"`
	SearchedPaths []string                       `json:"searched_paths"`
	Files         []CertificateIndicatorFile     `json:"files"`
	Counts        CertificateIndicatorFileCounts `json:"counts"`
	Errors        []string                       `json:"errors"`
}

type CertificateIndicatorFile struct {
	Path      string `json:"path"`
	Type      string `json:"type"`
	Extension string `json:"extension"`
	Readable  bool   `json:"readable"`
	Source    string `json:"source"`
}

type CertificateIndicatorFileCounts struct {
	Certificate int `json:"certificate"`
	Key         int `json:"key"`
	Keystore    int `json:"keystore"`
	Truststore  int `json:"truststore"`
	Unknown     int `json:"unknown"`
}

type ConfigFileIndicators struct {
	Collected     bool                       `json:"collected"`
	SearchedPaths []string                   `json:"searched_paths"`
	Files         []ConfigIndicatorFile      `json:"files"`
	Counts        ConfigIndicatorFileCounts  `json:"counts"`
	Errors        []string                   `json:"errors"`
}

type ConfigIndicatorFile struct {
	Path     string `json:"path"`
	Type     string `json:"type"`
	Readable bool   `json:"readable"`
	Source   string `json:"source"`
}

type ConfigIndicatorFileCounts struct {
	SSHServerConfig int `json:"ssh_server_config"`
	SSHClientConfig int `json:"ssh_client_config"`
	TLSServerConfig int `json:"tls_server_config"`
	VPNConfig       int `json:"vpn_config"`
	KeystoreConfig  int `json:"keystore_config"`
	Unknown         int `json:"unknown"`
}

type PackageMetadata struct {
	PackageManager string          `json:"package_manager"`
	Collected      bool            `json:"collected"`
	Packages       []CryptoPackage `json:"packages"`
	Errors         []string        `json:"errors"`
}

type CryptoPackage struct {
	Name    string `json:"name"`
	Version string `json:"version,omitempty"`
	Source  string `json:"source,omitempty"`
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
