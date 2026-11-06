import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { createBuildInfo } from "./build-info.mjs";

test("build identity follows the actual Git commit and marks uncommitted source", () => {
  const cwd = mkdtempSync(join(tmpdir(), "lunch-version-"));
  const git = (...args) => execFileSync("git", args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
  try {
    git("init", "-b", "main");
    git("config", "user.email", "fixture@example.invalid");
    git("config", "user.name", "Build fixture");
    writeFileSync(join(cwd, "source.txt"), "one");
    git("add", "source.txt");
    git("-c", "commit.gpgsign=false", "commit", "-m", "fixture");
    const commit = git("rev-parse", "HEAD");
    const clean = createBuildInfo({ cwd, env: {}, now: new Date("2026-11-06T00:00:00Z") });
    assert.equal(clean.commit, commit);
    assert.equal(clean.version, commit.slice(0, 12));
    assert.equal(clean.dirty, false);
    assert.equal(clean.builtAt, "2026-11-06T00:00:00.000Z");
    writeFileSync(join(cwd, "source.txt"), "two");
    assert.equal(createBuildInfo({ cwd, env: {} }).version, commit.slice(0, 12) + "-dirty");
    assert.throws(() => createBuildInfo({ cwd, env: { BUILD_COMMIT: "f".repeat(40) } }), /differs/);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
});

test("builds without Git use explicit metadata or say unknown", () => {
  const cwd = mkdtempSync(join(tmpdir(), "lunch-no-git-"));
  try {
    assert.equal(createBuildInfo({ cwd, env: {} }).version, "unknown");
    assert.equal(createBuildInfo({ cwd, env: { BUILD_COMMIT: "a".repeat(40), BUILD_DIRTY: "true" } }).version, "a".repeat(12) + "-dirty");
    assert.throws(() => createBuildInfo({ cwd, env: { BUILD_COMMIT: "fake" } }), /full Git SHA/);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
});
