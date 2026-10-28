import hashlib
import importlib.util
import json
import tarfile
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pack = load("pack", "package.py")
pin = load("pin", "source-pin.py")


class Release(unittest.TestCase):
    def test_archives_satisfy_node_extractor_contract(self):
        for target, triple in [("darwin-arm64", "aarch64-apple-darwin"), ("linux-x64", "x86_64-unknown-linux-musl")]:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                source = directory / "sea"
                source.write_bytes(b"fake executable\x00\xff")
                archive = pack.package(source, directory / "out", target)
                self.assertEqual(archive.name, f"zcode-{triple}.tar.gz")
                with tarfile.open(archive, "r:gz") as tar:
                    member, = tar.getmembers()
                    self.assertEqual(member.name, archive.name.removesuffix(".tar.gz"))
                    self.assertEqual(member.mode, 0o755)
                    self.assertEqual(tar.extractfile(member).read(), source.read_bytes())
                checksum = archive.with_name(archive.name + ".sha256").read_text().split()[0]
                self.assertEqual(checksum, hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_moving_and_missing_source_refs_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pin.json"
            for commit in [None, "main", "3c5b227", "x" * 40]:
                path.write_text(json.dumps({"repository": "zai-org/ZCode", "commit": commit}))
                with self.assertRaises(ValueError):
                    pin.source_pin(path)
        self.assertEqual(pin.source_pin(ROOT / "upstream.json"), "3c5b227649371507ddc4eb46ac5133afe6db1cab")

    def test_manifest_keeps_resume_mcp_and_home_contract(self):
        client = tomllib.loads((ROOT / "extension.toml").read_text())["client"]
        self.assertEqual(client["protocol"], "zcode-stream")
        self.assertEqual(client["home_env"], "HOME")
        self.assertEqual(client["install"]["repo"], "pointman-ai/pointman-zcode")
        self.assertEqual(client["run"]["resume"], ["--resume", "{value}"])
        self.assertEqual(client["mcp"]["settings"], {"features": {"mcp": True}})
        self.assertEqual(client["mcp"]["key"], "mcp.servers")
        self.assertEqual(client["instructions"]["file"], ".zcode/AGENTS.md")
        self.assertNotIn("model", client["run"])


if __name__ == "__main__":
    unittest.main()
