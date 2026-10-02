import React, { useState, useEffect, useRef } from 'react';
import {
  Brain, RefreshCw, Database, TrendingUp, CheckCircle,
  AlertTriangle, BarChart3, Layers, Cpu, Target, ShieldAlert, Play, Download,
  XCircle, Clock, Info, ChevronDown, ChevronUp, Terminal
} from 'lucide-react';

const MANDATORY_DISCLAIMER = "AI/model estimate — not investment advice.";

const HORIZON_LABELS = { "1d": "1-Day", "3d": "3-Day", "5d": "5-Day" };
const MODEL_COLORS = {
  "LogisticRegression": "#60a5fa",
  "RandomForest":       "#34d399",
  "GradientBoosting":   "#f59e0b",
};
const FEATURE_LABELS = [
  "Sentiment Score", "Sentiment Polarity", "Sentiment Strength", "Event Type",
  "Sector", "Recent 1D Return %", "Historical Volatility", "Relative Volume",
  "Market Trend (5D)", "Category Past Reaction", "News Recency",
];
const CLASS_LABELS = ["Negative", "Neutral", "Positive"];
const CLASS_COLORS = { Negative: "#f43f5e", Neutral: "#f59e0b", Positive: "#10b981" };

// Toast notification component - appears below sticky header
function Toast({ toast, onClose }) {
  if (!toast) return null;
  const styles = {
    success: { bg: '#e8f5e9', border: '#4caf50', iconColor: '#2e7d32', titleColor: '#1b5e20', icon: <CheckCircle size={16} color="#2e7d32" /> },
    error:   { bg: '#ffeaea', border: '#e53935', iconColor: '#b71c1c', titleColor: '#b71c1c', icon: <XCircle size={16} color="#b71c1c" /> },
    warning: { bg: '#fff8e1', border: '#f9a825', iconColor: '#e65100', titleColor: '#e65100', icon: <AlertTriangle size={16} color="#e65100" /> },
    info:    { bg: '#e3f2fd', border: '#1976d2', iconColor: '#0d47a1', titleColor: '#0d47a1', icon: <Info size={16} color="#1976d2" /> },
  };
  const c = styles[toast.type] || styles.info;
  return (
    <div style={{
      position: 'fixed',
      top: '80px',
      right: '20px',
      zIndex: 10000,
      padding: '14px 18px',
      borderRadius: '8px',
      maxWidth: '420px',
      minWidth: '280px',
      background: c.bg,
      border: `2px solid ${c.border}`,
      display: 'flex',
      alignItems: 'flex-start',
      gap: '10px',
      boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
      animation: 'toastSlideIn 0.25s ease',
    }}>
      <div style={{ flexShrink: 0, marginTop: '2px' }}>{c.icon}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: '700', color: c.titleColor, fontSize: '0.88rem', marginBottom: '4px', fontFamily: 'var(--font-sans)' }}>
          {toast.title}
        </div>
        <div style={{ fontSize: '0.79rem', color: '#333', lineHeight: 1.5, fontFamily: 'var(--font-sans)', whiteSpace: 'pre-line' }}>
          {toast.message}
        </div>
      </div>
      <button
        onClick={onClose}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#666', padding: '0 0 0 8px', fontSize: '1.1rem', lineHeight: 1 }}
      >×</button>
    </div>
  );
}

