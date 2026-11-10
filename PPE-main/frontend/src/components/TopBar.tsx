import React from 'react';
import { IconButton } from '@mui/material';
import { Menu, UserRound } from 'lucide-react';
import NotificationCenter from '@/components/NotificationCenter';

interface TopBarProps {
  title: string;
  /** Opens the mobile navigation drawer. */
  onMenuClick: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ title, onMenuClick }) => {
  return (
    <header className="glass-panel sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-slate-200 px-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-2">
        <IconButton
          onClick={onMenuClick}
          aria-label="Open navigation"
          className="lg:!hidden"
          edge="start"
          size="small"
        >
          <Menu className="h-6 w-6 text-slate-700" />
        </IconButton>
        <h1 className="truncate text-lg font-semibold tracking-tight text-slate-900 sm:text-xl">
          {title}
        </h1>
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        {/* Real-Time Notification Center */}
        <NotificationCenter />

        <div className="flex items-center gap-2 border-l border-slate-200 pl-2 sm:pl-3">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-200 text-slate-600"
            aria-label="Local operator profile"
          >
            <UserRound className="h-4 w-4" />
          </div>
          <div className="hidden leading-tight md:block">
            <p className="text-sm font-semibold text-slate-900">Safety Officer</p>
            <p className="text-[11px] text-slate-500">Local Operator</p>
          </div>
        </div>
      </div>
    </header>
  );
};

export default TopBar;
