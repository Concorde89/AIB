#!/usr/bin/env python3
"""
AIB Agent Miner - CPU miner for AI Bitcoin with EIP-8004 agent discount

Registered AI agents (via oracle.x402endpoints.online) get 256x easier
mining difficulty, enabling CPU mining to compete with GPU/ASIC miners.

Requirements:
    pip install eth_account requests

Environment Variables:
    AGENT_PRIVATE_KEY   - Ethereum private key (0x...) for signing blocks
    MINING_ADDRESS      - AIB address to receive mining rewards (aib1q...)
    AIB_RPC_URL         - Node RPC endpoint (default: http://127.0.0.1:18005)
    AIB_RPC_USER        - RPC username (default: aib)
    AIB_RPC_PASS        - RPC password (default: aib8004)

Usage:
    export AGENT_PRIVATE_KEY='0x...'
    export MINING_ADDRESS='aib1q...'
    python3 aib-agent-miner.py

The agent address is derived from AGENT_PRIVATE_KEY and must be registered
in the EIP-8004 oracle to receive the 256x mining discount.

Register at: https://oracle.x402endpoints.online
"""

import hashlib
import struct
import time
import requests
import os
import sys
from binascii import hexlify, unhexlify

# Need eth_account for signing
try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
except ImportError:
    print("ERROR: pip install eth_account")
    sys.exit(1)

# RPC Configuration (override via environment)
RPC_URL = os.environ.get("AIB_RPC_URL", "http://127.0.0.1:18005")
RPC_USER = os.environ.get("AIB_RPC_USER", "aib")
RPC_PASS = os.environ.get("AIB_RPC_PASS", "aib8004")

# Agent for 256x discount (address derived from private key)
AGENT_PRIVATE_KEY = os.environ.get("AGENT_PRIVATE_KEY") or os.environ.get("PRIVATE_KEY")
AGENT_ADDRESS = Account.from_key(AGENT_PRIVATE_KEY).address if AGENT_PRIVATE_KEY else None
AGENT_DISCOUNT = 256
TIP_CHECK_INTERVAL = 5  # seconds between chain-tip checks during mining

# Mining payout address (REQUIRED - set via environment)
MINING_ADDRESS = os.environ.get("MINING_ADDRESS")

def bech32_decode(addr):
    """Decode bech32/bech32m address to witness program"""
    CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    
    # Find separator
    pos = addr.rfind('1')
    if pos < 1:
        raise ValueError("Invalid bech32: no separator")
    
    hrp = addr[:pos]
    data_part = addr[pos+1:]
    
    # Decode data
    values = []
    for c in data_part:
        if c not in CHARSET:
            raise ValueError(f"Invalid bech32 character: {c}")
        values.append(CHARSET.index(c))
    
    # Remove checksum (last 6 characters)
    values = values[:-6]
    
    # First value is witness version
    witness_version = values[0]
    
    # Convert remaining 5-bit groups to 8-bit
    acc = 0
    bits = 0
    result = []
    for v in values[1:]:
        acc = (acc << 5) | v
        bits += 5
        while bits >= 8:
            bits -= 8
            result.append((acc >> bits) & 0xff)
    
    return witness_version, bytes(result)

def address_to_scriptpubkey(addr):
    """Convert AIB address to scriptPubKey"""
    if addr.startswith("aib1"):
        # Bech32 (SegWit)
        version, program = bech32_decode(addr)
        if version == 0 and len(program) == 20:
            # P2WPKH
            return bytes([0x00, 0x14]) + program
        elif version == 0 and len(program) == 32:
            # P2WSH
            return bytes([0x00, 0x20]) + program
        else:
            raise ValueError(f"Unsupported witness version/length: {version}/{len(program)}")
    elif addr.startswith("A"):
        # Legacy P2PKH - would need base58 decode
        raise ValueError("Legacy addresses not yet supported in miner - use bech32 (aib1...)")
    else:
        raise ValueError(f"Unknown address format: {addr}")

def rpc(method, params=[]):
    """Make RPC call"""
    r = requests.post(RPC_URL, auth=(RPC_USER, RPC_PASS), 
                      json={"jsonrpc":"2.0", "method":method, "params":params, "id":1},
                      timeout=30)
    result = r.json()
    if "error" in result and result["error"]:
        raise Exception(f"RPC Error: {result['error']}")
    return result.get("result")

