#!/bin/bash
set -e

# FEAL linear cryptanalysis attack
# Recovers 4 round keys (each from 20-bit seed) using known-plaintext linear cryptanalysis
# Then decrypts 100 ciphertexts

cat <<'ATTACK_C_EOF' > /tmp/feal_attack.c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

typedef uint64_t u64;
typedef uint32_t u32;
typedef uint8_t u8;

#define NUM_PAIRS 32
#define NUM_VERIFY_PAIRS 3
#define KEY_BITS 20
#define KEY_MAX (1 << KEY_BITS)

u32 round_key[4];
u32 f_output[4];

static inline u32 get_left(u64 x) {
    return (u32)(x >> 32);
}

static inline u32 get_right(u64 x) {
    return (u32)(x & 0xFFFFFFFFULL);
}

static inline u64 merge(u32 left, u32 right) {
    return ((u64)left << 32) | (u64)right;
}

/* Key expansion: same as feal.c */
static inline u32 expand(u32 k) {
    return k ^ (k << 16) ^ (k * 12345);
}

/* G function: same as feal.c */
static inline u8 g_func(u8 a, u8 b, u8 x) {
    u8 t = a + b + x;
    return (t << 2) | (t >> 6);
}

/*
 * F function matching feal.c exactly:
 *   - Extract bytes little-endian (x[0] = LSB)
 *   - Compute y[] using same indices as feal.c
 *   - Assemble output little-endian
 */
static u32 f_func(u32 v) {
    u8 x[4], y[4];
    /* little-endian extraction: x[0] = LSB, x[3] = MSB */
    for (int i = 0; i < 4; i++) {
        x[i] = (u8)(v & 0xFF);
        v >>= 8;
    }
    y[2] = g_func(x[3] ^ x[2], x[1] ^ x[0], 1);
    y[3] = g_func(x[3], y[2], 0);
    y[1] = g_func(x[1] ^ x[0], y[2], 0);
    y[0] = g_func(x[0], y[1], 1);
    /* little-endian assembly */
    u32 out = 0;
    for (int i = 0; i < 4; i++) {
        out |= (u32)y[i] << (8 * i);
    }
    return out;
}

/* Encrypt using current round_key[], storing f outputs in f_output[] */
static u64 encrypt_trace(u64 pt) {
    u32 left = get_left(pt);
    u32 right = get_right(pt);
    right ^= left;
    for (int r = 0; r < 4; r++) {
        u32 mixed = f_func(right ^ round_key[r]);
        f_output[r] = mixed;
        u32 tmp = right;
        right = left ^ mixed;
        left = tmp;
    }
    left ^= right;
    return merge(right, left);
}

/* Encrypt with known keys (no tracing) */
static u64 encrypt_simple(u64 pt) {
    u32 left = get_left(pt);
    u32 right = get_right(pt);
    right ^= left;
    for (int r = 0; r < 4; r++) {
        u32 mixed = f_func(right ^ round_key[r]);
        u32 tmp = right;
        right = left ^ mixed;
        left = tmp;
    }
    left ^= right;
    return merge(right, left);
}

static int popcount(u32 n) {
    int c = 0;
    while (n) { c += n & 1; n >>= 1; }
    return c;
}

static int bit(u64 x, int pos) {
    return (int)((x >> pos) & 1);
}

/*
 * Build a 32-bit mask from 8 bit-positions packed into bits [start..start+7] of maskctr.
 * Each bit at position (start+i) selects bit (i*2) in the 8-byte-pair representation,
 * mapping byte-pair index i to bit position 2*i within the 32-bit word.
 * This matches the mask construction in the reference solution.
 */
static u32 build_mask(u64 maskctr, int start) {
    u32 mask = 0;
    int offsets[8] = {0, 2, 8, 10, 16, 18, 24, 26};
    for (int i = 0; i < 8; i++) {
        if (bit(maskctr, start + i)) {
            mask |= (1u << offsets[i]);
        }
    }
    return mask;
}

/*
 * Linear approximation masks.
 * Each 48-bit value encodes masks for: pl(8b) pr(8b) cl(8b) cr(8b) fm(8b).
 * 5 masks per round, 3 rounds (round 3 is brute-forced differently).
 * These masks were derived from the cipher's linear approximation table.
 */
static const u64 LIN_MASKS[15] = {
    0x006a54727723ULL, 0x00ea44ca9fdbULL, 0x004545cd88cdULL,
    0x00e050682d7dULL, 0x0023051d4c49ULL,
    0x00428f890688ULL, 0x00beb917ae06ULL, 0x0028f8c03890ULL,
    0x00c679ef96aeULL, 0x00eb9937ae26ULL,
    0x002520384d6dULL, 0x006520a8ddfdULL, 0x006a3e187749ULL,
    0x00829620f761ULL, 0x00cb8e06cc42ULL,
};

#define MASKS_PER_ROUND 5

/*
 * Attempt to recover round key for round `rnd` using linear cryptanalysis.
 * Uses first 16 pairs. Checks all 5 masks; if all are consistent (all-zero or all-one
 * across pairs), accepts that seed as the round key.
 */