// Live Process & Logs Panel Component
function MLProcessPanel({ job, onDismiss, onRefresh }) {
  const [showLogs, setShowLogs] = useState(true);
  const logEndRef = useRef(null);

  useEffect(() => {
    if (showLogs && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [job?.logs?.length, showLogs]);

  if (!job || job.status === 'idle') return null;

  const isRunning = job.status === 'running';
  const isCompleted = job.status === 'completed';
  const isError = job.status === 'error';
  const jobTitle = job.job_type === 'collect' ? 'Stock Price Collection Pipeline' : 'ML Model Training Pipeline';

  return (
    <div style={{
      background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)',
      border: isRunning ? '2px solid #3b82f6' : (isCompleted ? '2px solid #10b981' : '2px solid #ef4444'),
      borderRadius: '12px',
      padding: '20px 24px',
      marginBottom: '24px',
      boxShadow: isRunning ? '0 12px 32px rgba(59, 130, 246, 0.25)' : '0 8px 24px rgba(0,0,0,0.3)',
      color: '#f8fafc',
      animation: 'toastSlideIn 0.3s ease',
    }}>
      {/* Top row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {isRunning && <Clock size={22} className="spin" color="#60a5fa" />}
          {isCompleted && <CheckCircle size={22} color="#34d399" />}
          {isError && <XCircle size={22} color="#f87171" />}
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', margin: 0, color: '#f8fafc' }}>
              {jobTitle}
            </h3>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '2px' }}>
              Job ID: <span style={{ fontFamily: 'monospace', color: '#cbd5e1' }}>{job.job_id || '—'}</span>
              {job.started_at && ` • Started at ${job.started_at.slice(11, 19)}`}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{
            fontSize: '0.74rem',
            fontWeight: '800',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            padding: '5px 12px',
            borderRadius: '20px',
            background: isRunning ? 'rgba(59,130,246,0.2)' : (isCompleted ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'),
            color: isRunning ? '#93c5fd' : (isCompleted ? '#6ee7b7' : '#fca5a5'),
            border: `1px solid ${isRunning ? '#3b82f6' : (isCompleted ? '#10b981' : '#ef4444')}`,
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            {isRunning && <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#60a5fa', animation: 'mlPulse 1.2s infinite' }} />}
            {isRunning ? `PROCESSING (${job.progress_pct}%)` : (isCompleted ? 'COMPLETED' : 'FAILED')}
          </span>

          {!isRunning && (
            <button
              onClick={onDismiss}
              style={{
                background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.15)',
                color: '#cbd5e1',
                borderRadius: '6px',
                padding: '5px 12px',
                fontSize: '0.75rem',
                cursor: 'pointer',
                fontWeight: '600'
              }}
            >
              Dismiss
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div style={{
        width: '100%',
        height: '10px',
        background: '#090d16',
        borderRadius: '6px',
        overflow: 'hidden',
        border: '1px solid rgba(255,255,255,0.1)',
        marginBottom: '12px',
        position: 'relative',
      }}>
        <div style={{
          width: `${Math.min(100, Math.max(3, job.progress_pct))}%`,
          height: '100%',
          background: isError ? '#ef4444' : (isCompleted ? 'linear-gradient(90deg, #10b981, #059669)' : 'linear-gradient(90deg, #3b82f6, #a855f7)'),
          transition: 'width 0.4s ease',
          borderRadius: '6px',
        }} />
      </div>

      {/* Current Step Description */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', fontSize: '0.84rem' }}>
        <div style={{ color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: '700', color: '#93c5fd' }}>{job.current_item || 'Status'}:</span>
          <span>{job.message}</span>
        </div>
        <div style={{ fontSize: '0.78rem', color: '#94a3b8', fontFamily: 'monospace' }}>
          {job.current_step > 0 && `${job.current_step} / ${job.total_steps} tasks`}
        </div>
      </div>

      {/* Streaming Console Logs */}
      <div style={{ marginTop: '10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <span style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: '700', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Terminal size={14} color="#60a5fa" />
            Live Console Execution Logs ({job.logs?.length || 0} lines)
          </span>
          <button
            onClick={() => setShowLogs(!showLogs)}
            style={{ background: 'none', border: 'none', color: '#60a5fa', fontSize: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            {showLogs ? <><ChevronUp size={14} /> Collapse</> : <><ChevronDown size={14} /> View Logs</>}
          </button>
        </div>

        {showLogs && (
          <div style={{
            background: '#020617',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '8px',
            padding: '12px 16px',
            maxHeight: '160px',
            overflowY: 'auto',
            fontFamily: 'Consolas, Monaco, "Courier New", monospace',
            fontSize: '0.76rem',
            lineHeight: 1.6,
          }}>
            {job.logs && job.logs.length > 0 ? (
              job.logs.map((line, idx) => {
                let color = '#94a3b8';
                if (line.includes('ERROR') || line.includes('Failed')) color = '#f87171';
                else if (line.includes('Done') || line.includes('Finished') || line.includes('Stored') || line.includes('Successfully')) color = '#34d399';
                else if (line.includes('Training') || line.includes('Fetching')) color = '#60a5fa';
                return (
                  <div key={idx} style={{ color }}>
                    {line}
                  </div>
                );
              })
            ) : (
              <div style={{ color: '#64748b' }}>Awaiting initial logs...</div>
            )}
            <div ref={logEndRef} />
          </div>
        )}
      </div>

      {/* Finished Summary Callout */}
      {isCompleted && (
        <div style={{
          marginTop: '16px',
          padding: '12px 16px',
          borderRadius: '8px',
          background: 'rgba(16,185,129,0.12)',
          border: '1px solid rgba(16,185,129,0.3)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}>
          <div style={{ fontSize: '0.84rem', color: '#6ee7b7', fontWeight: '600' }}>
            ✓ {job.message}
          </div>
          <button
            onClick={onRefresh}
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '0.78rem', padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '6px', background: '#064e3b', color: '#a7f3d0', borderColor: '#059669' }}
          >
            <RefreshCw size={13} /> Refresh Model Tables
          </button>
        </div>
      )}

      {/* Error Callout */}
      {isError && (
        <div style={{
          marginTop: '16px',
          padding: '12px 16px',
          borderRadius: '8px',
          background: 'rgba(239,68,68,0.12)',
          border: '1px solid rgba(239,68,68,0.3)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}>
          <div style={{ fontSize: '0.84rem', color: '#fca5a5' }}>
            ✗ {job.message}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ModelAnalyticsView() {
  const [status, setStatus]               = useState(null);
  const [metrics, setMetrics]             = useState(null);
  const [loading, setLoading]             = useState(true);
  const [toast, setToast]                 = useState(null);
  const [activeHorizon, setActiveHorizon] = useState("1d");
  const [activeModel, setActiveModel]     = useState("RandomForest");
  
  // Real-time job execution state
  const [job, setJob]                     = useState(null);
  const [jobDismissed, setJobDismissed]   = useState(false);
  const pollingRef                        = useRef(null);
  const toastTimer                        = useRef(null);

  const showToast = (type, title, message, duration = 6000) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ type, title, message });
    if (duration > 0) {
      toastTimer.current = setTimeout(() => setToast(null), duration);
    }
  };

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [sRes, mRes, jRes] = await Promise.all([
        fetch('/api/ml/status').then(r => r.json()),
        fetch('/api/ml/metrics').then(r => r.json()),
        fetch('/api/ml/job-status').then(r => r.json()),
      ]);
      setStatus(sRes);
      setMetrics(mRes);
      if (jRes) {
        setJob(jRes);
        if (jRes.status === 'running') {
          startPolling();
        }
      }
    } catch (e) {
      console.error("Failed to fetch ML analytics:", e);
    }
    setLoading(false);
  };

  const startPolling = () => {
    if (pollingRef.current) return;
    pollingRef.current = setInterval(async () => {
      try {
        const jRes = await fetch('/api/ml/job-status').then(r => r.json());
        setJob(jRes);
        if (jRes.status === 'completed') {
          stopPolling();
          showToast('success', `${jRes.job_type === 'collect' ? 'Price Collection' : 'ML Training'} Complete!`, jRes.message);
          // Refresh background metrics and stats
          const [sRes, mRes] = await Promise.all([
            fetch('/api/ml/status').then(r => r.json()),
            fetch('/api/ml/metrics').then(r => r.json()),
          ]);
          setStatus(sRes);
          setMetrics(mRes);
        } else if (jRes.status === 'error') {
          stopPolling();
          showToast('error', 'Execution Error', jRes.message);
        }
      } catch (err) {
        console.error("Job status polling error:", err);
      }
    }, 600);
  };

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  useEffect(() => {
    fetchAll();
    return () => stopPolling();
  }, []);

  const handleCollect = async () => {
    setJobDismissed(false);
    try {
      const res = await fetch('/api/ml/collect-prices', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'already_running') {
        showToast('warning', 'Task in Progress', data.message);
        startPolling();
      } else {
        showToast('info', 'Collecting Prices...', 'Price collection initiated. Watch real-time progress below.');
        startPolling();
      }
    } catch (e) {
      showToast('error', 'Request Failed', `Network error: ${e.message}`);
    }
  };

  const handleTrain = async () => {
    setJobDismissed(false);
    try {
      const res = await fetch('/api/ml/train', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'already_running') {
        showToast('warning', 'Task in Progress', data.message);
        startPolling();
      } else {
        showToast('info', 'Training ML Models...', 'ML pipeline training initiated. Watch real-time progress below.');
        startPolling();
      }
    } catch (e) {
      showToast('error', 'Request Failed', `Network error: ${e.message}`);
    }
  };

  const isJobRunning = job?.status === 'running';

  // Get metric for selected model + horizon
  const getMetric = (model, horizon) =>
    metrics?.metrics?.find(m => m.model_name === model && m.horizon === horizon);

  const selectedMetric = getMetric(activeModel, activeHorizon);

  return (
    <div>
      <Toast toast={toast} onClose={() => setToast(null)} />

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
                3 Models × 3 Horizons • 11-Feature Pipeline • Real Train/Test Split & Cross-Validation
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <a
              href="http://127.0.0.1:8000/api/ml/dataset/download"
              download="market_news_ml_dataset.csv"
              className="btn btn-secondary btn-sm"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', textDecoration: 'none' }}
            >
              <Download size={14} /> Dataset (CSV)
            </a>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleCollect}
              disabled={isJobRunning}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              {isJobRunning && job?.job_type === 'collect' ? <><Clock size={14} className="spin" /> Collecting...</> : <><Database size={14} /> Collect Prices</>}
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={handleTrain}
              disabled={isJobRunning}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'linear-gradient(135deg,#7c3aed,#3b82f6)' }}
            >
              {isJobRunning && job?.job_type === 'train' ? <><Clock size={14} className="spin" /> Training...</> : <><Play size={14} /> Train Models</>}
            </button>
            <button className="btn btn-secondary btn-sm" onClick={fetchAll} disabled={loading || isJobRunning}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
            </button>
          </div>
        </div>
      </div>

      {/* Live Process & Execution Panel */}
      {!jobDismissed && (
        <MLProcessPanel
          job={job}
          onDismiss={() => setJobDismissed(true)}
          onRefresh={fetchAll}
        />
      )}

      {/* System Status Cards */}
      {status && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px', marginBottom: '20px' }}>
          {[
            { label: 'Analysis Rows',   value: status.analysis_rows,   icon: <Layers size={16} color="#60a5fa" /> },
            { label: 'Price Rows',      value: status.stock_price_rows, icon: <BarChart3 size={16} color="#34d399" /> },
            { label: 'Tickers Tracked', value: status.unique_tickers,   icon: <Target size={16} color="#f59e0b" /> },
            { label: 'Trained Models',  value: status.trained_models,   icon: <Cpu size={16} color="#a78bfa" /> },
            { label: 'Dataset Rows',    value: metrics?.dataset_csv_rows != null ? metrics.dataset_csv_rows : '—', icon: <Download size={16} color="#38bdf8" /> },
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

      {/* Insufficient data banner if not enough samples */}
      {metrics && !metrics.has_sufficient_data && (
        <div style={{
          padding: '20px 24px', borderRadius: '12px', marginBottom: '20px',
          background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.25)',
          display: 'flex', alignItems: 'flex-start', gap: '12px'
        }}>
          <AlertTriangle size={20} color="#f87171" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <p style={{ fontWeight: '700', color: '#f87171', marginBottom: '4px' }}>
              Model requires more labeled data.
            </p>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
              The ML system needs articles whose stock price <em>outcome</em> (1d/3d/5d return after publication)
              can be verified from stored price data.<br />
              <strong>Step 1:</strong> Click <strong>Collect Prices</strong> — this downloads OHLCV data matching article dates.<br />
              <strong>Step 2:</strong> Click <strong>Train Models</strong> — labeled samples are built automatically.<br />
              Minimum {metrics.min_samples_required} labeled samples required per horizon.
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
              {/* Cross-Validation metrics */}
              {selectedMetric.cv_accuracy_mean != null && (
                <div style={{
                  marginTop: '12px', padding: '10px 14px', borderRadius: '8px',
                  background: 'rgba(96,165,250,0.07)', border: '1px solid rgba(96,165,250,0.2)',
                  fontSize: '0.78rem', color: 'var(--text-secondary)'
                }}>
                  <span style={{ fontWeight: '700', color: '#60a5fa' }}>Cross-Validation</span>
                  &nbsp;— CV Accuracy: <span className="font-mono" style={{ color: '#93c5fd' }}>
                    {(selectedMetric.cv_accuracy_mean * 100).toFixed(1)}% ± {(selectedMetric.cv_accuracy_std * 100).toFixed(1)}%
                  </span>
                  &nbsp;| CV F1: <span className="font-mono" style={{ color: '#a78bfa' }}>
                    {(selectedMetric.cv_f1_mean * 100).toFixed(1)}%
                  </span>
                  <span style={{ color: 'var(--text-muted)', marginLeft: '8px' }}>(stratified k-fold)</span>
                </div>
              )}
            </div>

            {/* Confusion Matrix */}
            <div className="glass-card" style={{ padding: '20px 24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <BarChart3 size={16} color="#a78bfa" />
                <h3 style={{ fontSize: '0.95rem', fontWeight: '700' }}>Confusion Matrix</h3>
              </div>
              {selectedMetric.confusion_matrix ? (
                <div>
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
                    Rows = Actual class, Columns = Predicted. Green diagonal = correct.
                  </p>
                </div>
              ) : (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No confusion matrix yet.</p>
              )}
            </div>

            {/* Feature Importances */}
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
                            width: `${Math.min(imp * 100 * 5, 100)}%`, height: '100%',
                            background: 'linear-gradient(90deg, #f59e0b, #ef4444)', borderRadius: '4px',
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

            {/* All Models Comparison */}
            <div className="glass-card" style={{ padding: '20px 24px', gridColumn: '1 / -1' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <Cpu size={16} color="#34d399" />
                <h3 style={{ fontSize: '0.95rem', fontWeight: '700' }}>All Models — {HORIZON_LABELS[activeHorizon]} Horizon</h3>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                      {['Model','N Train','N Test','Accuracy','Precision','Recall','F1 Macro','CV Acc'].map(h => (
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
                          <td colSpan={7} style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
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
                          <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: 'var(--text-secondary)', fontSize: '0.78rem' }}>
                            {m.cv_accuracy_mean != null
                              ? `${(m.cv_accuracy_mean * 100).toFixed(1)}%±${(m.cv_accuracy_std * 100).toFixed(1)}%`
                              : '—'}
                          </td>
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
              Insufficient labeled data for this model.
            </p>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              {selectedMetric.notes || 'Click Collect Prices then Train Models above.'}
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

      <style>{`
        @keyframes toastSlideIn { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes mlSpin { to { transform: rotate(360deg); } }
        @keyframes mlPulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(1.2); } }
        .spin { animation: mlSpin 0.8s linear infinite; }
      `}</style>
    </div>
  );
}
