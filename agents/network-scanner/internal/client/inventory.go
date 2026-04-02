package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"network-scanner/internal/scanner"
)

type IngestResponse struct {
	Source   string   `json:"source"`
	Created  int      `json:"created"`
	AssetIDs []string `json:"asset_ids"`
}

func PostScan(baseURL string, payload scanner.ScanOutput) (IngestResponse, error) {
	baseURL = strings.TrimRight(baseURL, "/")
	endpoint := baseURL + "/scans/ingest"

	body, err := json.Marshal(payload)
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
