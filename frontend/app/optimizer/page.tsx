
'use client';

import { useEffect, useState } from 'react';
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend
} from 'recharts';

import { Shell } from '@/components/shell';
import { Metric, Section, Empty, ErrorNote } from '@/components/ui';
import { api, API, money, number } from '@/lib/api';
import { DataTable } from '@/components/data-table';
import { Megaphone, Save, LoaderCircle } from 'lucide-react';

const COLORS = [
  '#8b5cf6', '#16a36a', '#f59e0b',
  '#3b82f6', '#e05252', '#06b6d4'
];

function getChartData(rows: any[], type: 'source' | 'video') {
  if (!Array.isArray(rows) || !rows.length) {
    return { data: [], valueLabel: 'Value' };
  }

  const keys = Object.keys(rows[0]);

  const labelCandidates = type === 'source'
    ? ['source', 'discovery_source', 'name', 'category', 'video_title', 'title']
    : ['title', 'video_title', 'video', 'name', 'video_id'];

  const valueCandidates = [
    'recommended_budget_rs',
    'allocation_rs',
    'budget_rs',
    'allocated_budget',
    'recommended_budget',
    'budget',
    'allocation',
    'amount',
    'spend',
    'comments_scraped',
    'comments',
    'say_bought',
    'named_any',
    'count'
  ];

  const labelKey =
    labelCandidates.find(key => keys.includes(key)) ||
    keys.find(key => typeof rows[0][key] === 'string') ||
    keys[0];

  const valueKey =
    valueCandidates.find(key => keys.includes(key)) ||
    keys.find(key =>
      rows.some(row =>
        row[key] !== null &&
        row[key] !== '' &&
        Number.isFinite(Number(String(row[key]).replace(/,/g, '')))
      )
    );

  if (!valueKey) {
    return { data: [], valueLabel: 'Value' };
  }

  const data = rows.map((row, index) => ({
    name: String(row[labelKey] ?? `Item ${index + 1}`),
    value: Number(String(row[valueKey] ?? 0).replace(/,/g, ''))
  })).filter(item => Number.isFinite(item.value) && item.value > 0);

  return {
    data,
    valueLabel: valueKey.replace(/_/g, ' ')
  };
}

