import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const desktopDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectDir = path.resolve(desktopDir, "..");
const isWindows = process.platform === "win32";
const localPython = path.join(projectDir, ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
const python = process.env.ZHIMING_LIFE_PYTHON || (existsSync(localPython) ? localPython : (isWindows ? "python" : "python3"));
const npm = isWindows ? "npm.cmd" : "npm";
const token = process.env.ZHIMING_LIFE_API_TOKEN || "zhiming-dev-token";
const sharedEnv = {
  ...process.env,
  ZHIMING_LIFE_API_TOKEN: token,
  ZHIMING_LIFE_API_PORT: "8765",
  ZHIMING_LIFE_DATA_DIR: path.join(projectDir, ".zhiming-life-data"),
  ZHIMING_LIFE_RESOURCE_DIR: path.join(desktopDir, "src-tauri", "resources"),
  VITE_ZHIMING_API_TOKEN: token,
};

const api = spawn(python, ["-m", "zhiming_life.desktop_api"], {
  cwd: projectDir,
  env: sharedEnv,
  stdio: "inherit",
});
const web = spawn(npm, ["run", "dev:web"], {
  cwd: desktopDir,
  env: sharedEnv,
  stdio: "inherit",
});

let stopping = false;
function stop(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  api.kill("SIGTERM");
  web.kill("SIGTERM");
  setTimeout(() => process.exit(exitCode), 300);
}

api.on("exit", (code) => stop(code ?? 1));
web.on("exit", (code) => stop(code ?? 0));
process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));
