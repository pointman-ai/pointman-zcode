# Candidate NixOS launcher for an already digest-verified linux-x64 SEA.
# Caller supplies its pinned nixpkgs; this file does not resolve a moving channel.
# Not evaluated or run in this macOS-only development environment.
{ pkgs, sea }:
assert pkgs.stdenv.hostPlatform.system == "x86_64-linux";
assert builtins.isPath sea;
let
  # Unlike steam.run, run-free supplies the FHS runtime without installing Steam.
  # Share /tmp so the node's sockets and files remain reachable by MCP children.
  runtime = (pkgs.steam.override { privateTmp = false; }).run-free;
in
pkgs.writeShellScriptBin "zcode" ''
  exec ${runtime}/bin/steam-run ${sea} "$@"
''
