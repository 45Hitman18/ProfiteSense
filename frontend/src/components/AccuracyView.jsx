import React, { useState, useEffect } from 'react';
import { Target, CheckCircle2, ShieldCheck, BarChart2, Info, AlertTriangle, RefreshCw, Database, TrendingUp } from 'lucide-react';

const MANDATORY_DISCLAIMER = "AI/model estimate — not investment advice. Past accuracy does not guarantee future returns.";

function AccBar({ value, color, max = 100 }) {
  const pct = value != null ? Math.min(Math.max(value, 0), max) : 0;
  return (
    <div style={{ width: '100%', height: '8px', background: '#1e293b', borderRadius: '4px', overflow: 'hidden' }}>
      <div style={{ width: `${pct}%`, height: '100%', backgroundColor: color, borderRadius: '4px', transition: 'width 0.6s ease' }} />
    </div>
  );
}

function MetricCard({ label, value, subtitle, color, borderColor }) {
  const isInsufficient = value == null;
  return (
    <div className="glass-card" style={{ padding: '20px', borderLeft: `4px solid ${borderColor || color}` }}>
      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </span>
      <div className="font-mono" style={{ fontSize: '2rem', fontWeight: '800', color: isInsufficient ? '#64748b' : color, marginBottom: '4px' }}>
        {isInsufficient ? '—' : `${value}%`}
      </div>
      <span style={{ fontSize: '0.75rem', color: isInsufficient ? '#64748b' : 'var(--text-secondary)' }}>
        {isInsufficient ? 'Insufficient price data' : subtitle}
      </span>
    </div>
  );
}

