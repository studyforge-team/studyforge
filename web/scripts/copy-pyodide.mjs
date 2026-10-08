// Copies Pyodide core files from node_modules and downloads the wheel closure
// for ROOTS from jsDelivr into public/pyodide/<ver>/, verifying sha256 from the lock.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const VER = '314.0.7';
const ROOTS = ['numpy', 'scipy', 'sympy', 'matplotlib'];
const CORE = ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json'];
const CDN = `https://cdn.jsdelivr.net/pyodide/v${VER}/full/`;

const src = path.resolve('node_modules/pyodide');
const out = path.resolve(`public/pyodide/${VER}`);
const cache = path.resolve('.wheel-cache');

const pkgJson = JSON.parse(fs.readFileSync(path.join(src, 'package.json'), 'utf8'));
if (pkgJson.version !== VER) throw new Error(`pyodide ${pkgJson.version} installed, expected ${VER}`);

const lock = JSON.parse(fs.readFileSync(path.join(src, 'pyodide-lock.json'), 'utf8'));
const find = (n) => lock.packages[n] ?? lock.packages[n.toLowerCase()];

const closure = new Map();
const stack = [...ROOTS];
while (stack.length) {
  const name = stack.pop();
  const p = find(name);
  if (!p) throw new Error(`package ${name} not in pyodide-lock.json`);
  if (closure.has(p.name)) continue;
  closure.set(p.name, p);
  stack.push(...(p.depends ?? []));
}

fs.mkdirSync(out, { recursive: true });
fs.mkdirSync(cache, { recursive: true });
for (const f of CORE) fs.copyFileSync(path.join(src, f), path.join(out, f));

const sha256 = (buf) => crypto.createHash('sha256').update(buf).digest('hex');
let total = 0;
for (const p of closure.values()) {
  const cached = path.join(cache, p.file_name);
  let buf = fs.existsSync(cached) ? fs.readFileSync(cached) : null;
  if (!buf || sha256(buf) !== p.sha256) {
    const res = await fetch(CDN + p.file_name);
    if (!res.ok) throw new Error(`${p.file_name}: HTTP ${res.status}`);
    buf = Buffer.from(await res.arrayBuffer());
    if (sha256(buf) !== p.sha256) throw new Error(`${p.file_name}: sha256 mismatch`);
    fs.writeFileSync(cached, buf);
  }
  fs.writeFileSync(path.join(out, p.file_name), buf);
  total += buf.length;
}
const core = CORE.reduce((s, f) => s + fs.statSync(path.join(out, f)).size, 0);
const mb = (b) => (b / 1048576).toFixed(1);
console.log(`pyodide ${VER}: ${closure.size} packages [${[...closure.keys()].sort().join(', ')}]`);
console.log(`wheels ${mb(total)} MB + core ${mb(core)} MB = ${mb(total + core)} MB`);
