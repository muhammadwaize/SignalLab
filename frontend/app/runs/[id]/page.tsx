
'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  LoaderCircle, MessageSquareText, Video, TrendingUp,
  ShoppingBag, Target
} from 'lucide-react';

import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Legend
} from 'recharts';

import { Shell } from '@/components/shell';
import { Metric, Section, ErrorNote } from '@/components/ui';
import { api, number } from '@/lib/api';
import { DataTable } from '@/components/data-table';

const COLORS = ['#16a36a', '#e05252', '#8b5cf6', '#f59e0b', '#3b82f6', '#06b6d4'];

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();

  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let timer: any;
    let stopped = false;

    const load = async () => {
      try {
        const x = await api<any>(`/api/runs/${id}`);

        if (stopped) return;

        setData(x);

    if (['queued', 'running'].includes(x.run.status)) {
      timer = setTimeout(load, 1000);
    }
      } catch (e: any) {
        setError(e.message);
      }
    };

    load();

    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [id]);

const r = data?.run;
const res = data?.results;

const progressPercent = r
  ? r.status === 'done'
    ? 100
    : Math.min(100, Math.max(0, Number(r.progress || 0) * 100))
  : 0;

  const sentimentData = res ? [
    { name: 'Positive', value: res.metrics.positive || 0 },
    {
      name: 'Negative',
      value: res.metrics.negative || 0
    },
    {
      name: 'Neutral',
      value: Math.max(
        0,
        100 - (res.metrics.positive || 0) - (res.metrics.negative || 0)
      )
    }
  ] : [];

  const typeData = (res?.types || []).filter(
    (item: any) => item.comments > 0
  );

  const topicData = (res?.topics || []).slice(0, 8);

  const buyingData = res ? [
    { name: 'Purchased', comments: res.metrics.bought || 0 },
    { name: 'Buying intent', comments: res.metrics.want || 0 }
  ] : [];

  return (
    <Shell
      title={r ? `${r.brand} analysis` : 'Analysis run'}
      subtitle={r ? `Run #${r.id} · ${r.created_at || ''}` : 'Loading analysis details…'}
    >
      {error && <ErrorNote message={error} />}

      {!r ? (
        <div className="analysis-loader">
          <div className="loader-icon">
            <LoaderCircle className="spin" size={38} />
          </div>
          <h2>Preparing your insights</h2>
          <p>Loading your brand analysis and audience data...</p>
        </div>
      ) : (
        <>
          <div className="run-progress">
            <div className="progress-head">
              <span className={`status status-${r.status}`}>
                {r.status}
              </span>
              <b>{Math.round(progressPercent)}%</b>
            </div>

            <div className="progress-track">
              <i
                style={{
                  width: `${progressPercent}%`,
                  transition: 'width 0.6s ease'
                }}
              />
            </div>

            <p>{r.message || 'Preparing analysis'}</p>

            {r.error && <ErrorNote message={r.error} />}
          </div>

          {res && (
            <>
              <div className="metric-grid">
                <Metric
                  label="Comments"
                  value={number(res.metrics.comments)}
                  icon={<MessageSquareText size={17} />}
                />

                <Metric
                  label="Videos"
                  value={number(res.metrics.videos)}
                  icon={<Video size={17} />}
                />

                <Metric
                  label="Positive comments"
                  value={`${res.metrics.positive}%`}
                  icon={<TrendingUp size={17} />}
                />

                <Metric
                  label="Negative comments"
                  value={`${res.metrics.negative}%`}
                  icon={<Target size={17} />}
                />
              </div>

              <div className="charts-grid">
                <Section
                  title="Sentiment distribution"
                  detail="Overall audience reaction"
                >
                  {sentimentData.some((item: any) => item.value > 0) ? (
                    <>
                      <div className="chart-container">
                        <ResponsiveContainer width="100%" height={260}>
                          <PieChart>
                            <Pie
                              data={sentimentData}
                              dataKey="value"
                              nameKey="name"
                              cx="50%"
                              cy="50%"
                              innerRadius={65}
                              outerRadius={95}
                              paddingAngle={4}
                            >
                              {sentimentData.map((item: any, index: number) => (
                                <Cell
                                  key={item.name}
                                  fill={COLORS[index]}
                                />
                              ))}
                            </Pie>
                            <Tooltip formatter={(value) => `${value}%`} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>

                      <div className="chart-legend">
                        {sentimentData.map((item: any, index: number) => (
                          <div key={item.name}>
                            <span
                              className="legend-dot"
                              style={{ background: COLORS[index] }}
                            />
                            {item.name}
                            <b>{item.value}%</b>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p>No sentiment data available.</p>
                  )}
                </Section>

                <Section
                  title="Comment categories"
                  detail="What customers are talking about"
                >
                  {typeData.length ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <PieChart>
                        <Pie
                          data={typeData}
                          dataKey="comments"
                          nameKey="comment_type"
                          cx="50%"
                          cy="50%"
                          outerRadius={105}
                          paddingAngle={3}
                        >
                          {typeData.map((item: any, index: number) => (
                            <Cell
                              key={item.comment_type}
                              fill={COLORS[index % COLORS.length]}
                            />
                          ))}
                        </Pie>
                        <Tooltip />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <p>No comment categories available.</p>
                  )}
                </Section>

                <Section
                  title="Topic comparison"
                  detail="Most discussed customer topics"
                >
                  {topicData.length ? (
                    <ResponsiveContainer width="100%" height={320}>
                      <BarChart
                        data={topicData}
                        layout="vertical"
                        margin={{ left: 15, right: 20 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis type="number" />
                        <YAxis
                          dataKey="topic"
                          type="category"
                          width={100}
                          tick={{ fontSize: 12 }}
                        />
                        <Tooltip />
                        <Bar
                          dataKey="comments"
                          fill="#8b5cf6"
                          radius={[0, 6, 6, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <p>No topic data available.</p>
                  )}
                </Section>

                <Section
                  title="Buying signals"
                  detail="Purchase activity and buying interest"
                >
                  <div className="buying-metrics">
                    <div>
                      <ShoppingBag size={20} />
                      <span>Purchased</span>
                      <strong>{number(res.metrics.bought)}</strong>
                    </div>

                    <div>
                      <Target size={20} />
                      <span>Buying intent</span>
                      <strong>{number(res.metrics.want)}</strong>
                    </div>
                  </div>

                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={buyingData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Bar
                        dataKey="comments"
                        fill="#16a36a"
                        radius={[6, 6, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </Section>
              </div>

              <Section
                title="Topic summary"
                detail="Themes appearing in the collected comments"
              >
                <DataTable
                  columns={Object.keys(res.topics?.[0] || {})}
                  rows={res.topics || []}
                  total={(res.topics || []).length}
                  page={1}
                  pages={1}
                  onPage={() => {}}
                />
              </Section>

              <Section title="Analysed videos">
                <DataTable
                  columns={[
                    'title',
                    'channel',
                    'views',
                    'likes',
                    'comments_count',
                    'content_type'
                  ]}
                  rows={res.videos || []}
                  total={(res.videos || []).length}
                  page={1}
                  pages={1}
                  onPage={() => {}}
                />
              </Section>

              <div className="quick-links">
                <Link className="button button-secondary" href="/optimizer">
                  Open ad optimizer
                </Link>

                <Link className="button button-secondary" href="/project3">
                  Open audience insights
                </Link>
              </div>
            </>
          )}
        </>
      )}
    </Shell>
  );
}
