#!/bin/bash
# AIB Node Safe Restart Script
# ALWAYS use this script to restart the node

CLI="/home/clawd/clawd/aib-coin/build/bin/bitcoin-cli -datadir=/home/clawd/.aib -rpcport=18005 -rpcuser=aib -rpcpassword=aib8004"
BITCOIND="/home/clawd/clawd/aib-coin/build/bin/bitcoind"
DATADIR="/home/clawd/.aib"

echo "=== AIB Safe Restart ==="

# Step 1: Stop node gracefully
echo "[1/5] Stopping node..."
$CLI stop 2>/dev/null || echo "Node not running"

# Step 2: Wait for complete shutdown
echo "[2/5] Waiting for shutdown..."
while pgrep -x bitcoind > /dev/null; do
    sleep 1
    echo -n "."
done
echo " Done"

# Step 3: Backup critical files
echo "[3/5] Backing up critical files..."
cp "$DATADIR/blocks/xor.dat" "$DATADIR/xor.dat.backup" 2>/dev/null
echo "  - xor.dat backed up"

# Step 4: Start node
echo "[4/5] Starting node..."
$BITCOIND -datadir=$DATADIR -daemon

# Step 5: Wait for RPC
echo "[5/5] Waiting for RPC..."
for i in {1..30}; do
    if $CLI getblockcount &>/dev/null; then
        HEIGHT=$($CLI getblockcount)
        echo ""
        echo "=== Node Ready ==="
        echo "Height: $HEIGHT"
        echo "Peers: $($CLI getconnectioncount)"
        exit 0
    fi
    sleep 1
    echo -n "."
done

echo ""
echo "ERROR: Node failed to start. Check ~/.aib/debug.log"
exit 1
