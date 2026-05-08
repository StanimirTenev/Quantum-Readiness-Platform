package scanner

type CertificateInfo struct {
	Subject    CertificateParty      `json:"subject"`
	Issuer     CertificateParty      `json:"issuer"`
	Validity   CertificateValidity   `json:"validity"`
	Algorithms CertificateAlgorithms `json:"algorithms"`
	Key        CertificateKeyData    `json:"key"`
	SAN        CertificateSAN        `json:"san"`
}

type CertificateParty struct {
	DisplayDN   string `json:"display_dn"`
	Fingerprint string `json:"fingerprint,omitempty"`
}

type CertificateValidity struct {
	NotBefore string `json:"not_before"`
	NotAfter  string `json:"not_after"`
}

type CertificateAlgorithms struct {
	Signature string `json:"signature"`
	PublicKey string `json:"public_key"`
}

type CertificateKeyData struct {
	Type     string `json:"type,omitempty"`
	SizeBits *int   `json:"size_bits,omitempty"`
}

type CertificateSAN struct {
	DNSNames []string `json:"dns_names"`
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

type TLSMetadata struct {
	Collected       bool                 `json:"collected"`
	Target          string               `json:"target"`
	Port            int                  `json:"port"`
	ServerName      string               `json:"server_name"`
	ProtocolVersion string               `json:"protocol_version"`
	CipherSuite     string               `json:"cipher_suite"`
	Certificate     *TLSCertificateBrief `json:"certificate"`
	Errors          []string             `json:"errors"`
}

type TLSCertificateBrief struct {
	Subject            string `json:"subject"`
	Issuer             string `json:"issuer"`
	NotBefore          string `json:"not_before"`
	NotAfter           string `json:"not_after"`
	SignatureAlgorithm string `json:"signature_algorithm"`
	PublicKeyAlgorithm string `json:"public_key_algorithm"`
	PublicKeySize      int    `json:"public_key_size"`
	FingerprintSHA256  string `json:"fingerprint_sha256"`
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
	TLSMetadata TLSMetadata    `json:"tls_metadata"`
	Assets      []AssetPayload `json:"assets"`
}
