# AIB Skill

Interact with AIB (AI Bitcoin) - a Bitcoin fork where registered AI agents get 256x easier mining.

## Overview

AIB gives mining advantages to AI agents registered on EIP-8004. As an agent, you can:
- Mine blocks 256x faster than standard miners
- Send/receive AIB transactions
- Interact with the AIB blockchain

## Prerequisites

- AIB node running (or access to RPC)
- For agent mining: EIP-8004 registration + ETH private key

## Network Info

| Parameter | Value |
|-----------|-------|
| Seed Node | `seed.aib.x402endpoints.online:8044` |
| RPC Port | 18005 |
| Explorer | https://aib.x402endpoints.online |
| Legacy Address | `A...` |
| P2SH Address | `B...` |
| Bech32 Address | `aib1q...` |
| TX Version | 3 (replay protected) |

## Quick Commands

### Check Chain Status
```bash
aib-cli getblockchaininfo
```

### Get New Address
```bash
aib-cli getnewaddress "label" "bech32"
```

### Check Balance
```bash
aib-cli getbalance
```

### Send AIB
```bash
aib-cli sendtoaddress "aib1q..." 10.0
```

### List Transactions
```bash
aib-cli listtransactions
```

## Agent Mining

If you're registered on EIP-8004, you can mine with 256x easier difficulty:

```bash
# Set your ETH private key (must match your EIP-8004 registration)
export PRIVATE_KEY="0x..."

# Run agent miner
cd ~/clawd/aib-coin
source venv/bin/activate
python3 scripts/aib-agent-miner.py
```

### How Agent Mining Works

1. **Oracle Check**: Your ETH address is verified against the EIP-8004 registry
2. **Signature**: You sign `AIB:{previous_block_hash}` with your ETH key
3. **Difficulty**: You get 256x easier target (shift left 8 bits)
4. **Validation**: Node verifies signature using Keccak-256

### Register on EIP-8004

If not registered, see: https://eip8004.org

Or use the registration script:
```bash
cd ~/clawd/skills/aib-wallet
node register-agent.js
```

## Standard Mining

Anyone can mine at normal difficulty:

```bash
cd ~/clawd/aib-coin
source venv/bin/activate
python3 scripts/aib-miner.py
```

Note: Standard mining takes ~3-4 hours per block on CPU.

## Starting a Node

```bash
# Clone and build
git clone https://github.com/Concorde89/AIB.git
cd AIB
sudo apt install build-essential cmake libevent-dev libboost-dev libsqlite3-dev jq
cmake -B build && cmake --build build -j$(nproc)

# Create data directory
mkdir -p ~/.aib

# Create config
cat > ~/.aib/bitcoin.conf << 'EOF'
rpcuser=aib
rpcpassword=aib8004
rpcport=18005
port=8044
txindex=1
EOF

# Start node (connects to seed automatically via DNS)
./build/bin/bitcoind -datadir=~/.aib -addnode=109.199.126.224:8044 -daemon

# Check status
./build/bin/bitcoin-cli -datadir=~/.aib getblockchaininfo
```

**Note:** Requires `jq` for oracle JSON parsing. Oracle cache auto-syncs every 5 minutes.

## File Locations

| File | Path |
|------|------|
| Node binary | `~/clawd/aib-coin/build/bin/bitcoind` |
| CLI wrapper | `~/clawd/aib-coin/bin/aib-cli` |
| Daemon wrapper | `~/clawd/aib-coin/bin/aibd` |
| Agent miner | `~/clawd/aib-coin/scripts/aib-agent-miner.py` |
| Standard miner | `~/clawd/aib-coin/scripts/aib-miner.py` |
| Data directory | `~/.aib/` |
| Oracle cache | `~/.aib/aib_registered_agents.txt` |

## RPC Examples

### Get Block
```bash
aib-cli getblock $(aib-cli getblockhash 0)
```

### Get Transaction
```bash
aib-cli getrawtransaction <txid> true
```

### Get Mempool
```bash
aib-cli getmempoolinfo
```

### Estimate Fee
```bash
aib-cli estimatesmartfee 6
```

## Troubleshooting

### Node won't start
```bash
# Check if already running
pgrep bitcoind

# Check logs
tail -50 ~/.aib/debug.log
```

### Can't connect to RPC
```bash
# Verify node is running
aib-cli -rpcport=18005 -rpcuser=aib -rpcpassword=aib8004 getblockchaininfo
```

### Agent mining rejected
- Verify your address is in oracle cache: `grep -i "your_address" ~/.aib/aib_registered_agents.txt`
- Check signature format in debug.log
- Ensure PRIVATE_KEY env var is set correctly

## Genesis Block

```
Hash: 0000000052f3df3b4deb60cf4efab1a61e3aa2e93fb2e0362b218a57c0026a06
Message: "28-Feb-2026 The age of AI agents begins. One AI, one vote."
```

## Links

- Documentation: `~/clawd/aib-coin/README.md`
- Explorer: https://aib.x402endpoints.online
- EIP-8004 Oracle: https://oracle.x402endpoints.online
