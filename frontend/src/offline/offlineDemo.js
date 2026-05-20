import { OFFLINE_SCENARIOS } from './scenarios';

/** True when building/running the offline mobile bundle (.env.mobile) */
export const isOfflineMode = () => import.meta.env.VITE_OFFLINE_DEMO === 'true';

export function getOfflineScenario(scenarioKey) {
  const key = (scenarioKey || 'idle').toLowerCase().trim();
  return OFFLINE_SCENARIOS[key] ?? OFFLINE_SCENARIOS.idle;
}

export function formatComparisonForUi(comparison) {
  if (!comparison) return null;
  if (comparison.baseline?.latency_ms != null) return comparison;
  return {
    baseline: {
      latency_ms: String(comparison.detection_time?.baseline ?? '—').replace(/[^\d.]/g, '') || '4200',
      detection: comparison.accuracy?.baseline ?? 'Keyword match',
    },
    ciro: {
      latency_ms: String(comparison.detection_time?.ciro ?? '28').replace(/[^\d.]/g, '') || '28',
      detection: comparison.accuracy?.ciro ?? 'CIRO fusion',
    },
    impact_summary: comparison.overall?.improvement ?? 'Validated automated response',
  };
}
