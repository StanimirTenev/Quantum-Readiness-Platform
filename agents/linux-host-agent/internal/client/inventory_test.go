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

		var payload map[string]any
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("failed to decode request body: %v", err)
		}

		if payload["source"] != "host" {
			t.Fatalf("expected source host, got %v", payload["source"])
		}

		cryptoEvidence, ok := payload["crypto_evidence"].(map[string]any)
		if !ok {
			t.Fatalf("expected crypto_evidence object, got %#v", payload["crypto_evidence"])
		}

		if _, exists := cryptoEvidence["package_metadata"]; exists {
			t.Fatalf("did not expect package_metadata in Stage 1 ingest payload")
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
		CryptoEvidence: collector.CryptoEvidence{
			OpenSSLAvailable: true,
			OpenSSLVersion:   "OpenSSL 3.0.0",
			SSHConfigPath:    "/etc/ssh/ssh_config",
			KnownCryptoFiles: []string{"/etc/ssl/certs"},
			PackageMetadata: collector.PackageMetadata{
				PackageManager: "dpkg",
				Collected:      true,
				Packages:       []collector.CryptoPackage{{Name: "openssl", Version: "3.0.0", Source: "dpkg"}},
				Errors:         []string{},
			},
		},
		Assets: []collector.AssetPayload{
			{
				AssetType: "server",
				Name:      "test-host",
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
		_ = json.NewEncoder(w).Encode(IngestResponse{Source: "host", Created: 1, WorkspaceID: "ws-123"})
	}))
	defer server.Close()

	response, err := PostScan(server.URL, collector.ScanOutput{
		Source: "host",
		Assets: []collector.AssetPayload{{AssetType: "server", Name: "test-host"}},
	}, "ws-123")
	if err != nil {
		t.Fatalf("PostScan returned error: %v", err)
	}
	if capturedQuery != "workspace_id=ws-123" {
		t.Fatalf("expected workspace_id query param, got %q", capturedQuery)
	}
	if response.WorkspaceID != "ws-123" {
		t.Fatalf("expected response.WorkspaceID to round-trip, got %q", response.WorkspaceID)
	}
}
