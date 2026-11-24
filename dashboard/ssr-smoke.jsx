// Render-smoke test: mounts every page's first render (no browser needed).
// Leaflet pages are excluded because Leaflet requires a real DOM.
import React from 'react';
import { renderToString } from 'react-dom/server';
import { ToastProvider } from './src/components/Toast';
import Overview from './src/pages/Overview';
import Complaints from './src/pages/Complaints';
import Departments from './src/pages/Departments';
import Officers from './src/pages/Officers';
import EscalationCentre from './src/pages/EscalationCentre';
import ResolutionVerification from './src/pages/ResolutionVerification';
import OfficerPerformance from './src/pages/OfficerPerformance';
import Reports from './src/pages/Reports';
import AuditLogs from './src/pages/AuditLogs';
import Settings from './src/pages/Settings';

const token = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJzdXBlcmFkbWluIn0.sig';

const pages = {
  Overview, Complaints, Departments, Officers, EscalationCentre,
  ResolutionVerification, OfficerPerformance, Reports, AuditLogs, Settings,
};

let failures = 0;
for (const [name, Page] of Object.entries(pages)) {
  try {
    const html = renderToString(
      React.createElement(ToastProvider, null, React.createElement(Page, { token }))
    );
    if (!html || html.length < 50) throw new Error('empty render');
    console.log(`OK   ${name.padEnd(24)} ${html.length} chars`);
  } catch (err) {
    failures += 1;
    console.log(`FAIL ${name}: ${err.message}`);
  }
}
console.log(failures ? `${failures} page(s) failed` : 'ALL 10 PAGE RENDERS PASSED');
process.exitCode = failures ? 1 : 0;
