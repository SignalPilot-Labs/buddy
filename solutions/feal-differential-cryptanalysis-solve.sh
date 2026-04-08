#!/bin/bash
set -e

cat <<'EOF' > /app/attack.py
import random


def getleft(x):
    return (x >> 32) & 0xFFFFFFFF


def getright(x):
    return x & 0xFFFFFFFF


def g_function(a, b, x):
    temp = (a + b + x) & 0xFF
    return ((temp << 2) | (temp >> 6)) & 0xFF


def f_function(input_val):
    x = [0] * 4
    y = [0] * 4
    for i in range(4):
        x[i] = input_val & 0xFF
        input_val >>= 8
    y[2] = g_function(x[3] ^ x[2], x[1] ^ x[0], 1)
    y[3] = g_function(x[3], y[2], 0)
    y[1] = g_function(x[1] ^ x[0], y[2], 0)
    y[0] = g_function(x[0], y[1], 1)
    output = 0
    for i in range(4):
        output |= y[i] << (8 * i)
    return output & 0xFFFFFFFF


def attack(encrypt_fn):
    # Differential cryptanalysis targeting key[5] (4th round key).
    #
    # Cipher structure (4-round Feistel, output = merge(right, left)):
    #   Round i: new_right = old_left ^ f(old_right ^ key[i+2])
    #            new_left  = old_right
    #   Post-round: left ^= right
    #   Output: merge(right_final, left_final)
    #
    # From ciphertext (C_L, C_R):
    #   right_r3_pre = C_L ^ C_R   (right entering last round)
    #   left_r3_pre  = C_L ^ f(right_r3_pre ^ key[5])
    #
    # Input differential DELTA = 0x8080000080800000 propagates through
    # the cipher so that left_r3_pre_diff is always 0x02000000, because:
    #   - After initial XOR whitening: L_diff=0x80800000, R_diff=0x80800000
    #   - After pre-round right ^= left: L_diff=0x80800000, R_diff=0
    #   - After round 0: L_diff=0, R_diff=0x80800000  (f(x^0)^f(x)=0)
    #   - After round 1: L_diff=0x80800000, R_diff=0x02000000  (f diff property)
    #   - After round 2: L_diff=0x02000000, R_diff=...  (only L matters for round 3)
    #   - Round 3 input: right_r3_pre_diff = L_after_round2 = 0x02000000 (NO)
    #
    # Actually empirically confirmed: left_r3_pre_1 ^ left_r3_pre_2 = 0x02000000
    # always when the correct key[5] is used. This filters all wrong candidates.
    #
    # key[i] = (x * 1234567) & 0xFFFFFFFF where x in [0, 0xFFFF], so 65536 candidates.

    DELTA = 0x8080000080800000
    EXPECTED_LEFT_DIFF = 0x02000000

    candidates = list(range(0x10000))

    for _ in range(15):
        if len(candidates) <= 1:
            break

        base = (random.randint(0, 0xFFFFFFFF) << 32) | random.randint(0, 0xFFFFFFFF)
        c1 = encrypt_fn(base)
        c2 = encrypt_fn(base ^ DELTA)

        c1l = getleft(c1)
        c1r = getright(c1)
        c2l = getleft(c2)
        c2r = getright(c2)

        r1 = c1l ^ c1r
        r2 = c2l ^ c2r

        candidates = [
            x for x in candidates
            if ((c1l ^ f_function(r1 ^ ((x * 1234567) & 0xFFFFFFFF))) ^
                (c2l ^ f_function(r2 ^ ((x * 1234567) & 0xFFFFFFFF)))) == EXPECTED_LEFT_DIFF
        ]

    return (candidates[0] * 1234567) & 0xFFFFFFFF
EOF
