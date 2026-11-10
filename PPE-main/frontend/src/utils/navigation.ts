import {
  LayoutDashboard,
  Video,
  Users,
  HardHat,
  TriangleAlert,
  History,
  FileText,
  Settings,
} from 'lucide-react';
import type { NavItem } from '@/types/navigation';

/** Single source of truth for sidebar items, routes and page metadata. */
export const NAV_ITEMS: NavItem[] = [
  {
    label: 'Overview',
    path: '/',
    icon: LayoutDashboard,
    description: 'High-level summary of site safety status, active workers and recent alerts.',
  },
  {
    label: 'Live Monitoring',
    path: '/live-monitoring',
    icon: Video,
    description: 'Real-time camera feed with PPE detections and worker tracking.',
  },
  {
    label: 'Workers',
    path: '/workers',
    icon: Users,
    description: 'Tracked workers, their lifecycle state and current compliance status.',
  },
  {
    label: 'PPE Compliance',
    path: '/ppe-compliance',
    icon: HardHat,
    description: 'Per-worker PPE compliance evaluation across required equipment categories.',
  },
  {
    label: 'Violations',
    path: '/violations',
    icon: TriangleAlert,
    description: 'Confirmed PPE violations, running timers and active alarms.',
  },
  {
    label: 'Incident History',
    path: '/incident-history',
    icon: History,
    description: 'Searchable record of past violation events and their resolution.',
  },
  {
    label: 'Reports',
    path: '/reports',
    icon: FileText,
    description: 'Safety summaries and exportable compliance reports.',
  },
  {
    label: 'Settings',
    path: '/settings',
    icon: Settings,
    description: 'Monitoring, alarm and camera configuration.',
  },
];

export const APP_NAME = 'SafeVision AI';

export function getNavItem(path: string): NavItem | undefined {
  if (path === '/notifications') {
    return {
      label: 'Notification Center',
      path: '/notifications',
      icon: Settings,
      description: 'System event log, violation alerts and hardware notifications.',
    };
  }
  return NAV_ITEMS.find((item) => item.path === path);
}

