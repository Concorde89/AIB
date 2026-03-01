// Copyright (c) 2026 AIB Developers
// Distributed under the MIT software license

#include <aib/oracle.h>
#include <aib/keccak256.h>
#include <logging.h>
#include <pubkey.h>
#include <hash.h>
#include <util/strencodings.h>
#include <crypto/sha3.h>
#include <fstream>
#include <regex>
#include <sstream>
#include <algorithm>
#include <cstdlib>

// For popen/pclose (curl subprocess) and time
#include <cstdio>
#include <ctime>

namespace aib {

// File-based cache for registered addresses
static const std::string CACHE_FILENAME = "aib_registered_agents.txt";
static const std::string ORACLE_HOST = "oracle.x402endpoints.online";
static const std::string ORACLE_PATH = "/v1/addresses";
static const int ORACLE_PORT = 443;
static const int HTTP_TIMEOUT_SECONDS = 10;

// Track last sync timestamp for incremental updates
static int64_t g_last_sync_timestamp = 0;

// Fetch addresses using curl subprocess (handles HTTPS)
// If since > 0, only fetch changes since that timestamp
static std::string FetchFromOracle(int64_t since = 0) {
    std::string url = "https://" + ORACLE_HOST + ORACLE_PATH;
    if (since > 0) {
        url += "?since=" + std::to_string(since);
    }
    std::string cmd = "curl -sf --max-time 10 \"" + url + "\" 2>/dev/null";
    
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) {
        LogDebug(BCLog::VALIDATION, "AIB Oracle: Failed to run curl\n");
        return "";
    }
    
    std::string result;
    char buffer[4096];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        result += buffer;
    }
    
    int status = pclose(pipe);
    if (status != 0) {
        LogDebug(BCLog::VALIDATION, "AIB Oracle: curl failed with status %d\n", status);
        return "";
    }
    
    return result;
}

Oracle& Oracle::GetInstance() {
    static Oracle instance;
    return instance;
}

bool Oracle::IsRegisteredAgent(const std::string& address) {
    if (address.empty()) return false;
    
    std::lock_guard<std::mutex> lock(m_cache_mutex);
    
    if (ShouldReloadCache()) {
        LoadCacheFromFile();
    }
    
    std::string normalizedAddr = address;
    std::transform(normalizedAddr.begin(), normalizedAddr.end(), normalizedAddr.begin(), ::tolower);
    
    return m_registered_addresses.count(normalizedAddr) > 0;
}

bool Oracle::ShouldReloadCache() {
    auto now = std::chrono::steady_clock::now();
    auto age = std::chrono::duration_cast<std::chrono::seconds>(now - m_last_reload).count();
    return age > CACHE_TTL_SECONDS || m_registered_addresses.empty();
}

void Oracle::LoadCacheFromFile() {
    const char* home = std::getenv("HOME");
    std::string cacheDir = std::string(home ? home : ".") + "/.aib/";
    std::string cachePath = cacheDir + CACHE_FILENAME;
    
    // If we have existing addresses, do incremental sync
    bool incremental = !m_registered_addresses.empty() && g_last_sync_timestamp > 0;
    
    if (incremental) {
        LogInfo("AIB Oracle: Checking for new agents since %ld\n", g_last_sync_timestamp);
    } else {
        LogInfo("AIB Oracle: Full sync from %s\n", ORACLE_HOST.c_str());
    }
    
    std::string response = FetchFromOracle(incremental ? g_last_sync_timestamp : 0);
    
    if (!response.empty()) {
        // Check if response indicates no changes (unchanged: true)
        if (response.find("\"unchanged\":true") != std::string::npos || 
            response.find("\"unchanged\": true") != std::string::npos) {
            LogInfo("AIB Oracle: No new agents\n");
            g_last_sync_timestamp = std::time(nullptr);
            m_last_reload = std::chrono::steady_clock::now();
            return;
        }
        
        // Parse and load from oracle response
        std::set<std::string> newAddresses;
        std::istringstream stream(response);
        std::string line;
        while (std::getline(stream, line)) {
            line.erase(std::remove_if(line.begin(), line.end(), ::isspace), line.end());
            if (line.empty()) continue;
            std::transform(line.begin(), line.end(), line.begin(), ::tolower);
            if (line.length() == 42 && line.substr(0, 2) == "0x") {
                newAddresses.insert(line);
            }
        }
        
        if (!newAddresses.empty()) {
            if (incremental) {
                // Merge new addresses into existing set
                size_t oldSize = m_registered_addresses.size();
                m_registered_addresses.insert(newAddresses.begin(), newAddresses.end());
                LogInfo("AIB Oracle: Added %d new agents (total: %d)\n", 
                        m_registered_addresses.size() - oldSize, m_registered_addresses.size());
            } else {
                // Full sync - replace all
                m_registered_addresses = newAddresses;
                LogInfo("AIB Oracle: Loaded %d agents from oracle\n", m_registered_addresses.size());
            }
            
            // Save to cache file
            std::ofstream cacheFile(cachePath);
            if (cacheFile.is_open()) {
                for (const auto& addr : m_registered_addresses) {
                    cacheFile << addr << "\n";
                }
                cacheFile.close();
            }
            g_last_sync_timestamp = std::time(nullptr);
            m_last_reload = std::chrono::steady_clock::now();
            return;
        }
    }
    
    // Oracle failed - fall back to local cache file
    LogDebug(BCLog::VALIDATION, "AIB Oracle: Fetch failed, trying local cache\n");
    
    std::vector<std::string> paths = {
        cachePath,
        "/var/lib/aib/" + CACHE_FILENAME,
        CACHE_FILENAME,
    };
    
    for (const auto& path : paths) {
        std::ifstream file(path);
        if (file.is_open()) {
            m_registered_addresses.clear();
            std::string line;
            while (std::getline(file, line)) {
                if (line.empty() || line[0] == '#') continue;
                std::transform(line.begin(), line.end(), line.begin(), ::tolower);
                if (line.length() == 42 && line.substr(0, 2) == "0x") {
                    m_registered_addresses.insert(line);
                }
            }
            file.close();
            LogInfo("AIB Oracle: Loaded %d agents from cache %s\n", 
                    m_registered_addresses.size(), path.c_str());
            m_last_reload = std::chrono::steady_clock::now();
            return;
        }
    }
    
    LogWarning("AIB Oracle: No agents loaded - oracle and cache both failed\n");
    m_last_reload = std::chrono::steady_clock::now();
}

