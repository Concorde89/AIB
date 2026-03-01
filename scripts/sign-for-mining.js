#!/usr/bin/env node
/**
 * AIB Mining Signature Generator
 * 
 * Generates the signature needed for the coinbase to claim agent discount.
 * 
 * Usage:
 *   node sign-for-mining.js <eth_private_key> <prev_block_hash>
 * 
 * Output:
 *   The coinbase string to include: 0x{address}:{signature}
 */

const { ethers } = require('ethers');

async function main() {
    const args = process.argv.slice(2);

    if (args.length < 2) {
        console.log(`
AIB Mining Signature Generator

Generates the coinbase string for claiming the 256x agent mining discount.

Usage:
  node sign-for-mining.js <eth_private_key> <prev_block_hash>

Arguments:
  eth_private_key   Your Ethereum private key (with or without 0x prefix)
  prev_block_hash   The previous block hash (without 0x prefix)

Example:
  node sign-for-mining.js 0x1234567890abcdef... 000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f

Output:
  Coinbase string to include in your mining coinbase scriptSig.
  Format: 0x{address}:{signature}

Note:
  - Your ETH address must be registered in EIP-8004 to get the discount
  - The signature proves you own the address
  - Message signed: "AIB:{prev_block_hash}"
`);
        process.exit(1);
    }

    let privateKey = args[0];
    const prevBlockHash = args[1];

    // Add 0x prefix if missing
    if (!privateKey.startsWith('0x')) {
        privateKey = '0x' + privateKey;
    }

    try {
        const wallet = new ethers.Wallet(privateKey);
        const message = 'AIB:' + prevBlockHash;
        
        console.log('Signing message:', message);
        console.log('With address:', wallet.address);
        
        const signature = await wallet.signMessage(message);
        
        // Remove 0x prefix from signature for coinbase format
        const sigWithoutPrefix = signature.slice(2);
        
        // Coinbase string
        const coinbaseString = wallet.address.toLowerCase() + ':' + sigWithoutPrefix;
        
        console.log('\n=== COINBASE STRING ===');
        console.log(coinbaseString);
        console.log('=======================\n');
        
        console.log('Include this in your coinbase scriptSig after the block height.');
        console.log('Length:', coinbaseString.length, 'characters');
        
    } catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    }
}

main();
