import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Drawer } from '@mui/material';
import SidebarContent from '@/components/SidebarContent';
import TopBar from '@/components/TopBar';
import { APP_NAME, getNavItem } from '@/utils/navigation';

const SIDEBAR_WIDTH = 264;
const SIDEBAR_COLLAPSED_WIDTH = 76;

export const DashboardLayout: React.FC = () => {
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const title = getNavItem(pathname)?.label ?? APP_NAME;

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      {/* Desktop sidebar (collapsible) */}
      <aside
        className="sticky top-0 hidden h-screen shrink-0 border-r border-slate-200 transition-[width] duration-200 lg:block"
        style={{ width: collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH }}
      >
        <SidebarContent collapsed={collapsed} onToggleCollapse={() => setCollapsed((c) => !c)} />
      </aside>

      {/* Mobile / tablet drawer */}
      <Drawer
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{ display: { xs: 'block', lg: 'none' } }}
        slotProps={{ paper: { sx: { width: SIDEBAR_WIDTH, maxWidth: '85vw' } } }}
      >
        <SidebarContent onNavigate={() => setMobileOpen(false)} onClose={() => setMobileOpen(false)} />
      </Drawer>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar title={title} onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;