def sha256d(data):
    """Double SHA256"""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def sign_for_mining(prev_block_hash):
    """Sign the mining message with ETH key for agent discount"""
    if not AGENT_PRIVATE_KEY:
        raise Exception("AGENT_PRIVATE_KEY not set")
    message = f"AIB:{prev_block_hash}"
    msg = encode_defunct(text=message)
    signed = Account.sign_message(msg, AGENT_PRIVATE_KEY)
    return signed.signature  # bytes

def int_to_varint(n):
    """Integer to Bitcoin varint"""
    if n < 0xfd:
        return bytes([n])
    elif n <= 0xffff:
        return b'\xfd' + struct.pack('<H', n)
    elif n <= 0xffffffff:
        return b'\xfe' + struct.pack('<I', n)
    else:
        return b'\xff' + struct.pack('<Q', n)

def build_merkle_root(tx_hashes):
    """Build merkle root from tx hashes (already as bytes)"""
    if not tx_hashes:
        return b'\x00' * 32
    
    hashes = list(tx_hashes)
    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])
        hashes = [sha256d(hashes[i] + hashes[i+1]) for i in range(0, len(hashes), 2)]
    
    return hashes[0]

def create_coinbase_tx(height, value_sats, witness_commitment=None, agent_signature=None):
    """Create coinbase transaction with optional witness commitment and agent credentials"""
    # BIP34 height in scriptSig
    if height == 0:
        height_bytes = b'\x00'
    else:
        height_bytes = height.to_bytes((height.bit_length() + 7) // 8, 'little')
    height_script = bytes([len(height_bytes)]) + height_bytes
    
    # Extra nonce
    extra_nonce = os.urandom(4)
    scriptsig = height_script + bytes([len(extra_nonce)]) + extra_nonce
    
    # Determine if we need SegWit format (only if we have witness commitment)
    use_segwit = witness_commitment is not None
    
    # Build transaction
    tx = b''
    tx += struct.pack('<I', 1)  # version
    
    # SegWit marker and flag (only if we have witness transactions)
    if use_segwit:
        tx += b'\x00\x01'
    
    # Input (coinbase)
    tx += b'\x01'  # input count
    tx += b'\x00' * 32  # null txid
    tx += b'\xff\xff\xff\xff'  # index -1
    tx += int_to_varint(len(scriptsig)) + scriptsig
    tx += b'\xff\xff\xff\xff'  # sequence
    
    # Count outputs
    output_count = 1  # reward output
    if witness_commitment:
        output_count += 1
    if agent_signature:
        output_count += 1
    tx += int_to_varint(output_count)
    
    # Main output (reward) - pay to MINING_ADDRESS
    tx += struct.pack('<Q', value_sats)
    scriptpubkey = address_to_scriptpubkey(MINING_ADDRESS)
    tx += int_to_varint(len(scriptpubkey)) + scriptpubkey
    
    # Agent credentials OP_RETURN (for 256x discount)
    # Format: OP_RETURN <address>:<signature>
    if agent_signature:
        tx += struct.pack('<Q', 0)  # 0 value
        # Build credentials: "0xaddress:signature_hex"
        credentials = f"{AGENT_ADDRESS}:{agent_signature.hex()}".encode('utf-8')
        # OP_RETURN OP_PUSHDATA1 <len> <data>
        if len(credentials) < 76:
            agent_script = bytes([0x6a, len(credentials)]) + credentials
        else:
            agent_script = bytes([0x6a, 0x4c, len(credentials)]) + credentials
        tx += int_to_varint(len(agent_script)) + agent_script
    
    # Witness commitment output (required for SegWit blocks with witness data)
    if witness_commitment:
        tx += struct.pack('<Q', 0)  # 0 value
        # OP_RETURN OP_PUSHBYTES_36 0xaa21a9ed + 32-byte commitment
        commitment_script = bytes.fromhex("6a24aa21a9ed") + witness_commitment
        tx += int_to_varint(len(commitment_script)) + commitment_script
    
    # Witness data (only for SegWit coinbase)
    if use_segwit:
        tx += b'\x01'  # witness stack count
        tx += b'\x20' + b'\x00' * 32  # witness reserved value
    
    tx += struct.pack('<I', 0)  # locktime
    
    return tx

def parse_varint(data, pos):
    """Parse Bitcoin varint, return (value, new_pos)"""
    first = data[pos]
    if first < 0xfd:
        return first, pos + 1
    elif first == 0xfd:
        return struct.unpack('<H', data[pos+1:pos+3])[0], pos + 3
    elif first == 0xfe:
        return struct.unpack('<I', data[pos+1:pos+5])[0], pos + 5
    else:
        return struct.unpack('<Q', data[pos+1:pos+9])[0], pos + 9

def get_coinbase_txid(coinbase_tx):
    """Get txid of coinbase (without witness) - proper parsing"""
    tx = coinbase_tx
    pos = 0
    
    # Version (4 bytes)
    version = tx[0:4]
    pos = 4
    
    # Check for SegWit marker/flag
    has_witness = False
    if tx[pos] == 0x00 and tx[pos+1] == 0x01:
        has_witness = True
        pos += 2  # Skip marker and flag
    
    # Input count
    input_count, pos = parse_varint(tx, pos)
    
    # Store inputs start position
    inputs_start = pos
    
    # Skip inputs
    for _ in range(input_count):
        pos += 32 + 4  # prev_txid + prev_index
        script_len, pos = parse_varint(tx, pos)
        pos += script_len + 4  # scriptsig + sequence
    
    inputs_end = pos
    
    # Output count
    output_count, pos = parse_varint(tx, pos)
    
    # Store outputs start position  
    outputs_start = pos
    
    # Skip outputs
    for _ in range(output_count):
        pos += 8  # value
        script_len, pos = parse_varint(tx, pos)
        pos += script_len
    
    outputs_end = pos
    
    # Build non-witness serialization for txid
    non_witness = version  # version
    non_witness += int_to_varint(input_count)
    non_witness += tx[inputs_start:inputs_end]  # inputs
    non_witness += int_to_varint(output_count)
    non_witness += tx[outputs_start:outputs_end]  # outputs
    non_witness += struct.pack('<I', 0)  # locktime
    
    return sha256d(non_witness)

def mine_block():
    """Mine and submit a single block using getblocktemplate"""
    # Get block template with transactions
    template = rpc("getblocktemplate", [{"rules": ["segwit"]}])
    
    height = template["height"]
    prev_hash = template["previousblockhash"]
    bits = int(template["bits"], 16)
    curtime = template["curtime"]
    version = template["version"]
    
    print(f"\n{'='*50}")
    print(f"Mining block {height}")
    print(f"Previous: {prev_hash[:16]}...")
    print(f"Transactions in template: {len(template['transactions'])}")
    
    # Get transactions from template
    txs = template["transactions"]
    total_fees = sum(tx.get("fee", 0) for tx in txs)
    
    # Calculate reward
    reward_sats = template["coinbasevalue"]
    print(f"Reward: {reward_sats / 1e8} AIB (includes {total_fees / 1e8} fees)")
    
    # Sign for agent discount
    agent_signature = sign_for_mining(prev_hash)
    print(f"Agent: {AGENT_ADDRESS}")
    print(f"Signature: {agent_signature.hex()[:40]}...")
    
    # Calculate witness commitment if we have witness transactions
    witness_commitment = None
    if any(tx.get("txid") != tx.get("hash") for tx in txs):
        # Build witness merkle root
        # First element is coinbase witness (32 zero bytes)
        wtxids = [b'\x00' * 32]  # Coinbase wtxid placeholder
        for tx in txs:
            wtxid = unhexlify(tx["hash"])[::-1]  # Little-endian
            wtxids.append(wtxid)
        
        witness_merkle = build_merkle_root(wtxids)
        # Commitment = SHA256(witness_merkle || witness_reserved)
        witness_reserved = b'\x00' * 32
        witness_commitment = sha256d(witness_merkle + witness_reserved)
        print(f"Witness commitment: {witness_commitment.hex()[:16]}...")
    
    # Create coinbase with agent signature and witness commitment
    coinbase_tx = create_coinbase_tx(height, reward_sats, witness_commitment, agent_signature)
    coinbase_hex = hexlify(coinbase_tx).decode()
    
    # Build merkle root with all transactions
    # Coinbase txid first, then template txids
    tx_hashes = [get_coinbase_txid(coinbase_tx)]
    for tx in txs:
        txid = unhexlify(tx["txid"])[::-1]  # Little-endian
        tx_hashes.append(txid)
    
    merkle_root = build_merkle_root(tx_hashes)
    
    # Calculate target from bits (compact target format)
    exponent = bits >> 24
    mantissa = bits & 0xffffff
    if exponent <= 3:
        base_target = mantissa >> (8 * (3 - exponent))
    else:
        base_target = mantissa << (8 * (exponent - 3))
    
    # Apply agent discount (256x easier = target * 256)
    target = base_target * AGENT_DISCOUNT
    print(f"Agent discount: {AGENT_DISCOUNT}x (target from bits 0x{bits:08x})")
    
    # Prepare header components
    prev_hash_bytes = unhexlify(prev_hash)[::-1]
    
    print(f"Mining...")
    nonce = 0
    start = time.time()
    last_tip_check = start
    
    while True:
        # Build header
        header = struct.pack('<I', version)
        header += prev_hash_bytes
        header += merkle_root
        header += struct.pack('<I', curtime)
        header += struct.pack('<I', bits)
        header += struct.pack('<I', nonce)
        
        # Check hash
        block_hash = sha256d(header)
        if int.from_bytes(block_hash, 'little') < target:
            elapsed = time.time() - start
            hash_hex = block_hash[::-1].hex()
            
            print(f"\n✅ FOUND!")
            print(f"Nonce: {nonce}")
            print(f"Hash: {hash_hex}")
            print(f"Time: {elapsed:.1f}s ({nonce/elapsed:,.0f} H/s)")
            
            # Build full block
            block_data = header
            
            # Transaction count (coinbase + template txs)
            tx_count = 1 + len(txs)
            block_data += int_to_varint(tx_count)
            
            # Add coinbase
            block_data += coinbase_tx
            
            # Add template transactions
            for tx in txs:
                block_data += unhexlify(tx["data"])
            
            block_hex = hexlify(block_data).decode()
            
            # Submit
            print(f"\nSubmitting block with {tx_count} transactions...")
            try:
                result = rpc("submitblock", [block_hex])
                if result is None:
                    print(f"✅ Block {height} ACCEPTED!")
                    return True
                else:
                    print(f"❌ Rejected: {result}")
                    return False
            except Exception as e:
                print(f"❌ Submit error: {e}")
                return False
        
        nonce += 1
        if nonce % 2000000 == 0:
            elapsed = time.time() - start
            print(f"  {nonce//1000000}M nonces @ {nonce/elapsed:,.0f} H/s")
        
        # Stale-template guard: if another miner extended the chain,
        # abort and let the outer loop fetch a fresh template.
        now = time.time()
        if now - last_tip_check > TIP_CHECK_INTERVAL:
            last_tip_check = now
            try:
                tip = rpc("getblockchaininfo")["bestblockhash"]
                if tip != prev_hash:
                    print(f"\n\u23ed  Tip changed ({prev_hash[:16]}... -> {tip[:16]}...) "
                          f"after nonce={nonce}, elapsed={now-start:.1f}s -- restarting")
                    return False
            except Exception:
                pass  # transient RPC error, keep mining
        
        if nonce > 0xFFFFFFFF:
            print("Nonce overflow, updating time...")
            curtime = int(time.time())
            nonce = 0

def main():
    print("="*50)
    print("AIB Agent Miner")
    print("256x Discount for EIP-8004 Registered Agents")
    print("="*50)
    
    # Check for required environment variables
    if not MINING_ADDRESS:
        print("ERROR: MINING_ADDRESS not set")
        print("\nUsage:")
        print("  export MINING_ADDRESS='aib1q...'")
        print("  export AGENT_PRIVATE_KEY='0x...'")
        print("  python3 aib-agent-miner.py")
        sys.exit(1)
    
    if not AGENT_PRIVATE_KEY:
        print("ERROR: AGENT_PRIVATE_KEY not set")
        print("\nUsage:")
        print("  export MINING_ADDRESS='aib1q...'")
        print("  export AGENT_PRIVATE_KEY='0x...'")
        print("  python3 aib-agent-miner.py")
        sys.exit(1)
    
    # Validate mining address
    try:
        scriptpubkey = address_to_scriptpubkey(MINING_ADDRESS)
        print(f"Mining to: {MINING_ADDRESS}")
    except Exception as e:
        print(f"ERROR: Invalid MINING_ADDRESS: {e}")
        sys.exit(1)
    
    print(f"Agent: {AGENT_ADDRESS}")
    
    # Check connection
    info = rpc("getblockchaininfo")
    print(f"Connected to AIB node")
    print(f"Chain: {info['chain']}")
    print(f"Height: {info['blocks']}")
    
    # Mine continuously
    while True:
        try:
            mine_block()
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nStopping miner...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
