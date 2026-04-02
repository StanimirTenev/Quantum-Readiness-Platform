package client

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"linux-host-agent/internal/collector"
)

func TestPostScan(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/scans/ingest" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}

		var payload collector.ScanOutput
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("failed to decode request body: %v", err)
		}

		if payload.Source != "host" {
			t.Fatalf("expected source host, got %s", payload.Source)
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(IngestResponse{
			Source:   "host",
			Created:  1,
			AssetIDs: []string{"asset-1"},
		})
	}))
	defer server.Close()

	response, err := PostScan(server.URL, collector.ScanOutput{
		Source: "host",
		Assets: []collector.AssetPayload{
			{
				AssetType: "server",
				Name:      "test-host",
			},
		},
	})
	if err != nil {
		t.Fatalf("PostScan returned error: %v", err)
	}

	if response.Created != 1 {
		t.Fatalf("expected 1 created asset, got %d", response.Created)
	}
}
