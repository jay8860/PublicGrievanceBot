// Application shell: register-style sidebar and a quiet top bar.
import React, { useState } from 'react';
import { LogOut, Menu, X } from 'lucide-react';
import { cls, initials, ROLES } from '../lib/utils';
import { findNavItem, visibleSections } from '../lib/nav';

function SidebarContent({ page, onNavigate, canManage, onClose }) {
  return (
    <div className="flex h-full flex-col bg-slate-900 text-slate-300">
      <div className="px-5 h-16 flex items-center border-b border-white/10">
        <div className="min-w-0">
          <p className="font-serif text-[17px] leading-tight text-white">Grievance Register</p>
          <p className="text-[11px] text-slate-400">District administration</p>
        </div>
        {onClose && (
          <button onClick={onClose} className="ml-auto lg:hidden text-slate-400 hover:text-white">
            <X size={18} />
          </button>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto py-3">
        {visibleSections(canManage).map((section) => (
          <div key={section.label} className="mb-3">
            <p className="px-5 pb-1 text-[11px] text-slate-500">{section.label}</p>
            {section.items.map((item) => {
              const active = item.key === page;
              const Icon = item.icon;
              return (
                <button
                  key={item.key}
                  onClick={() => { onNavigate(item.key); onClose?.(); }}
                  className={cls('w-full flex items-center gap-2.5 pl-4 pr-3 py-2 text-[13px] border-l-2',
                    active
                      ? 'border-blue-300 bg-white/5 text-white'
                      : 'border-transparent text-slate-300 hover:bg-white/5 hover:text-white')}
                >
                  <Icon size={15} strokeWidth={1.75}
                    className={active ? 'text-white' : 'text-slate-400'} />
                  {item.label}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="px-5 py-3 border-t border-white/10 text-[11px] text-slate-500">
        TAT checks run on the server
      </div>
    </div>
  );
}

export default function Layout({ page, onNavigate, user, token, onLogout, children, alertCount = 0 }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const item = findNavItem(page);
  const canManage = ['superadmin', 'admin'].includes(user?.role);

  return (
    <div className="min-h-screen bg-slate-100 text-slate-800">
      <aside className="hidden lg:block fixed inset-y-0 left-0 w-60 z-40">
        <SidebarContent page={page} onNavigate={onNavigate} canManage={canManage} />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-64">
            <SidebarContent page={page} onNavigate={onNavigate} canManage={canManage}
              onClose={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 bg-slate-50 border-b border-slate-200">
          <div className="flex items-center gap-3 px-4 sm:px-6 h-16">
            <button onClick={() => setMobileOpen(true)} className="lg:hidden p-2 -ml-2 text-slate-500">
              <Menu size={18} />
            </button>
            <div className="min-w-0">
              <h1 className="font-serif text-[17px] leading-tight text-slate-900 truncate">
                {item.title}
              </h1>
              <p className="text-[11px] text-slate-500 truncate">{item.subtitle}</p>
            </div>

            <div className="ml-auto flex items-center gap-3">
              {alertCount > 0 && (
                <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] text-red-700">
                  <span className="h-1.5 w-1.5 rounded-full bg-red-600" />
                  {alertCount} past TAT
                </span>
              )}
              <div className="hidden sm:text-right leading-tight">
                <p className="text-[12px] text-slate-800">{user?.username}</p>
                <p className="text-[11px] text-slate-500">{ROLES[user?.role] || user?.role}</p>
              </div>
              <div className="h-8 w-8 rounded-sm border border-slate-300 text-slate-700 text-[11px]
                              font-medium grid place-items-center">
                {initials(user?.username || 'AD')}
              </div>
              <button onClick={onLogout} title="Sign out"
                className="p-2 rounded-sm text-slate-500 hover:bg-slate-200/60 hover:text-slate-800">
                <LogOut size={16} strokeWidth={1.75} />
              </button>
            </div>
          </div>
        </header>

        <main className="px-4 sm:px-6 py-5 sm:py-6 max-w-[1600px] mx-auto">{children}</main>
      </div>
    </div>
  );
}

