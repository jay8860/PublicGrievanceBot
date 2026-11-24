// Guard against the class of bug where a page renders a prop it never received
// (e.g. <ComplaintDrawer token={token} /> inside a component declared with no
// props, which crashed the Complaints page at runtime).
// Run: node checks/component-props.mjs
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const pagesDir = fileURLToPath(new URL('../src/pages/', import.meta.url));
const componentsDir = fileURLToPath(new URL('../src/components/', import.meta.url));
const WATCHED = ['token', 'onNavigate'];
let failures = 0;

for (const file of readdirSync(pagesDir).filter((name) => name.endsWith('.jsx'))) {
  const source = readFileSync(join(pagesDir, file), 'utf8');
  const signature = source.match(/export default function\s+\w+\s*\(([^)]*)\)/);
  if (!signature) {
    failures += 1;
    console.log(`FAIL ${file}: no "export default function" signature found`);
    continue;
  }

  const declared = new Set(
    signature[1]
      .replace(/[{}]/g, ' ')
      .split(',')
      .map((part) => part.split(/[:=]/)[0].trim())
      .filter(Boolean)
  );

  // Skip the signature itself; only the body matters.
  const body = source.slice((signature.index || 0) + signature[0].length);

  for (const prop of WATCHED) {
    if (new RegExp(`\\b${prop}\\b`).test(body) && !declared.has(prop)) {
      failures += 1;
      console.log(`FAIL ${file}: uses "${prop}" but does not destructure it in its props`);
    }
  }
}

for (const [name, prop] of [['ComplaintDrawer.jsx', 'token'], ['Layout.jsx', 'token']]) {
  const source = readFileSync(join(componentsDir, name), 'utf8');
  if (!new RegExp(`function\\s+\\w+\\s*\\([^)]*\\b${prop}\\b`).test(source)) {
    failures += 1;
    console.log(`FAIL components/${name}: expected a "${prop}" prop`);
  }
}

console.log(failures ? `${failures} problem(s)` : 'component prop check passed');
process.exitCode = failures ? 1 : 0;
