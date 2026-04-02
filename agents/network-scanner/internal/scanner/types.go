package scanner

type CertificateInfo struct {
	Subject            string `json:"subject"`
	Issuer             string `json:"issuer"`
	NotBefore          string `json:"not_before"`
	NotAfter           string `json:"not_after"`
	SignatureAlgorithm string `json:"signature_algorithm"`
	PublicKeyAlgorithm string `json:"public_key_algorithm"`
	DNSNames           []string `json:"dns_names"`
}

type TLSEvidence struct {
	Target      string          `json:"target"`
	TLSVersion  string          `json:"tls_version"`
	CipherSuite string          `json:"cipher_suite"`
	ServerName  string          `json:"server_name"`
	Certificate CertificateInfo `json:"certificate"`
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
	Source      string       `json:"source"`
	TLSEvidence *TLSEvidence `json:"tls_evidence,omitempty"`
	Assets      []AssetPayload `json:"assets"`
}
