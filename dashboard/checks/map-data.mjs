// Checks the pure map maths (heat cells + pin colours) without a browser.
// Run: node checks/map-data.mjs
import { heatCells, heatColor, severityColor } from '../src/lib/mapData.js';

let failures = 0;

function check(label, condition, detail = '') {
  if (condition) return;
  failures += 1;
  console.log(`FAIL ${label}${detail ? ` — ${detail}` : ''}`);
}

const nearby = [
  { id: 'a', lat: 20.7000, lon: 81.5500 },
  { id: 'b', lat: 20.7010, lon: 81.5510 },
  { id: 'c', lat: 20.7005, lon: 81.5505 },
];
const far = { id: 'd', lat: 21.5000, lon: 82.5000 };

const cells = heatCells([...nearby, far, { id: 'e', lat: null, lon: null }]);

check('two cells (null coords skipped)', cells.length === 2, `got ${cells.length}`);

const dense = cells.find((cell) => cell.count === 3);
check('nearby points group into one cell', Boolean(dense));
check('cell centre is the average', dense && Math.abs(dense.lat - (20.7000 + 20.7010 + 20.7005) / 3) < 1e-9);
check('3 reports use the 2–3 colour', dense && dense.color === '#9d6347', dense && dense.color);

const single = cells.find((cell) => cell.count === 1);
check('far point is its own cell', single && Math.abs(single.lat - 21.5) < 1e-9);
check('single report uses the lightest heat', single && single.color === '#b89a58', single && single.color);

check('heat colour scales up', heatColor(1) === '#b89a58' && heatColor(2) === '#9d6347' && heatColor(9) === '#7f3f36');

check('pin colour by priority', severityColor('High') === '#9d5145'
  && severityColor('Low') === '#557059'
  && severityColor('Unknown') === '#27425f');

console.log(failures ? `${failures} problem(s)` : 'map data check passed');
process.exitCode = failures ? 1 : 0;
