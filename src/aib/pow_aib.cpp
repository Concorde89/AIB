// Copyright (c) 2026 AIB Developers
// Distributed under the MIT software license

#include <aib/pow_aib.h>
#include <aib/oracle.h>
#include <arith_uint256.h>
#include <logging.h>
#include <pow.h>
#include <script/script.h>

namespace aib {

arith_uint256 GetEffectiveTarget(
    unsigned int nBits,
    const Consensus::Params& params,
    const std::string& minerAddress)
{
    auto bnTarget = DeriveTarget(nBits, params.powLimit);
    if (!bnTarget) {
        return arith_uint256(0);
    }
    
    arith_uint256 target = *bnTarget;
    
    if (!minerAddress.empty()) {
        unsigned int multiplier = Oracle::GetInstance().GetDifficultyMultiplier(minerAddress);
        if (multiplier > 1) {
            // 256x easier (shift left 8 bits)
            // Do NOT cap at powLimit - the discount intentionally exceeds it
            target <<= 8;
            
            LogDebug(BCLog::VALIDATION, "AIB: Agent discount applied for %s (256x easier)\n", minerAddress);
        }
    }
    
    return target;
}

bool CheckProofOfWorkWithAgentDiscount(
    uint256 hash,
    unsigned int nBits,
    const Consensus::Params& params,
    const std::optional<CTransaction>& coinbase,
    const uint256& prevBlockHash)
{
    auto bnTarget = DeriveTarget(nBits, params.powLimit);
    if (!bnTarget) {
        return false;
    }
    
    arith_uint256 hashValue = UintToArith256(hash);
    
    // Check if it passes normal difficulty
    if (hashValue <= *bnTarget) {
        return true;
    }
    
    // Try agent discount
    if (!coinbase.has_value() || coinbase->vin.empty()) {
        LogDebug(BCLog::VALIDATION, "AIB: No coinbase for agent check\n");
        return false;
    }
    
    // Extract miner credentials from coinbase (checks scriptSig and OP_RETURN)
    MinerCredentials creds = ExtractMinerCredentialsFromTx(*coinbase);
    
    if (!creds.valid) {
        LogDebug(BCLog::VALIDATION, "AIB: No valid address format in coinbase\n");
        return false;
    }
    
    std::string minerAddress = creds.address;
    LogDebug(BCLog::VALIDATION, "AIB: Found miner address %s in coinbase\n", minerAddress);
    
    // Check if miner is a registered agent
    if (!Oracle::GetInstance().IsRegisteredAgent(minerAddress)) {
        LogDebug(BCLog::VALIDATION, "AIB: Miner %s is not a registered agent\n", minerAddress);
        return false;
    }
    
    // SECURITY: Verify signature proves ownership of the registered address
    // Miner must sign "AIB:{prev_block_hash}" with their ETH private key
    if (!VerifyMinerSignature(creds, prevBlockHash)) {
        LogDebug(BCLog::VALIDATION, "AIB: Signature verification failed for %s\n", minerAddress);
        return false;
    }
    
    LogDebug(BCLog::VALIDATION, "AIB: Signature verified for %s\n", minerAddress);
    
    // Get effective target with discount
    arith_uint256 effectiveTarget = GetEffectiveTarget(nBits, params, minerAddress);
    
    if (effectiveTarget == 0) {
        return false;
    }
    
    // Check against effective target
    if (hashValue > effectiveTarget) {
        LogDebug(BCLog::VALIDATION, "AIB: Hash still too high even with discount\n");
        return false;
    }
    
    LogInfo("AIB: Block accepted with agent discount for %s\n", minerAddress);
    return true;
}

} // namespace aib
