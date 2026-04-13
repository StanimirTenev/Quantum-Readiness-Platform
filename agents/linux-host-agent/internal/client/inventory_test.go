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
				PackageManagerType: "dpkg",
				CryptoPackages:     []collector.CryptoPackage{{Name: "openssl", Version: "3.0.0"}},
			},
		},
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
