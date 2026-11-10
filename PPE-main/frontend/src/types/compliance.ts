/**
 * Types for the PPE Compliance Dashboard (UI only; demo data until backend integration).
 */

export type ComplianceStandardStatus =
  | 'Compliant'
  | 'Non-Compliant'
  | 'Needs Review'
  | 'Uncertain'
  | 'Not Verifiable';

export type PPEStandardCategory =
  | 'Hardhat'
  | 'Safety Vest'
  | 'Gloves'
  | 'Goggles'
  | 'Mask'
  | 'Safety Shoes';

export interface PPECategoryComplianceSummary {
  category: PPEStandardCategory;
  complianceRate: number;
  compliantCount: number;
  violationCount: number;
  reviewCount: number;
  totalMonitored: number;
}

export interface WorkerComplianceRow {
  workerId: number;
  name: string;
  role: string;
  zone: string;
  firstSeen: string;
  lastSeen: string;
  hardhat: ComplianceStandardStatus;
  safetyVest: ComplianceStandardStatus;
  gloves: ComplianceStandardStatus;
  goggles: ComplianceStandardStatus;
  mask: ComplianceStandardStatus;
  safetyShoes: ComplianceStandardStatus;
  overallStatus: ComplianceStandardStatus;
}

export interface ComplianceSummaryMetrics {
  overallComplianceRate: number;
  compliantWorkersCount: number;
  nonCompliantWorkersCount: number;
  reviewWorkersCount: number;
  totalWorkersCount: number;
}

