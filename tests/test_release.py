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
        for target in ["darwin-arm64", "linux-x64"]:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                source = directory / "sea"
                source.write_bytes(b"fake executable\x00\xff")
                archive = pack.package(source, directory / "out", target)
                self.assertEqual(archive.name, f"zcode-{target}.tar.gz")
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

    def test_environment_isolates_paths_and_covers_database_alias(self):
        env = tomllib.loads((ROOT / "extension.toml").read_text())["client"]["run"]["env"]
        self.assertEqual(env, {
            "HOME": "{home}", "USERPROFILE": "{home}", "ZCODE_DATA_BASE_DIR": "{home}",
            "ZCODE_STORAGE_DIR": "{home}/.zcode",
            "ZCODE_SESSION_DB_PATH": "{home}/.zcode/cli/db/db.sqlite",
            "ZCODE_SESSION_DB": "{home}/.zcode/cli/db/db.sqlite",
            "ZCODE_PERSONAL_PROVIDER_CONFIG_FILE": "{home}/.zcode/v2/provider_config.json",
            "ZCODE_LOG_DIR": "{home}/.zcode/cli/log",
            "ZCODE_BUILTIN_PROVIDER_CONFIG_FILE": "",
            "ZCODE_BUILTIN_PROVIDER_BUNDLED_CONFIG_FILE": "",
            "ZCODE_BFS_BINARY": "", "ZCODE_RG_BINARY": "", "ZCODE_UGREP_BINARY": "",
        })
        # Contract fixture: apply the node's documented replacement/overwrite semantics
        # to two agents in the presence of every hostile inherited key. The parent
        # owns the integration test of its actual command environment construction.
        for home in ["/state/agents/one/home", "/state/agents/two/home with spaces"]:
            inherited = {key: "/personal/hostile" for key in env}
            inherited.update({key: value.replace("{home}", home) for key, value in env.items()})
            for key, value in inherited.items():
                self.assertTrue(value == "" or value == home or value.startswith(home + "/"), key)
            self.assertEqual(inherited["ZCODE_SESSION_DB"], inherited["ZCODE_SESSION_DB_PATH"])

    def test_manifest_keeps_resume_mcp_and_home_contract(self):
        manifest = tomllib.loads((ROOT / "extension.toml").read_text())
        self.assertEqual(manifest["extension"]["node"], ">=0.4.2")
        client = manifest["client"]
        self.assertEqual(client["protocol"], "zcode-stream")
        self.assertEqual(client["home_env"], "HOME")
        self.assertEqual(client["install"]["repo"], "pointman-ai/pointman-zcode")
        self.assertEqual(client["install"]["asset"], "zcode-{platform}.tar.gz")
        self.assertEqual(client["run"]["resume"], ["--resume", "{value}"])
        self.assertEqual(client["mcp"]["settings"], {"features": {"mcp": True}})
        self.assertEqual(client["mcp"]["key"], "mcp.servers")
        self.assertEqual(client["instructions"]["file"], ".zcode/AGENTS.md")
        self.assertNotIn("model", client["run"])


if __name__ == "__main__":
    unittest.main()
