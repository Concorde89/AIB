#!/usr/bin/env python3
"""
AIB Agent Miner - Mines with EIP-8004 agent discount
Includes proper signature in coinbase for verification
"""

import hashlib
import struct
import time
import requests
import os
import sys
from binascii import hexlify, unhexlify

from eth_account import Account
from eth_account.messages import encode_defunct

# Config
# Config - can be overridden via environment variables
RPC_URL = os.environ.get("AIB_RPC_URL", "http://127.0.0.1:18005")
RPC_USER = os.environ.get("AIB_RPC_USER", "aib")
RPC_PASS = os.environ.get("AIB_RPC_PASS", "aib8004")
AGENT_ADDRESS = os.environ.get("AGENT_ADDRESS", "")  # Your EIP-8004 registered ETH address
AGENT_DISCOUNT = 256

def rpc(method, params=[]):
    r = requests.post(RPC_URL, auth=(RPC_USER, RPC_PASS), 
                      json={"jsonrpc":"2.0", "method":method, "params":params, "id":1}, timeout=30)
    result = r.json()
    if "error" in result and result["error"]:
        raise Exception(f"RPC: {result['error']}")
    return result.get("result")

def sha256d(data):
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def varint(n):
    if n < 0xfd: return bytes([n])
    elif n <= 0xffff: return b'\xfd' + struct.pack('<H', n)
    else: return b'\xfe' + struct.pack('<I', n)

def sign_for_mining(private_key, prev_hash):
    """Sign AIB:{prev_hash} with ETH key - returns 130 hex chars (65 bytes: r+s+v)"""
    message = f"AIB:{prev_hash}"
    msg = encode_defunct(text=message)
    signed = Account.sign_message(msg, private_key)
    # signature.hex() returns 0x + 130 chars (r:32 + s:32 + v:1 = 65 bytes)
    sig_hex = signed.signature.hex()
    if sig_hex.startswith('0x'):
        sig_hex = sig_hex[2:]
    # Ensure it's 130 chars (65 bytes)
    if len(sig_hex) != 130:
        # If v is missing, add it
        sig_hex = sig_hex + format(signed.v, '02x')
    return sig_hex

def bech32_decode(addr):
    """Decode bech32 address to witness version and program"""
    CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    hrp, data_part = addr.rsplit('1', 1)
    values = [CHARSET.index(c) for c in data_part]
    # Skip checksum (last 6 chars)
    values = values[:-6]
    # First value is witness version
    wit_ver = values[0]
    # Rest is 5-bit encoded data
    acc = 0
    bits = 0
    result = []
    for v in values[1:]:
        acc = (acc << 5) | v
        bits += 5
        while bits >= 8:
            bits -= 8
            result.append((acc >> bits) & 0xff)
    return wit_ver, bytes(result)

