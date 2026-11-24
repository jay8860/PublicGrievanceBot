// Regression test: render Complaints with data, so every JSX expression in the
// page (including <ComplaintDrawer token={token} />) is evaluated.
import React from 'react';
import { renderToString } from 'react-dom/server';
import { ToastProvider } from '../src/components/Toast';
import Complaints from '../src/pages/Complaints';
import ErrorBoundary from '../src/components/ErrorBoundary';

const token = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJzdXBlcmFkbWluIn0.sig';

try {
  const html = renderToString(
    React.createElement(ToastProvider, null,
      React.createElement(ErrorBoundary, null,
        React.createElement(Complaints, { token })))
  );
  const checks = ['GRV-2026-000001', 'Potholes', 'Mohan Yadav'];
  const missing = checks.filter((needle) => !html.includes(needle));
  if (missing.length) {
    console.log(`FAIL: rendered HTML is missing ${missing.join(', ')}`);
    process.exitCode = 1;
  } else {
    console.log(`OK: Complaints rendered with data (${html.length} chars)`);
  }
} catch (error) {
  console.log(`FAIL: ${error.message}`);
  process.exitCode = 1;
}
