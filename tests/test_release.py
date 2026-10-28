import hashlib
import importlib.util
import json
import re
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
                upstream = directory / "upstream"
                upstream.mkdir()
                for name in pack.NOTICES:
                    (upstream / name).write_bytes(f"original {name}\n".encode())
                archive = pack.package(source, directory / "out", target, upstream)
                self.assertEqual(archive.name, f"zcode-{target}.tar.gz")
                with tarfile.open(archive, "r:gz") as tar:
                    # The node selects the first regular file with this basename.
                    member, = [m for m in tar.getmembers() if m.isfile() and Path(m.name).name == f"zcode-{target}"]
                    self.assertEqual(member.name, archive.name.removesuffix(".tar.gz"))
                    self.assertEqual(member.mode, 0o755)
                    self.assertEqual(tar.extractfile(member).read(), source.read_bytes())
                    self.assertEqual(sum(m.mode & 0o111 != 0 for m in tar.getmembers()), 1)
                    for name in pack.NOTICES:
                        notice = tar.getmember(f"licenses/zcode/{name}")
                        self.assertEqual(notice.mode, 0o644)
                        self.assertEqual(tar.extractfile(notice).read(), (upstream / name).read_bytes())
                    self.assertEqual(tar.extractfile("licenses/pointman-zcode/LICENSE").read(), (ROOT / "LICENSE").read_bytes())
                    self.assertEqual(tar.extractfile("upstream.json").read(), (ROOT / "upstream.json").read_bytes())
                checksum = archive.with_name(archive.name + ".sha256").read_text().split()[0]
                self.assertEqual(checksum, hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_missing_or_empty_notices_prevent_packaging(self):
        for missing in pack.NOTICES:
            for empty in [False, True]:
                with self.subTest(missing=missing, empty=empty), tempfile.TemporaryDirectory() as temp:
                    directory = Path(temp)
                    (directory / "sea").write_bytes(b"fake executable")
                    for name in pack.NOTICES:
                        if name != missing or empty:
                            (directory / name).write_text("" if name == missing else name)
                    with self.assertRaises((FileNotFoundError, ValueError)):
                        pack.package(directory / "sea", directory / "out", "linux-x64", directory)
                    self.assertFalse((directory / "out").exists())

    def test_vault_form_and_provider_contract(self):
        manifest = tomllib.loads((ROOT / "extension.toml").read_text())
        self.assertNotIn("run", manifest, "a credential form needs no process")
        self.assertEqual(manifest["permissions"]["secrets"], ["zcode.key"])
        credential, = manifest["credentials"]
        command, = manifest["commands"]
        self.assertEqual((command["kind"], command["slash"], command["form"]), ("zcode.add", "add", credential["id"]))
        self.assertEqual(credential["item"], "zcode.key")
        self.assertTrue(re.fullmatch(credential["value"], "offline.fake-key"))
        for invalid in ["", " ", "line\nbreak"]:
            self.assertIsNone(re.fullmatch(credential["value"], invalid))
        key = manifest["client"]["key"]
        self.assertEqual(key["secret"], credential["item"])
        self.assertEqual(key["file"], ".zcode/v2/pointman-provider.json")
        self.assertEqual(key["env_file"], "ZCODE_PERSONAL_PROVIDER_CONFIG_FILE")
        self.assertNotEqual("{home}/" + key["file"], manifest["client"]["run"]["env"][key["env_file"]])
        settings = key["settings"]
        self.assertEqual(settings["schemaVersion"], 1)
        provider, = settings["config"]["providerConfigRules"]["providerRules"]
        self.assertEqual(provider["templateId"], "zai-api")
        self.assertFalse(provider["providerId"].startswith("account:"))
        self.assertEqual(provider["config"]["access"]["type"], "zhipu-coding-plan-api-key")
        self.assertEqual(provider["config"]["api"], {"type": "anthropic-messages", "baseUrl": "https://api.z.ai/api/anthropic"})
        self.assertEqual(settings["config"]["defaultModelSelection"], {"providerId": provider["providerId"], "modelId": "GLM-5.3"})
        # Exercise the pointer with its array index; it must address only the key.
        parts = key["path"].split("/")[1:]
        node = settings
        for part in parts[:-1]:
            node = node[int(part)] if isinstance(node, list) else node[part]
        self.assertEqual(node[parts[-1]], "")
        node[parts[-1]] = "offline.fake-key"
        self.assertEqual(provider["config"]["access"]["apiKey"], "offline.fake-key")

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
