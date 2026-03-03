// Copyright (c) 2026 AIB Developers
// Distributed under the MIT software license

#ifndef AIB_ORACLE_H
#define AIB_ORACLE_H

#include <string>
#include <set>
#include <mutex>
#include <chrono>
#include <vector>
#include <uint256.h>
#include <primitives/transaction.h>

namespace aib {

/**
 * EIP-8004 Oracle Client
 * 
 * Checks if an address is a registered AI agent.
 * Registered agents get 256x easier mining difficulty.
 * 
 * Uses a file-based cache that is synced externally from:
 * https://oracle.x402endpoints.online/v1/addresses
 */
class Oracle {
public:
    static Oracle& GetInstance();
    
    /**
     * Check if an address is registered as an EIP-8004 agent.
     */
    bool IsRegisteredAgent(const std::string& address);
    
    /**
     * Force reload the cache from file.
     */
    void RefreshCache();
    
    /**
     * Get the difficulty multiplier for an address.
     * Returns 256 for registered agents, 1 for others.
     */
    unsigned int GetDifficultyMultiplier(const std::string& address);
    
    /**
     * Get number of registered addresses in cache.
     */
    size_t GetRegisteredCount();

    static constexpr int CACHE_TTL_SECONDS = 300;
    static constexpr unsigned int AGENT_DIFFICULTY_MULTIPLIER = 256;

private:
    Oracle() = default;
    Oracle(const Oracle&) = delete;
    Oracle& operator=(const Oracle&) = delete;
    
    std::set<std::string> m_registered_addresses;
    std::chrono::steady_clock::time_point m_last_reload;
    std::mutex m_cache_mutex;
    
    void LoadCacheFromFile();
    bool ShouldReloadCache();
};

/**
 * Result of parsing miner credentials from coinbase
 */
struct MinerCredentials {
    std::string address;      // Claimed ETH address (0x...)
    std::vector<unsigned char> signature;  // 65-byte signature (r, s, v)
    bool valid;               // Whether parsing succeeded
};

/**
 * Extract miner credentials from coinbase scriptSig.
 * 
 * Expected format: 0x{40 hex chars}:{130 hex chars signature}
 * Example: 0x1234...abcd:abc123...def (address:signature)
 * 
 * @param script_data The coinbase scriptSig bytes
 * @return Parsed credentials (check .valid field)
 */
MinerCredentials ExtractMinerCredentials(const std::vector<unsigned char>& script_data);
MinerCredentials ExtractMinerCredentialsFromTx(const CTransaction& coinbase);

/**
 * Verify that the signature proves ownership of the claimed address.
 * 
 * Message format: "AIB:{prev_block_hash_hex}"
 * Signature: 65 bytes (r[32] + s[32] + v[1])
 * 
 * Uses secp256k1 ECDSA recovery to get the public key,
 * then derives Ethereum address (keccak256 of pubkey, last 20 bytes).
 * 
 * @param credentials Parsed miner credentials
 * @param prevBlockHash Previous block hash (for message)
 * @return true if signature is valid and matches claimed address
 */
bool VerifyMinerSignature(const MinerCredentials& credentials, const uint256& prevBlockHash);

/**
 * Full extraction and verification of miner address.
 * Returns verified address or empty string if invalid.
 * 
 * @param coinbase_script The coinbase scriptSig bytes
 * @param prevBlockHash Previous block hash
 * @return Verified ETH address or empty string
 */
std::string ExtractAndVerifyMinerAddress(
    const std::vector<unsigned char>& coinbase_script,
    const uint256& prevBlockHash
);

} // namespace aib

#endif // AIB_ORACLE_H
