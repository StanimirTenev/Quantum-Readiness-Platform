// Buildless "build": copy public/ into dist/ for static hosting.
// Copies file-by-file to stay robust on Windows extended-length paths.
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const src = path.join(root, "public");
const out = path.join(root, "dist");

fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });

function copyDir(from, to) {
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    const s = path.join(from, entry.name);
    const d = path.join(to, entry.name);
    if (entry.isDirectory()) {
      fs.mkdirSync(d, { recursive: true });
      copyDir(s, d);
    } else {
      fs.copyFileSync(s, d);
    }
  }
}

copyDir(src, out);
const files = fs.readdirSync(out);
console.log(`web-ui: copied ${files.length} file(s) to dist/: ${files.join(", ")}`);
