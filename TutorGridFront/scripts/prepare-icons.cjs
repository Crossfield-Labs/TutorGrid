const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const sourcePng = path.join(root, "build", "icons", "app-icon.png");
const targetIco = path.join(root, "build", "icons", "app-icon.ico");
const targetFavicon = path.join(root, "public", "favicon.png");
const helperScript = path.join(root, "scripts", "prepare_icons.py");

if (!fs.existsSync(sourcePng)) {
  console.warn(`[icons] Source icon not found: ${sourcePng}`);
  process.exit(0);
}

const pythonCommand = process.platform === "win32" ? "python" : "python3";
const result = spawnSync(
  pythonCommand,
  [helperScript, sourcePng, targetIco, targetFavicon],
  {
    cwd: root,
    stdio: "inherit",
  }
);

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}