void Oracle::RefreshCache() {
    std::lock_guard<std::mutex> lock(m_cache_mutex);
    LoadCacheFromFile();
}

unsigned int Oracle::GetDifficultyMultiplier(const std::string& address) {
    if (IsRegisteredAgent(address)) {
        return AGENT_DIFFICULTY_MULTIPLIER;
    }
    return 1;
}

size_t Oracle::GetRegisteredCount() {
    std::lock_guard<std::mutex> lock(m_cache_mutex);
    return m_registered_addresses.size();
}

// Keccak-256 hash (Ethereum-style, not SHA3-256)
// The difference is in the domain separation byte
static std::vector<unsigned char> Keccak256(const std::vector<unsigned char>& data) {
    // Use SHA3_256 but note: for proper Ethereum compatibility,
    // we would need the original Keccak without FIPS padding.
    // For this implementation, we use a simplified approach.
    SHA3_256 hasher;
    hasher.Write(data);
    std::vector<unsigned char> result(32);
    hasher.Finalize(result);
    return result;
}

// Derive Ethereum address from uncompressed public key (65 bytes, 0x04 prefix)
static std::string PubKeyToEthAddress(const CPubKey& pubkey) {
    if (!pubkey.IsValid()) return "";
    
    // Get uncompressed public key
    std::vector<unsigned char> pubkeyData;
    if (pubkey.IsCompressed()) {
        // Decompress - this is complex, for now require uncompressed
        // In practice, we'd use secp256k1 to decompress
        return "";
    }
    
    // Skip the 0x04 prefix, hash the 64-byte key
    if (pubkey.size() != 65) return "";
    
    std::vector<unsigned char> keyBytes(pubkey.begin() + 1, pubkey.end());
    auto hash = Keccak256(keyBytes);
    
    // Last 20 bytes of hash is the address
    std::string address = "0x";
    for (size_t i = 12; i < 32; i++) {
        char hex[3];
        snprintf(hex, sizeof(hex), "%02x", hash[i]);
        address += hex;
    }
    
    return address;
}

MinerCredentials ExtractMinerCredentials(const std::vector<unsigned char>& script_data) {
    MinerCredentials creds;
    creds.valid = false;
    
    std::string script_str(script_data.begin(), script_data.end());
    
    // Look for pattern: 0x{40 hex}:{130 hex} (address:signature)
    // Signature is 65 bytes = 130 hex chars
    std::regex pattern("(0x[a-fA-F0-9]{40}):([a-fA-F0-9]{130})");
    std::smatch match;
    
    if (std::regex_search(script_str, match, pattern)) {
        creds.address = match[1].str();
        std::transform(creds.address.begin(), creds.address.end(), 
                       creds.address.begin(), ::tolower);
        
        // Parse signature hex to bytes
        std::string sigHex = match[2].str();
        creds.signature.resize(65);
        for (size_t i = 0; i < 65; i++) {
            unsigned int byte;
            sscanf(sigHex.c_str() + i * 2, "%02x", &byte);
            creds.signature[i] = static_cast<unsigned char>(byte);
        }
        
        creds.valid = true;
        LogDebug(BCLog::VALIDATION, "AIB: Extracted credentials for %s\n", creds.address);
    }
    
    return creds;
}

