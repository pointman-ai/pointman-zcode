# Z.ai ZCode for Pointman

Source-built ZCode CLI extension. Requires Pointman node **0.4.2 or newer**
for its stream protocol, run environment, platform assets and MCP settings.
The manifest uses `zcode-stream`, one headless
process per wake, explicit session resume, and a separate home for each agent.
This repository has not yet published a release. Real-account runs are untested.

## Provenance and build

`upstream.json` pins public [zai-org/ZCode commit
3c5b227649371507ddc4eb46ac5133afe6db1cab](https://github.com/zai-org/ZCode/commit/3c5b227649371507ddc4eb46ac5133afe6db1cab).
The SHA was verified from the first line of the official
[commit patch](https://github.com/zai-org/ZCode/commit/3c5b227.patch).
The upstream commit message's `Source-Commit` is an internal sync source, **not**
the public checkout SHA. Never substitute it.

CI uses Node 24.14.0 and pnpm 10.33.2, installs the frozen workspace lockfile,
then follows the upstream CLI package's `build:sea` dependency and bundle steps:

```sh
pnpm exec turbo --skip-infer --cwd apps/zcode-cli run build --filter=!@zcode/cli --force
pnpm --filter @zcode/cli build
pnpm --filter @zcode/cli sea --target darwin-arm64 # or linux-x64
```

These commands run at the upstream repository root. Building only the CLI's
TypeScript is insufficient: the SEA embeds TUI assets, official plugins, bundled
skills, native search tools, Playwright assets and provider configuration.
The SEA builder locates `postject` in installed dependencies, creates its blob
with Node's SEA API, downloads the target Node binary, injects the blob, and
ad-hoc signs the macOS executable with `codesign`. Native runners avoid cross
platform native dependency mismatches. Optional browser runtime downloads remain
upstream's responsibility; headless browser use is not enabled by this manifest.

Outputs come from `apps/zcode-cli/packages/cli/dist/zcode-darwin-arm64` and
`apps/zcode-cli/packages/cli/dist/zcode-linux-x64`, as resolved by upstream's
`build-sea.mjs` and `sea-targets.mjs`. CI uploads both archives, checksums and
upstream license notices as artifacts. A `v*` tag additionally creates a **draft**
GitHub release. Publish it only after inspecting both builds. Pointman's installer
uses GitHub's asset digest; sidecar checksums are supplementary.

The archives contain one executable with the archive's basename, matching
Pointman's `fetch::unpack_file` contract. Assets are named
`zcode-darwin-arm64.tar.gz` and `zcode-linux-x64.tar.gz`. The manifest requires
node support for `{platform}` in release assets; the existing `{triple}` path
always selects musl on Linux and is unsuitable for these upstream binaries.

**The embedded official Node binary uses glibc, not musl.** NixOS execution needs
an actual loader strategy. To meet installation without preinstalled tools, the
node must provision a compatible glibc loader/library closure and launch the
SEA through it, or package a Nix derivation that patches the ELF interpreter and
RPATH while retaining its glibc dependencies. A documented requirement to enable
nix-ld manually would not satisfy that acceptance criterion. This repository
includes a source-reviewed FHS wrapper candidate below; node provisioning and
pristine NixOS execution remain unverified. Do not advertise this asset as static or as a working NixOS build before that check.

## Run contract

The keeper must use the wake's working directory as the child process cwd.
ZCode supports `--cwd`, but the manifest has no cwd placeholder; the process cwd
provides the same effective directory. Arguments use `--prompt`, `--output-format
stream-json`, `--no-color`, and `--resume <sessionId>` on later wakes. New runs
let ZCode allocate the session ID. There is no supported `--model` override here.
`default`, `plan`, `acceptEdits`, and `auto` map to ZCode's build, plan, edit, and
yolo modes. Yolo does not guarantee every tool's approval gate can be answered.
Headless approval requests normally fail through ZCode's deny broker.

Login is `zcode login`; no automated sign-in check is claimed. An operator must
provision account state in the isolated home. This implementation does not sign
in or call a paid model.

MCP configuration merges into `.zcode/cli/config.json` at `mcp.servers`, with
`features.mcp=true`, preserving other provider/runtime settings. Instructions go
in `.zcode/AGENTS.md`. Both paths are relative to the isolated `HOME`.
This requires Pointman's dotted MCP keys and settings merge support.

### Explicit run environment

`client.run.env` pins HOME, USERPROFILE and ZCODE_DATA_BASE_DIR to `{home}`.
The source layouts are pinned explicitly as well:

| Environment key | Value |
| --- | --- |
| ZCODE_STORAGE_DIR | `{home}/.zcode` |
| ZCODE_SESSION_DB_PATH | `{home}/.zcode/cli/db/db.sqlite` |
| ZCODE_SESSION_DB | `{home}/.zcode/cli/db/db.sqlite` |
| ZCODE_PERSONAL_PROVIDER_CONFIG_FILE | `{home}/.zcode/v2/provider_config.json` |
| ZCODE_LOG_DIR | `{home}/.zcode/cli/log` |

Both session database names are accepted by `env-config.adapter.ts`; setting
only one lets a hostile inherited alias win according to environment iteration
order. Storage and logger defaults were verified in contracts/src/config/index.ts
and adapters/src/logging/index.ts. Storage is `.zcode`, not `.zcode/cli`.

The two built-in provider override keys are set to empty strings. The CLI's
`prepareCliProviderRuntimeEnv` treats blank overrides as absent and materializes
its embedded provider config under the isolated data base directory. Setting
only the personal path is supported by this CLI preparation step; its later
provider runtime receives the completed pair. Do not point the built-in override
at an invented empty file. The BFS, ripgrep and ugrep override keys are also
blanked so the SEA verifies and extracts those binaries into its isolated cache.

These explicit settings must overwrite inherited environment values before
launch. Prompt runs load the first ancestor `.env` with `override:false`, so
removing inherited keys alone is insufficient: that file could restore them.
The offline contract checks exact source layouts and placeholder expansion for
two agent homes against hostile inherited values. Actual node integration still
needs tests with ancestor `.env`, two agents, provider setup and session resume.

### Smallest concrete NixOS launcher candidate

`nix/sea-wrapper.nix` wraps an already verified SEA in Nixpkgs' existing free
Steam FHS runtime. It supplies no Steam client. This is smaller implementation
work than building a bespoke loader closure and leaves the binary named
`linux-x64`. The runtime footprint is broader than a custom dependency closure.

The wrapper uses `(pkgs.steam.override { privateTmp = false; }).run-free`, then
executes `bin/steam-run <SEA> "$@"`. Keeping the host temporary directory visible
preserves node/MCP sockets. Nix interpolation copies the verified SEA into the
store; the caller passes its own pinned package set and keeps the output link
as a garbage collection root. For example, with real paths substituted:

```sh
nix-build --expr 'let pkgs = import /absolute/pinned/nixpkgs {}; in
  import ./nix/sea-wrapper.nix {
    inherit pkgs;
    sea = /absolute/verified/zcode-linux-x64;
  }' --out-link /node/state/runtimes/zcode-fhs
/node/state/runtimes/zcode-fhs/bin/zcode --version
```

The node would provision this output on first install and launch its `bin/zcode`.
No system nix-ld setting or user-installed Node/pnpm is needed. Nix itself is
part of the NixOS environment. This is a source-reviewed candidate, **not a
verified working install**: this machine has no Nix and no Linux SEA to test.
It needs permitted unprivileged namespaces and a runtime smoke test that covers
SEA self re-exec, extracted search tools, native plugin libraries, working
folder, isolated HOME, and the Pointman MCP connection.

An interpreter patch on the SEA alone is insufficient evidence: the CLI also
extracts native search tools at runtime, and native libraries/plugins may have
separate loader requirements. An FHS environment applies to that whole process
tree. This candidate does not enable optional browser or desktop CUA features.

Source details:
[storage defaults](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/packages/contracts/src/config/index.ts),
[database environment aliases](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/packages/adapters/src/config/env-config.adapter.ts),
[logger directory](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/packages/adapters/src/logging/index.ts),
[provider preparation](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/packages/cli/src/provider-runtime-env.ts),
[SEA tool extraction](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/packages/cli/src/sea-runtime-tools.ts).

Nix sources:
[buildFHSEnv manual](https://nixos.org/manual/nixpkgs/stable/#sec-fhs-environments),
[Steam free runtime definition](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/st/steam/package.nix),
[free runtime package alias](https://github.com/NixOS/nixpkgs/blob/master/pkgs/top-level/all-packages.nix).

## Decoder contract

The accompanying node change owns only `node/src/clientstream/zcode.rs`.
Events have a camelCase `sessionId`, `type`, and nested `payload`:

| ZCode event | Pointman event |
| --- | --- |
| session.created / session.resumed | Started |
| turn.completed response | Message |
| tool.updated scheduled / started | ToolUse |
| turn.failed with structured limit fields | Limit, error Result |
| turn.failed / unsuccessful turn.completed | error Result |
| result with response and sessionId | Result |

Reasoning, user/system messages and streaming text deltas are ignored to avoid
private text and duplicate message snapshots. Final summary `response` is kept
in Outcome, not emitted as another Message. Cost is unknown, not invented.
Unknown lines and malformed summaries yield no events.

The keeper must preserve raw NDJSON, require a literal valid `type=result`
summary, and synthesize failure on a missing summary or bad exit. It must also
latch any earlier error Result: upstream's closing summary omits `resultType`,
so it must not erase a preceding turn failure. Exceptions are written to stderr
with exit 1; they need not produce any JSON error event. Limits are recognized
only from structured error type/code, never arbitrary assistant/tool prose.

## Verification and remaining work

Run `python3 -m unittest discover -s tests -v`. Decoder unit tests live inside the
Rust decoder file and use upstream schema-shaped examples (not real-account
captures). The standalone test harness extracts Event and Outcome from the
parent's actual clientspec.rs without editing shared files.

Not checked here: full pnpm/SEA build (shell GitHub DNS unavailable), GitHub CI,
published release install, NixOS dynamic loader compatibility, authenticated
first wake/resume, MCP tool execution, and real quota failures. The task remains
incomplete until integration and real-account acceptance are performed. Nix is
not installed on this development Mac, so the wrapper has not been evaluated.

Sources read on 2026-10-28:

- [CLI package scripts](https://github.com/zai-org/ZCode/blob/3c5b227649371507ddc4eb46ac5133afe6db1cab/apps/zcode-cli/packages/cli/package.json)
- [SEA builder](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/packages/cli/scripts/build-sea.mjs) and [target filenames](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/packages/cli/scripts/sea-targets.mjs)
- [Event mapper](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/packages/bootstrap/src/zcode-protocol/session-mapper.ts) and [event schema](https://github.com/zai-org/ZCode/blob/main/packages/shared/src/zcode-protocol/index.ts)
- [Prompt runner](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/packages/cli/src/prompt-command.ts)
- [CLI config](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/docs/usage/03-config.md) and [automation](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/docs/usage/13-automation.md)
- [Runtime environment sanitizer](https://github.com/zai-org/ZCode/blob/main/packages/shared/src/runtimeEnv.ts)
- [BigModel failures](https://github.com/zai-org/ZCode/blob/main/docs/bigmodel-business-error-retry.md) and [Start Plan failures](https://github.com/zai-org/ZCode/blob/main/docs/start-plan-provider-business-errors.md)

Except for the package script and public SHA evidence, web retrieval resolved
`main` snapshots; full source checkout at the pin was blocked. CI must establish
the complete build against the immutable checkout before release.
