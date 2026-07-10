package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"time"

	"linux-host-agent/internal/client"
	"linux-host-agent/internal/collector"
)

type collectOutcome struct {
	result collector.ScanOutput
	err    error
}

func main() {
	ingest := flag.Bool("ingest", false, "Post collected data to inventory-service")
	inventoryURL := flag.String("inventory-url", "http://127.0.0.1:8001", "Inventory service base URL")
	timeoutSec := flag.Int("timeout", 60, "Overall collection deadline in seconds (bounded mode -- prevents a stuck subprocess from hanging the whole run)")
	workspaceID := flag.String("workspace-id", "", "Group this scan under an existing workspace (POST /workspaces); omit to auto-create a single-scan workspace")
	flag.Parse()

	outcomeCh := make(chan collectOutcome, 1)
	go func() {
		result, err := collector.Collect()
		outcomeCh <- collectOutcome{result, err}
	}()

	var outcome collectOutcome
	select {
	case outcome = <-outcomeCh:
	case <-time.After(time.Duration(*timeoutSec) * time.Second):
		fmt.Fprintf(os.Stderr, "collector timed out after %ds -- a subprocess likely hung (e.g. a package-manager lock); increase -timeout or investigate the host\n", *timeoutSec)
		os.Exit(1)
	}

	result, err := outcome.result, outcome.err
	if err != nil {
		fmt.Fprintf(os.Stderr, "collector error: %v\n", err)
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
