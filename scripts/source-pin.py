#!/usr/bin/env python3
"""Fail closed until a reviewed public, immutable source commit is available."""
import json
import re
from pathlib import Path


def source_pin(path):
    pin = json.loads(Path(path).read_text())
    if pin["repository"] != "zai-org/ZCode":
        raise ValueError("expected the official zai-org/ZCode repository")
    if not re.fullmatch(r"[0-9a-f]{40}", pin.get("commit") or ""):
        raise ValueError("upstream.json needs a verified full public commit SHA; main and short SHAs are refused")
    return pin["commit"]


if __name__ == "__main__":
    print(source_pin(Path(__file__).resolve().parents[1] / "upstream.json"))
