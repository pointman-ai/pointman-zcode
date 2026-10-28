#!/usr/bin/env python3
"""Package the SEA and required notices for Pointman's release installer."""
import argparse
import hashlib
import io
import tarfile
from pathlib import Path

# Use upstream platform names. The Linux SEA embeds glibc Node, not musl.
TARGETS = ("darwin-arm64", "linux-x64")
NOTICES = ("LICENSE", "NOTICE.md", "THIRD-PARTY-NOTICES.md")
ROOT = Path(__file__).resolve().parents[1]


def package(source, output, target, upstream):
    source, output = Path(source), Path(output)
    if target not in TARGETS:
        raise ValueError(f"unsupported target: {target}")
    # Read everything before creating an archive: missing notices fail the build.
    notices = {f"licenses/zcode/{name}": (Path(upstream) / name).read_bytes() for name in NOTICES}
    if any(not data.strip() for data in notices.values()):
        raise ValueError("upstream license notices must not be empty")
    notices["licenses/pointman-zcode/LICENSE"] = (ROOT / "LICENSE").read_bytes()
    notices["upstream.json"] = (ROOT / "upstream.json").read_bytes()
    name = f"zcode-{target}"
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{name}.tar.gz"
    data = source.read_bytes()
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo(name)
        info.mode = 0o755
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        # unpack_file selects only the executable basename, skipping these files.
        for path, contents in notices.items():
            info = tarfile.TarInfo(path)
            info.mode = 0o644
            info.size = len(contents)
            tar.addfile(info, io.BytesIO(contents))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target", choices=TARGETS, required=True)
    parser.add_argument("--upstream", required=True, help="pinned upstream checkout containing its license notices")
    args = parser.parse_args()
    print(package(args.source, args.output, args.target, args.upstream))
