#!/bin/bash
# AIB Node Safe Stop Script

CLI="/home/clawd/clawd/aib-coin/build/bin/bitcoin-cli -datadir=/home/clawd/.aib -rpcport=18005 -rpcuser=aib -rpcpassword=aib8004"

echo "=== AIB Safe Stop ==="

# Check if running
if ! pgrep -x bitcoind > /dev/null; then
    echo "Node not running"
    exit 0
fi

# Get current height
HEIGHT=$($CLI getblockcount 2>/dev/null || echo "?")
echo "Current height: $HEIGHT"

# Stop gracefully
echo "Stopping node..."
$CLI stop

# Wait for complete shutdown
echo -n "Waiting for shutdown"
while pgrep -x bitcoind > /dev/null; do
    sleep 1
    echo -n "."
done
echo " Done"

echo ""
echo "Node stopped safely. Safe to modify files now."
