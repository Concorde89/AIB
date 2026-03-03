#ifndef BITCOIN_CHAINPARAMSSEEDS_H
#define BITCOIN_CHAINPARAMSSEEDS_H
/**
 * List of fixed seed nodes for the AIB network
 * 
 * AIB uses DNS seeds (seed.aib.x402endpoints.online) as primary discovery.
 * Fixed seeds cleared to prevent fallback to Bitcoin network.
 *
 * Each line contains a BIP155 serialized (networkID, addr, port) tuple.
 */

// AIB mainnet: No fixed seeds - use DNS seeder only
// Note: Single null byte to satisfy C++ zero-length array restriction
// Seed loading code treats this as empty (size < minimum BIP155 entry)
static const uint8_t chainparams_seed_main[] = {0x00};

// AIB testnet: No fixed seeds
static const uint8_t chainparams_seed_test[] = {0x00};

#endif // BITCOIN_CHAINPARAMSSEEDS_H
