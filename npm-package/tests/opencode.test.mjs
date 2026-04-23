// Tests for opencode client support.
// Run with: node --test npm-package/tests/opencode.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync, readFileSync, existsSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  getOpencodeConfigDir,
  getOpencodeConfigPath,
  getOpencodeCommandDir,
  readOpencodeConfig,
  writeOpencodeConfig,
  opencodeMcpBlock,
  registerOpencodeMcp,
  unregisterOpencodeMcp,
  installOpencodeSkills,
  detectOpencodeState,
} from "../bin/opencode.mjs";

function makeSandbox() {
  const root = mkdtempSync(join(tmpdir(), "terrain-opencode-test-"));
  const xdg = join(root, "config");
  mkdirSync(xdg, { recursive: true });
  const home = root;
  const env = { XDG_CONFIG_HOME: xdg };
  const cleanup = () => rmSync(root, { recursive: true, force: true });
  return { root, home, env, xdg, cleanup };
}

test("getOpencodeConfigDir prefers XDG_CONFIG_HOME", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    const dir = getOpencodeConfigDir(env, home);
    assert.equal(dir, join(env.XDG_CONFIG_HOME, "opencode"));
  } finally { cleanup(); }
});

test("getOpencodeConfigDir falls back to ~/.config when XDG is unset", () => {
  const dir = getOpencodeConfigDir({}, "/tmp/fakehome");
  assert.equal(dir, "/tmp/fakehome/.config/opencode");
});

test("getOpencodeConfigPath prefers opencode.jsonc when it exists", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    const dir = getOpencodeConfigDir(env, home);
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "opencode.jsonc"), "{}");
    assert.equal(getOpencodeConfigPath(env, home), join(dir, "opencode.jsonc"));
  } finally { cleanup(); }
});

test("getOpencodeConfigPath defaults to opencode.json", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    const dir = getOpencodeConfigDir(env, home);
    assert.equal(getOpencodeConfigPath(env, home), join(dir, "opencode.json"));
  } finally { cleanup(); }
});

test("readOpencodeConfig returns empty cfg when file missing", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    const result = readOpencodeConfig(env, home);
    assert.deepEqual(result.cfg, {});
    assert.equal(result.existed, false);
  } finally { cleanup(); }
});

test("readOpencodeConfig throws with EOPENCODE_UNPARSEABLE on invalid JSON", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    const dir = getOpencodeConfigDir(env, home);
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "opencode.json"), "{ /* comment */ }");
    assert.throws(() => readOpencodeConfig(env, home), (err) => err.code === "EOPENCODE_UNPARSEABLE");
  } finally { cleanup(); }
});

test("opencodeMcpBlock produces the right shape", () => {
  const block = opencodeMcpBlock({ isWin: false });
  assert.equal(block.type, "local");
  assert.equal(block.enabled, true);
  assert.deepEqual(block.command, ["npx", "-y", "terrain-ai@latest", "--server"]);

  const winBlock = opencodeMcpBlock({ isWin: true });
  assert.deepEqual(winBlock.command, ["cmd", "/c", "npx", "-y", "terrain-ai@latest", "--server"]);
});

test("registerOpencodeMcp creates a new opencode.json with $schema", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    const path = registerOpencodeMcp({ env, home, isWin: false });
    const cfg = JSON.parse(readFileSync(path, "utf-8"));
    assert.equal(cfg.$schema, "https://opencode.ai/config.json");
    assert.equal(cfg.mcp.terrain.type, "local");
    assert.equal(cfg.mcp.terrain.enabled, true);
    assert.deepEqual(cfg.mcp.terrain.command, ["npx", "-y", "terrain-ai@latest", "--server"]);
  } finally { cleanup(); }
});

test("registerOpencodeMcp preserves other mcp entries and fields", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    const dir = getOpencodeConfigDir(env, home);
    mkdirSync(dir, { recursive: true });
    const existing = {
      $schema: "https://opencode.ai/config.json",
      theme: "tokyonight",
      mcp: {
        other: { type: "local", command: ["foo"], enabled: true }
      }
    };
    writeFileSync(join(dir, "opencode.json"), JSON.stringify(existing, null, 2));

    registerOpencodeMcp({ env, home, isWin: false });
    const cfg = JSON.parse(readFileSync(join(dir, "opencode.json"), "utf-8"));
    assert.equal(cfg.theme, "tokyonight");
    assert.ok(cfg.mcp.other);
    assert.ok(cfg.mcp.terrain);
  } finally { cleanup(); }
});

