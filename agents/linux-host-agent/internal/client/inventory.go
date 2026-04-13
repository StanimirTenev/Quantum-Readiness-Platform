package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"linux-host-agent/internal/collector"
)

type IngestResponse struct {
	Source   string   `json:"source"`
	Created  int      `json:"created"`
	AssetIDs []string `json:"asset_ids"`
}

type ingestCryptoEvidence struct {
	OpenSSLAvailable bool     `json:"openssl_available"`
	OpenSSLVersion   string   `json:"openssl_version,omitempty"`
	SSHConfigPath    string   `json:"ssh_config_path,omitempty"`
	KnownCryptoFiles []string `json:"known_crypto_files"`
}

type ingestScanPayload struct {
	Source         string                   `json:"source"`
	HostInventory  collector.HostInventory  `json:"host_inventory"`
	CryptoEvidence ingestCryptoEvidence     `json:"crypto_evidence"`
	Assets         []collector.AssetPayload `json:"assets"`
}

func PostScan(baseURL string, payload collector.ScanOutput) (IngestResponse, error) {
	baseURL = strings.TrimRight(baseURL, "/")
	endpoint := baseURL + "/scans/ingest"

	ingestPayload := ingestScanPayload{
		Source:        payload.Source,
		HostInventory: payload.HostInventory,
		CryptoEvidence: ingestCryptoEvidence{
			OpenSSLAvailable: payload.CryptoEvidence.OpenSSLAvailable,
			OpenSSLVersion:   payload.CryptoEvidence.OpenSSLVersion,
			SSHConfigPath:    payload.CryptoEvidence.SSHConfigPath,
			KnownCryptoFiles: payload.CryptoEvidence.KnownCryptoFiles,
		},
		Assets: payload.Assets,
	}

	body, err := json.Marshal(ingestPayload)
	if err != nil {
		return IngestResponse{}, fmt.Errorf("marshal payload: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, endpoint, bytes.NewBuffer(body))
	if err != nil {
		return IngestResponse{}, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	httpClient := &http.Client{Timeout: 10 * time.Second}
	resp, err := httpClient.Do(req)
	if err != nil {
		return IngestResponse{}, fmt.Errorf("post ingest: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return IngestResponse{}, fmt.Errorf("unexpected status: %s", resp.Status)
	}

	var parsed IngestResponse
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return IngestResponse{}, fmt.Errorf("decode response: %w", err)
	}

	return parsed, nil
}
