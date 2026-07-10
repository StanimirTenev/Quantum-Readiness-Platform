package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"network-scanner/internal/client"
	"network-scanner/internal/scanner"
)

func main() {
	target := flag.String("target", "", "Target in host:port format")
	protocol := flag.String("protocol", "tls", "Protocol to scan: tls or ssh")
	insecure := flag.Bool("insecure", false, "Skip certificate verification (tls only)")
	timeoutSeconds := flag.Int("timeout", 5, "Connection timeout in seconds")
	ingest := flag.Bool("ingest", false, "Post collected data to inventory-service")
	inventoryURL := flag.String("inventory-url", "http://127.0.0.1:8001", "Inventory service base URL")
	workspaceID := flag.String("workspace-id", "", "Group this scan under an existing workspace (POST /workspaces); omit to auto-create a single-scan workspace")
	flag.Parse()

	if *target == "" {
		fmt.Fprintln(os.Stderr, "missing required -target argument")
		os.Exit(1)
	}

	var result scanner.ScanOutput
	var err error
	switch *protocol {
	case "tls":
		result, err = scanner.ScanTLS(*target, *insecure, *timeoutSeconds)
	case "ssh":
		result, err = scanner.ScanSSH(*target, *timeoutSeconds)
	default:
		fmt.Fprintf(os.Stderr, "invalid -protocol %q: must be \"tls\" or \"ssh\"\n", *protocol)
		os.Exit(1)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "scan error: %v\n", err)
		os.Exit(1)
	}

	if *ingest {
		response, err := client.PostScan(*inventoryURL, result, *workspaceID)
		if err != nil {
			fmt.Fprintf(os.Stderr, "ingest error: %v\n", err)
			os.Exit(1)
		}

		encoded, err := json.MarshalIndent(response, "", "  ")
		if err != nil {
			fmt.Fprintf(os.Stderr, "json encode error: %v\n", err)
			os.Exit(1)
		}

		fmt.Println(string(encoded))
		return
	}

	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "json encode error: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(encoded))
}
