/**
 * Neutral, user-facing aliases for detection models.
 * Real model names, repositories and weight files are never shown in the UI.
 */
const MODEL_ALIASES: Record<string, { name: string; summary: string }> = {
  constructelligence: {
    name: 'Detection Profile A',
    summary: 'Standard PPE detection profile. Reports missing equipment violations.',
  },
  vyra: {
    name: 'Detection Profile B',
    summary: 'Extended PPE detection profile. Verifies both worn and missing equipment.',
  },
};

export function getModelAlias(modelId?: string | null, fallbackIndex = 0): string {
  if (modelId && MODEL_ALIASES[modelId]) return MODEL_ALIASES[modelId].name;
  return `Detection Profile ${String.fromCharCode(65 + fallbackIndex)}`;
}

export function getModelSummary(modelId?: string | null): string {
  return (modelId && MODEL_ALIASES[modelId]?.summary) || 'PPE detection profile.';
}
