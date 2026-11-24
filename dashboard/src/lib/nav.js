// Single source of truth for sidebar navigation + role gating.
import {
  AlertTriangle, BarChart3, Building2, FileSpreadsheet, FileText, History,
  LayoutDashboard, Map, Settings, ShieldCheck, Users,
} from 'lucide-react';

export const NAV_SECTIONS = [
  {
    label: 'Register',
    items: [
      { key: 'overview', label: 'Overview', icon: LayoutDashboard, title: 'Overview',
        subtitle: 'District workload, last 14 days' },
      { key: 'complaints', label: 'Complaints', icon: FileText, title: 'Complaints',
        subtitle: 'Registered grievances and their current state' },
      { key: 'escalation', label: 'Escalation Centre', icon: AlertTriangle, title: 'Escalation Centre',
        subtitle: 'Cases past their deadline, by level' },
      { key: 'geo', label: 'Geographic Monitoring', icon: Map, title: 'Geographic Monitoring',
        subtitle: 'Where complaints are being reported' },
    ],
  },
  {
    label: 'Administration',
    admin: true,
    items: [
      { key: 'departments', label: 'Departments', icon: Building2, title: 'Departments',
        subtitle: 'Categories and TAT policy' },
      { key: 'officers', label: 'Officer Management', icon: Users, title: 'Officer Management',
        subtitle: 'L1–L4 roster, jurisdictions, Telegram links' },
      { key: 'verification', label: 'Resolution Verification', icon: ShieldCheck,
        title: 'Resolution Verification',
        subtitle: 'Photo check results and pending decisions' },
    ],
  },
  {
    label: 'Analysis',
    items: [
      { key: 'performance', label: 'Officer Performance', icon: BarChart3,
        title: 'Officer Performance', subtitle: 'Workload, turnaround and ratings' },
      { key: 'reports', label: 'Reports', icon: FileSpreadsheet, title: 'Reports',
        subtitle: 'Exports and period comparisons' },
      { key: 'audit', label: 'Audit Logs', icon: History, title: 'Audit Logs',
        subtitle: 'Every recorded action, with actor and time' },
    ],
  },
  {
    label: 'System',
    admin: true,
    items: [
      { key: 'settings', label: 'Settings', icon: Settings, title: 'Settings',
        subtitle: 'Account, administrators, deployment status' },
    ],
  },
];


export const ALL_ITEMS = NAV_SECTIONS.flatMap((section) => section.items);

export function findNavItem(key) {
  return ALL_ITEMS.find((item) => item.key === key) || ALL_ITEMS[0];
}

export function visibleSections(canManage) {
  return NAV_SECTIONS.filter((section) => !section.admin || canManage);
}
