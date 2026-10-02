import React, { useState, useEffect } from 'react';
import {
  Brain, RefreshCw, Database, TrendingUp, CheckCircle,
  AlertTriangle, BarChart3, Layers, Cpu, Target, ShieldAlert, Play, Download
} from 'lucide-react';

const MANDATORY_DISCLAIMER = "AI/model estimate — not investment advice.";

const HORIZON_LABELS = { "1d": "1-Day", "3d": "3-Day", "5d": "5-Day" };
const MODEL_COLORS = {
  "LogisticRegression": "#60a5fa",
  "RandomForest":       "#34d399",
  "GradientBoosting":   "#f59e0b",
};
const FEATURE_LABELS = [
  "Sentiment Score",
  "Sentiment Polarity",
  "Sentiment Strength",
  "Event Type",
  "Sector",
  "Recent 1D Return %",
  "Historical Volatility",
  "Relative Volume",
  "Market Trend (5D)",
  "Category Past Reaction",
  "News Recency",
];
const CLASS_LABELS = ["Negative", "Neutral", "Positive"];
const CLASS_COLORS = { Negative: "#f43f5e", Neutral: "#f59e0b", Positive: "#10b981" };

export default function ModelAnalyticsView() {
  const [status, setStatus]       = useState(null);
  const [metrics, setMetrics]     = useState(null);
  const [loading, setLoading]     = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [training, setTraining]   = useState(false);
  const [activeHorizon, setActiveHorizon] = useState("1d");
  const [activeModel, setActiveModel]     = useState("RandomForest");

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [sRes, mRes] = await Promise.all([
        fetch('/api/ml/status').then(r => r.json()),
        fetch('/api/ml/metrics').then(r => r.json()),
      ]);
      setStatus(sRes);
      setMetrics(mRes);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, []);

  const handleCollect = async () => {
    setCollecting(true);
    await fetch('/api/ml/collect-prices', { method: 'POST' });
    setTimeout(() => { setCollecting(false); fetchAll(); }, 3000);
  };

  const handleTrain = async () => {
    setTraining(true);
    await fetch('/api/ml/train', { method: 'POST' });
    // Poll for 45s
    let polls = 0;
    const poll = setInterval(async () => {
      polls++;
      const m = await fetch('/api/ml/metrics').then(r => r.json());
      setMetrics(m);
      if (m.has_sufficient_data || polls > 9) {
        clearInterval(poll);
        setTraining(false);
        fetchAll();
      }
    }, 5000);
  };

  // Get metric for selected model + horizon
  const getMetric = (model, horizon) =>
    metrics?.metrics?.find(m => m.model_name === model && m.horizon === horizon);

  const selectedMetric = getMetric(activeModel, activeHorizon);

  return (
    <div>
      {/* Header */}
      <div className="glass-card" style={{ padding: '20px 24px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '42px', height: '42px', borderRadius: '10px', background: 'linear-gradient(135deg,#7c3aed,#3b82f6)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Brain size={22} color="#fff" />
            </div>
            <div>
              <h2 style={{ fontSize: '1.3rem', fontWeight: '800', marginBottom: '2px' }}>ML Model Analytics</h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                3 Models × 3 Horizons • 11-Feature Pipeline • Real Train/Test Split
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <a
              href="http://127.0.0.1:8000/api/ml/dataset/download"
              download="market_news_ml_dataset.csv"
              className="btn btn-secondary btn-sm"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', textDecoration: 'none' }}
              title="Download full ML dataset (articles, sentiment, indicators, and future stock return labels)"
            >
              <Download size={14} />
              Dataset (CSV)
            </a>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleCollect}
              disabled={collecting}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Database size={14} />
              {collecting ? 'Collecting...' : 'Collect Prices'}
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={handleTrain}
              disabled={training || collecting}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'linear-gradient(135deg,#7c3aed,#3b82f6)' }}
            >
              <Play size={14} />
              {training ? 'Training...' : 'Train Models'}
            </button>
            <button className="btn btn-secondary btn-sm" onClick={fetchAll} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
            </button>
          </div>
        </div>
      </div>

      {/* System Status Cards */}
      {status && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px', marginBottom: '20px' }}>
          {[
            { label: 'Analysis Rows',   value: status.analysis_rows,    icon: <Layers size={16} color="#60a5fa" /> },
            { label: 'Price Rows',      value: status.stock_price_rows,  icon: <BarChart3 size={16} color="#34d399" /> },
            { label: 'Tickers Tracked', value: status.unique_tickers,    icon: <Target size={16} color="#f59e0b" /> },
            { label: 'Trained Models',  value: status.trained_models,    icon: <Cpu size={16} color="#a78bfa" /> },
            { label: 'Dataset CSV',     value: '234 Rows',               icon: <Download size={16} color="#38bdf8" /> },
          ].map(({ label, value, icon }) => (
            <div key={label} className="glass-card" style={{ padding: '14px 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                {icon}
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>{label.toUpperCase()}</span>
              </div>
              <span className="font-mono" style={{ fontSize: '1.6rem', fontWeight: '800' }}>{value ?? '—'}</span>
            </div>
          ))}
        </div>
      )}

      {/* Ready-to-train status banner */}
      {status && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          padding: '12px 16px', borderRadius: '10px', marginBottom: '20px',
          background: status.ready_to_train ? 'rgba(16,185,129,0.08)' : 'rgba(245,158,11,0.08)',
          border: `1px solid ${status.ready_to_train ? 'rgba(16,185,129,0.3)' : 'rgba(245,158,11,0.3)'}`,
        }}>
          {status.ready_to_train
            ? <CheckCircle size={16} color="#10b981" />
            : <AlertTriangle size={16} color="#f59e0b" />}
          <span style={{ fontSize: '0.85rem', color: status.ready_to_train ? '#6ee7b7' : '#fcd34d' }}>
            {status.message}
          </span>
        </div>
      )}

      {/* Insufficient data banner */}
      {metrics && !metrics.has_sufficient_data && (
        <div style={{
          padding: '20px 24px', borderRadius: '12px', marginBottom: '20px',
          background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.25)',
          display: 'flex', alignItems: 'flex-start', gap: '12px'
        }}>
          <AlertTriangle size={20} color="#f87171" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <p style={{ fontWeight: '700', color: '#f87171', marginBottom: '4px' }}>
              Model requires more historical data for reliable training.
            </p>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
              Steps to enable training:<br/>
              <strong>1.</strong> Sync news articles (Live Terminal → Sync News).<br/>
              <strong>2.</strong> Click <strong>Collect Prices</strong> to download 90-day OHLCV history for all tracked stocks.<br/>
              <strong>3.</strong> Click <strong>Train Models</strong> once price collection completes.<br/>
              Minimum {metrics.min_samples_required} labeled samples per horizon required. Need stock data to create outcome labels.
            </p>
          </div>
        </div>
      )}

      {/* Model / Horizon Selector */}
      <div className="glass-card" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: '600', marginBottom: '6px' }}>MODEL</p>
            <div style={{ display: 'flex', gap: '6px' }}>
              {Object.keys(MODEL_COLORS).map(m => (
                <button key={m} onClick={() => setActiveModel(m)} style={{
                  padding: '5px 12px', borderRadius: '8px', fontSize: '0.78rem', fontWeight: '700',
                  border: `1px solid ${activeModel === m ? MODEL_COLORS[m] : 'var(--border-color)'}`,
                  background: activeModel === m ? `${MODEL_COLORS[m]}20` : 'transparent',
                  color: activeModel === m ? MODEL_COLORS[m] : 'var(--text-secondary)',
                  cursor: 'pointer',
                }}>
                  {m.replace('Regression', ' Reg.').replace('Gradient', 'Grad.')}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: '600', marginBottom: '6px' }}>HORIZON</p>
            <div style={{ display: 'flex', gap: '6px' }}>
              {["1d","3d","5d"].map(h => (
                <button key={h} onClick={() => setActiveHorizon(h)} style={{
                  padding: '5px 12px', borderRadius: '8px', fontSize: '0.78rem', fontWeight: '700',
                  border: `1px solid ${activeHorizon === h ? '#60a5fa' : 'var(--border-color)'}`,
                  background: activeHorizon === h ? 'rgba(96,165,250,0.15)' : 'transparent',
                  color: activeHorizon === h ? '#93c5fd' : 'var(--text-secondary)',
                  cursor: 'pointer',
                }}>
                  {HORIZON_LABELS[h]}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Metrics Panel */}
      {selectedMetric ? (
        selectedMetric.is_sufficient ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>

            {/* Core Metrics */}
            <div className="glass-card" style={{ padding: '20px 24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <Target size={16} color="#60a5fa" />
                <h3 style={{ fontSize: '0.95rem', fontWeight: '700' }}>Evaluation Metrics</h3>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                  n_test={selectedMetric.n_test}
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                {[
                  { label: 'Accuracy',   value: selectedMetric.accuracy,        color: '#60a5fa' },
                  { label: 'Precision',  value: selectedMetric.precision_macro,  color: '#34d399' },
                  { label: 'Recall',     value: selectedMetric.recall_macro,     color: '#f59e0b' },
                  { label: 'F1 (Macro)', value: selectedMetric.f1_macro,         color: '#a78bfa' },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{
                    background: 'var(--bg-primary)', borderRadius: '10px', padding: '14px',
                    border: `1px solid ${color}30`
                  }}>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: '600' }}>{label.toUpperCase()}</span>
                    <div className="font-mono" style={{ fontSize: '1.8rem', fontWeight: '900', color, marginTop: '4px' }}>
                      {value != null ? (value * 100).toFixed(1) + '%' : '—'}
                    </div>
                    {/* Bar */}
                    <div style={{ height: '4px', background: '#1e293b', borderRadius: '2px', marginTop: '8px', overflow: 'hidden' }}>
                      <div style={{ width: `${(value || 0) * 100}%`, height: '100%', background: color }} />
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: '12px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Train: {selectedMetric.n_train} samples &nbsp;|&nbsp; Test: {selectedMetric.n_test} samples
                &nbsp;|&nbsp; Trained: {selectedMetric.trained_at?.slice(0, 16)}
              </div>
            </div>

            {/* Confusion Matrix */}
            <div className="glass-card" style={{ padding: '20px 24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <BarChart3 size={16} color="#a78bfa" />
                <h3 style={{ fontSize: '0.95rem', fontWeight: '700' }}>Confusion Matrix</h3>
              </div>
              {selectedMetric.confusion_matrix ? (
                <div>
                  {/* Header row */}
                  <div style={{ display: 'flex', gap: '2px', marginBottom: '2px' }}>
                    <div style={{ width: '80px' }} />
                    {CLASS_LABELS.map(cl => (
                      <div key={cl} style={{
                        flex: 1, textAlign: 'center', fontSize: '0.68rem',
                        fontWeight: '700', color: CLASS_COLORS[cl], padding: '4px 0'
                      }}>
                        Pred {cl.slice(0,3)}
                      </div>
                    ))}
                  </div>
                  {selectedMetric.confusion_matrix.map((row, ri) => {
                    const rowTotal = row.reduce((a, b) => a + b, 0);
                    return (
                      <div key={ri} style={{ display: 'flex', gap: '2px', marginBottom: '2px' }}>
                        <div style={{
                          width: '80px', display: 'flex', alignItems: 'center',
                          fontSize: '0.68rem', fontWeight: '700',
                          color: CLASS_COLORS[CLASS_LABELS[ri]], padding: '4px 6px'
                        }}>
                          Act {CLASS_LABELS[ri].slice(0,3)}
                        </div>
                        {row.map((cell, ci) => {
                          const intensity = rowTotal ? cell / rowTotal : 0;
                          const isCorrect = ri === ci;
                          return (
                            <div key={ci} style={{
                              flex: 1, textAlign: 'center', padding: '10px 4px',
                              borderRadius: '6px', fontWeight: '700', fontSize: '1rem',
                              background: isCorrect
                                ? `rgba(16,185,129,${0.12 + intensity * 0.4})`
                                : `rgba(244,63,94,${0.08 + intensity * 0.25})`,
                              color: isCorrect ? '#34d399' : (cell > 0 ? '#f87171' : 'var(--text-muted)'),
                              border: isCorrect ? '1px solid rgba(16,185,129,0.3)' : '1px solid rgba(244,63,94,0.15)',
                            }}>
                              {cell}
                            </div>
                          );
                        })}
                      </div>
                    );
                  })}
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '10px' }}>
                    Rows = Actual class, Columns = Predicted class. Green diagonal = correct predictions.
                  </p>
                </div>
              ) : (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No confusion matrix data yet.</p>
              )}
            </div>

            {/* Feature Importances (RF / GB only) */}
            {selectedMetric.feature_importances && (
              <div className="glass-card" style={{ padding: '20px 24px', gridColumn: '1 / -1' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                  <Layers size={16} color="#f59e0b" />
                  <h3 style={{ fontSize: '0.95rem', fontWeight: '700' }}>Feature Importances</h3>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                    {activeModel} • {HORIZON_LABELS[activeHorizon]} horizon
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {selectedMetric.feature_importances
                    .map((imp, i) => ({ imp, label: FEATURE_LABELS[i] || `Feature ${i}` }))
                    .sort((a, b) => b.imp - a.imp)
                    .map(({ imp, label }) => (
                      <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', width: '180px', flexShrink: 0 }}>
                          {label}
                        </span>
                        <div style={{ flex: 1, height: '8px', background: '#1e293b', borderRadius: '4px', overflow: 'hidden' }}>
                          <div style={{
                            width: `${Math.min(imp * 100 * 5, 100)}%`,
                            height: '100%',
                            background: 'linear-gradient(90deg, #f59e0b, #ef4444)',
                            borderRadius: '4px',
                          }} />
                        </div>
                        <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', width: '44px', textAlign: 'right' }}>
                          {(imp * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))
                  }
                </div>
              </div>
            )}

            {/* All Models Comparison Table for selected horizon */}
            <div className="glass-card" style={{ padding: '20px 24px', gridColumn: '1 / -1' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <Cpu size={16} color="#34d399" />
                <h3 style={{ fontSize: '0.95rem', fontWeight: '700' }}>All Models — {HORIZON_LABELS[activeHorizon]} Horizon</h3>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                      {['Model','N Train','N Test','Accuracy','Precision','Recall','F1 Macro'].map(h => (
                        <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: '700' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys(MODEL_COLORS).map(mn => {
                      const m = getMetric(mn, activeHorizon);
                      if (!m || !m.is_sufficient) return (
                        <tr key={mn} style={{ borderBottom: '1px solid var(--border-color)' }}>
                          <td style={{ padding: '10px 12px', color: MODEL_COLORS[mn], fontWeight: '700' }}>{mn}</td>
                          <td colSpan={6} style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                            Insufficient data
                          </td>
                        </tr>
                      );
                      const isActive = mn === activeModel;
                      return (
                        <tr key={mn} onClick={() => setActiveModel(mn)} style={{
                          borderBottom: '1px solid var(--border-color)',
                          background: isActive ? `${MODEL_COLORS[mn]}10` : 'transparent',
                          cursor: 'pointer'
                        }}>
                          <td style={{ padding: '10px 12px', color: MODEL_COLORS[mn], fontWeight: '700' }}>{mn}</td>
                          <td style={{ padding: '10px 12px', fontFamily: 'monospace' }}>{m.n_train}</td>
                          <td style={{ padding: '10px 12px', fontFamily: 'monospace' }}>{m.n_test}</td>
                          {[m.accuracy, m.precision_macro, m.recall_macro, m.f1_macro].map((v, i) => (
                            <td key={i} style={{ padding: '10px 12px', fontFamily: 'monospace', fontWeight: '700',
                              color: v > 0.6 ? '#34d399' : (v > 0.45 ? '#f59e0b' : '#f87171') }}>
                              {v != null ? (v * 100).toFixed(1) + '%' : '—'}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        ) : (
          <div className="glass-card" style={{ padding: '28px', textAlign: 'center' }}>
            <AlertTriangle size={28} color="#f59e0b" style={{ marginBottom: '12px' }} />
            <p style={{ fontWeight: '700', color: '#fcd34d', marginBottom: '8px' }}>
              Model requires more historical data for reliable training.
            </p>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              {selectedMetric.notes || 'Collect stock prices and sync more articles to enable training.'}
            </p>
          </div>
        )
      ) : (
        <div className="glass-card" style={{ padding: '28px', textAlign: 'center' }}>
          <Brain size={28} color="#7c3aed" style={{ marginBottom: '12px' }} />
          <p style={{ fontWeight: '700', marginBottom: '8px' }}>No model trained yet.</p>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Click <strong>Collect Prices</strong> → then <strong>Train Models</strong> to begin.
          </p>
        </div>
      )}

      {/* Compliance footer */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '24px', fontSize: '0.75rem', color: '#f59e0b' }}>
        <ShieldAlert size={14} />
        <span>{MANDATORY_DISCLAIMER}</span>
      </div>
    </div>
  );
}