def create_coinbase_with_agent(height, reward_sats, agent_address, signature, payout_address=None):
    """Create coinbase with agent credentials
    Agent data goes in OP_RETURN output (scriptSig max is 100 bytes)
    Returns (full_tx_hex, txid) where txid is used for merkle root
    NOTE: Creates NON-SEGWIT transaction (no witness) for simplicity
    """
    # BIP34 height (must be in scriptSig)
    h_bytes = height.to_bytes((height.bit_length()+7)//8, 'little') if height else b'\x00'
    scriptsig = bytes([len(h_bytes)]) + h_bytes + b'\x08' + b'AIB/1.0/'  # Keep it short!
    
    # Agent data goes in OP_RETURN output
    agent_data = f"{agent_address}:{signature}".encode()
    op_return_script = b'\x6a' + bytes([len(agent_data)]) + agent_data  # OP_RETURN + push
    
    # Create payout scriptPubKey
    if payout_address and payout_address.startswith('aib1'):
        # Bech32 P2WPKH
        wit_ver, wit_prog = bech32_decode(payout_address)
        # P2WPKH: OP_0 <20-byte-pubkey-hash>
        payout_script = bytes([wit_ver, len(wit_prog)]) + wit_prog
    else:
        # Fallback to OP_TRUE (anyone can spend)
        payout_script = b'\x51'
    
    # Build NON-SEGWIT transaction (no witness data)
    tx = struct.pack('<I', 3)  # version (AIB replay protection)
    tx += b'\x01'  # 1 input
    tx += b'\x00' * 32 + b'\xff\xff\xff\xff'  # null outpoint
    tx += varint(len(scriptsig)) + scriptsig
    tx += b'\xff\xff\xff\xff'  # sequence
    tx += b'\x02'  # 2 outputs
    # Output 1: reward to payout address
    tx += struct.pack('<Q', reward_sats)
    tx += varint(len(payout_script)) + payout_script
    # Output 2: OP_RETURN with agent data
    tx += struct.pack('<Q', 0)  # 0 value
    tx += varint(len(op_return_script)) + op_return_script
    tx += struct.pack('<I', 0)  # locktime
    
    txid = sha256d(tx)
    
    return tx, txid

def get_payout_address():
    """Get or create a payout address from the miner wallet"""
    try:
        wallets = rpc("listwallets")
        wallet_name = None
        
        # Check for existing wallets
        for name in ["mining", "miner"]:
            if name in wallets:
                wallet_name = name
                break
        
        # Load or create wallet
        if not wallet_name:
            try:
                rpc("loadwallet", ["mining"])
                wallet_name = "mining"
            except:
                try:
                    rpc("createwallet", ["mining"])
                    wallet_name = "mining"
                except:
                    return None
        
        # Get new address from wallet
        # Use wallet-specific RPC by passing wallet in URL isn't supported,
        # so we use the default loaded wallet
        addr = rpc("getnewaddress", ["mining_reward", "bech32"])
        return addr
    except Exception as e:
        print(f"Warning: Could not get wallet address: {e}")
        return None

# Global payout address (reuse for consistency)
PAYOUT_ADDRESS = None

def mine_block(private_key):
    """Mine one block with agent discount"""
    global PAYOUT_ADDRESS
    
    info = rpc("getblockchaininfo")
    height = info["blocks"] + 1
    prev_hash = info["bestblockhash"]
    
    # Get payout address once
    if PAYOUT_ADDRESS is None:
        PAYOUT_ADDRESS = get_payout_address()
        if PAYOUT_ADDRESS:
            print(f"Payout address: {PAYOUT_ADDRESS}")
    
    print(f"\n{'='*50}")
    print(f"Mining block {height} with agent discount")
    print(f"Previous: {prev_hash[:16]}...")
    
    # Sign for this block
    signature = sign_for_mining(private_key, prev_hash)
    print(f"Agent: {AGENT_ADDRESS}")
    print(f"Signature: {signature[:32]}...")
    
    # Reward
    halvings = height // 210000
    reward_sats = (50 * 100000000) >> halvings
    
    # Create coinbase with credentials and payout address
    coinbase, txid = create_coinbase_with_agent(height, reward_sats, AGENT_ADDRESS, signature, PAYOUT_ADDRESS)
    coinbase_hex = hexlify(coinbase).decode()
    
    # Target with discount
    target = int("00000000ffff0000000000000000000000000000000000000000000000000000", 16)
    target *= AGENT_DISCOUNT
    print(f"Discount: {AGENT_DISCOUNT}x")
    
    # Header components
    prev_bytes = unhexlify(prev_hash)[::-1]
    merkle = txid  # Use txid for merkle root (not full tx hash)
    curtime = int(time.time())
    
    print("Mining...")
    nonce = 0
    start = time.time()
    
    while True:
        header = struct.pack('<I', 0x20000000)  # version
        header += prev_bytes
        header += merkle
        header += struct.pack('<III', curtime, 0x1d00ffff, nonce)
        
        h = sha256d(header)
        if int.from_bytes(h, 'little') < target:
            elapsed = time.time() - start
            hash_hex = h[::-1].hex()
            
            print(f"\n✅ FOUND!")
            print(f"Nonce: {nonce}")
            print(f"Hash: {hash_hex}")
            print(f"Time: {elapsed:.1f}s ({nonce/elapsed:,.0f} H/s)")
            
            # Build and submit block
            block_hex = hexlify(header).decode() + "01" + coinbase_hex
            
            print("Submitting...")
            result = rpc("submitblock", [block_hex])
            if result is None:
                print(f"✅ Block {height} ACCEPTED!")
                return True
            else:
                print(f"❌ Rejected: {result}")
                return False
        
        nonce += 1
        if nonce % 2000000 == 0:
            e = time.time() - start
            print(f"  {nonce//1000000}M @ {nonce/e:,.0f} H/s", flush=True)
        
        if nonce >= 0xFFFFFFFF:
            curtime += 1
            nonce = 0

def main():
    global AGENT_ADDRESS
    
    print("=" * 50)
    print("AIB Agent Miner v1.1")
    print("=" * 50)
    
    # Get private key
    private_key = os.environ.get("PRIVATE_KEY")
    if not private_key:
        print("Error: Set PRIVATE_KEY environment variable")
        print("  export PRIVATE_KEY='0x...'")
        sys.exit(1)
    
    # Derive agent address from private key if not set
    if not AGENT_ADDRESS:
        acct = Account.from_key(private_key)
        AGENT_ADDRESS = acct.address
    
    print(f"Agent: {AGENT_ADDRESS}")
    print(f"Discount: {AGENT_DISCOUNT}x")
    
    # Connect
    info = rpc("getblockchaininfo")
    print(f"Connected - Height: {info['blocks']}")
    
    # Mine continuously
    blocks = 0
    while True:
        try:
            if mine_block(private_key):
                blocks += 1
                print(f"\nTotal mined: {blocks}")
            time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n\nStopped. Mined {blocks} blocks.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