test("registerOpencodeMcp is idempotent (no duplicate entries)", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    registerOpencodeMcp({ env, home, isWin: false });
    registerOpencodeMcp({ env, home, isWin: false });
    const path = getOpencodeConfigPath(env, home);
    const cfg = JSON.parse(readFileSync(path, "utf-8"));
    assert.equal(Object.keys(cfg.mcp).length, 1);
    assert.ok(cfg.mcp.terrain);
  } finally { cleanup(); }
});

test("unregisterOpencodeMcp removes only the terrain entry", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    const dir = getOpencodeConfigDir(env, home);
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "opencode.json"), JSON.stringify({
      $schema: "https://opencode.ai/config.json",
      mcp: {
        terrain: opencodeMcpBlock({ isWin: false }),
        other: { type: "local", command: ["foo"], enabled: true }
      }
    }, null, 2));

    const removed = unregisterOpencodeMcp({ env, home });
    assert.equal(removed, true);

    const cfg = JSON.parse(readFileSync(join(dir, "opencode.json"), "utf-8"));
    assert.ok(!cfg.mcp.terrain);
    assert.ok(cfg.mcp.other);
  } finally { cleanup(); }
});

test("unregisterOpencodeMcp drops empty mcp section", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    registerOpencodeMcp({ env, home, isWin: false });
    const removed = unregisterOpencodeMcp({ env, home });
    assert.equal(removed, true);
    const cfg = JSON.parse(readFileSync(getOpencodeConfigPath(env, home), "utf-8"));
    assert.equal(cfg.mcp, undefined);
  } finally { cleanup(); }
});

test("unregisterOpencodeMcp returns false when nothing registered", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    assert.equal(unregisterOpencodeMcp({ env, home }), false);
  } finally { cleanup(); }
});

test("unregisterOpencodeMcp returns false on unparseable config (no damage)", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    const dir = getOpencodeConfigDir(env, home);
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "opencode.json"), "{ /* jsonc */ }");
    assert.equal(unregisterOpencodeMcp({ env, home }), false);
    // File untouched
    assert.equal(readFileSync(join(dir, "opencode.json"), "utf-8"), "{ /* jsonc */ }");
  } finally { cleanup(); }
});

test("installOpencodeSkills copies md files into command/ dir", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    const srcDir = join(home, "src-commands");
    mkdirSync(srcDir, { recursive: true });
    writeFileSync(join(srcDir, "ask.md"), "# ask");
    writeFileSync(join(srcDir, "trace.md"), "# trace");
    writeFileSync(join(srcDir, "README.txt"), "ignored");

    const { installed, targetDir } = installOpencodeSkills({ env, home, srcDir });
    assert.deepEqual(installed.sort(), ["ask.md", "trace.md"]);
    assert.equal(targetDir, getOpencodeCommandDir(env, home));
    assert.ok(existsSync(join(targetDir, "ask.md")));
    assert.ok(existsSync(join(targetDir, "trace.md")));
    assert.ok(!existsSync(join(targetDir, "README.txt")));
  } finally { cleanup(); }
});

test("detectOpencodeState reflects registered state", () => {
  const { env, home, cleanup } = makeSandbox();
  try {
    const commandExists = () => false;
    let state = detectOpencodeState({ env, home, commandExists });
    assert.equal(state.hasCli, false);
    assert.equal(state.hasMcp, false);
    assert.deepEqual(state.installedSkills, []);

    registerOpencodeMcp({ env, home, isWin: false });
    const srcDir = join(home, "src-commands");
    mkdirSync(srcDir, { recursive: true });
    writeFileSync(join(srcDir, "ask.md"), "# ask");
    installOpencodeSkills({ env, home, srcDir });

    state = detectOpencodeState({ env, home, commandExists: () => true });
    assert.equal(state.hasCli, true);
    assert.equal(state.hasMcp, true);
    assert.deepEqual(state.installedSkills, ["ask.md"]);
  } finally { cleanup(); }
});
