package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"linux-host-agent/internal/client"
	"linux-host-agent/internal/collector"
)

func main() {
	ingest := flag.Bool("ingest", false, "Post collected data to inventory-service")
	inventoryURL := flag.String("inventory-url", "http://127.0.0.1:8001", "Inventory service base URL")
	flag.Parse()

	result, err := collector.Collect()
	if err != nil {
		fmt.Fprintf(os.Stderr, "collector error: %v\n", err)
		os.Exit(1)
	}

	if *ingest {
		response, err := client.PostScan(*inventoryURL, result)
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
