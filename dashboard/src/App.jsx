import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Login from './Login';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './components/Toast';
import { EscalationApi } from './services/apiV2';
import { canManage, decodeToken, roleOf } from './lib/utils';
import { visibleSections } from './lib/nav';
import Overview from './pages/Overview';
import Complaints from './pages/Complaints';
import Departments from './pages/Departments';
import Officers from './pages/Officers';
import EscalationCentre from './pages/EscalationCentre';
import GeoMonitoring from './pages/GeoMonitoring';
import ResolutionVerification from './pages/ResolutionVerification';
import OfficerPerformance from './pages/OfficerPerformance';
import Reports from './pages/Reports';
import AuditLogs from './pages/AuditLogs';
import Settings from './pages/Settings';

const PAGES = {
  overview: Overview,
  complaints: Complaints,
  departments: Departments,
  officers: Officers,
  escalation: EscalationCentre,
  geo: GeoMonitoring,
  verification: ResolutionVerification,
  performance: OfficerPerformance,
  reports: Reports,
  audit: AuditLogs,
  settings: Settings,
};

function parseHash() {
  const raw = window.location.hash.replace(/^#\/?/, '').trim();
  return PAGES[raw] ? raw : 'overview';
}

function useHashRoute() {
  const [route, setRoute] = useState(parseHash);

  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const navigate = useCallback((key) => {
    if (!PAGES[key]) return;
    window.location.hash = `#/${key}`;
    setRoute(key);
  }, []);

  return [route, navigate];
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('token') || null);
  const [route, navigate] = useHashRoute();
  const [overdueCount, setOverdueCount] = useState(0);

  const user = useMemo(() => {
    const claims = decodeToken(token) || {};
    return { username: claims.sub || 'administrator', role: roleOf(token) };
  }, [token]);
  const manage = canManage(token);

  // A "bypass-login" placeholder is not a real JWT - drop it.
  useEffect(() => {
    if (token && !decodeToken(token)) {
      localStorage.removeItem('token');
      setToken(null);
    }
  }, [token]);

  useEffect(() => {
    if (!token || !manage) return undefined;
    let alive = true;
    EscalationApi.centre()
      .then((data) => { if (alive) setOverdueCount(data?.counts?.overdue || 0); })
      .catch(() => {});
    return () => { alive = false; };
  }, [token, manage, route]);

  // Role guard: viewers cannot open administrator-only pages.
  useEffect(() => {
    if (!token) return;
    const allowed = new Set(
      visibleSections(manage).flatMap((section) => section.items.map((item) => item.key))
    );
    if (!allowed.has(route)) navigate('overview');
  }, [route, token, manage, navigate]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    window.location.hash = '';
  };

  if (!token) {
    return (
      <Login
        onLogin={(newToken) => {
          localStorage.setItem('token', newToken);
          setToken(newToken);
        }}
      />
    );
  }

  const PageComponent = PAGES[route] || Overview;

  return (
    <ToastProvider>
      <Layout page={route} onNavigate={navigate} user={user} token={token}
        onLogout={handleLogout} alertCount={overdueCount}>
        <ErrorBoundary key={route}>
          <PageComponent key={route} token={token} onNavigate={navigate} />
        </ErrorBoundary>
      </Layout>
    </ToastProvider>
  );
}
