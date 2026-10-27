#!/usr/bin/env python3
"""Reproducible encoder for the standalone, course-compliant PPM decoder."""
import argparse
from pathlib import Path
from time import perf_counter

from decompress import HEADER, MAGIC, checksum, decode_bytes


class RangeEncoder:
    def __init__(self):
        self.low = 0
        self.range = 0xffffffff
        self.cache = 0
        self.cache_size = 1
        self.output = bytearray()

    def shift(self):
        # Delay 0xff bytes until a carry from the low interval is resolved.
        low = self.low
        if (low & 0xffffffff) < 0xff000000 or low >> 32:
            carry = low >> 32
            self.output.append((self.cache + carry) & 255)
            self.output.extend(bytes(((255 + carry) & 255,)) * (self.cache_size - 1))
            self.cache = (low >> 24) & 255
            self.cache_size = 0
        self.cache_size += 1
        self.low = (low & 0xffffff) << 8

    def put(self, start, count, total):
        self.range //= total
        self.low += start * self.range
        self.range *= count
        while self.range < (1 << 24):
            self.range <<= 8
            self.shift()

    def finish(self):
        for _ in range(5):
            self.shift()
        return bytes(self.output)


def encode_bytes(data, order=5):
    if not 1 <= order <= 8:
        raise ValueError("context order must be between 1 and 8")
    alphabet = bytes(sorted(set(data)))
    coder = RangeEncoder()
    models = {b"": dict.fromkeys(alphabet, 1)}
    estimators = {}
    history = b""
    singles = [bytes((s,)) for s in range(256)]
    bits = [1 << s for s in range(256)]

    for symbol in data:
        excluded = 0
        chain = [models.setdefault(history[j:], {}) for j in range(len(history) + 1)]
        for level, context in enumerate(chain):
            if not context:
                continue
            eligible = [(s, 2 * c - 1) for s, c in context.items()
                        if not excluded & bits[s]]
            if not eligible:
                continue
            total = sum(c for s, c in eligible)
            if level < len(chain) - 1:
                n = len(eligible)
                bucket = (len(chain) - level - 1,
                          n if n < 8 else 8 + n.bit_length(),
                          (total // n).bit_length(), bool(excluded))
                prediction = estimators.setdefault(bucket, [total, n])
                hits, escapes = prediction
                escaped = symbol not in context
                coder.put(hits if escaped else 0, escapes if escaped else hits, hits + escapes)
                prediction[1 if escaped else 0] += 1
                if sum(prediction) >= 1024:
                    prediction[:] = [(c + 1) >> 1 for c in prediction]
                if escaped:
                    for s, c in eligible:
                        excluded |= bits[s]
                    continue

            cumulative = 0
            for s, count in eligible:
                if s == symbol:
                    coder.put(cumulative, count, total)
                    break
                cumulative += count
            else:
                raise AssertionError("encoder model lost the input symbol")
            break
        else:
            raise AssertionError("encoder exhausted all context models")

        for context in chain[:level + 1]:
            context[symbol] = context.get(symbol, 0) + 1
            if context[symbol] >= 4096:
                for s, count in context.items():
                    context[s] = (count + 1) >> 1
        history = (history + singles[symbol])[-order:]

    payload = coder.finish()
    return HEADER.pack(MAGIC, 1, order, len(alphabet), len(data), len(payload), checksum(data)) + alphabet + payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", default="austen.txt", type=Path)
    parser.add_argument("destination", nargs="?", default="compressed", type=Path)
    parser.add_argument("--order", type=int, choices=range(1, 9), default=5)
    parser.add_argument("--verify", action="store_true", help="decode and compare before writing")
    args = parser.parse_args()
    if args.source.resolve() == args.destination.resolve():
        parser.error("source and destination must be different files")
    raw = args.source.read_bytes()
    start = perf_counter()
    packed = encode_bytes(raw, args.order)
    elapsed = perf_counter() - start
    if args.verify and decode_bytes(packed) != raw:
        raise AssertionError("round-trip verification failed")
    args.destination.write_bytes(packed)
    ratio = len(packed) / len(raw) if raw else 0
    print(f"{len(raw):,} -> {len(packed):,} bytes; {ratio:.2%}; encode {elapsed:.3f} s")


if __name__ == "__main__":
    main()
