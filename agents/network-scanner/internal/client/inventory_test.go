package client

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"network-scanner/internal/scanner"
)

func TestPostScan(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/scans/ingest" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}

		var payload scanner.ScanOutput
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("failed to decode request body: %v", err)
		}

		if payload.Source != "network" {
			t.Fatalf("expected source network, got %s", payload.Source)
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(IngestResponse{
			Source:   "network",
			Created:  1,
			AssetIDs: []string{"asset-network-1"},
		})
	}))
	defer server.Close()

	response, err := PostScan(server.URL, scanner.ScanOutput{
		Source: "network",
		Assets: []scanner.AssetPayload{
			{
				AssetType: "endpoint",
				Name:      "google.com:443",
			},
		},
	}, "")
	if err != nil {
		t.Fatalf("PostScan returned error: %v", err)
	}

	if response.Created != 1 {
		t.Fatalf("expected 1 created asset, got %d", response.Created)
	}
}

func TestPostScanWithWorkspaceIDAppendsQueryParam(t *testing.T) {
	var capturedQuery string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedQuery = r.URL.RawQuery
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(IngestResponse{Source: "network", Created: 1, WorkspaceID: "ws-456"})
	}))
	defer server.Close()

	response, err := PostScan(server.URL, scanner.ScanOutput{
		Source: "network",
		Assets: []scanner.AssetPayload{{AssetType: "endpoint", Name: "google.com:443"}},
	}, "ws-456")
	if err != nil {
		t.Fatalf("PostScan returned error: %v", err)
	}
	if capturedQuery != "workspace_id=ws-456" {
		t.Fatalf("expected workspace_id query param, got %q", capturedQuery)
	}
	if response.WorkspaceID != "ws-456" {
		t.Fatalf("expected response.WorkspaceID to round-trip, got %q", response.WorkspaceID)
	}
}
