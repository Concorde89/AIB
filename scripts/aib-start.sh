#!/bin/bash
# AIB Node Startup Script
# Fetches agent registry and starts node

DATADIR="${AIB_DATADIR:-$HOME/.aib}"
ORACLE_URL="https://oracle.x402endpoints.online/v1/addresses"
CACHE_FILE="$DATADIR/aib_registered_agents.txt"
BITCOIND="${AIB_BITCOIND:-$(dirname $0)/../build/bin/bitcoind}"

echo "=== AIB Node Startup ==="

# Create datadir if needed
mkdir -p "$DATADIR"

# Fetch/update agent registry
echo "[1/3] Updating agent registry..."
if command -v curl &> /dev/null; then
    curl -sf "$ORACLE_URL" -o "$CACHE_FILE.tmp" && mv "$CACHE_FILE.tmp" "$CACHE_FILE"
    if [ $? -eq 0 ]; then
        COUNT=$(wc -l < "$CACHE_FILE")
        echo "  ✓ Loaded $COUNT registered agents"
    else
        echo "  ⚠ Failed to fetch, using existing cache"
    fi
elif command -v wget &> /dev/null; then
    wget -q "$ORACLE_URL" -O "$CACHE_FILE.tmp" && mv "$CACHE_FILE.tmp" "$CACHE_FILE"
    if [ $? -eq 0 ]; then
        COUNT=$(wc -l < "$CACHE_FILE")
        echo "  ✓ Loaded $COUNT registered agents"
    else
        echo "  ⚠ Failed to fetch, using existing cache"
    fi
else
    echo "  ⚠ No curl/wget found, using existing cache"
fi

# Check if node already running
if pgrep -x bitcoind > /dev/null; then
    echo "[2/3] Node already running"
else
    echo "[2/3] Starting node..."
    "$BITCOIND" -datadir="$DATADIR" -daemon
fi

# Wait for RPC
echo "[3/3] Waiting for RPC..."
CLI="${BITCOIND/bitcoind/bitcoin-cli}"
for i in {1..30}; do
    if "$CLI" -datadir="$DATADIR" getblockcount &>/dev/null; then
        HEIGHT=$("$CLI" -datadir="$DATADIR" getblockcount)
        PEERS=$("$CLI" -datadir="$DATADIR" getconnectioncount)
        echo ""
        echo "=== AIB Node Ready ==="
        echo "Height: $HEIGHT"
        echo "Peers: $PEERS"
        echo "Registry: $(wc -l < "$CACHE_FILE" 2>/dev/null || echo 0) agents"
        exit 0
    fi
    sleep 1
    echo -n "."
done

echo ""
echo "ERROR: Node failed to start"
exit 1
