import { spawnSync } from "node:child_process";
import fs from "node:fs";
const python =
  process.env.RESTORE_PYTHON ||
  (process.platform === "win32" && fs.existsSync(".venv/Scripts/python.exe")
    ? ".venv/Scripts/python.exe"
    : "python");
function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status) process.exit(result.status);
}
switch (process.argv[2]) {
  case "lint":
    run(process.execPath, ["--check", "web/app.js"]);
    run(process.execPath, ["--check", "vendor/audiojs/process.mjs"]);
    run(python, ["scripts/verify_source.py"]);
    break;
  case "test":
    fs.mkdirSync("output", { recursive: true });
    run(python, [
      "-m",
      "pytest",
      "tests",
      "-q",
      "--tb=short",
      "--basetemp",
      fs.mkdtempSync("output/test-"),
    ]);
    break;
  case "build":
    run(python, ["scripts/build_release.py"]);
    break;
  default:
    throw Error("Expected lint, test or build");
}
