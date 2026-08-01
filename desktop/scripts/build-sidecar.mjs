import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const desktopDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectDir = path.resolve(desktopDir, "..");
const isWindows = process.platform === "win32";
const executable = isWindows ? "python.exe" : "python";
const candidates = [
  process.env.ZHIMING_LIFE_PYTHON,
  path.join(projectDir, "build", "pyinstaller-venv", isWindows ? "Scripts" : "bin", executable),
  path.join(projectDir, ".venv", isWindows ? "Scripts" : "bin", executable),
].filter(Boolean);
const python = candidates.find((candidate) => existsSync(candidate)) ?? (isWindows ? "python" : "python3");
const result = spawnSync(python, [path.join(desktopDir, "scripts", "build-sidecar.py")], {
  cwd: desktopDir,
  env: process.env,
  stdio: "inherit",
});

if (result.error) throw result.error;
process.exit(result.status ?? 1);
