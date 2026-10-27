#!/usr/bin/env python3
# Standalone decoder: the course permits only struct and decimal imports.
import struct

MAGIC = b"APM1"
# magic, version, maximum context order, alphabet size, original size,
# range-coded payload size, Adler-32 of the original bytes
HEADER = struct.Struct("<4sBBHQII")


def checksum(data):
    a, b = 1, 0
    for symbol in data:
        a = (a + symbol) % 65521
        b = (b + a) % 65521
    return (b << 16) | a


class RangeDecoder:
    def __init__(self, data):
        if len(data) < 5 or data[0] != 0:
            raise ValueError("invalid range-coder initialization")
        self.data = data
        self.position = 5
        self.code = int.from_bytes(data[:5], "big")
        self.range = 0xffffffff

    def target(self, total):
        self.range //= total
        target = self.code // self.range
        if target >= total:
            raise ValueError("invalid arithmetic interval")
        return target

    def take(self, start, count):
        self.code -= start * self.range
        self.range *= count
        while self.range < (1 << 24):
            if self.position >= len(self.data):
                raise ValueError("truncated range-coded payload")
            self.range <<= 8
            self.code = (self.code << 8) | self.data[self.position]
            self.position += 1


def decode_bytes(blob):
    if len(blob) < HEADER.size:
        raise ValueError("truncated file header")
    magic, version, order, alphabet_size, length, size, expected = HEADER.unpack_from(blob)
    if magic != MAGIC or version != 1:
        raise ValueError("unsupported compressed format")
    if not 1 <= order <= 8 or alphabet_size > 256:
        raise ValueError("invalid model parameters")
    boundary = HEADER.size + alphabet_size
    if len(blob) != boundary + size:
        raise ValueError("compressed file length mismatch")
    alphabet = blob[HEADER.size:boundary]
    if alphabet != bytes(sorted(set(alphabet))) or bool(length) != bool(alphabet):
        raise ValueError("invalid alphabet")
    coder = RangeDecoder(blob[boundary:])
    models = {b"": dict.fromkeys(alphabet, 1)}
    estimators = {}
    history = b""
    singles = [bytes((s,)) for s in range(256)]
    bits = [1 << s for s in range(256)]
    output = bytearray()

    for _ in range(length):
        excluded = 0
        # Descend from the longest available suffix to the order-zero model.
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
                # Secondary escape estimation pools similar contexts. Store
                # [hit count, escape count]; the initial odds are PPM method D.
                n = len(eligible)
                bucket = (len(chain) - level - 1,
                          n if n < 8 else 8 + n.bit_length(),
                          (total // n).bit_length(), bool(excluded))
                prediction = estimators.setdefault(bucket, [total, n])
                hits, escapes = prediction
                escaped = coder.target(hits + escapes) >= hits
                coder.take(hits if escaped else 0, escapes if escaped else hits)
                prediction[1 if escaped else 0] += 1
                if sum(prediction) >= 1024:
                    prediction[:] = [(c + 1) >> 1 for c in prediction]
                if escaped:
                    for s, c in eligible:
                        excluded |= bits[s]
                    continue

            target = coder.target(total)
            cumulative = 0
            for symbol, count in eligible:
                if target < cumulative + count:
                    coder.take(cumulative, count)
                    break
                cumulative += count
            else:
                raise ValueError("symbol interval not found")
            break
        else:
            raise ValueError("all context models exhausted")

        # Update exclusion: update only models down to the one that succeeded.
        for context in chain[:level + 1]:
            context[symbol] = context.get(symbol, 0) + 1
            if context[symbol] >= 4096:
                for s, count in context.items():
                    context[s] = (count + 1) >> 1
        history = (history + singles[symbol])[-order:]
        output.append(symbol)

    if coder.position != len(coder.data) or coder.code != 0:
        raise ValueError("noncanonical range-coder termination")
    if checksum(output) != expected:
        raise ValueError("decoded content checksum mismatch")
    return bytes(output)


def main():
    with open("compressed", "rb") as source:
        restored = decode_bytes(source.read())
    # Write only after the stream has been decoded and verified in full.
    with open("out.txt", "wb") as destination:
        destination.write(restored)


if __name__ == "__main__":
    main()
