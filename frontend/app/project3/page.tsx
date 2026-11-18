
'use client';

import { useEffect, useState } from 'react';

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts';

import { Shell } from '@/components/shell';
import { Metric, Section, Empty, ErrorNote } from '@/components/ui';
import { api, number } from '@/lib/api';
import { DataTable } from '@/components/data-table';
import { Play, LoaderCircle } from 'lucide-react';

const COLORS = {
  purple: '#8b5cf6',
  green: '#16a36a',
  red: '#e05252',
  orange: '#f59e0b',
  blue: '#3b82f6'
};

export default function Project3() {
  const [runs, setRuns] = useState<any[]>([]);
  const [runId, setRunId] = useState('');
  const [data, setData] = useState<any>(null);
  const [k, setK] = useState(4);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load(id: string) {
    setRunId(id);
    setError('');
    setData(null);

    if (id) {
      try {
        setData(await api(`/api/project3/${id}`));
      } catch (e: any) {
        setError(e.message);
      }
    }
  }

  useEffect(() => {
    api<any>('/api/runs')
      .then(x => {
        const done = x.runs.filter(
          (r: any) => r.status === 'done'
        );

        setRuns(done);

        if (done.length) {
          load(String(done[0].id));
        }
      })
      .catch(e => setError(e.message));
  }, []);

  async function run() {
    setBusy(true);
    setError('');
    setNotice('');

    try {
      const x = await api<any>(
        `/api/project3/${runId}/run`,
        {
          method: 'POST',
          body: JSON.stringify({ n_clusters: k })
        }
      );

      setData(x);
      setNotice(x.message || 'Project 3 analysis complete.');

      if (x.error) {
        setError(x.error);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const profiles = data?.profiles || [];
  const unusual = data?.unusual || [];

  const clusterDistribution = profiles.map((item: any) => ({
    name: item.label || `Cluster ${item.cluster_no}`,
    comments: Number(item.comment_count || 0)
  }));

  const sentimentData = profiles.map((item: any) => {
    const positive = Number(item.positive_pct || 0);
    const negative = Number(item.negative_pct || 0);

    return {
      name: item.label || `Cluster ${item.cluster_no}`,
      Positive: positive,
      Negative: negative,
      Neutral: Math.max(0, 100 - positive - negative)
    };
  });

  const buyingData = profiles.map((item: any) => ({
    name: item.label || `Cluster ${item.cluster_no}`,
    Purchased: Number(item.purchase_pct || 0),
    'Buying intent': Number(item.intent_pct || 0)
  }));

  const unusualData = unusual
    .filter((item: any) =>
      Number.isFinite(Number(item.engagement_rate_pct))
    )
    .slice(0, 10)
    .map((item: any, index: number) => ({
      name: item.title
        ? `${item.title.slice(0, 24)}${item.title.length > 24 ? '…' : ''}`
        : `Post ${index + 1}`,
      engagement: Number(item.engagement_rate_pct || 0)
    }));

  return (
    <Shell
      title="Audience insights"
      subtitle="Explore comment-pattern clusters and detect posts with unusual performance signals."
    >
      {error && <ErrorNote message={error} />}

      <div className="control-row">
        <label className="inline-field">
          <span>Analysis run</span>
          <select
            value={runId}
            onChange={e => load(e.target.value)}
          >
            {runs.map(r => (
              <option key={r.id} value={r.id}>
                #{r.id} · {r.brand}
              </option>
            ))}
          </select>
        </label>

        <label className="inline-field">
          <span>Number of clusters</span>
          <select
            value={k}
            onChange={e => setK(+e.target.value)}
          >
            {[2, 3, 4, 5, 6, 7, 8].map(v => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>

        <button
          className="button button-primary"
          onClick={run}
          disabled={!runId || busy}
        >
          {busy
            ? <LoaderCircle size={15} className="spin" />
            : <Play size={15} />}
          Run Project 3
        </button>
      </div>

      {notice && (
        <div className="success-note">{notice}</div>
      )}

      {!runs.length ? (
        <Empty
          title="No completed analysis"
          detail="Run sentiment analysis first to prepare comment and post data."
        />
      ) : data && (
        <>
          <div className="metric-grid three">
            <Metric
              label="Comments available"
              value={number(data.comment_count)}
            />

            <Metric
              label="Comments clustered"
              value={number(data.clustered_count)}
            />

            <Metric
              label="Unusual posts flagged"
              value={number(unusual.length)}
            />
          </div>

          <div className="charts-grid">
            <Section
              title="Cluster distribution"
              detail="Number of comments assigned to each audience pattern"
            >
              {clusterDistribution.length ? (
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={290}>
                    <BarChart
                      data={clusterDistribution}
                      margin={{ top: 10, right: 15, left: 0, bottom: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="name"
                        tick={{ fontSize: 11 }}
                      />
                      <YAxis />
                      <Tooltip />
                      <Bar
                        dataKey="comments"
                        name="Comments"
                        fill={COLORS.purple}
                        radius={[6, 6, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <Empty
                  title="No cluster data"
                  detail="Run the clustering analysis to generate this chart."
                />
              )}
            </Section>

            <Section
              title="Sentiment by cluster"
              detail="Positive, negative and neutral comment percentages"
            >
              {sentimentData.length ? (
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={290}>
                    <BarChart
                      data={sentimentData}
                      margin={{ top: 10, right: 15, left: 0, bottom: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="name"
                        tick={{ fontSize: 11 }}
                      />
                      <YAxis domain={[0, 100]} unit="%" />
                      <Tooltip formatter={(value) => `${value}%`} />
                      <Legend />
                      <Bar
                        dataKey="Positive"
                        stackId="sentiment"
                        fill={COLORS.green}
                      />
                      <Bar
                        dataKey="Neutral"
                        stackId="sentiment"
                        fill={COLORS.orange}
                      />
                      <Bar
                        dataKey="Negative"
                        stackId="sentiment"
                        fill={COLORS.red}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <Empty
                  title="No sentiment data"
                  detail="Cluster sentiment information is not available."
                />
              )}
            </Section>

            <Section
              title="Purchase interest by cluster"
              detail="Compare purchase claims with buying intent"
            >
              {buyingData.length ? (
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart
                      data={buyingData}
                      margin={{ top: 10, right: 15, left: 0, bottom: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="name"
                        tick={{ fontSize: 11 }}
                      />
                      <YAxis unit="%" />
                      <Tooltip formatter={(value) => `${value}%`} />
                      <Legend />
                      <Bar
                        dataKey="Purchased"
                        fill={COLORS.green}
                        radius={[5, 5, 0, 0]}
                      />
                      <Bar
                        dataKey="Buying intent"
                        fill={COLORS.blue}
                        radius={[5, 5, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <Empty
                  title="No purchase data"
                  detail="Purchase and intent percentages are not available."
                />
              )}
            </Section>

            <Section
              title="Unusual post engagement"
              detail="Engagement rates of posts flagged by the anomaly detector"
            >
              {unusualData.length ? (
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={320}>
                    <BarChart
                      data={unusualData}
                      layout="vertical"
                      margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" unit="%" />
                      <YAxis
                        dataKey="name"
                        type="category"
                        width={130}
                        tick={{ fontSize: 10 }}
                      />
                      <Tooltip formatter={(value) => `${value}%`} />
                      <Bar
                        dataKey="engagement"
                        name="Engagement rate"
                        fill={COLORS.orange}
                        radius={[0, 6, 6, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <Empty
                  title="No unusual posts to chart"
                  detail="The anomaly detector has not returned posts with engagement-rate data."
                />
              )}
            </Section>
          </div>

          <Section
            title="Audience pattern clusters"
            detail="Clusters describe comment patterns, not unique individual people."
          >
            <DataTable
              columns={[
                'cluster_no',
                'label',
                'comment_count',
                'positive_pct',
                'negative_pct',
                'purchase_pct',
                'intent_pct',
                'avg_sentiment',
                'top_topic',
                'top_language'
              ]}
              rows={profiles}
              total={profiles.length}
              page={1}
              pages={1}
              onPage={() => {}}
              downloadUrl={`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/project3/${runId}/csv?kind=clusters`}
            />
          </Section>

          <Section
            title="Unusual posts"
            detail="Statistical outliers across views, likes, engagement and comment signals."
          >
            <DataTable
              columns={[
                'title',
                'channel',
                'views',
                'likes',
                'comments_count',
                'engagement_rate_pct',
                'anomaly_count',
                'reasons',
                'data_origin'
              ]}
              rows={unusual}
              total={unusual.length}
              page={1}
              pages={1}
              onPage={() => {}}
              downloadUrl={`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/project3/${runId}/csv?kind=posts`}
            />
          </Section>
        </>
      )}
    </Shell>
  );
}
