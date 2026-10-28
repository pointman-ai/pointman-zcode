# Z.ai ZCode for Pointman

Source-built ZCode CLI extension. The manifest uses `zcode-stream`, one headless
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
Pointman's `fetch::unpack_file` contract. On Linux the installer's current triple
is `x86_64-unknown-linux-musl`; that archive name is only an installer ABI name.
**The embedded official Node binary uses glibc, not musl.** NixOS execution needs
its dynamic loader compatibility environment (for example nix-ld) or node-side
wrapping. Installation on a pristine NixOS machine has not been proven. Do not
advertise this asset as static or as a working NixOS build before that check.

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

### Required isolation glue in the node

Setting `HOME` alone does not isolate ZCode. Its runtime sanitizer preserves
state override variables, and prompt runs load the first ancestor `.env` before
creating the app (`override:false`). The node must control these paths before
starting the CLI, rather than merely removing inherited keys that `.env` can
restore:

- Set `HOME`, `USERPROFILE`, and `ZCODE_DATA_BASE_DIR` to the agent home.
- Set `ZCODE_STORAGE_DIR` to `<home>/.zcode/cli` and
  `ZCODE_SESSION_DB_PATH` to `<home>/.zcode/cli/db/db.sqlite`.
- Set `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` to
  `<home>/.zcode/v2/provider_config.json`; set `ZCODE_LOG_DIR` inside the home.
- Test with hostile inherited state overrides and ancestor `.env` files. No
  unrelated personal account/configuration may be read. These tests belong to
  the node's command/environment owner, not this manifest.

Those overrides are documented in upstream's CLI config and automation guides.
The exact source pin's handling of all other config overrides still needs a
runtime audit; no complete isolation claim is made from documentation alone.

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
incomplete until integration and real-account acceptance are performed.

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
