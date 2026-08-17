import { copyFile, mkdir, rm } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const requested = process.argv[2] ?? "all";
const targets = requested === "all" ? ["chrome", "firefox"] : [requested];

if (targets.some((target) => !["chrome", "firefox"].includes(target))) {
  throw new Error("Build target must be chrome, firefox, or all");
}

await rm(resolve(root, "dist"), { recursive: true, force: true });

for (const target of targets) {
  const output = resolve(root, "dist", target);
  const result = spawnSync(
    process.platform === "win32" ? "vite.cmd" : "vite",
    ["build", "--outDir", output, "--emptyOutDir"],
    { cwd: root, env: process.env, stdio: "inherit" },
  );
  if (result.status !== 0) process.exit(result.status ?? 1);
  await mkdir(output, { recursive: true });
  await copyFile(resolve(root, "manifests", `${target}.json`), resolve(output, "manifest.json"));
}
