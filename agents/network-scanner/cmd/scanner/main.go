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
	target := flag.String("target", "", "TLS target in host:port format")
	insecure := flag.Bool("insecure", false, "Skip certificate verification")
	timeoutSeconds := flag.Int("timeout", 5, "Connection timeout in seconds")
	ingest := flag.Bool("ingest", false, "Post collected data to inventory-service")
	inventoryURL := flag.String("inventory-url", "http://127.0.0.1:8001", "Inventory service base URL")
	workspaceID := flag.String("workspace-id", "", "Group this scan under an existing workspace (POST /workspaces); omit to auto-create a single-scan workspace")
	flag.Parse()

	if *target == "" {
		fmt.Fprintln(os.Stderr, "missing required -target argument")
		os.Exit(1)
	}

	result, err := scanner.ScanTLS(*target, *insecure, *timeoutSeconds)
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