export default function AccuracyView() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/analytics/accuracy');
      const data = await res.json();
      setMetrics(data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  const refresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  useEffect(() => { load(); }, []);

  const hasReal = metrics?.has_real_data;

  return (
    <div>
      {/* Top Banner */}
      <div className="glass-card" style={{ marginBottom: '24px', padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '38px', height: '38px', borderRadius: '10px', background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Target size={22} color="#10b981" />
            </div>
            <div>
              <h2 style={{ fontSize: '1.3rem', fontWeight: '800' }}>Real-World Backtesting Accuracy</h2>
              <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)' }}>
                Directional accuracy computed from actual post-news stock price returns. No fabricated numbers.
              </p>
            </div>
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={refresh}
            disabled={refreshing || loading}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
            Recompute
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <div className="pulse-dot" style={{ width: '20px', height: '20px', backgroundColor: '#10b981', margin: '0 auto' }} />
          <p style={{ marginTop: '16px', color: 'var(--text-secondary)' }}>Computing real backtesting accuracy from price data...</p>
        </div>
      ) : (
        <div>
          {/* Insufficient data warning */}
          {!hasReal && (
            <div style={{
              padding: '20px 24px', borderRadius: '12px', marginBottom: '24px',
              background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)',
              display: 'flex', alignItems: 'flex-start', gap: '12px'
            }}>
              <AlertTriangle size={20} color="#f59e0b" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <p style={{ fontWeight: '700', color: '#fbbf24', marginBottom: '4px' }}>
                  INSUFFICIENT DATA — Real accuracy cannot be computed yet
                </p>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                  {metrics?.message || 'No stock price data found. To enable real backtesting:'}<br />
                  <strong>1.</strong> Go to <strong>ML Models</strong> tab → Click <strong>Collect Prices</strong> to download 90-day OHLCV history.<br />
                  <strong>2.</strong> After collection, return here and click <strong>Recompute</strong>.<br />
                  The system will then cross-reference all {metrics?.total_evaluated || 0} analyzed articles against actual stock price movements.
                </p>
              </div>
            </div>
          )}

          {/* Top Metric Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            <MetricCard
              label="Overall Directional Accuracy"
              value={metrics?.overall_accuracy_pct}
              subtitle={`Across ${metrics?.total_evaluated || 0} evaluated predictions`}
              color="#10b981"
              borderColor="#10b981"
            />
            <MetricCard
              label="High-Impact Catalysts"
              value={metrics?.high_impact_accuracy}
              subtitle="Earnings, M&A, RBI decisions"
              color="#60a5fa"
              borderColor="#3b82f6"
            />
            <MetricCard
              label="3-Day Horizon"
              value={metrics?.horizon_3d_accuracy}
              subtitle="Peak institutional digestion window"
              color="#a78bfa"
              borderColor="#8b5cf6"
            />
            <MetricCard
              label="1-Day Horizon"
              value={metrics?.horizon_1d_accuracy}
              subtitle="Immediate market reaction"
              color="#34d399"
              borderColor="#10b981"
            />
          </div>

          {/* Horizon breakdown */}
          {hasReal && metrics?.horizons && (
            <div className="glass-card" style={{ marginBottom: '24px', padding: '24px' }}>
              <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <BarChart2 size={18} color="#60a5fa" />
                <span>Accuracy by Time Horizon & Impact Level</span>
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
                {/* By Horizon */}
                <div>
                  <h4 style={{ fontSize: '0.88rem', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                    By Time Horizon
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {[
                      { label: '1 Day — Immediate Reaction', key: '1d', color: '#3b82f6' },
                      { label: '3 Days — Drift & Follow-Through', key: '3d', color: '#10b981' },
                      { label: '5 Days — Weekly Consolidation', key: '5d', color: '#8b5cf6' },
                    ].map(({ label, key, color }) => {
                      const h = metrics.horizons[key] || {};
                      const val = h.accuracy_pct;
                      return (
                        <div key={key}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '5px' }}>
                            <span>{label}</span>
                            <span className="font-mono" style={{ fontWeight: '700', color }}>
                              {val != null ? `${val}%` : '—'} {h.total_evaluated > 0 ? `(n=${h.total_evaluated})` : ''}
                            </span>
                          </div>
                          <AccBar value={val} color={color} />
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* By Impact Level (from 3d horizon) */}
                <div>
                  <h4 style={{ fontSize: '0.88rem', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                    By Impact Level (3-Day Horizon)
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {[
                      { label: 'High Impact', key: 'HIGH', color: '#f472b6' },
                      { label: 'Medium Impact', key: 'MEDIUM', color: '#a78bfa' },
                      { label: 'Low Impact', key: 'LOW', color: '#38bdf8' },
                    ].map(({ label, key, color }) => {
                      const ia = metrics?.horizons?.['3d']?.impact_accuracy?.[key] || {};
                      const val = ia.accuracy_pct;
                      return (
                        <div key={key}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '5px' }}>
                            <span>{label}</span>
                            <span className="font-mono" style={{ fontWeight: '700', color }}>
                              {val != null ? `${val}%` : '—'} {ia.n > 0 ? `(n=${ia.n})` : ''}
                            </span>
                          </div>
                          <AccBar value={val} color={color} />
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Sector Accuracy (3d horizon) */}
          {hasReal && metrics?.horizons?.['3d']?.sector_accuracy && (() => {
            const sectorAcc = metrics.horizons['3d'].sector_accuracy;
            const sectorList = Object.entries(sectorAcc)
              .filter(([, v]) => v.n >= 3)
              .sort((a, b) => (b[1].accuracy_pct || 0) - (a[1].accuracy_pct || 0))
              .slice(0, 8);
            return sectorList.length > 0 ? (
              <div className="glass-card" style={{ marginBottom: '24px', padding: '24px' }}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <TrendingUp size={18} color="#34d399" />
                  <span>Accuracy by Sector (3-Day Horizon, min 3 predictions)</span>
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {sectorList.map(([sector, data]) => (
                    <div key={sector} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', width: '180px', flexShrink: 0 }}>{sector}</span>
                      <div style={{ flex: 1 }}>
                        <AccBar value={data.accuracy_pct} color="#34d399" />
                      </div>
                      <span className="font-mono" style={{ fontSize: '0.8rem', color: '#34d399', width: '80px', textAlign: 'right' }}>
                        {data.accuracy_pct != null ? `${data.accuracy_pct}%` : '—'} <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>n={data.n}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null;
          })()}

          {/* Methodology */}
          <div className="glass-card" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <Info size={18} color="#60a5fa" />
              <h3 style={{ fontSize: '1rem', fontWeight: '700' }}>Evaluation Methodology</h3>
            </div>
            <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '12px' }}>
              {metrics?.methodology || 'Directional accuracy: UP prediction = correct if actual stock return > +0.5% within horizon window. DOWN = correct if return < -0.5%. NEUTRAL = correct if -0.5% ≤ return ≤ +0.5%. All returns sourced from the local stock_price database (Yahoo Finance OHLCV).'}
            </p>
            <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              <span>Total Evaluated: <strong className="font-mono" style={{ color: 'var(--text-primary)' }}>{metrics?.total_evaluated ?? 0}</strong></span>
              <span>•</span>
              <span>Data Source: <strong>Local SQLite stock_price table (Yahoo Finance)</strong></span>
              {metrics?.computed_at && (
                <>
                  <span>•</span>
                  <span>Computed: <strong>{metrics.computed_at?.slice(0, 16)}</strong></span>
                </>
              )}
            </div>
            {/* Compliance disclaimer */}
            <div style={{ marginTop: '16px', padding: '10px 14px', background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldCheck size={14} color="#f59e0b" />
              <span style={{ fontSize: '0.78rem', color: '#fbbf24' }}>{MANDATORY_DISCLAIMER}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
