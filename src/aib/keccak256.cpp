// Copyright (c) 2026 AIB Developers
// Ethereum-compatible Keccak-256 hash

#include <aib/keccak256.h>
#include <crypto/common.h>
#include <pubkey.h>
#include <logging.h>
#include <algorithm>
#include <cassert>

// Use Bitcoin Core's KeccakF from crypto/sha3.cpp (global namespace)
extern "C++" void KeccakF(uint64_t (&st)[25]);

namespace aib {

// Wrapper to call global KeccakF
static inline void DoKeccakF(uint64_t (&st)[25]) {
    ::KeccakF(st);
}

Keccak256& Keccak256::Write(std::span<const unsigned char> data)
{
    if (m_bufsize && data.size() >= sizeof(m_buffer) - m_bufsize) {
        std::copy(data.begin(), data.begin() + (sizeof(m_buffer) - m_bufsize), m_buffer + m_bufsize);
        data = data.subspan(sizeof(m_buffer) - m_bufsize);
        m_state[m_pos++] ^= ReadLE64(m_buffer);
        m_bufsize = 0;
        if (m_pos == RATE_BUFFERS) {
            DoKeccakF(m_state);
            m_pos = 0;
        }
    }
    while (data.size() >= sizeof(m_buffer)) {
        m_state[m_pos++] ^= ReadLE64(data.data());
        data = data.subspan(8);
        if (m_pos == RATE_BUFFERS) {
            DoKeccakF(m_state);
            m_pos = 0;
        }
    }
    if (data.size()) {
        std::copy(data.begin(), data.end(), m_buffer + m_bufsize);
        m_bufsize += data.size();
    }
    return *this;
}

Keccak256& Keccak256::Finalize(std::span<unsigned char> output)
{
    assert(output.size() == OUTPUT_SIZE);
    std::fill(m_buffer + m_bufsize, m_buffer + sizeof(m_buffer), 0);
    // Keccak-256 padding: 0x01 (NOT SHA3's 0x06)
    m_buffer[m_bufsize] ^= 0x01;
    m_state[m_pos] ^= ReadLE64(m_buffer);
    m_state[RATE_BUFFERS - 1] ^= 0x8000000000000000ULL;
    DoKeccakF(m_state);
    for (unsigned i = 0; i < 4; ++i) {
        WriteLE64(output.data() + 8 * i, m_state[i]);
    }
    return *this;
}

Keccak256& Keccak256::Reset()
{
    m_bufsize = 0;
    m_pos = 0;
    std::fill(std::begin(m_state), std::end(m_state), 0);
    return *this;
}

std::array<unsigned char, 32> Keccak256::Hash(std::span<const unsigned char> data)
{
    std::array<unsigned char, 32> result;
    Keccak256().Write(data).Finalize(result);
    return result;
}

std::array<unsigned char, 32> Keccak256::Hash(const std::string& data)
{
    return Hash(std::span<const unsigned char>(
        reinterpret_cast<const unsigned char*>(data.data()), data.size()));
}

std::array<unsigned char, 32> EthereumMessageHash(const std::string& message)
{
    // Ethereum signed message format:
    // "\x19Ethereum Signed Message:\n" + length + message
    std::string prefix = std::string(1, '\x19') + "Ethereum Signed Message:\n" + std::to_string(message.size()) + message;
    return Keccak256::Hash(prefix);
}

std::vector<unsigned char> RecoverAddress(
    const std::array<unsigned char, 32>& messageHash,
    const std::vector<unsigned char>& signature)
{
    if (signature.size() != 65) {
        LogDebug(BCLog::VALIDATION, "AIB: RecoverAddress: invalid sig size %d\n", signature.size());
        return {};
    }
    
    // Parse signature: r (32) + s (32) + v (1)
    // v is recovery id (0-3, or 27-30 for Ethereum)
    int recid = signature[64];
    LogDebug(BCLog::VALIDATION, "AIB: RecoverAddress: v=%d\n", recid);
    if (recid >= 27) recid -= 27;  // Ethereum uses 27/28
    if (recid < 0 || recid > 3) {
        LogDebug(BCLog::VALIDATION, "AIB: RecoverAddress: invalid recid %d\n", recid);
        return {};
    }
    
    // Convert to Bitcoin compact signature format
    // Bitcoin format: header (1) + r (32) + s (32)
    // header = 27 + recid + (4 if uncompressed)
    std::vector<unsigned char> compactSig(65);
    compactSig[0] = 27 + recid + 4;  // 4 = uncompressed pubkey flag
    std::copy(signature.begin(), signature.begin() + 64, compactSig.begin() + 1);
    LogDebug(BCLog::VALIDATION, "AIB: RecoverAddress: header=%d, recid=%d\n", compactSig[0], recid);
    
    // Convert message hash to uint256 for Bitcoin's API
    uint256 hash;
    std::copy(messageHash.begin(), messageHash.end(), hash.begin());
    
    // Recover public key using Bitcoin Core's API
    CPubKey recoveredPubKey;
    if (!recoveredPubKey.RecoverCompact(hash, compactSig)) {
        LogDebug(BCLog::VALIDATION, "AIB: RecoverAddress: RecoverCompact failed\n");
        return {};
    }
    
    // Get uncompressed public key (65 bytes)
    if (!recoveredPubKey.IsValid()) {
        LogDebug(BCLog::VALIDATION, "AIB: RecoverAddress: invalid pubkey\n");
        return {};
    }
    
    LogDebug(BCLog::VALIDATION, "AIB: RecoverAddress: pubkey size=%d, compressed=%d\n", 
             recoveredPubKey.size(), recoveredPubKey.IsCompressed());
    
    // Get raw bytes - need uncompressed (65 bytes) for Ethereum
    std::vector<unsigned char> pubkeyBytes;
    
    if (recoveredPubKey.IsCompressed()) {
        // Decompress the public key (modifies in place, returns success)
        CPubKey decompressed = recoveredPubKey;  // Copy first
        if (!decompressed.Decompress()) {
            LogDebug(BCLog::VALIDATION, "AIB: RecoverAddress: failed to decompress pubkey\n");
            return {};
        }
        pubkeyBytes.assign(decompressed.begin(), decompressed.end());
        LogDebug(BCLog::VALIDATION, "AIB: RecoverAddress: decompressed to size=%d\n", pubkeyBytes.size());
    } else {
        pubkeyBytes.assign(recoveredPubKey.begin(), recoveredPubKey.end());
    }
    
    // Ethereum address = last 20 bytes of Keccak256(pubkey[1:65])
    // Skip the 0x04 prefix byte for uncompressed keys
    if (pubkeyBytes.size() >= 65 && pubkeyBytes[0] == 0x04) {
        auto pubkey_hash = Keccak256::Hash(std::span<const unsigned char>(pubkeyBytes.data() + 1, 64));
        return std::vector<unsigned char>(pubkey_hash.end() - 20, pubkey_hash.end());
    }
    
    LogDebug(BCLog::VALIDATION, "AIB: RecoverAddress: unexpected pubkey format, size=%d, first=%02x\n",
             pubkeyBytes.size(), pubkeyBytes.empty() ? 0 : pubkeyBytes[0]);
    
    return {};
}

} // namespace aib
