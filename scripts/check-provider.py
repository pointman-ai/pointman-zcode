#!/usr/bin/env python3
"""Check the manifest's provider settings with the pinned upstream codec offline.

Requires the upstream checkout and its frozen dependencies (as installed in CI).
Uses a fake key only. Does not log config or start ZCode.
"""
import argparse
import json
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(upstream):
    upstream = Path(upstream).resolve()
    manifest = tomllib.loads((ROOT / "extension.toml").read_text())
    key = manifest["client"]["key"]
    settings = key["settings"]
    node = settings
    parts = [part.replace("~1", "/").replace("~0", "~") for part in key["path"].split("/")[1:]]
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    node[parts[-1]] = "offline.fake-key"
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp) / "provider.json"
        fixture.write_text(json.dumps(settings))
        subprocess.run(["pnpm", "exec", "tsx", str(ROOT / "scripts/check-provider.mts"),
                        str(upstream), str(fixture)], cwd=upstream, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True)
    check(parser.parse_args().upstream)
