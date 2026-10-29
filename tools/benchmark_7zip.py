#!/usr/bin/env python3
"""Compare the project codec with an installed 7-Zip binary on the master text.

Development benchmark only. External executables are not used by decompress.py.
Run: python tools/benchmark_7zip.py --sevenzip /path/to/7zz
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import py_compile
import resource
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compress import encode_bytes


def child_run(command, directory):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = perf_counter()
    result = subprocess.run(command, cwd=directory, capture_output=True, timeout=1200)
    elapsed = perf_counter() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace") + result.stdout[:2000].decode(errors="replace"))
    return result.stdout, {"wall_seconds": elapsed,
                           "user_seconds": after.ru_utime - before.ru_utime,
                           "system_seconds": after.ru_stime - before.ru_stime}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sevenzip", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/sevenzip_results.json")
    args = parser.parse_args()
    executable = shutil.which(args.sevenzip)
    if executable is None:
        raise SystemExit("7-Zip executable not found")
    executable = str(Path(executable).resolve())
    raw = (ROOT / "austen.txt").read_bytes()
    digest = hashlib.md5(raw).hexdigest()
    if digest != "967205af325fc85e5783b6847eaf8dba":
        raise SystemExit("Input does not match the master MD5 in project.pdf")
    info = subprocess.run([executable, "i"], capture_output=True, check=True).stdout.decode()
    version = next(line.strip() for line in info.splitlines() if line.startswith("7-Zip"))
    report = {"sevenzip_version": version, "python": sys.version,
              "platform": platform.platform(), "source_bytes": len(raw),
              "source_md5": digest,
              "comparison_note": "7-Zip sizes include the 7z container but exclude the native decoder executable. The project's scored size includes its .pyc decoder.",
              "sevenzip_trials": []}
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        (folder / "austen.txt").write_bytes(raw)
        variants = [("LZMA2-normal", ["-mx=5", "-m0=LZMA2"]),
                    ("LZMA2-ultra-64MiB", ["-mx=9", "-m0=LZMA2", "-md=64m"])]
        variants += [(f"PPMd-order-{order}-64MiB", ["-mx=9", f"-m0=PPMd:mem=64m:o={order}"])
                     for order in (4, 5, 6, 7, 8, 10, 12)]
        for name, settings in variants:
            filename = name + ".7z"
            command = [executable, "a", "-t7z", "-mmt=1", "-bd", "-bso0",
                       "-mtm=off", "-mtc=off", "-mta=off"] + settings + [filename, "austen.txt"]
            _, encode = child_run(command, folder)
            restored, decode = child_run([executable, "x", "-so", "-bd", "-bso0", filename], folder)
            if restored != raw:
                raise AssertionError("7-Zip round trip failed: " + name)
            listing = subprocess.run([executable, "l", "-slt", filename], cwd=folder,
                                     capture_output=True, check=True).stdout.decode()
            methods = sorted(set(line for line in listing.splitlines() if line.startswith("Method = ")))
            size = (folder / filename).stat().st_size
            row = {"name": name, "settings": settings, "methods": methods,
                   "archive_bytes": size, "encode": encode, "decode": decode,
                   "round_trip": True, "decoded_md5": hashlib.md5(restored).hexdigest()}
            report["sevenzip_trials"].append(row)
            print(f"{name}: {size:,} bytes; encode user {encode['user_seconds']:.3f}s; "
                  f"decode user {decode['user_seconds']:.3f}s; verified", flush=True)

        start = perf_counter()
        before = resource.getrusage(resource.RUSAGE_SELF)
        packed = encode_bytes(raw, order=5)
        after = resource.getrusage(resource.RUSAGE_SELF)
        encode = {"wall_seconds": perf_counter() - start,
                  "user_seconds": after.ru_utime - before.ru_utime,
                  "system_seconds": after.ru_stime - before.ru_stime}
        if packed != (ROOT / "compressed").read_bytes():
            raise AssertionError("Project bitstream differs from the committed artifact")
        # Test the project decoder in isolation from the original and the encoder.
        isolated = folder / "project"
        isolated.mkdir()
        shutil.copyfile(ROOT / "decompress.py", isolated / "decompress.py")
        (isolated / "compressed").write_bytes(packed)
        _, decode = child_run([sys.executable, "-I", "-S", "-B", "decompress.py"], isolated)
        if (isolated / "out.txt").read_bytes() != raw:
            raise AssertionError("Isolated project decoder failed")
        pyc = folder / "decompress.pyc"
        py_compile.compile(str(ROOT / "decompress.py"), cfile=str(pyc),
                           dfile="decompress.py", doraise=True)
        report["project"] = {"data_bytes": len(packed), "decoder_pyc_bytes": pyc.stat().st_size,
                             "scored_bytes": len(packed) + pyc.stat().st_size,
                             "encode": encode, "decode": decode,
                             "round_trip": True, "decoded_md5": digest}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["project"], indent=2))
    print("Results saved to", args.output)


if __name__ == "__main__":
    main()