export default function Optimizer() {
  const [runs, setRuns] = useState<any[]>([]);
  const [runId, setRunId] = useState('');
  const [data, setData] = useState<any>(null);
  const [budget, setBudget] = useState(1000000);
  const [minShare, setMinShare] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    api<any>('/api/runs')
      .then(x => {
        const done = x.runs.filter((r: any) => r.status === 'done');
        setRuns(done);

        if (done.length) {
          setRunId(String(done[0].id));
        }
      })
      .catch(e => setError(e.message));
  }, []);

  useEffect(() => {
    if (!runId) return;

    api<any>(`/api/optimizer/${runId}?min_share=${minShare / 100}`)
      .then(x => {
        setData(x);
        setBudget(x.budget || 1000000);
        setMinShare((x.min_share ?? 0.05) * 100);
      })
      .catch(e => setError(e.message));
  }, [runId]);

  async function save() {
    setBusy(true);
    setError('');
    setNotice('');

    try {
      await api(`/api/optimizer/${runId}`, {
        method: 'POST',
        body: JSON.stringify({ budget_rs: budget })
      });

      setNotice('Budget settings saved.');

      const x = await api<any>(
        `/api/optimizer/${runId}?min_share=${minShare / 100}`
      );

      setData(x);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const sourceChart = getChartData(data?.source_alloc || [], 'source');
  const videoChart = getChartData(data?.video_alloc || [], 'video');

  return (
    <Shell
      title="Ad optimizer"
      subtitle="Use customer discovery and purchase signals to guide advertising budget allocation."
    >
      {error && <ErrorNote message={error} />}

      <div className="control-row">
        <label className="inline-field">
          <span>Analysis run</span>
          <select
            value={runId}
            onChange={e => setRunId(e.target.value)}
          >
            {runs.map(r => (
              <option key={r.id} value={r.id}>
                #{r.id} · {r.brand}
              </option>
            ))}
          </select>
        </label>

        {notice && <span className="success-text">{notice}</span>}
      </div>

      {!runs.length ? (
        <Empty
          title="No completed analysis"
          detail="Complete a sentiment analysis first. The optimizer uses its collected comments."
        />
      ) : data && (
        <>
          <div className="budget-panel">
            <div>
              <div className="eyebrow">TOTAL ADVERTISING BUDGET</div>
              <h2>{money(budget)}</h2>
              <p>
                Recommendations inferred from the selected run’s comments.
              </p>
            </div>

            <div className="budget-controls">
              <label className="field">
                <span>Budget in PKR</span>
                <input
                  type="number"
                  min="10000"
                  value={budget}
                  onChange={e => setBudget(+e.target.value)}
                />
              </label>

              <label className="field">
                <span>Minimum share (%)</span>
                <input
                  type="number"
                  min="0"
                  max="15"
                  step="0.5"
                  value={minShare}
                  onChange={e =>
                    setMinShare(Math.max(0, Math.min(15, +e.target.value)))
                  }
                />
              </label>

              <button
                className="button button-primary"
                onClick={save}
                disabled={busy}
              >
                {busy
                  ? <LoaderCircle size={15} className="spin" />
                  : <Save size={15} />}
                Save budget
              </button>
            </div>
          </div>

          <div className="metric-grid three">
            <Metric
              label="Comments with discovery data"
              value={number(data.coverage?.named_any)}
              detail={`${data.coverage?.['named_any_%'] || 0}% of comments`}
            />

            <Metric
              label="Purchase claims"
              value={number(data.coverage?.say_bought)}
            />

            <Metric
              label="Ad / influencer mentions"
              value={number(data.coverage?.friend_ad_influencer)}
            />
          </div>

          <div className="charts-grid">
            <Section
              title="Budget allocation"
              detail="Distribution across discovery sources"
            >
              {sourceChart.data.length ? (
                <>
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height={280}>
                      <PieChart>
                        <Pie
                          data={sourceChart.data}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          innerRadius={65}
                          outerRadius={100}
                          paddingAngle={3}
                        >
                          {sourceChart.data.map((item, index) => (
                            <Cell
                              key={item.name}
                              fill={COLORS[index % COLORS.length]}
                            />
                          ))}
                        </Pie>
                        <Tooltip />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="chart-legend">
                    Based on: {sourceChart.valueLabel}
                  </p>
                </>
              ) : (
                <Empty
                  title="No chart data available"
                  detail="There are no positive numeric source allocation values to display."
                />
              )}
            </Section>

            <Section
              title="Video comparison"
              detail="Compare recommendations across videos"
            >
              {videoChart.data.length ? (
                <>
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart
                        data={videoChart.data}
                        margin={{ top: 10, right: 15, left: 0, bottom: 45 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="name"
                          angle={-25}
                          textAnchor="end"
                          interval={0}
                          height={75}
                          tick={{ fontSize: 10 }}
                        />
                        <YAxis />
                        <Tooltip />
                        <Bar
                          dataKey="value"
                          name={videoChart.valueLabel}
                          fill="#8b5cf6"
                          radius={[6, 6, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="chart-legend">
                    Based on: {videoChart.valueLabel}
                  </p>
                </>
              ) : (
                <Empty
                  title="No chart data available"
                  detail="There are no positive numeric video allocation values to display."
                />
              )}
            </Section>
          </div>

          <Section
            title="Budget by discovery source"
            detail="Suggested allocation based on observed comment signals"
            action={
              <a
                className="button button-quiet button-small"
                href={`${API}/optimizer/${runId}/csv?kind=sources`}
              >
                Export CSV
              </a>
            }
          >
            {data.source_alloc?.length ? (
              <DataTable
                columns={Object.keys(data.source_alloc[0])}
                rows={data.source_alloc}
                total={data.source_alloc.length}
                page={1}
                pages={1}
                onPage={() => {}}
              />
            ) : (
              <Empty
                title="No source allocation yet"
                detail="Collected comments did not contain enough source information for this breakdown."
              />
            )}
          </Section>

          <Section
            title="Budget by video"
            detail="Videos associated with stronger purchase and discovery signals"
            action={
              <a
                className="button button-quiet button-small"
                href={`${API}/optimizer/${runId}/csv?kind=videos`}
              >
                Export CSV
              </a>
            }
          >
            {data.video_alloc?.length ? (
              <DataTable
                columns={Object.keys(data.video_alloc[0])}
                rows={data.video_alloc}
                total={data.video_alloc.length}
                page={1}
                pages={1}
                onPage={() => {}}
              />
            ) : (
              <Empty
                title="No video allocation yet"
                detail="No eligible video-level signals were found for this run."
              />
            )}
          </Section>

          <p className="disclaimer">
            These are comment-derived planning recommendations, not verified
            ad conversions, platform traffic or campaign performance.
          </p>
        </>
      )}
    </Shell>
  );
}
