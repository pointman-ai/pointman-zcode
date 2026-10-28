#!/usr/bin/env python3
"""Package the SEA with the basename required by Pointman's release installer."""
import argparse
import hashlib
import io
import tarfile
from pathlib import Path

# These archive names implement the current Pointman installer ABI. Linux's ABI
# name says musl, but the enclosed official Node SEA is glibc; see README.
TRIPLES = {"darwin-arm64": "aarch64-apple-darwin", "linux-x64": "x86_64-unknown-linux-musl"}


def package(source, output, target):
    source, output = Path(source), Path(output)
    name = f"zcode-{TRIPLES[target]}"
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{name}.tar.gz"
    data = source.read_bytes()
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo(name)
        info.mode = 0o755
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target", choices=TRIPLES, required=True)
    args = parser.parse_args()
    print(package(args.source, args.output, args.target))
