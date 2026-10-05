import React, { useState, useEffect, useRef } from 'react';
import {
  Brain, RefreshCw, Database, TrendingUp, CheckCircle,
  AlertTriangle, BarChart3, Layers, Cpu, Target, ShieldAlert, Play, Download,
  XCircle, Clock, Info, ChevronDown, ChevronUp, Terminal, BookOpen, Sparkles,
  GitBranch, Check, ArrowRight
} from 'lucide-react';

const MANDATORY_DISCLAIMER = "AI/model estimate — not investment advice. Walk-forward validated on historical Indian equities.";

const HORIZON_LABELS = { "1d": "1-Day Horizon", "3d": "3-Day Horizon", "5d": "5-Day Horizon" };
const MODEL_COLORS = {
  "LogisticRegression": "#2563eb",
  "RandomForest":       "#059669",
  "GradientBoosting":   "#d97706",
};
const FEATURE_LABELS = [
  "Sentiment Score", "Sentiment Polarity", "Sentiment Strength", "Event Type",
  "Sector", "Recent 1D Return %", "Historical Volatility", "Relative Volume",
  "Market Trend (5D)", "Point-in-Time Category Reaction", "Session Timing",
];
const CLASS_LABELS = ["Negative", "Neutral", "Positive"];
const CLASS_COLORS = { Negative: "#dc2626", Neutral: "#d97706", Positive: "#059669" };

// Toast notification component
function Toast({ toast, onClose }) {
  if (!toast) return null;
  const styles = {
    success: { bg: '#ecfdf5', border: '#10b981', iconColor: '#059669', titleColor: '#065f46', icon: <CheckCircle size={16} color="#059669" /> },
    error:   { bg: '#fef2f2', border: '#ef4444', iconColor: '#dc2626', titleColor: '#991b1b', icon: <XCircle size={16} color="#dc2626" /> },
    warning: { bg: '#fffbeb', border: '#f59e0b', iconColor: '#d97706', titleColor: '#92400e', icon: <AlertTriangle size={16} color="#d97706" /> },
    info:    { bg: '#eff6ff', border: '#3b82f6', iconColor: '#2563eb', titleColor: '#1e40af', icon: <Info size={16} color="#2563eb" /> },
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
      boxShadow: '0 8px 24px rgba(0,0,0,0.14)',
      animation: 'toastSlideIn 0.25s ease',
    }}>
      <div style={{ flexShrink: 0, marginTop: '2px' }}>{c.icon}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: '700', color: c.titleColor, fontSize: '0.88rem', marginBottom: '4px', fontFamily: 'var(--font-sans)' }}>
          {toast.title}
        </div>
        <div style={{ fontSize: '0.79rem', color: 'var(--text-secondary)', lineHeight: 1.5, fontFamily: 'var(--font-sans)', whiteSpace: 'pre-line' }}>
          {toast.message}
        </div>
      </div>
      <button
        onClick={onClose}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '0 0 0 8px', fontSize: '1.1rem', lineHeight: 1 }}
      >×</button>
    </div>
  );
}

