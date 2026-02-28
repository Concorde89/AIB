// Copyright (c) 2026 AIB Developers
// Distributed under the MIT software license

#ifndef AIB_POW_H
#define AIB_POW_H

#include <uint256.h>
#include <arith_uint256.h>
#include <consensus/params.h>
#include <primitives/transaction.h>
#include <optional>
#include <string>

namespace aib {

/**
 * Check proof of work with EIP-8004 agent difficulty discount.
 * 
 * Registered AI agents get 256x easier difficulty.
 * Miner must prove ownership of their ETH address via signature.
 * 
 * Coinbase format: 0x{address}:{signature}
 * Signature over: "AIB:{prev_block_hash}"
 * 
 * @param hash The block hash to check
 * @param nBits The difficulty bits from the block header
 * @param params Consensus parameters
 * @param coinbase Optional coinbase transaction
 * @param prevBlockHash Previous block hash (for signature verification)
 * @return true if proof of work is valid
 */
bool CheckProofOfWorkWithAgentDiscount(
    uint256 hash,
    unsigned int nBits,
    const Consensus::Params& params,
    const std::optional<CTransaction>& coinbase,
    const uint256& prevBlockHash
);

/**
 * Get the effective target for a miner, accounting for agent discount.
 */
arith_uint256 GetEffectiveTarget(
    unsigned int nBits,
    const Consensus::Params& params,
    const std::string& minerAddress
);

} // namespace aib

#endif // AIB_POW_H
