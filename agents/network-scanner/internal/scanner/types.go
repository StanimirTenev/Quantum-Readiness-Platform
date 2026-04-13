package scanner

type CertificateInfo struct {
	Subject            string   `json:"subject"`
	Issuer             string   `json:"issuer"`
	SubjectFingerprint string   `json:"subject_fingerprint,omitempty"`
	IssuerFingerprint  string   `json:"issuer_fingerprint,omitempty"`
	NotBefore          string   `json:"not_before"`
	NotAfter           string   `json:"not_after"`
	SignatureAlgorithm string   `json:"signature_algorithm"`
	PublicKeyAlgorithm string   `json:"public_key_algorithm"`
	KeyType            string   `json:"key_type,omitempty"`
	KeySizeBits        *int     `json:"key_size_bits,omitempty"`
	DNSNames           []string `json:"dns_names"`
}

type CertificateChainDetails struct {
	Available              bool    `json:"available"`
	Presence               bool    `json:"presence"`
	PresentedChainLength   int     `json:"presented_chain_length"`
	VerifiedChainLength    *int    `json:"verified_chain_length,omitempty"`
	Summary                string  `json:"summary"`
	UnavailableReason      *string `json:"unavailable_reason,omitempty"`
	VerificationPerformed  bool    `json:"verification_performed"`
	VerifiedChainAvailable bool    `json:"verified_chain_available"`
}

type TLSEvidence struct {
	Target               string                  `json:"target"`
	TLSVersion           string                  `json:"tls_version"`
	CipherSuite          string                  `json:"cipher_suite"`
	ServerName           string                  `json:"server_name"`
	Certificate          CertificateInfo         `json:"certificate"`
	CertificateChainInfo CertificateChainDetails `json:"certificate_chain"`
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
	Source      string         `json:"source"`
	TLSEvidence *TLSEvidence   `json:"tls_evidence,omitempty"`
	Assets      []AssetPayload `json:"assets"`
}
