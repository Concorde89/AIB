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
static const uint8_t chainparams_seed_main[] = {};

// AIB testnet: No fixed seeds
static const uint8_t chainparams_seed_test[] = {};

#endif // BITCOIN_CHAINPARAMSSEEDS_H