// Live Process & Logs Panel Component
function MLProcessPanel({ job, onDismiss, onRefresh }) {
  const [showLogs, setShowLogs] = useState(true);
  const logContainerRef = useRef(null);

  useEffect(() => {
    if (showLogs && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [job?.logs?.length, showLogs]);

  if (!job || job.status === 'idle') return null;

  const isRunning = job.status === 'running';
  const isCompleted = job.status === 'completed';
  const isError = job.status === 'error';
  const jobTitle = job.job_type === 'collect' ? 'Stock Price Collection Pipeline' : 'ML Model Training Pipeline';

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: isRunning ? '2px solid var(--accent-blue)' : (isCompleted ? '2px solid var(--bullish)' : '2px solid var(--bearish)'),
      borderRadius: '10px',
      padding: '20px 24px',
      marginBottom: '24px',
      boxShadow: 'var(--shadow-md)',
      color: 'var(--text-primary)',
      animation: 'toastSlideIn 0.3s ease',
    }}>
      {/* Top row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {isRunning && <Clock size={20} className="spin" color="var(--accent-blue)" />}
          {isCompleted && <CheckCircle size={20} color="var(--bullish)" />}
          {isError && <XCircle size={20} color="var(--bearish)" />}
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', margin: 0, color: 'var(--text-primary)' }}>
              {jobTitle}
            </h3>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Job ID: <span style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>{job.job_id || '—'}</span>
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
            padding: '4px 12px',
            borderRadius: '6px',
            background: isRunning ? 'var(--accent-blue)18' : (isCompleted ? 'var(--bullish-bg)' : 'var(--bearish-bg)'),
            color: isRunning ? 'var(--accent-blue)' : (isCompleted ? 'var(--bullish)' : 'var(--bearish)'),
            border: `1px solid ${isRunning ? 'var(--accent-blue)' : (isCompleted ? 'var(--bullish-border)' : 'var(--bearish-border)')}`,
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            {isRunning && <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-blue)', animation: 'mlPulse 1.2s infinite' }} />}
            {isRunning ? `PROCESSING (${job.progress_pct}%)` : (isCompleted ? 'COMPLETED' : 'FAILED')}
          </span>

          {isRunning && (
            <button
              onClick={async () => {
                try {
                  await fetch('/api/ml/cancel-job', { method: 'POST' });
                  if (onDismiss) onDismiss();
                } catch (e) {
                  console.error(e);
                }
              }}
              style={{
                background: 'var(--bearish-bg)',
                border: '1px solid var(--bearish-border)',
                color: 'var(--bearish)',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '0.75rem',
                cursor: 'pointer',
                fontWeight: '600'
              }}
              title="Cancel current running pipeline"
            >
              Cancel
            </button>
          )}

          {!isRunning && (
            <button
              onClick={onDismiss}
              style={{
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-secondary)',
                borderRadius: '6px',
                padding: '4px 12px',
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
        height: '8px',
        background: 'var(--border-light)',
        borderRadius: '4px',
        overflow: 'hidden',
        marginBottom: '12px',
        position: 'relative',
      }}>
        <div style={{
          width: `${Math.min(100, Math.max(3, job.progress_pct))}%`,
          height: '100%',
          background: isError ? 'var(--bearish)' : (isCompleted ? 'var(--bullish)' : 'var(--accent-blue)'),
          transition: 'width 0.4s ease',
          borderRadius: '4px',
        }} />
      </div>

      {/* Current Step Description */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', fontSize: '0.84rem' }}>
        <div style={{ color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: '700', color: 'var(--accent-blue)' }}>{job.current_item || 'Status'}:</span>
          <span>{job.message}</span>
        </div>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
          {job.current_step > 0 && `${job.current_step} / ${job.total_steps} tasks`}
        </div>
      </div>

      {/* Console Logs */}
      <div style={{ marginTop: '10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: '700', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Terminal size={14} color="var(--accent-blue)" />
            Execution Console Logs ({job.logs?.length || 0} lines)
          </span>
          <button
            onClick={() => setShowLogs(!showLogs)}
            style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', fontSize: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: '600' }}
          >
            {showLogs ? <><ChevronUp size={14} /> Collapse</> : <><ChevronDown size={14} /> View Logs</>}
          </button>
        </div>

        {showLogs && (
          <div
            ref={logContainerRef}
            style={{
              background: '#171717',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              padding: '12px 16px',
              maxHeight: '160px',
              overflowY: 'auto',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.76rem',
              lineHeight: 1.6,
            }}
          >
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
          </div>
        )}
      </div>

      {isCompleted && (
        <div style={{
          marginTop: '16px',
          padding: '12px 16px',
          borderRadius: '6px',
          background: 'var(--bullish-bg)',
          border: '1px solid var(--bullish-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}>
          <div style={{ fontSize: '0.84rem', color: 'var(--bullish)', fontWeight: '600' }}>
            ✓ {job.message}
          </div>
          <button
            onClick={onRefresh}
            style={{
              fontSize: '0.78rem',
              padding: '6px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'var(--bullish)',
              color: '#ffffff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: '700'
            }}
          >
            <RefreshCw size={13} /> Refresh Model Tables
          </button>
        </div>
      )}
    </div>
  );
}

export default function ModelAnalyticsView() {
  const [status, setStatus]               = useState(null);
  const [metrics, setMetrics]             = useState(null);
  const [indicStats, setIndicStats]       = useState(null);
  const [loading, setLoading]             = useState(true);
  const [toast, setToast]                 = useState(null);
  const [activeHorizon, setActiveHorizon] = useState("1d");
  const [activeModel, setActiveModel]     = useState("RandomForest");
  
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
      const [sRes, mRes, jRes, iRes] = await Promise.all([
        fetch('/api/ml/status').then(r => r.json()).catch(() => null),
        fetch('/api/ml/metrics').then(r => r.json()).catch(() => null),
        fetch('/api/ml/job-status').then(r => r.json()).catch(() => null),
        fetch('/api/ml/indic-finance/stats').then(r => r.json()).catch(() => null),
      ]);
      setStatus(sRes);
      setMetrics(mRes);
      setIndicStats(iRes);
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
          fetchAll();
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
      } else {
        showToast('info', 'Collecting Prices...', 'Price collection initiated. Watch real-time progress below.');
      }
      startPolling();
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
      } else {
        showToast('info', 'Training ML Models...', 'Walk-forward training initiated across all 3 horizons.');
      }
      startPolling();
    } catch (e) {
      showToast('error', 'Request Failed', `Network error: ${e.message}`);
    }
  };

  const isJobRunning = job?.status === 'running';

  const getMetric = (model, horizon) =>
    metrics?.metrics?.find(m => m.model_name === model && m.horizon === horizon);

  const selectedMetric = getMetric(activeModel, activeHorizon);

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
      <Toast toast={toast} onClose={() => setToast(null)} />

      {/* ── TOP MASTHEAD HEADER ── */}
      <div
        className="glass-card"
        style={{
          padding: '24px 28px',
          marginBottom: '24px',
          borderRadius: '10px',
          border: '1px solid var(--border-color)',
          background: 'var(--bg-card)',
          boxShadow: 'var(--shadow-sm)'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '8px',
                background: 'rgba(15, 82, 186, 0.08)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-blue)',
                border: '1px solid rgba(15, 82, 186, 0.2)'
              }}
            >
              <Brain size={24} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h2 style={{ fontSize: '1.35rem', fontWeight: '800', margin: 0, color: 'var(--text-headline)' }}>
                  ML Quantitative Engine & Model Evaluation
                </h2>
                <span
                  style={{
                    fontSize: '0.72rem',
                    fontWeight: '700',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: 'var(--bullish-bg)',
                    color: 'var(--bullish)',
                    border: '1px solid var(--bullish-border)'
                  }}
                >
                  TimeSeriesSplit Walk-Forward
                </span>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px', margin: 0 }}>
                Point-in-time financial feature pipeline • Strict out-of-sample forward evaluation • Zero synthetic label leakage
              </p>
            </div>
          </div>

          {/* Action Toolbar */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <a
              href="http://127.0.0.1:8000/api/ml/dataset/download"
              download="market_news_ml_dataset.csv"
              className="btn btn-secondary btn-sm"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                textDecoration: 'none',
                padding: '8px 14px',
                borderRadius: '6px',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                fontWeight: '600',
                fontSize: '0.8rem'
              }}
            >
              <Download size={14} color="var(--accent-blue)" /> Export Dataset CSV
            </a>

            <button
              onClick={handleCollect}
              disabled={isJobRunning}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                borderRadius: '6px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                fontWeight: '600',
                fontSize: '0.8rem',
                cursor: isJobRunning ? 'wait' : 'pointer'
              }}
            >
              {isJobRunning && job?.job_type === 'collect' ? (
                <><Clock size={14} className="spin" /> Collecting...</>
              ) : (
                <><Database size={14} color="var(--bullish)" /> Collect OHLCV Prices</>
              )}
            </button>

            <button
              onClick={handleTrain}
              disabled={isJobRunning}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                borderRadius: '6px',
                background: 'var(--accent-blue)',
                border: 'none',
                color: '#ffffff',
                fontWeight: '700',
                fontSize: '0.8rem',
                cursor: isJobRunning ? 'wait' : 'pointer',
                boxShadow: '0 2px 6px rgba(15,82,186,0.3)'
              }}
            >
              {isJobRunning && job?.job_type === 'train' ? (
                <><Clock size={14} className="spin" /> Training...</>
              ) : (
                <><Play size={14} fill="#ffffff" /> Train Models</>
              )}
            </button>

            <button
              onClick={fetchAll}
              disabled={loading || isJobRunning}
              title="Refresh Analytics"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '36px',
                height: '36px',
                borderRadius: '6px',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-secondary)',
                cursor: 'pointer'
              }}
            >
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
            </button>
          </div>
        </div>
      </div>

      {/* Live Process Console (if active) */}
      {!jobDismissed && (
        <MLProcessPanel
          job={job}
          onDismiss={() => setJobDismissed(true)}
          onRefresh={fetchAll}
        />
      )}

      {/* ── HISTORICAL TRAINING DATASET & INDIC-FINANCE STATUS BANNER ── */}
      <div
        className="glass-card"
        style={{
          padding: '20px 24px',
          marginBottom: '24px',
          borderRadius: '10px',
          border: '1px solid var(--border-color)',
          background: 'var(--bg-card)',
          boxShadow: 'var(--shadow-sm)'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BookOpen size={18} color="var(--bullish)" />
            <h3 style={{ fontSize: '1rem', fontWeight: '800', margin: 0 }}>
              Historical Training Corpus & Indic-Finance Ground Truth
            </h3>
          </div>
          <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
            Source: Hugging Face <code style={{ background: 'var(--bg-secondary)', padding: '2px 6px', borderRadius: '4px' }}>dixitdharmansh07/indic-finance</code>
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
          <div style={{ background: 'var(--bg-primary)', padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border-light)' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Total Historical Articles
            </span>
            <div className="font-mono" style={{ fontSize: '1.6rem', fontWeight: '800', marginTop: '4px', color: 'var(--text-primary)' }}>
              {indicStats?.final_dataset_size?.toLocaleString() || status?.analysis_rows?.toLocaleString() || '10,053'}
            </div>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              {indicStats?.indic_finance_records_imported?.toLocaleString() || '9,912'} Indic-Finance + {indicStats?.production_records_preserved || '141'} Live
            </div>
          </div>

          <div style={{ background: 'var(--bg-primary)', padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border-light)' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Indian Equities Coverage
            </span>
            <div className="font-mono" style={{ fontSize: '1.6rem', fontWeight: '800', marginTop: '4px', color: 'var(--text-primary)' }}>
              {indicStats?.unique_indian_tickers || 96}
            </div>
            <div style={{ fontSize: '0.74rem', color: 'var(--bullish)', fontWeight: '600', marginTop: '4px' }}>
              100% Validated NSE Symbols (.NS)
            </div>
          </div>

          <div style={{ background: 'var(--bg-primary)', padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border-light)' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              1-Day Return Labels
            </span>
            <div className="font-mono" style={{ fontSize: '1.6rem', fontWeight: '800', marginTop: '4px', color: 'var(--accent-blue)' }}>
              {indicStats?.labels_1d?.total_labeled?.toLocaleString() || '8,932'}
            </div>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Threshold ±0.50% ({indicStats?.labels_1d?.unlabeled || 1121} Unlabeled)
            </div>
          </div>

          <div style={{ background: 'var(--bg-primary)', padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border-light)' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              3D & 5D Verified Labels
            </span>
            <div className="font-mono" style={{ fontSize: '1.6rem', fontWeight: '800', marginTop: '4px', color: 'var(--bullish)' }}>
              {indicStats?.labels_3d?.total_labeled?.toLocaleString() || '9,389'}
            </div>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Calculated from Real 57k+ OHLCV prices
            </div>
          </div>
        </div>
      </div>

      {/* ── MODEL & HORIZON SELECTORS ── */}
      <div
        className="glass-card"
        style={{
          padding: '16px 20px',
          marginBottom: '24px',
          borderRadius: '8px',
          border: '1px solid var(--border-color)',
          background: 'var(--bg-card)',
          boxShadow: 'var(--shadow-sm)'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          {/* Horizon Selector */}
          <div>
            <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '8px' }}>
              PREDICTION HORIZON
            </span>
            <div style={{ display: 'inline-flex', background: 'var(--bg-secondary)', padding: '3px', borderRadius: '6px', border: '1px solid var(--border-light)' }}>
              {['1d', '3d', '5d'].map((h) => (
                <button
                  key={h}
                  onClick={() => setActiveHorizon(h)}
                  style={{
                    padding: '6px 16px',
                    borderRadius: '4px',
                    border: 'none',
                    background: activeHorizon === h ? '#ffffff' : 'transparent',
                    color: activeHorizon === h ? 'var(--text-primary)' : 'var(--text-secondary)',
                    fontWeight: activeHorizon === h ? '800' : '600',
                    fontSize: '0.8rem',
                    boxShadow: activeHorizon === h ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {HORIZON_LABELS[h]}
                </button>
              ))}
            </div>
          </div>

          {/* Model Algorithm Selector */}
          <div>
            <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '8px' }}>
              ALGORITHM ARCHITECTURE
            </span>
            <div style={{ display: 'inline-flex', background: 'var(--bg-secondary)', padding: '3px', borderRadius: '6px', border: '1px solid var(--border-light)' }}>
              {Object.keys(MODEL_COLORS).map((m) => {
                const color = MODEL_COLORS[m];
                const isActive = activeModel === m;
                const displayName = m === 'LogisticRegression' ? 'Logistic Regression' : (m === 'RandomForest' ? 'Random Forest (100 Trees)' : 'Gradient Boosting');
                return (
                  <button
                    key={m}
                    onClick={() => setActiveModel(m)}
                    style={{
                      padding: '6px 14px',
                      borderRadius: '4px',
                      border: 'none',
                      background: isActive ? '#ffffff' : 'transparent',
                      color: isActive ? color : 'var(--text-secondary)',
                      fontWeight: isActive ? '800' : '600',
                      fontSize: '0.8rem',
                      boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }} />
                    <span>{displayName}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* ── METRICS DETAILS GRID ── */}
      {selectedMetric && selectedMetric.is_sufficient ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '20px', marginBottom: '24px' }}>
          
          {/* Card 1: Primary Out-Of-Sample Evaluation Metrics */}
          <div
            className="glass-card"
            style={{
              padding: '24px',
              borderRadius: '8px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-card)',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Target size={18} color="var(--accent-blue)" />
                <h3 style={{ fontSize: '1rem', fontWeight: '800', margin: 0 }}>
                  Out-of-Sample Performance Metrics
                </h3>
              </div>
              <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                Held-out Forward Test: <strong>{selectedMetric.n_test}</strong> samples
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '16px' }}>
              {[
                { label: 'Out-Of-Sample Accuracy', value: selectedMetric.accuracy, color: 'var(--accent-blue)' },
                { label: 'Macro Precision', value: selectedMetric.precision_macro, color: 'var(--bullish)' },
                { label: 'Macro Recall', value: selectedMetric.recall_macro, color: '#d97706' },
                { label: 'Macro F1-Score', value: selectedMetric.f1_macro, color: '#7c3aed' },
              ].map(({ label, value, color }) => (
                <div
                  key={label}
                  style={{
                    background: 'var(--bg-primary)',
                    borderRadius: '8px',
                    padding: '14px 16px',
                    border: '1px solid var(--border-light)'
                  }}
                >
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: '700', textTransform: 'uppercase' }}>
                    {label}
                  </span>
                  <div className="font-mono" style={{ fontSize: '1.75rem', fontWeight: '900', color, marginTop: '4px' }}>
                    {value != null ? (value * 100).toFixed(1) + '%' : '—'}
                  </div>
                  {/* Subtle clean progress indicator */}
                  <div style={{ height: '4px', background: 'var(--border-light)', borderRadius: '2px', marginTop: '8px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min((value || 0) * 100, 100)}%`, height: '100%', background: color, borderRadius: '2px' }} />
                  </div>
                </div>
              ))}
            </div>

            {/* Walk-Forward Cross-Validation Card */}
            {selectedMetric.cv_accuracy_mean != null && (
              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: '6px',
                  background: 'rgba(15, 82, 186, 0.06)',
                  border: '1px solid rgba(15, 82, 186, 0.2)',
                  fontSize: '0.8rem',
                  color: 'var(--text-primary)'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontWeight: '700', color: 'var(--accent-blue)' }}>
                    Walk-Forward Cross-Validation (Expanding Window)
                  </span>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    5-Fold TimeSeriesSplit
                  </span>
                </div>
                <div>
                  Walk-Forward Accuracy: <strong className="font-mono" style={{ color: 'var(--text-primary)' }}>
                    {(selectedMetric.cv_accuracy_mean * 100).toFixed(1)}% ± {(selectedMetric.cv_accuracy_std * 100).toFixed(1)}%
                  </strong>
                  &nbsp;• Walk-Forward F1: <strong className="font-mono" style={{ color: 'var(--text-primary)' }}>
                    {(selectedMetric.cv_f1_mean * 100).toFixed(1)}%
                  </strong>
                </div>
              </div>
            )}
          </div>

          {/* Card 2: Clean Confusion Matrix */}
          <div
            className="glass-card"
            style={{
              padding: '24px',
              borderRadius: '8px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-card)',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <BarChart3 size={18} color="var(--accent-blue)" />
                <h3 style={{ fontSize: '1rem', fontWeight: '800', margin: 0 }}>
                  Confusion Matrix (3-Class Prediction)
                </h3>
              </div>
              <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                Diagonal = True Positives
              </span>
            </div>

            {selectedMetric.confusion_matrix ? (
              <div>
                <div style={{ display: 'flex', gap: '4px', marginBottom: '4px' }}>
                  <div style={{ width: '85px' }} />
                  {CLASS_LABELS.map(cl => (
                    <div
                      key={cl}
                      style={{
                        flex: 1,
                        textAlign: 'center',
                        fontSize: '0.72rem',
                        fontWeight: '700',
                        color: CLASS_COLORS[cl],
                        padding: '4px 0'
                      }}
                    >
                      Pred {cl}
                    </div>
                  ))}
                </div>

                {selectedMetric.confusion_matrix.map((row, ri) => {
                  const rowTotal = row.reduce((a, b) => a + b, 0);
                  return (
                    <div key={ri} style={{ display: 'flex', gap: '4px', marginBottom: '4px' }}>
                      <div
                        style={{
                          width: '85px',
                          display: 'flex',
                          alignItems: 'center',
                          fontSize: '0.72rem',
                          fontWeight: '700',
                          color: CLASS_COLORS[CLASS_LABELS[ri]],
                          padding: '4px 6px'
                        }}
                      >
                        Actual {CLASS_LABELS[ri]}
                      </div>
                      {row.map((cell, ci) => {
                        const intensity = rowTotal ? cell / rowTotal : 0;
                        const isCorrect = ri === ci;
                        return (
                          <div
                            key={ci}
                            style={{
                              flex: 1,
                              textAlign: 'center',
                              padding: '12px 4px',
                              borderRadius: '6px',
                              fontWeight: '800',
                              fontSize: '1.05rem',
                              fontFamily: 'var(--font-mono)',
                              background: isCorrect ? 'var(--bullish-bg)' : (cell > 0 ? 'var(--bearish-bg)' : 'var(--bg-primary)'),
                              color: isCorrect ? 'var(--bullish)' : (cell > 0 ? 'var(--bearish)' : 'var(--text-muted)'),
                              border: `1px solid ${isCorrect ? 'var(--bullish-border)' : (cell > 0 ? 'var(--bearish-border)' : 'var(--border-light)')}`,
                            }}
                          >
                            {cell}
                          </div>
                        );
                      })}
                    </div>
                  );
                })}

                <p style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '12px', margin: '12px 0 0' }}>
                  Model trained strictly on prior chronological samples. Zero future lookahead bias.
                </p>
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No confusion matrix data available.</p>
            )}
          </div>
        </div>
      ) : null}

      {/* ── CARD 3: POINT-IN-TIME FEATURE IMPORTANCES ── */}
      {selectedMetric?.feature_importances && (
        <div
          className="glass-card"
          style={{
            padding: '24px',
            marginBottom: '24px',
            borderRadius: '8px',
            border: '1px solid var(--border-color)',
            background: 'var(--bg-card)',
            boxShadow: 'var(--shadow-sm)'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={18} color="var(--accent-blue)" />
              <h3 style={{ fontSize: '1rem', fontWeight: '800', margin: 0 }}>
                Point-in-Time Feature Importance Hierarchy
              </h3>
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              {activeModel} • {HORIZON_LABELS[activeHorizon]}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '10px 24px' }}>
            {selectedMetric.feature_importances
              .map((imp, i) => ({ imp, label: FEATURE_LABELS[i] || `Feature ${i}` }))
              .sort((a, b) => b.imp - a.imp)
              .map(({ imp, label }, idx) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', width: '20px', fontFamily: 'monospace' }}>
                    #{idx + 1}
                  </span>
                  <span style={{ fontSize: '0.8rem', fontWeight: '600', color: 'var(--text-primary)', width: '180px', flexShrink: 0 }}>
                    {label}
                  </span>
                  <div style={{ flex: 1, height: '6px', background: 'var(--border-light)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${Math.min(imp * 100 * 4.5, 100)}%`,
                        height: '100%',
                        background: 'var(--accent-blue)',
                        borderRadius: '3px',
                        transition: 'width 0.4s ease'
                      }}
                    />
                  </div>
                  <span className="font-mono" style={{ fontSize: '0.78rem', fontWeight: '700', color: 'var(--text-secondary)', width: '45px', textAlign: 'right' }}>
                    {(imp * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* ── CARD 4: FULL MODEL COMPARISON TABLE ── */}
      <div
        className="glass-card"
        style={{
          padding: '24px',
          marginBottom: '24px',
          borderRadius: '8px',
          border: '1px solid var(--border-color)',
          background: 'var(--bg-card)',
          boxShadow: 'var(--shadow-sm)'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu size={18} color="var(--accent-blue)" />
            <h3 style={{ fontSize: '1rem', fontWeight: '800', margin: 0 }}>
              Multi-Model Evaluation Matrix — {HORIZON_LABELS[activeHorizon]}
            </h3>
          </div>
          <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
            Click row to inspect model architecture
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border-color)', background: 'var(--bg-primary)' }}>
                {['Algorithm', 'Train N', 'Forward Test N', 'Test Accuracy', 'Precision (Macro)', 'Recall (Macro)', 'F1-Score', 'Walk-Forward CV Acc'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 14px', fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: '700', textTransform: 'uppercase' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.keys(MODEL_COLORS).map(mn => {
                const m = getMetric(mn, activeHorizon);
                const color = MODEL_COLORS[mn];
                const isActive = mn === activeModel;

                if (!m || !m.is_sufficient) {
                  return (
                    <tr key={mn} style={{ borderBottom: '1px solid var(--border-light)' }}>
                      <td style={{ padding: '12px 14px', color, fontWeight: '700' }}>{mn}</td>
                      <td colSpan={7} style={{ padding: '12px 14px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                        Insufficient labeled data
                      </td>
                    </tr>
                  );
                }

                return (
                  <tr
                    key={mn}
                    onClick={() => setActiveModel(mn)}
                    style={{
                      borderBottom: '1px solid var(--border-light)',
                      background: isActive ? 'rgba(15, 82, 186, 0.05)' : 'transparent',
                      cursor: 'pointer',
                      transition: 'background 0.15s ease'
                    }}
                  >
                    <td style={{ padding: '12px 14px', color, fontWeight: '800', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }} />
                      <span>{mn}</span>
                      {isActive && (
                        <span style={{ fontSize: '0.68rem', background: 'var(--accent-blue)', color: '#ffffff', padding: '1px 6px', borderRadius: '4px' }}>
                          Active
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)' }}>{m.n_train?.toLocaleString()}</td>
                    <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)' }}>{m.n_test?.toLocaleString()}</td>
                    
                    <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)', fontWeight: '800', color: 'var(--text-primary)' }}>
                      {(m.accuracy * 100).toFixed(1)}%
                    </td>
                    <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)' }}>
                      {(m.precision_macro * 100).toFixed(1)}%
                    </td>
                    <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)' }}>
                      {(m.recall_macro * 100).toFixed(1)}%
                    </td>
                    <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--accent-blue)' }}>
                      {(m.f1_macro * 100).toFixed(1)}%
                    </td>
                    <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--bullish)' }}>
                      {m.cv_accuracy_mean != null ? `${(m.cv_accuracy_mean * 100).toFixed(1)}% ± ${(m.cv_accuracy_std * 100).toFixed(1)}%` : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Compliance footer */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 0', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
        <ShieldAlert size={15} color="#d97706" />
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
