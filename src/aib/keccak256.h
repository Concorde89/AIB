// Copyright (c) 2026 AIB Developers
// Ethereum-compatible Keccak-256 hash

#ifndef AIB_KECCAK256_H
#define AIB_KECCAK256_H

#include <cstdint>
#include <cstdlib>
#include <span>
#include <array>
#include <vector>
#include <string>

namespace aib {

// Forward declaration - uses Bitcoin Core's KeccakF
void KeccakF(uint64_t (&st)[25]);

class Keccak256 {
private:
    uint64_t m_state[25] = {0};
    unsigned char m_buffer[8];
    unsigned m_bufsize = 0;
    unsigned m_pos = 0;

    static constexpr unsigned RATE_BITS = 1088;
    static constexpr unsigned RATE_BUFFERS = RATE_BITS / 64;

public:
    static constexpr size_t OUTPUT_SIZE = 32;

    Keccak256() = default;
    Keccak256& Write(std::span<const unsigned char> data);
    Keccak256& Finalize(std::span<unsigned char> output);
    Keccak256& Reset();
    
    // Convenience function
    static std::array<unsigned char, 32> Hash(std::span<const unsigned char> data);
    static std::array<unsigned char, 32> Hash(const std::string& data);
};

// Ethereum signature recovery
// Returns recovered address (20 bytes) or empty if invalid
std::vector<unsigned char> RecoverAddress(
    const std::array<unsigned char, 32>& messageHash,
    const std::vector<unsigned char>& signature  // 65 bytes: r(32) + s(32) + v(1)
);

// Hash a message with Ethereum prefix: "\x19Ethereum Signed Message:\n" + len + message
std::array<unsigned char, 32> EthereumMessageHash(const std::string& message);

} // namespace aib

#endif // AIB_KECCAK256_H
