import type { LucideIcon } from 'lucide-react';

/** A single entry in the application navigation (sidebar, routes, page titles). */
export interface NavItem {
  /** Visible label and page title. */
  label: string;
  /** Route path (Overview is the index route "/"). */
  path: string;
  icon: LucideIcon;
  /** Short description of the page's purpose. */
  description: string;
}

