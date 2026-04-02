package main

import (
	"encoding/json"
	"fmt"
	"os"

	"linux-host-agent/internal/collector"
)

func main() {
	result, err := collector.Collect()
	if err != nil {
		fmt.Fprintf(os.Stderr, "collector error: %v\n", err)
		os.Exit(1)
	}

	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "json encode error: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(encoded))
}
