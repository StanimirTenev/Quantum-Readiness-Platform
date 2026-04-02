package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"network-scanner/internal/scanner"
)

func main() {
	target := flag.String("target", "", "TLS target in host:port format")
	insecure := flag.Bool("insecure", false, "Skip certificate verification")
	timeoutSeconds := flag.Int("timeout", 5, "Connection timeout in seconds")
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

	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "json encode error: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(encoded))
}
