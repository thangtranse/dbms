import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const validCommit = (value) => /^[a-f0-9]{40}(?:[a-f0-9]{24})?$/.test(value);

export function createBuildInfo({ cwd = frontend, env = process.env, now = new Date() } = {}) {
  let commit;
  let dirty;
  try {
    commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
    dirty = execFileSync("git", ["status", "--porcelain", "--untracked-files=normal"], { cwd, encoding: "utf8" }).trim().length > 0;
  } catch {
    commit = env.BUILD_COMMIT || "unknown";
    dirty = env.BUILD_DIRTY === "true";
  }
  if (commit !== "unknown" && !validCommit(commit)) throw new Error("BUILD_COMMIT must be a full Git SHA");
  if (env.BUILD_COMMIT && env.BUILD_COMMIT !== "unknown" && env.BUILD_COMMIT !== commit) {
    throw new Error("BUILD_COMMIT differs from the checkout; refusing to label this build");
  }
  if (env.BUILD_DIRTY && !["true", "false"].includes(env.BUILD_DIRTY)) throw new Error("BUILD_DIRTY must be true or false");
  const shortCommit = commit === "unknown" ? "unknown" : commit.slice(0, 12);
  return {
    version: shortCommit + (dirty && commit !== "unknown" ? "-dirty" : ""),
    commit,
    shortCommit,
    builtAt: now.toISOString(),
    dirty: commit === "unknown" ? null : dirty,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const info = createBuildInfo();
  writeFileSync(resolve(frontend, "build-info.json"), JSON.stringify(info, null, 2) + "\n");
  console.log(`Build version: ${info.version} (${info.builtAt})`);
}