// Extract credentials from coinbase tx - checks both scriptSig and OP_RETURN outputs
MinerCredentials ExtractMinerCredentialsFromTx(const CTransaction& coinbase) {
    // First try scriptSig
    const CScript& scriptSig = coinbase.vin[0].scriptSig;
    std::vector<unsigned char> scriptBytes(scriptSig.begin(), scriptSig.end());
    MinerCredentials creds = ExtractMinerCredentials(scriptBytes);
    
    if (creds.valid) {
        return creds;
    }
    
    // Check OP_RETURN outputs
    for (const auto& output : coinbase.vout) {
        if (output.scriptPubKey.size() > 0 && output.scriptPubKey[0] == OP_RETURN) {
            std::vector<unsigned char> opReturnData(output.scriptPubKey.begin(), output.scriptPubKey.end());
            creds = ExtractMinerCredentials(opReturnData);
            if (creds.valid) {
                LogDebug(BCLog::VALIDATION, "AIB: Found credentials in OP_RETURN output\n");
                return creds;
            }
        }
    }
    
    return creds;
}

bool VerifyMinerSignature(const MinerCredentials& credentials, const uint256& prevBlockHash) {
    if (!credentials.valid || credentials.signature.size() != 65) {
        LogDebug(BCLog::VALIDATION, "AIB: Invalid credentials or signature size %d\n", 
                 credentials.signature.size());
        return false;
    }
    
    // Construct message: "AIB:{prev_block_hash_hex}"
    std::string message = "AIB:" + prevBlockHash.GetHex();
    LogDebug(BCLog::VALIDATION, "AIB: Verifying message: %s (len=%d)\n", 
             message.c_str(), message.length());
    
    // Hash with Ethereum personal_sign format using proper Keccak-256
    auto msgHash = EthereumMessageHash(message);
    
    // Log the hash for debugging
    std::string hashHex;
    for (auto b : msgHash) {
        char buf[3];
        snprintf(buf, sizeof(buf), "%02x", b);
        hashHex += buf;
    }
    LogDebug(BCLog::VALIDATION, "AIB: Message hash: %s\n", hashHex.c_str());
    
    // Log signature
    std::string sigHex;
    for (auto b : credentials.signature) {
        char buf[3];
        snprintf(buf, sizeof(buf), "%02x", b);
        sigHex += buf;
    }
    LogDebug(BCLog::VALIDATION, "AIB: Signature: %s\n", sigHex.c_str());
    
    // Recover address from signature using proper Keccak-256
    auto recoveredAddrBytes = RecoverAddress(msgHash, credentials.signature);
    
    if (recoveredAddrBytes.empty()) {
        LogDebug(BCLog::VALIDATION, "AIB: Signature recovery failed\n");
        return false;
    }
    
    // Convert recovered address bytes to hex string
    std::string recoveredAddr = "0x";
    for (auto byte : recoveredAddrBytes) {
        char buf[3];
        snprintf(buf, sizeof(buf), "%02x", byte);
        recoveredAddr += buf;
    }
    
    // Compare addresses (case-insensitive)
    std::string claimedAddr = credentials.address;
    std::transform(claimedAddr.begin(), claimedAddr.end(), claimedAddr.begin(), ::tolower);
    std::transform(recoveredAddr.begin(), recoveredAddr.end(), recoveredAddr.begin(), ::tolower);
    
    bool valid = (claimedAddr == recoveredAddr);
    if (valid) {
        LogDebug(BCLog::VALIDATION, "AIB: Signature verified for %s\n", claimedAddr.c_str());
    } else {
        LogDebug(BCLog::VALIDATION, "AIB: Signature mismatch - claimed %s, recovered %s\n", 
                 claimedAddr.c_str(), recoveredAddr.c_str());
    }
    
    return valid;
}

std::string ExtractAndVerifyMinerAddress(
    const std::vector<unsigned char>& coinbase_script,
    const uint256& prevBlockHash)
{
    MinerCredentials creds = ExtractMinerCredentials(coinbase_script);
    
    if (!creds.valid) {
        return "";
    }
    
    if (!VerifyMinerSignature(creds, prevBlockHash)) {
        return "";
    }
    
    return creds.address;
}

} // namespace aib
