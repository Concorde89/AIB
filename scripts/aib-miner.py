#!/usr/bin/env python3
"""
AIB CPU Miner - Standard mining without agent discount
For registered EIP-8004 agents, use aib-agent-miner.py for 256x easier mining.
"""

import hashlib
import struct
import time
import requests
import sys
import os
from binascii import hexlify, unhexlify

# Config - can be overridden via environment variables
RPC_URL = os.environ.get("AIB_RPC_URL", "http://127.0.0.1:18005")
RPC_USER = os.environ.get("AIB_RPC_USER", "aib")
RPC_PASS = os.environ.get("AIB_RPC_PASS", "aib8004")

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

def bech32_decode(addr):
    """Decode bech32 address to witness version and program"""
    CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    hrp, data_part = addr.rsplit('1', 1)
    values = [CHARSET.index(c) for c in data_part]
    values = values[:-6]  # Skip checksum
    wit_ver = values[0]
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

def create_coinbase(height, reward_sats, payout_address=None):
    """Create standard coinbase transaction"""
    # BIP34 height in scriptSig
    h_bytes = height.to_bytes((height.bit_length()+7)//8, 'little') if height else b'\x00'
    scriptsig = bytes([len(h_bytes)]) + h_bytes + b'\x08' + b'AIB/1.0/'
    
    # Create payout scriptPubKey
    if payout_address and payout_address.startswith('aib1'):
        wit_ver, wit_prog = bech32_decode(payout_address)
        payout_script = bytes([wit_ver, len(wit_prog)]) + wit_prog
    else:
        # Fallback to OP_TRUE
        payout_script = b'\x51'
    
    # Build transaction
    tx = struct.pack('<I', 1)  # version
    tx += b'\x01'  # 1 input
    tx += b'\x00' * 32 + b'\xff\xff\xff\xff'  # null outpoint
    tx += varint(len(scriptsig)) + scriptsig
    tx += b'\xff\xff\xff\xff'  # sequence
    tx += b'\x01'  # 1 output
    tx += struct.pack('<Q', reward_sats)
    tx += varint(len(payout_script)) + payout_script
    tx += struct.pack('<I', 0)  # locktime
    
    txid = sha256d(tx)
    return tx, txid

def get_payout_address():
    """Get payout address from wallet"""
    try:
        wallets = rpc("listwallets")
        if not wallets:
            try:
                rpc("loadwallet", ["mining"])
            except:
                rpc("createwallet", ["mining"])
        return rpc("getnewaddress", ["mining_reward", "bech32"])
    except Exception as e:
        print(f"Warning: Could not get wallet address: {e}")
        return None

def mine_block(payout_address):
    """Mine one block at standard difficulty"""
    info = rpc("getblockchaininfo")
    height = info["blocks"] + 1
    prev_hash = info["bestblockhash"]
    
    print(f"\n{'='*50}")
    print(f"Mining block {height} (standard difficulty)")
    print(f"Previous: {prev_hash[:16]}...")
    if payout_address:
        print(f"Payout: {payout_address[:20]}...")
    
    # Reward with halving
    halvings = height // 210000
    reward_sats = (50 * 100000000) >> halvings
    
    # Create coinbase
    coinbase, txid = create_coinbase(height, reward_sats, payout_address)
    coinbase_hex = hexlify(coinbase).decode()
    
    # Standard target (difficulty 1)
    target = int("00000000ffff0000000000000000000000000000000000000000000000000000", 16)
    
    # Header components
    prev_bytes = unhexlify(prev_hash)[::-1]
    merkle = txid
    bits_bytes = unhexlify("ffff001d")[::-1]
    
    print("Mining...")
    nonce = 0
    start = time.time()
    last_report = start
    
    while True:
        curtime = int(time.time())
        
        header = struct.pack('<I', 0x20000000)  # version
        header += prev_bytes
        header += merkle
        header += struct.pack('<I', curtime)
        header += bits_bytes
        header += struct.pack('<I', nonce)
        
        h = sha256d(header)
        hash_int = int.from_bytes(h[::-1], 'big')
        
        if hash_int < target:
            elapsed = time.time() - start
            hash_hex = h[::-1].hex()
            print(f"\n✅ FOUND!")
            print(f"Nonce: {nonce}")
            print(f"Hash: {hash_hex}")
            print(f"Time: {elapsed:.1f}s ({nonce/elapsed:,.0f} H/s)")
            
            # Build block
            block_hex = hexlify(header).decode()
            block_hex += "01"  # tx count
            block_hex += coinbase_hex
            
            print("Submitting...")
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
        if nonce >= 0xFFFFFFFF:
            nonce = 0
            # Update time to get new block template
        
        # Progress report
        now = time.time()
        if now - last_report >= 10:
            elapsed = now - start
            rate = nonce / elapsed
            print(f"  {nonce/1e6:.0f}M @ {rate:,.0f} H/s")
            last_report = now

def main():
    print("=" * 50)
    print("AIB CPU Miner v1.0 (Standard Difficulty)")
    print("=" * 50)
    print("NOTE: For 256x easier mining, register as an")
    print("EIP-8004 agent and use aib-agent-miner.py")
    print("=" * 50)
    
    # Connect
    try:
        info = rpc("getblockchaininfo")
        print(f"Connected - Height: {info['blocks']}")
    except Exception as e:
        print(f"Cannot connect to AIB node: {e}")
        sys.exit(1)
    
    # Get payout address
    payout_address = get_payout_address()
    if payout_address:
        print(f"Payout address: {payout_address}")
    
    # Mine blocks
    total_mined = 0
    while True:
        try:
            if mine_block(payout_address):
                total_mined += 1
                print(f"\nTotal mined: {total_mined}")
        except KeyboardInterrupt:
            print(f"\n\nStopped. Total mined: {total_mined}")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
