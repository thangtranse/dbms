// Next.js substitutes these constants at build time; runtime Git changes do not relabel a build.
export const buildInfo = {
  version: process.env.NEXT_PUBLIC_BUILD_VERSION ?? "unknown",
  commit: process.env.NEXT_PUBLIC_BUILD_COMMIT ?? "unknown",
  shortCommit: process.env.NEXT_PUBLIC_BUILD_SHORT_COMMIT ?? "unknown",
  builtAt: process.env.NEXT_PUBLIC_BUILD_AT ?? null,
  dirty: process.env.NEXT_PUBLIC_BUILD_DIRTY === "true" ? true : process.env.NEXT_PUBLIC_BUILD_DIRTY === "false" ? false : null,
};
