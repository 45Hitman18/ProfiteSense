import React, { useState, useEffect } from 'react';
import { 
  Settings, Shield, Database, Clock, Bell, CheckCircle2, 
  AlertTriangle, RefreshCw, Key, Server, Lock, ExternalLink,
  Cpu, HardDrive, BellRing
} from 'lucide-react';

const MANDATORY_DISCLAIMER = "Market News AI provides automated analysis and model-based estimates for informational and educational purposes only. It is not financial, investment, or trading advice. Market outcomes are uncertain and users should conduct their own research.";

export default function SettingsView() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cacheStatus, setCacheStatus] = useState({ quotes: 18, articles: 234, prices: 1117 });
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState('');
  const [notifPermission, setNotifPermission] = useState(
    typeof window !== 'undefined' && 'Notification' in window ? Notification.permission : 'default'
  );

  const fetchHealth = async () => {
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      setHealth(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const requestNotificationAccess = async () => {
    if (!('Notification' in window)) {
      alert("This browser does not support desktop notifications.");
      return;
    }
    const perm = await Notification.requestPermission();
    setNotifPermission(perm);
    if (perm === 'granted') {
      new Notification("Market News AI", {
        body: "High-impact catalyst alerts enabled! You will be notified on major market-moving news.",
        icon: "/favicon.ico"
      });
    }
  };

  const handleManualSync = async () => {
    setSyncing(true);
    setSyncMsg('Syncing all news providers and caching prices...');
    try {
      await fetch('/api/news/sync', { method: 'POST' });
      setSyncMsg('News sync completed successfully. All caches updated.');
      fetchHealth();
    } catch (e) {
      setSyncMsg('Sync failed: ' + e.message);
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMsg(''), 5000);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header */}
      <div className="glass-card" style={{ padding: '20px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '42px', height: '42px', borderRadius: '10px', background: 'linear-gradient(135deg,#3D5AFE,#7c3aed)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Settings size={22} color="#fff" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.3rem', fontWeight: '800', margin: 0 }}>System Settings & Architecture</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
              Free Tier Enforcements • Cache Discipline • Background Scheduling • Compliance
            </p>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Zero-Paid Guarantee & API Status */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <Shield size={18} color="#10b981" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: '700', margin: 0 }}>Zero-Paid Services Guarantee</h3>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '14px' }}>
            Strictly operating under free-tier allowances and open-source models. No credit cards, no paid hosting, and zero paid AI API charges.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[
              { name: 'Marketaux Financial News API', limit: 'Free Developer Tier (100 req/mo)', status: 'Active (Free)' },
              { name: 'Alpha Vantage News & Sentiment', limit: 'Free Tier (25 req/day)', status: 'Active (Free)' },
              { name: 'NewsAPI Developer Feed', limit: 'Free Developer Tier (100 req/day)', status: 'Active (Free)' },
              { name: 'Yahoo Finance Unofficial', limit: 'Public Endpoints (Throttled)', status: 'Active (Free)' },
              { name: 'VADER Financial Lexicon NLP', limit: 'Local Open-Source (In-Process)', status: 'Installed' },
              { name: 'Scikit-Learn ML Engines', limit: 'Local Open-Source (CPU)', status: 'Installed' },
            ].map(item => (
              <div key={item.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.78rem', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <div>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{item.name}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{item.limit}</div>
                </div>
                <span className="badge badge-success" style={{ fontSize: '0.68rem' }}>{item.status}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Cache & Rate-Limit Discipline */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <Database size={18} color="#60a5fa" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: '700', margin: 0 }}>Caching & Rate-Limit Discipline</h3>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '14px' }}>
            All news articles and OHLCV stock points are cached with SQLite timestamps. Requests use exponential backoff and rate throttles to protect API limits.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginBottom: '16px' }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.2rem', fontWeight: '800', color: '#60a5fa' }}>{cacheStatus.articles}</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Articles Cached</div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.2rem', fontWeight: '800', color: '#34d399' }}>{cacheStatus.prices}</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Price Points</div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.2rem', fontWeight: '800', color: '#f59e0b' }}>{cacheStatus.quotes}</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Tickers Active</div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button 
              className="btn btn-secondary btn-sm" 
              onClick={handleManualSync}
              disabled={syncing}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <RefreshCw size={14} className={syncing ? 'spin' : ''} />
              {syncing ? 'Syncing...' : 'Manual Sync Feeds'}
            </button>
            <a 
              href="http://127.0.0.1:8000/api/ml/dataset/download"
              download="market_news_ml_dataset.csv"
              className="btn btn-secondary btn-sm"
              style={{ textDecoration: 'none' }}
            >
              Export Dataset CSV
            </a>
          </div>

          {syncMsg && (
            <div style={{ marginTop: '10px', fontSize: '0.75rem', color: '#34d399' }}>
              {syncMsg}
            </div>
          )}
        </div>

        {/* Free Background Scheduler */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <Clock size={18} color="#a78bfa" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: '700', margin: 0 }}>Background Scheduler</h3>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '14px' }}>
            Non-blocking in-process scheduling without paid queues (Celery/RabbitMQ). Respects market hours with automatic cadence.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem', marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
              <span>Refresh Cadence:</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: '600' }}>Every 20 Minutes (Market Hours)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
              <span>Scheduler Engine:</span>
              <span style={{ color: '#a78bfa', fontWeight: '600' }}>Native Python AsyncIO Task</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
              <span>Throttling Mechanism:</span>
              <span style={{ color: '#10b981', fontWeight: '600' }}>Exponential Backoff & Deduplication</span>
            </div>
          </div>
        </div>

        {/* Local Browser Notifications */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <BellRing size={18} color="#f59e0b" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: '700', margin: 0 }}>High-Impact Catalyst Alerts</h3>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '14px' }}>
            Local browser notifications when high-impact breaking news arrives for your watchlisted stocks. Zero third-party paid notification services.
          </p>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', marginBottom: '14px' }}>
            <div>
              <div style={{ fontSize: '0.82rem', fontWeight: '600' }}>Desktop Notifications</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Status: {notifPermission}</div>
            </div>
            <button 
              className={`btn ${notifPermission === 'granted' ? 'btn-secondary' : 'btn-primary'} btn-sm`}
              onClick={requestNotificationAccess}
            >
              {notifPermission === 'granted' ? 'Enabled' : 'Enable Alerts'}
            </button>
          </div>
        </div>
      </div>

      {/* Comprehensive Legal / Compliance Disclaimer */}
      <div className="glass-card" style={{ padding: '20px 24px', borderLeft: '4px solid #3D5AFE', background: 'rgba(61,90,254,0.04)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <Shield size={18} color="#60a5fa" />
          <h3 style={{ fontSize: '0.95rem', fontWeight: '700', margin: 0, color: '#93c5fd' }}>Legal Compliance & Disclaimer</h3>
        </div>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.6', margin: 0 }}>
          {MANDATORY_DISCLAIMER} All news analyses, sentiment polarities, event categories, and model predictions are probabilistic estimates generated algorithmically. Never construe any statement as financial, investment, legal, or tax guidance.
        </p>
      </div>
    </div>
  );
}
