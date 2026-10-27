import ast
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compress import encode_bytes
from decompress import HEADER, decode_bytes


class CodecTests(unittest.TestCase):
    def test_boundary_and_binary_inputs(self):
        # These expose the reference implementation's tail loss and restricted
        # alphabet, as well as accidental newline/Unicode transformations.
        cases = [b"", b"a", b"ab", b"abc", b"abcd", b"abcde",
                 b"no final newline", b"two final newlines\n\n",
                 b" \t\r\n\x00\xff", bytes(range(256)),
                 "中文、English 混合\r\n".encode()]
        for order in (1, 5, 8):
            for raw in cases:
                with self.subTest(order=order, raw=raw[:20]):
                    self.assertEqual(decode_bytes(encode_bytes(raw, order)), raw)

    def test_adaptation_and_count_rescaling(self):
        rng = random.Random(5620)
        # Long deterministic runs exercise both estimator and model rescaling.
        cases = [b"a" * 50000, b"abac" * 15000,
                 rng.randbytes(12000),
                 bytes(rng.randrange(8) for _ in range(15000))]
        for raw in cases:
            with self.subTest(size=len(raw)):
                self.assertEqual(decode_bytes(encode_bytes(raw)), raw)

    def test_deterministic_bitstream(self):
        raw = b"the same context and the same words\n" * 100
        self.assertEqual(encode_bytes(raw), encode_bytes(raw))

    def test_invalid_encoder_parameters(self):
        for order in (0, 9, -1):
            with self.assertRaises(ValueError):
                encode_bytes(b"example", order)

    def test_corrupt_files(self):
        raw = b"the text must survive exactly as it was\n" * 100
        blob = encode_bytes(raw)
        for cut in (0, 1, HEADER.size - 1, len(blob) - 1):
            with self.subTest(cut=cut), self.assertRaises(ValueError):
                decode_bytes(blob[:cut])
        mutations = [(0, 1), (4, 1), (5, 255), (6, 255),
                     (HEADER.size - 1, 1), (len(blob) // 2, 8),
                     (len(blob) - 1, 1)]
        for position, mask in mutations:
            damaged = bytearray(blob)
            damaged[position] ^= mask
            with self.subTest(position=position), self.assertRaises(ValueError):
                decode_bytes(damaged)
        with self.assertRaises(ValueError):
            decode_bytes(blob + b"extra")

    def test_only_permitted_imports(self):
        tree = ast.parse((ROOT / "decompress.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        self.assertEqual(imports, ["struct"])
        # Check that the standalone entry point has no hidden dynamic imports.
        forbidden = {"__import__", "eval", "exec", "compile"}
        self.assertFalse(any(isinstance(node, ast.Name) and node.id in forbidden
                             for node in ast.walk(tree)))

    def test_standalone_decoder_and_failed_write(self):
        raw = (b"only compressed and decompress.py are available\r\n" * 70)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            shutil.copyfile(ROOT / "decompress.py", folder / "decompress.py")
            packed = encode_bytes(raw)
            (folder / "compressed").write_bytes(packed)
            result = subprocess.run([sys.executable, "-I", "-S", "-B", "decompress.py"],
                                    cwd=folder, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual((folder / "out.txt").read_bytes(), raw)
            sentinel = b"previous valid output"
            (folder / "out.txt").write_bytes(sentinel)
            (folder / "compressed").write_bytes(packed[:-1])
            result = subprocess.run([sys.executable, "-I", "-S", "-B", "decompress.py"],
                                    cwd=folder, capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((folder / "out.txt").read_bytes(), sentinel)


if __name__ == "__main__":
    unittest.main()
