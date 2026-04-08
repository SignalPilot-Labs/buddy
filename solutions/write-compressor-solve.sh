#!/bin/bash
set -e

cat <<'PYTHON_EOF' > /tmp/compress.py
#!/usr/bin/env python3
"""
Compressor for decomp.c's range coder.
Two-pass approach: backward pass finds valid fraction intervals,
forward pass chooses bytes satisfying those constraints.
"""
import sys
import math

RADIX = 255
OFF1 = 5
OFF2 = 2
LITSIZE = 4


class Encoder:
    def __init__(self):
        self.bits_and_contexts = []

    def encode_bit(self, bit, ctx):
        self.bits_and_contexts.append((bit, ctx))

    def encode_integer(self, n, tmp_init, ctx_orig):
        ctx = ctx_orig * 99
        subtract_it = 1 << tmp_init
        result_ans = n + subtract_it
        num_data_bits = result_ans.bit_length() - 1
        extra_zeros = num_data_bits - tmp_init
        tmp = tmp_init
        for _ in range(extra_zeros):
            tmp += 1
            self.encode_bit(0, tmp + ctx)
        tmp += 1
        self.encode_bit(1, tmp + ctx)
        tmp -= 1
        for i in range(tmp - 1, -1, -1):
            b = (result_ans >> i) & 1
            self.encode_bit(b, ctx)

    def finalize(self):
        return _encode_bits(self.bits_and_contexts)


def _simulate_ranges(bits_and_contexts):
    range_ = 1
    counts = [[0, 0] for _ in range(100000)]
    info = []
    for bit, ctx in bits_and_contexts:
        needs_expand = range_ < RADIX
        if needs_expand:
            range_ *= RADIX
        c = counts[ctx]
        total = c[0] + c[1] + 2
        split = range_ * (c[0] + 1) // total
        range_after_bit = (range_ - split) if bit else split
        info.append((needs_expand, range_, split, range_after_bit))
        range_ = range_after_bit
        c[bit] += 1
    return info


def _backward_pass(bits_and_contexts, info):
    n = len(bits_and_contexts)
    post_exp = [(0, 0)] * n
    pre_lo = 0
    pre_hi = info[n - 1][3] - 1
    for i in range(n - 1, -1, -1):
        bit, _ctx = bits_and_contexts[i]
        needs_expand, range_after_expand, split, _range_after_bit = info[i]
        if bit == 0:
            post_lo = pre_lo
            post_hi = min(pre_hi, split - 1)
        else:
            post_lo = max(pre_lo + split, split)
            post_hi = min(pre_hi + split, range_after_expand - 1)
        post_exp[i] = (post_lo, post_hi)
        if needs_expand:
            lo_before = max(0, math.ceil((post_lo - (RADIX - 1)) / RADIX))
            hi_before = post_hi // RADIX
            pre_lo = lo_before
            pre_hi = hi_before
        else:
            pre_lo = post_lo
            pre_hi = post_hi
    return post_exp


def _forward_pass(bits_and_contexts, info, post_exp):
    counts = [[0, 0] for _ in range(100000)]
    fraction = 0
    range_ = 1
    output = []
    for i, (bit, ctx) in enumerate(bits_and_contexts):
        needs_expand, range_after_expand, split, _range_after_bit = info[i]
        post_lo, post_hi = post_exp[i]
        if needs_expand:
            lo_b = max(0, post_lo - fraction * RADIX)
            hi_b = min(RADIX - 1, post_hi - fraction * RADIX)
            b_raw = (lo_b + hi_b) // 2
            output.append(b_raw + 1)
            fraction = fraction * RADIX + b_raw
            range_ = range_after_expand
        if bit == 0:
            range_ = split
        else:
            fraction -= split
            range_ -= split
        counts[ctx][bit] += 1
    output += [1] * 8
    return output


def _encode_bits(bits_and_contexts):
    info = _simulate_ranges(bits_and_contexts)
    post_exp = _backward_pass(bits_and_contexts, info)
    output = _forward_pass(bits_and_contexts, info, post_exp)
    return bytes(output)


def find_best_match(pos, chars, n):
    best_off = 0
    best_len = 0
    for off in range(1, min(pos + 1, 8000) + 1):
        ref = pos - off
        mlen = 0
        while mlen < 250 and pos + mlen < n and chars[ref + mlen] == chars[pos + mlen]:
            mlen += 1
        if mlen > best_len:
            best_len = mlen
            best_off = off
            if mlen >= 100:
                break
    return best_off, best_len


def tokenize(data):
    n = len(data)
    chars = list(data)
    tokens = []
    pos = 0
    while pos < n:
        best_off, best_len = find_best_match(pos, chars, n)
        if best_len >= 2:
            tokens.append(('match', best_off - 1, best_len - 1))
            pos += best_len
        else:
            tokens.append(('lit', chars[pos]))
            pos += 1
    return tokens


def compress(data):
    tokens = tokenize(data)
    enc = Encoder()
    enc.encode_integer(len(tokens), 9, 0)
    for tok in tokens:
        if tok[0] == 'match':
            off_val, len_val = tok[1], tok[2]
            enc.encode_bit(1, 1)
            enc.encode_integer(off_val, OFF1, 2)
            enc.encode_integer(len_val, OFF2, 3)
        else:
            val = tok[1]
            enc.encode_bit(0, 1)
            sign = 1 if val < 0 else 0
            enc.encode_bit(sign, 8)
            enc.encode_integer(abs(val), LITSIZE, 9)
    return enc.finalize()


with open('/app/data.txt', 'rb') as f:
    data = f.read()

compressed = compress(data)

with open('/app/data.comp', 'wb') as f:
    f.write(compressed)

print(f"Compressed {len(data)} bytes to {len(compressed)} bytes", file=sys.stderr)
PYTHON_EOF

python3 /tmp/compress.py

SIZE=$(wc -c < /app/data.comp)
echo "Compressed file size: $SIZE bytes"

if [ "$SIZE" -gt 2500 ]; then
    echo "ERROR: compressed file too large ($SIZE > 2500 bytes)"
    exit 1
fi

echo "Done. data.comp is ready."
