// Run with the pinned checkout's pnpm exec tsx. No network or model calls.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const [upstream, fixture] = process.argv.slice(2);
const { decodeProviderConfigFile } = await import(pathToFileURL(resolve(
  upstream, "packages/provider-node/src/provider-config-file-codec.ts",
)).href);
const personal = JSON.parse(readFileSync(fixture, "utf8"));
decodeProviderConfigFile(personal);

// Confirm the template/transport/model really exist in this immutable checkout.
const builtin = JSON.parse(readFileSync(resolve(upstream, "config/provider/zcode-builtin.json"), "utf8"));
const [provider] = personal.config.providerConfigRules.providerRules;
const template = builtin.config.providerConfigRules.templateRules.find(
  (rule: { templateId: string }) => rule.templateId === provider.templateId,
);
assert.ok(template, "provider template must exist at the upstream pin");
assert.equal(provider.config.access.type, template.config.access.type);
assert.deepEqual(provider.config.api, template.config.api);
assert.ok(template.config.builtinModelIds.includes(personal.config.defaultModelSelection.modelId));
assert.equal(personal.config.defaultModelSelection.providerId, provider.providerId);
console.log("Provider fixture passes pinned upstream codec and template checks; no model call.");
