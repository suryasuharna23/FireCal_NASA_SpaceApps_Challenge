import { useState } from 'react';
import { apiPost } from '../api/client';
import { useStats, useSeriesRequest } from '../api/queries';
import { useAppStore } from '../state/useAppStore';
import { Panel } from './Panel';

interface InsightResponse {
  text: string;
  model: string;
  data_version: string;
}

export function AiInsight() {
  const aoi = useAppStore((s) => s.aoi);
  const body = useSeriesRequest();
  const { data: stats, isFetching: statsLoading } = useStats();
  const [result, setResult] = useState<InsightResponse | null>(null);
  const [requestKey, setRequestKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const key = JSON.stringify([body, aoi?.label, stats?.data_version]);
  const current = requestKey === key ? result : null;

  async function generate() {
    if (!body || !stats || loading) return;
    setLoading(true);
    setError('');
    setResult(null);
    setRequestKey(key);
    try {
      const insight = await apiPost<InsightResponse>('/insights', {
        ...body,
        region_name: aoi?.label ?? 'Selected area',
      });
      setResult(insight);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'AI analysis failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Panel title="AI insight" className="ai-insight">
      <div className="ai-insight__content">
        <div>
          <p className="muted">
            A short interpretation of the selected area’s satellite hotspot statistics.
          </p>
          {current && (
            <p className="ai-insight__text" aria-live="polite">
              {current.text}
            </p>
          )}
          {error && requestKey === key && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
        </div>
        <button
          className="btn btn--primary"
          type="button"
          onClick={generate}
          disabled={!stats || statsLoading || loading}
        >
          {loading ? 'Analysing…' : current ? 'Regenerate insight' : 'Generate insight'}
        </button>
      </div>
      <p className="ai-insight__note">
        AI-generated interpretation · Source: NASA FIRMS / FireCal statistics
        {current ? ` · ${current.model}` : ''}. Hotspots are detections, not confirmed fires.
      </p>
    </Panel>
  );
}
