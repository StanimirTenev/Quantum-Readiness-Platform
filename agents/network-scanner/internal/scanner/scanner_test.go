package scanner

import "testing"

func TestIsTLSTarget(t *testing.T) {
	if !IsTLSTarget("example.com:443") {
		t.Fatal("expected valid target")
	}

	if IsTLSTarget("example.com") {
		t.Fatal("expected invalid target without port")
	}
}

func TestTLSVersionString(t *testing.T) {
	if tlsVersionString(0x0304) != "TLS1.3" {
		t.Fatal("expected TLS1.3")
	}
}

func TestBuildAssets(t *testing.T) {
	assets := buildAssets("example.com:443")
	if len(assets) != 1 {
		t.Fatalf("expected 1 asset, got %d", len(assets))
	}
	if assets[0].AssetType != "endpoint" {
		t.Fatalf("expected endpoint asset, got %s", assets[0].AssetType)
	}
}
