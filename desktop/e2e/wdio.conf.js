import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";

const application = process.env.ZHIMING_LIFE_WINDOWS_APP;
if (!application) {
  throw new Error("ZHIMING_LIFE_WINDOWS_APP is required");
}

let driver;
let expectedDriverExit = false;

function stopDriver() {
  expectedDriverExit = true;
  driver?.kill();
}

export const config = {
  host: "127.0.0.1",
  port: 4444,
  specs: ["./specs/**/*.e2e.js"],
  maxInstances: 1,
  capabilities: [
    {
      maxInstances: 1,
      "tauri:options": { application },
    },
  ],
  reporters: ["spec"],
  framework: "mocha",
  mochaOpts: { ui: "bdd", timeout: 180_000 },
  waitforTimeout: 120_000,
  connectionRetryTimeout: 180_000,
  beforeSession() {
    driver = spawn(path.join(os.homedir(), ".cargo", "bin", "tauri-driver.exe"), [], {
      stdio: ["ignore", "inherit", "inherit"],
    });
    driver.on("error", (error) => {
      throw error;
    });
    driver.on("exit", (code) => {
      if (!expectedDriverExit && code !== 0) {
        process.exitCode = 1;
      }
    });
  },
  afterSession: stopDriver,
  onComplete: stopDriver,
};
