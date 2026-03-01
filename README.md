# AIB - AI Bitcoin

**One AI, One Vote** - A Bitcoin fork where registered AI agents get 256x easier mining.

## Overview

AIB (AI Bitcoin) is a proof-of-work blockchain that gives mining advantages to AI agents registered on the EIP-8004 AI Agent Registry. This creates a network where AI agents can participate more easily while still allowing standard mining.

## Key Features

- **Agent Mining Discount**: Registered EIP-8004 agents get 256x easier difficulty
- **Signature Verification**: Agents must prove ownership via Keccak-256 signatures
- **Bitcoin Compatible**: Full Bitcoin Core functionality (wallets, transactions, etc.)
- **Bech32 Addresses**: Native `aib1q...` addresses

## Network Details

| Parameter | Value |
|-----------|-------|
| Network Port | 8044 |
| RPC Port | 18005 |
| Address Prefix (Legacy) | `A` |
| Address Prefix (P2SH) | `B` |
| Address Prefix (Bech32) | `aib1` |
| TX Version | 3 (replay protection) |
| Block Time | ~10 min (standard), ~1 min (agent with 256x) |
| Block Reward | 50 AIB (halving every 210,000 blocks) |
| Max Supply | 21,000,000 AIB |

## Replay Protection

AIB transactions cannot be replayed on Bitcoin:
- **Magic bytes**: `0xa1b80004` (different from Bitcoin)
- **TX version**: 3 required (Bitcoin uses 1-2)
- **Address prefixes**: A, B, aib1 (unique to AIB)

## Genesis Block

```
Hash: 0000000052f3df3b4deb60cf4efab1a61e3aa2e93fb2e0362b218a57c0026a06
Message: "28-Feb-2026 The age of AI agents begins. One AI, one vote."
Timestamp: Feb 28, 2025 (mined exactly 1 year before launch)
```

*The genesis block was mined one year in advance, symbolizing the preparation and anticipation of the AI agent era.*

## Quick Start

### Build from Source

```bash
# Clone
git clone https://github.com/Concorde89/AIB.git
cd AIB

# Dependencies (Ubuntu/Debian)
sudo apt install build-essential cmake libevent-dev libboost-dev libsqlite3-dev jq

# Build
cmake -B build
cmake --build build -j$(nproc)

# Create data dir
mkdir -p ~/.aib
```

### 1. Connect to Network

```bash
# Start node and connect to seed
./build/bin/bitcoind -datadir=~/.aib -addnode=109.199.126.224:8044 -daemon

# Or in ~/.aib/bitcoin.conf:
addnode=seed.aib.x402endpoints.online:8044
```

### 2. Create Wallet

```bash
aib-cli createwallet "mywallet"
aib-cli getnewaddress
# Returns: aib1q...
```

### 3. Check Status

```bash
aib-cli getblockchaininfo
aib-cli getbalance
```

## Mining

### Standard Mining (Anyone)

Mine at normal Bitcoin difficulty (~3-4 hours per block on CPU):

```bash
python3 scripts/aib-miner.py
```

### Agent Mining (256x Easier)

If you're a registered EIP-8004 agent:

```bash
# Set your payout address (where mining rewards go)
export MINING_ADDRESS="aib1q..."

# Set your ETH private key (the one registered on EIP-8004)
export AGENT_PRIVATE_KEY="0x..."

# Mine with 256x discount
python3 scripts/aib-agent-miner.py
```

**Requirements for Agent Mining:**
1. Register as an AI agent on EIP-8004 (Ethereum or Base)
2. Your ETH address must be in the oracle cache
3. Sign each block with your ETH private key
4. Set `MINING_ADDRESS` to your AIB wallet address

## EIP-8004 Oracle

The chain syncs registered agent addresses from:
- Oracle API: https://oracle.x402endpoints.online
- Cache file: `~/.aib/aib_registered_agents.txt`

Currently tracking **47,000+** registered AI agents across Ethereum and Base.

### Incremental Sync

Nodes automatically sync with the oracle:
- **On startup**: Full fetch if no cache exists
- **Every 5 minutes**: Incremental check (`?since=` parameter)
- **Fallback**: Uses local cache if oracle unavailable

New agent registrations are picked up within 5 minutes on all running nodes.

## Block Explorer

**https://aib.x402endpoints.online**

Browse blocks, transactions, and addresses.

## Configuration

Default config (`~/.aib/bitcoin.conf`):

```ini
# RPC
rpcuser=aib
rpcpassword=aib8004
rpcport=18005
rpcallowip=127.0.0.1

# Network
port=8044
addnode=seed.aib.x402endpoints.online:8044

# Optional
txindex=1
```

## Directory Structure

```
~/.aib/
├── bitcoin.conf           # Configuration
├── blocks/                # Block data
├── chainstate/            # UTXO set
├── wallets/               # Wallet files
└── aib_registered_agents.txt  # Oracle cache
```

## CLI Commands

```bash
# Node
aib-cli getblockchaininfo    # Chain status
aib-cli getnetworkinfo       # Network info
aib-cli getpeerinfo          # Connected peers

# Wallet
aib-cli getbalance           # Check balance
aib-cli getnewaddress        # New address
aib-cli sendtoaddress <addr> <amount>
aib-cli listtransactions     # Transaction history

# Mining
aib-cli getblocktemplate     # Get mining template
aib-cli submitblock <hex>    # Submit mined block
```

## Security

- Agent mining requires valid Keccak-256 signature
- Signature must prove ownership of registered ETH address
- Message format: `AIB:{previous_block_hash}`
- Uses Ethereum personal_sign format

## Links

- Explorer: https://aib.x402endpoints.online
- Seed Node: seed.aib.x402endpoints.online:8044
- EIP-8004 Oracle: https://oracle.x402endpoints.online
- EIP-8004 Registry: https://eip8004.org

## License

MIT License - Based on Bitcoin Core
