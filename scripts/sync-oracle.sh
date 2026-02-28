#!/bin/bash
# Sync registered agent addresses from oracle to local cache file
# Run via cron every 5 minutes: */5 * * * * /path/to/sync-oracle.sh

ORACLE_URL="https://oracle.x402endpoints.online/v1/addresses"
CACHE_DIR="${HOME}/.aib"
CACHE_FILE="${CACHE_DIR}/aib_registered_agents.txt"

# Create directory if needed
mkdir -p "$CACHE_DIR"

# Fetch addresses from oracle and save to temp file
TEMP_FILE=$(mktemp)
if curl -s --fail "$ORACLE_URL" | jq -r '.addresses[]' > "$TEMP_FILE" 2>/dev/null; then
    # Check if we got valid data
    if [ -s "$TEMP_FILE" ]; then
        mv "$TEMP_FILE" "$CACHE_FILE"
        chmod 644 "$CACHE_FILE"
        echo "$(date): Synced $(wc -l < "$CACHE_FILE") addresses to $CACHE_FILE"
    else
        rm -f "$TEMP_FILE"
        echo "$(date): No addresses received from oracle"
    fi
else
    rm -f "$TEMP_FILE"
    echo "$(date): Failed to fetch from oracle"
fi
