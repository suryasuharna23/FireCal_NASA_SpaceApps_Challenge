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
  const [question, setQuestion] = useState('');
  const key = JSON.stringify([body, aoi?.label, stats?.data_version, question.trim()]);
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
        question: question.trim(),
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
        <p className="muted">
          Ask about the selected area’s satellite hotspot statistics, or leave this blank for a
          short summary.
        </p>
        <label className="ai-insight__question">
          Your question
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={500}
            rows={2}
            disabled={loading}
            placeholder="How does the latest month compare with the historical median?"
          />
        </label>
        <button
          className="btn btn--primary"
          type="button"
          onClick={generate}
          disabled={!stats || statsLoading || loading}
        >
          {loading
            ? 'Analysing…'
            : current
              ? 'Regenerate answer'
              : question.trim()
                ? 'Ask FireCal'
                : 'Generate insight'}
        </button>
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
      <p className="ai-insight__note">
        AI-generated interpretation · Source: NASA FIRMS / FireCal statistics
        {current ? ` · ${current.model}` : ''}. Hotspots are detections, not confirmed fires.
      </p>
    </Panel>
  );
}
