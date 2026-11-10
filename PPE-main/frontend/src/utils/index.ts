/**
 * Utility functions for formatting and styling PPE compliance data
 */

export function formatSeconds(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '0s';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'compliant':
      return '#10b981'; // Emerald
    case 'non_compliant':
      return '#ef4444'; // Crimson
    case 'needs_review':
      return '#f59e0b'; // Amber
    default:
      return '#64748b'; // Slate
  }
}

