#!/usr/bin/env python3
"""Verify the full deliverable in isolation and record the PDF's scoring metric.

Development tool only; none of these imports is required by decompress.py.
"""
import argparse
import ast
import bz2
import gzip
import hashlib
import json
import lzma
from pathlib import Path
import platform
import py_compile
import resource
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter

from compress import encode_bytes

ROOT = Path(__file__).resolve().parent
MASTER_MD5 = "967205af325fc85e5783b6847eaf8dba"


def reference_size(raw):
    tree = ast.parse((ROOT / "reference/compress.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "prefices_tuple" for t in node.targets):
            phrases = [word.encode("ascii") for word in ast.literal_eval(node.value)]
            break
    first = {}
    for phrase in phrases:
        first.setdefault(phrase[0], []).append(phrase)
    position, tokens, tail_start = 0, 0, 0
    while position < len(raw):
        if tokens % 4 == 0:
            tail_start = position
        for phrase in first.get(raw[position], ()):
            if raw.startswith(phrase, position):
                position += len(phrase)
                tokens += 1
                break
        else:
            raise ValueError("reference alphabet does not cover input")
    lost = raw[tail_start:] if tokens % 4 else b""
    return {"data_bytes": tokens // 4 * 3, "tokens": tokens,
            "discarded_tail_bytes": len(lost),
            "discarded_tail_hex": lost.hex(),
            "method": "same greedy phrase choices; offset scan avoids quadratic slicing"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", nargs="*", type=int, choices=range(1, 9), default=[])
    parser.add_argument("--output", type=Path, default=ROOT / "docs/benchmark_results.json")
    args = parser.parse_args()
    raw = (ROOT / "austen.txt").read_bytes()
    digest = hashlib.md5(raw).hexdigest()
    if digest != MASTER_MD5:
        raise SystemExit(f"austen.txt does not match PDF's master MD5: {digest}")
    packed = (ROOT / "compressed").read_bytes()
    result = {"python": sys.version, "platform": platform.platform(),
              "source_bytes": len(raw), "source_md5": digest,
              "compressed_bytes": len(packed),
              "compressed_sha256": hashlib.sha256(packed).hexdigest(),
              "reference_format": reference_size(raw)}

    # Compile under the basename used in the PDF. co_filename affects .pyc size.
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        shutil.copyfile(ROOT / "decompress.py", folder / "decompress.py")
        (folder / "compressed").write_bytes(packed)
        # Only these two files are provided to the decoder, with site imports and
        # user search paths disabled. There is no source text or project module.
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = perf_counter()
        decoded = subprocess.run([sys.executable, "-I", "-S", "-B", "decompress.py"],
                                 cwd=folder, capture_output=True, timeout=1200)
        wall = perf_counter() - start
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        if decoded.returncode:
            raise RuntimeError(decoded.stderr.decode())
        restored = (folder / "out.txt").read_bytes()
        if restored != raw:
            raise AssertionError("standalone decoder did not reproduce the master")
        result.update({"isolated_round_trip": True,
                       "decoded_md5": hashlib.md5(restored).hexdigest(),
                       "decode_wall_seconds": wall,
                       "decode_user_seconds": after.ru_utime - before.ru_utime,
                       "decode_system_seconds": after.ru_stime - before.ru_stime,
                       "decode_peak_rss_kib_linux": after.ru_maxrss})

    # py_compile is used only by this development tool, never by the decoder.
    # dfile fixes the filename stored inside bytecode to the PDF's command.
    with tempfile.TemporaryDirectory() as directory:
        pyc = Path(directory) / "decompress.pyc"
        py_compile.compile(str(ROOT / "decompress.py"), cfile=str(pyc),
                           dfile="decompress.py", doraise=True)
        result["decoder_pyc_bytes"] = pyc.stat().st_size
    total = len(packed) + result["decoder_pyc_bytes"]
    result.update({"scored_bytes": total, "scored_bits_per_character": total * 8 / len(raw),
                   "scored_ratio": total / len(raw),
                   "data_bits_per_character": len(packed) * 8 / len(raw)})
    result["baselines"] = {}
    codecs = [("gzip-9", lambda d: gzip.compress(d, compresslevel=9, mtime=0), gzip.decompress),
              ("bzip2-9", lambda d: bz2.compress(d, compresslevel=9), bz2.decompress),
              ("xz-9", lambda d: lzma.compress(d, preset=9), lzma.decompress)]
    for name, encode, decode in codecs:
        start = perf_counter()
        data = encode(raw)
        elapsed = perf_counter() - start
        assert decode(data) == raw
        result["baselines"][name] = {"data_bytes": len(data), "encode_wall_seconds": elapsed,
                                      "round_trip": True,
                                      "scored_reduction_vs_data_only": 1 - total / len(data)}
    result["order_experiments"] = []
    for order in args.orders:
        start = perf_counter()
        trial = encode_bytes(raw, order)
        elapsed = perf_counter() - start
        result["order_experiments"].append({"order": order, "data_bytes": len(trial),
                                             "encode_wall_seconds": elapsed})
        print(f"order {order}: {len(trial):,} bytes; {elapsed:.3f} s", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