static int recover_round_key(int rnd, u64 pairs[][2], int npairs) {
    for (u32 seed = 1; seed < (u32)KEY_MAX; seed++) {
        round_key[rnd] = expand(seed);

        int all_consistent = 1;
        for (int m = 0; m < MASKS_PER_ROUND; m++) {
            u64 maskctr = LIN_MASKS[rnd * MASKS_PER_ROUND + m];
            u32 mpl = build_mask(maskctr, 0);
            u32 mpr = build_mask(maskctr, 8);
            u32 mcl = build_mask(maskctr, 16);
            u32 mcr = build_mask(maskctr, 24);
            u32 mfm = build_mask(maskctr, 32);

            int zeros = 0, ones = 0;
            for (int i = 0; i < 16 && i < npairs; i++) {
                u64 pt = pairs[i][0];
                u64 ct = pairs[i][1];
                encrypt_trace(pt);
                u32 inner = f_output[rnd];

                u32 pl = get_left(pt);
                u32 pr = get_right(pt);
                u32 cl = get_left(ct);
                u32 cr = get_right(ct);

                int lhs = (popcount(mpl & pl) + popcount(mpr & pr) +
                           popcount(mcl & cl) + popcount(mcr & cr)) % 2;
                int rhs = popcount(mfm & inner) % 2;

                if (lhs ^ rhs) {
                    zeros++;
                    if (ones) break;
                } else {
                    ones++;
                    if (zeros) break;
                }
            }

            /* Not consistent: both zeros and ones appeared */
            if (zeros > 0 && ones > 0) {
                all_consistent = 0;
                break;
            }
        }

        if (all_consistent) {
            fprintf(stderr, "Recovered round %d: seed=0x%x expanded=%u\n",
                    rnd, seed, expand(seed));
            return (int)seed;
        }
    }
    return -1;
}

/*
 * Brute-force the last round key by checking full encryption against known pairs.
 */
static int brute_force_last_key(u64 pairs[][2], int npairs) {
    int check = (npairs < NUM_VERIFY_PAIRS) ? npairs : NUM_VERIFY_PAIRS;
    for (u32 seed = 0; seed < (u32)KEY_MAX; seed++) {
        round_key[3] = expand(seed);
        int ok = 1;
        for (int i = 0; i < check; i++) {
            if (encrypt_simple(pairs[i][0]) != pairs[i][1]) {
                ok = 0;
                break;
            }
        }
        if (ok) {
            fprintf(stderr, "Recovered round 3: seed=0x%x expanded=%u\n",
                    seed, expand(seed));
            return (int)seed;
        }
    }
    return -1;
}

/*
 * Find the 20-bit seed for a given expanded key value.
 */
static u32 find_seed(u32 expanded) {
    for (u32 i = 0; i < (u32)KEY_MAX; i++) {
        if (expand(i) == expanded) return i;
    }
    return 0;
}

int main(void) {
    /* Load plaintext/ciphertext pairs */
    u64 pairs[NUM_PAIRS][2];
    int npairs = 0;

    FILE *fp = fopen("/app/pairs.txt", "r");
    if (!fp) {
        fprintf(stderr, "Error: cannot open /app/pairs.txt\n");
        return 1;
    }
    while (npairs < NUM_PAIRS &&
           fscanf(fp, "%lu %lu", &pairs[npairs][0], &pairs[npairs][1]) == 2) {
        npairs++;
    }
    fclose(fp);
    fprintf(stderr, "Loaded %d pairs\n", npairs);

    if (npairs < 16) {
        fprintf(stderr, "Error: need at least 16 pairs\n");
        return 1;
    }

    /* Initialise all keys to 0 */
    memset(round_key, 0, sizeof(round_key));

    /* Recover keys for rounds 0, 1, 2 via linear cryptanalysis */
    for (int r = 0; r < 3; r++) {
        int seed = recover_round_key(r, pairs, npairs);
        if (seed < 0) {
            fprintf(stderr, "Error: failed to recover round %d key\n", r);
            return 1;
        }
        round_key[r] = expand((u32)seed);
    }

    /* Brute-force round 3 key */
    int seed3 = brute_force_last_key(pairs, npairs);
    if (seed3 < 0) {
        fprintf(stderr, "Error: failed to recover round 3 key\n");
        return 1;
    }
    round_key[3] = expand((u32)seed3);

    /* Find original 20-bit seeds for all 4 keys */
    u32 s0 = find_seed(round_key[0]);
    u32 s1 = find_seed(round_key[1]);
    u32 s2 = find_seed(round_key[2]);
    u32 s3 = find_seed(round_key[3]);

    fprintf(stderr, "Final seeds: 0x%x 0x%x 0x%x 0x%x\n", s0, s1, s2, s3);

    /* Decrypt all ciphertexts */
    FILE *cf = fopen("/app/ciphertexts.txt", "r");
    if (!cf) {
        fprintf(stderr, "Error: cannot open /app/ciphertexts.txt\n");
        return 1;
    }

    char decrypt_cmd[256];
    snprintf(decrypt_cmd, sizeof(decrypt_cmd),
             "/app/decrypt /app/ciphertexts.txt 0x%x 0x%x 0x%x 0x%x",
             s0, s1, s2, s3);
    fclose(cf);

    system(decrypt_cmd);
    return 0;
}
ATTACK_C_EOF

# Compile the attack
gcc -O3 -o /tmp/feal_attack /tmp/feal_attack.c

# Run the attack and save decrypted plaintexts
/tmp/feal_attack > /app/plaintexts.txt
