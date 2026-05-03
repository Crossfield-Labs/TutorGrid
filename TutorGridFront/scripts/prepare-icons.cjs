const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const sourcePng = path.join(root, "build", "icons", "app-icon.png");
const targetIco = path.join(root, "build", "icons", "app-icon.ico");
const targetFavicon = path.join(root, "public", "favicon.png");

function readPngSize(buffer) {
  if (buffer.length < 24 || buffer.toString("ascii", 1, 4) !== "PNG") {
    throw new Error("Invalid PNG source icon.");
  }
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
  };
}

function buildIcoFromPng(buffer, width, height) {
  const header = Buffer.alloc(6 + 16);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(1, 4);
  header.writeUInt8(width >= 256 ? 0 : width, 6);
  header.writeUInt8(height >= 256 ? 0 : height, 7);
  header.writeUInt8(0, 8);
  header.writeUInt8(0, 9);
  header.writeUInt16LE(1, 10);
  header.writeUInt16LE(32, 12);
  header.writeUInt32LE(buffer.length, 14);
  header.writeUInt32LE(22, 18);
  return Buffer.concat([header, buffer]);
}

if (!fs.existsSync(sourcePng)) {
  console.warn(`[icons] Source icon not found: ${sourcePng}`);
  process.exit(0);
}

const pngBuffer = fs.readFileSync(sourcePng);
const { width, height } = readPngSize(pngBuffer);
const icoBuffer = buildIcoFromPng(pngBuffer, width, height);

fs.mkdirSync(path.dirname(targetIco), { recursive: true });
fs.mkdirSync(path.dirname(targetFavicon), { recursive: true });
fs.writeFileSync(targetIco, icoBuffer);
fs.copyFileSync(sourcePng, targetFavicon);

console.log(`[icons] Prepared ${path.relative(root, targetIco)} and ${path.relative(root, targetFavicon)}`);
