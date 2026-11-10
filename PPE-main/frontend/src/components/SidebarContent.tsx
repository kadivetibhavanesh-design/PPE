import React from 'react';
import { NavLink } from 'react-router-dom';
import { Tooltip, IconButton } from '@mui/material';
import { ShieldCheck, PanelLeftClose, PanelLeftOpen, X } from 'lucide-react';
import { NAV_ITEMS, APP_NAME } from '@/utils/navigation';

interface SidebarContentProps {
  /** Icon-only rendering (desktop collapsed state). */
  collapsed?: boolean;
  /** Called after a nav link is clicked (used to close the mobile drawer). */
  onNavigate?: () => void;
  /** Desktop: toggles collapsed state. Omit to hide the toggle. */
  onToggleCollapse?: () => void;
  /** Mobile: shows a close button in the header. */
  onClose?: () => void;
}

export const SidebarContent: React.FC<SidebarContentProps> = ({
  collapsed = false,
  onNavigate,
  onToggleCollapse,
  onClose,
}) => (
  <div className="flex h-full flex-col bg-white">
    {/* Brand */}
    <div
      className={`flex h-16 shrink-0 items-center border-b border-slate-200 ${
        collapsed ? 'justify-center px-2' : 'justify-between px-4'
      }`}
    >
      <div className="flex items-center gap-3 overflow-hidden">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-900 text-white shadow-sm">
          <ShieldCheck className="h-6 w-6 text-blue-400" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-base font-bold leading-tight tracking-tight text-slate-900">
              {APP_NAME}
            </p>
            <p className="truncate text-[11px] font-medium text-slate-500">PPE Safety Monitor</p>
          </div>
        )}
      </div>
      {onClose && (
        <IconButton size="small" onClick={onClose} aria-label="Close navigation">
          <X className="h-5 w-5 text-slate-500" />
        </IconButton>
      )}
    </div>

    {/* Navigation */}
    <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Main navigation">
      {NAV_ITEMS.map(({ label, path, icon: Icon }) => (
        // The Tooltip child must be a plain element: MUI merges `className` as a string,
        // which silently drops NavLink's function-valued className.
        <Tooltip key={path} title={collapsed ? label : ''} placement="right" arrow>
          <div>
            <NavLink
              to={path}
              end={path === '/'}
              onClick={onNavigate}
              aria-label={label}
              className={({ isActive }) =>
                [
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  collapsed ? 'justify-center' : '',
                  isActive
                    ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-100'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                ].join(' ')
              }
            >
              <Icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          </div>
        </Tooltip>
      ))}
    </nav>

    {/* Collapse toggle (desktop only) */}
    {onToggleCollapse && (
      <div className="shrink-0 border-t border-slate-200 p-3">
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 ${
            collapsed ? 'justify-center' : ''
          }`}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-5 w-5" />
          ) : (
            <>
              <PanelLeftClose className="h-5 w-5" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    )}
  </div>
);

export default SidebarContent;

