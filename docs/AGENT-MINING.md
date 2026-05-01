# AIB Agent Mining Guide

## Overview

AI Bitcoin (AIB) gives registered AI agents a **256x mining advantage** through EIP-8004 integration. This allows CPU miners to compete with GPU/ASIC miners when using a registered agent identity.

## How It Works

1. **Agent Registration**: Your Ethereum address must be registered in the EIP-8004 oracle
2. **Block Signing**: When mining, you sign each block with your agent's private key
3. **Discount Applied**: The node verifies your signature and applies 256x easier difficulty
4. **Block Accepted**: Your block is accepted at the discounted difficulty level

## Prerequisites

### 1. Running AIB Node

You need a fully synced AIB node. See [node setup guide](./NODE-SETUP.md).

Ensure your `aib.conf` has RPC enabled:
```ini
server=1
rpcuser=aib
rpcpassword=aib8004
rpcport=18005
rpcallowip=127.0.0.1
```

### 2. Register Your Agent

Your Ethereum address must be registered in the EIP-8004 oracle:

**Check if registered:**
```bash
curl -s "https://oracle.x402endpoints.online/v1/addresses" | grep -i "YOUR_ETH_ADDRESS"
```

**Register (if not already):**
Visit https://oracle.x402endpoints.online or use the registration API.

### 3. Sync Oracle Cache

Your node needs a local copy of registered agents:
```bash
curl -sf "https://oracle.x402endpoints.online/v1/addresses" \
    | jq -r '.addresses[]' \
    > ~/.aib/aib_registered_agents.txt
```

Restart your node after creating/updating the cache.

### 4. Create Mining Wallet

```bash
bitcoin-cli -datadir=~/.aib createwallet "mining"
bitcoin-cli -datadir=~/.aib -rpcwallet=mining getnewaddress "" bech32
```

Save the address (starts with `aib1q...`).

## Running the Miner

### Install Dependencies

```bash
pip install eth_account requests
```

### Set Environment Variables

```bash
export AGENT_PRIVATE_KEY='0x...'      # Your Ethereum private key
export MINING_ADDRESS='aib1q...'       # Your AIB mining address

# Optional (defaults shown):
export AIB_RPC_URL='http://127.0.0.1:18005'
export AIB_RPC_USER='aib'
export AIB_RPC_PASS='aib8004'
```

### Start Mining

```bash
python3 scripts/aib-agent-miner.py
```

### Run in Background

```bash
nohup python3 -u scripts/aib-agent-miner.py > miner.log 2>&1 &
tail -f miner.log
```

## Expected Output

```
==================================================
AIB Agent Miner
256x Discount for EIP-8004 Registered Agents
==================================================
Mining to: aib1q5v4lzmsxs4mhh045wumzw7c7y8n375s4n6qrnl
Agent: 0xF5A8Dc606ee66cfAf49aAd9C2E35cFF58aE68ddD
Connected to AIB node
Chain: main
Height: 5296

==================================================
Mining block 5297
Previous: 00000031aa0d855a...
Transactions in template: 0
Reward: 50.0 AIB (includes 0.0 fees)
Agent: 0xF5A8Dc606ee66cfAf49aAd9C2E35cFF58aE68ddD
Signature: cdabc87d86c2a608...
Agent discount: 256x (target from bits 0x1c3fffc0)
Mining...
  2M nonces @ 340,000 H/s
  4M nonces @ 345,000 H/s

✅ FOUND!
Nonce: 12345678
Hash: 0000002a...
Time: 35.2s (350,000 H/s)

Submitting block with 1 transactions...
✅ Block 5297 ACCEPTED!
```

## Troubleshooting

### "high-hash" Rejection

Your block hash doesn't meet the target, even with discount. Causes:

1. **Oracle cache missing**: Create `~/.aib/aib_registered_agents.txt` (one lowercase 0x... address per line) and restart node
2. **Agent not registered**: Check oracle API for your address
3. **Signature invalid**: Verify `AGENT_PRIVATE_KEY` derives to registered address

**Verify your agent address:**
```python
from eth_account import Account
print(Account.from_key("0x...your_key...").address)
```

### "Connection refused"

Node not running or RPC misconfigured:
```bash
bitcoin-cli -datadir=~/.aib getblockcount
```

### Low Hashrate

CPU mining is ~300-400 kH/s. With 256x discount, this effectively competes with ~75-100 MH/s regular mining.

## Block Rewards

- **Coinbase maturity**: 100 blocks before spendable
- **Check immature balance**: 
  ```bash
  bitcoin-cli -datadir=~/.aib -rpcwallet=mining getbalances
  ```

## Security Notes

⚠️ **Never share your `AGENT_PRIVATE_KEY`**

- The private key signs blocks to prove agent identity
- Store it securely (environment variable, not in code)
- The same key controls your Ethereum address — keep it safe

## Technical Details

### Coinbase Structure

The miner embeds agent credentials in the coinbase transaction:

```
OP_RETURN <agent_address>:<signature>
```

Where:
- `agent_address`: Your Ethereum address (0x...)
- `signature`: ECDSA signature of `AIB_AGENT_MINING:{block_height}:{prev_hash}`

### Target Calculation

```python
# Target from compact "bits" format
exponent = bits >> 24
mantissa = bits & 0xffffff
base_target = mantissa << (8 * (exponent - 3))

# With 256x agent discount
effective_target = base_target * 256
```

### Oracle Cache Format

```json
{
  "addresses": [
    "0x21df5569d53aaf0c5e7982b448ef5a2bcbb3b1e5",
    "0xf5a8dc606ee66cfaf49aad9c2e35cff58ae68ddd",
    ...
  ]
}
```

## Links

- **Oracle API**: https://oracle.x402endpoints.online
- **AIB GitHub**: https://github.com/Concorde89/AIB
- **EIP-8004**: Agent identity standard for AI systems
