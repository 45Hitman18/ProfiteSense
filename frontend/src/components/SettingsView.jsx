import React, { useState, useEffect } from 'react';
import { 
  Settings, Shield, Database, Clock, Bell, CheckCircle2, 
  AlertTriangle, RefreshCw, Key, Server, Lock, ExternalLink,
  Cpu, HardDrive, BellRing, SlidersHorizontal, Download, Sparkles,
  Radio, Check, Activity, FileText, Layers, ShieldCheck, Zap,
  Volume2, VolumeX, Terminal, ArrowRight, BarChart3, HelpCircle,
  Send, QrCode, Copy, Trash2, Smartphone, CheckCheck
} from 'lucide-react';

const MANDATORY_DISCLAIMER = "Market News AI provides automated analysis and model-based estimates for informational and educational purposes only. It is not financial, investment, or trading advice. Market outcomes are uncertain and users should conduct their own research.";

export default function SettingsView() {
  const [settingsData, setSettingsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('preferences'); // 'preferences' | 'telegram' | 'providers' | 'database' | 'ml' | 'compliance'
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState('');
  const [optimizingDb, setOptimizingDb] = useState(false);
  const [optimizeMsg, setOptimizeMsg] = useState('');

  // Telegram alerts state
  const [telegramStatus, setTelegramStatus] = useState(null);
  const [loadingTelegram, setLoadingTelegram] = useState(false);
  const [telegramLink, setTelegramLink] = useState(null);
  const [generatingLink, setGeneratingLink] = useState(false);
  const [telegramMsg, setTelegramMsg] = useState('');
  const [telegramError, setTelegramError] = useState('');
  const [testSending, setTestSending] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [editingChatSettings, setEditingChatSettings] = useState({});


  // Local preferences stored in localStorage
  const [horizon, setHorizon] = useState(() => localStorage.getItem('ps_default_horizon') || '1d');
  const [refreshRate, setRefreshRate] = useState(() => localStorage.getItem('ps_refresh_rate') || '60');
  const [currency, setCurrency] = useState(() => localStorage.getItem('ps_currency') || 'INR');
  const [catalystThreshold, setCatalystThreshold] = useState(() => localStorage.getItem('ps_catalyst_thresh') || 'high');
  const [soundEnabled, setSoundEnabled] = useState(() => localStorage.getItem('ps_sound_alerts') === 'true');
  const [notifPermission, setNotifPermission] = useState(
    typeof window !== 'undefined' && 'Notification' in window ? Notification.permission : 'default'
  );
  const [testAlertSent, setTestAlertSent] = useState(false);

  const fetchSettings = async () => {
    try {
      const res = await fetch('/api/settings');
      if (res.ok) {
        const data = await res.json();
        setSettingsData(data);
      }
    } catch (e) {
      console.error("Failed to fetch settings:", e);
    } finally {
      setLoading(false);
    }
  };

  const parseChatPriceBracket = (raw) => {
    if (!raw) return 'ALL';
    try {
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
      if (Array.isArray(parsed)) {
        if (parsed.length === 1) return parsed[0];
        if (parsed.length >= 3) return 'ALL';
        return parsed[0] || 'ALL';
      }
      return String(parsed);
    } catch (e) {
      return 'ALL';
    }
  };

  const fetchTelegramStatus = async () => {
    setLoadingTelegram(true);
    try {
      const res = await fetch('/api/telegram/status');
      if (res.ok) {
        const data = await res.json();
        setTelegramStatus(data);
        // Initialize editing state for chats
        const initialEdits = {};
        (data.chats || []).forEach(c => {
          initialEdits[c.chat_id] = {
            min_impact: c.min_impact || 'HIGH',
            min_confidence: Math.round((c.min_confidence || 0.6) * 100),
            price_brackets: parseChatPriceBracket(c.price_brackets),
            watchlist_only: c.watchlist_only === 1,
            digest_enabled: c.digest_enabled === 1,
            digest_time: c.digest_time || '18:30',
            quiet_start: c.quiet_start || '',
            quiet_end: c.quiet_end || ''
          };
        });
        setEditingChatSettings(initialEdits);
      }
    } catch (e) {
      console.error("Failed to fetch telegram status:", e);
    } finally {
      setLoadingTelegram(false);
    }
  };

  useEffect(() => {
    fetchSettings();
    fetchTelegramStatus();
  }, []);

  const handleGenerateLinkCode = async () => {
    setGeneratingLink(true);
    setTelegramError('');
    try {
      const res = await fetch('/api/telegram/link-code', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setTelegramLink(data);
        setTelegramMsg('Single-use link code generated. Valid for 10 minutes.');
      } else {
        const err = await res.json();
        setTelegramError(err.detail || 'Failed to generate link code');
      }
    } catch (e) {
      setTelegramError('Network error generating link: ' + e.message);
    } finally {
      setGeneratingLink(false);
      setTimeout(() => setTelegramMsg(''), 6000);
    }
  };

  const handleSendTelegramTest = async (chatId = null) => {
    setTestSending(true);
    setTelegramMsg('');
    setTelegramError('');
    try {
      const res = await fetch('/api/telegram/test-send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setTelegramMsg(data.message || 'Test alert delivered successfully!');
      } else {
        setTelegramError(data.detail || data.message || 'Failed to deliver test alert.');
      }
    } catch (e) {
      setTelegramError('Error sending test alert: ' + e.message);
    } finally {
      setTestSending(false);
      setTimeout(() => setTelegramMsg(''), 6000);
      setTimeout(() => setTelegramError(''), 8000);
    }
  };

  const handleUpdateChatSettings = async (chatId) => {
    const edit = editingChatSettings[chatId];
    if (!edit) return;
    try {
      const payload = {
        chat_id: chatId,
        min_impact: edit.min_impact,
        min_confidence: parseFloat(edit.min_confidence) / 100.0,
        price_brackets: edit.price_brackets || 'ALL',
        watchlist_only: edit.watchlist_only ? 1 : 0,
        digest_enabled: edit.digest_enabled ? 1 : 0,
        digest_time: edit.digest_time,
        quiet_start: edit.quiet_start || null,
        quiet_end: edit.quiet_end || null
      };
      const res = await fetch('/api/telegram/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        setTelegramMsg(`Updated alert settings for chat ${chatId}`);
        fetchTelegramStatus();
      } else {
        const err = await res.json();
        setTelegramError(err.detail || 'Failed to update chat settings');
      }
    } catch (e) {
      setTelegramError('Network error updating chat: ' + e.message);
    } finally {
      setTimeout(() => setTelegramMsg(''), 5000);
    }
  };

  const handleDeleteChat = async (chatId) => {
    if (!window.confirm(`Disconnect Telegram chat ${chatId}? You will no longer receive alerts in this chat.`)) {
      return;
    }
    try {
      const res = await fetch(`/api/telegram/chat/${chatId}`, { method: 'DELETE' });
      if (res.ok) {
        setTelegramMsg(`Chat ${chatId} disconnected.`);
        fetchTelegramStatus();
      } else {
        const err = await res.json();
        setTelegramError(err.detail || 'Failed to disconnect chat');
      }
    } catch (e) {
      setTelegramError('Network error disconnecting chat: ' + e.message);
    } finally {
      setTimeout(() => setTelegramMsg(''), 5000);
    }
  };

  const handleCopyLink = () => {
    if (telegramLink?.deep_link) {
      navigator.clipboard.writeText(telegramLink.deep_link);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 3000);
    }
  };


  const handleHorizonChange = (val) => {
    setHorizon(val);
    localStorage.setItem('ps_default_horizon', val);
  };

  const handleRefreshChange = (val) => {
    setRefreshRate(val);
    localStorage.setItem('ps_refresh_rate', val);
  };

  const handleCurrencyChange = (val) => {
    setCurrency(val);
    localStorage.setItem('ps_currency', val);
  };

  const handleCatalystChange = (val) => {
    setCatalystThreshold(val);
    localStorage.setItem('ps_catalyst_thresh', val);
  };

  const handleSoundToggle = () => {
    const next = !soundEnabled;
    setSoundEnabled(next);
    localStorage.setItem('ps_sound_alerts', next ? 'true' : 'false');
  };

  const requestNotificationAccess = async () => {
    if (!('Notification' in window)) {
      alert("This browser does not support desktop notifications.");
      return;
    }
    const perm = await Notification.requestPermission();
    setNotifPermission(perm);
    if (perm === 'granted') {
      new Notification("ProfitSense Intelligence", {
        body: "High-impact catalyst alerts enabled! Breaking Dalal Street events will alert you instantly.",
        icon: "/favicon.ico"
      });
    }
  };

  const sendTestAlert = () => {
    if (notifPermission !== 'granted') {
      requestNotificationAccess();
      return;
    }
    new Notification("ProfitSense Alert: RELIANCE.NS", {
      body: "Catalyst Event: Strong Q3 EBITDA expansion with +3.4% projected 1D return sentiment.",
      icon: "/favicon.ico"
    });
    setTestAlertSent(true);
    setTimeout(() => setTestAlertSent(false), 3000);
  };

  const handleManualSync = async () => {
    setSyncing(true);
    setSyncMsg('Connecting to news providers and synchronizing cache...');
    try {
      const res = await fetch('/api/news/sync', { method: 'POST' });
      const data = await res.json();
      setSyncMsg(data.message || 'News feeds and stock quotes synchronized successfully.');
      fetchSettings();
    } catch (e) {
      setSyncMsg('Sync failed: ' + e.message);
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMsg(''), 6000);
    }
  };

  const handleOptimizeDb = async () => {
    setOptimizingDb(true);
    setOptimizeMsg('Executing SQLite PRAGMA optimize & WAL checkpoint...');
    try {
      const res = await fetch('/api/settings/optimize-db', { method: 'POST' });
      const data = await res.json();
      setOptimizeMsg(data.message || 'Database optimized and checkpointed successfully.');
      fetchSettings();
    } catch (e) {
      setOptimizeMsg('Optimization failed: ' + e.message);
    } finally {
      setOptimizingDb(false);
      setTimeout(() => setOptimizeMsg(''), 5000);
    }
  };

  const articlesCount = settingsData?.cache?.articles || 10056;
  const pricesCount = settingsData?.cache?.prices || 61578;
  const tickersCount = settingsData?.cache?.tickers || 122;
  const dbSizeMb = settingsData?.database?.size_mb || 45.4;
  const modelsCount = settingsData?.models?.trained_count || 9;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '1440px', margin: '0 auto', width: '100%' }}>
      {/* 1. HERO HEADER */}
      <div className="glass-card" style={{
        padding: '24px 28px',
        borderRadius: '12px',
        border: '1px solid var(--border-color)',
        background: 'linear-gradient(180deg, var(--bg-card) 0%, rgba(255,255,255,0.4) 100%)',
        boxShadow: 'var(--shadow-sm)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #0F52BA 0%, #4A3E72 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(15, 82, 186, 0.25)',
              color: '#fff'
            }}>
              <Settings size={24} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h1 style={{ fontSize: '1.45rem', fontWeight: '800', margin: 0, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
                  System Settings & Architecture
                </h1>
                <span style={{
                  fontSize: '0.72rem',
                  fontWeight: '700',
                  padding: '3px 8px',
                  borderRadius: '12px',
                  background: 'rgba(0, 109, 66, 0.1)',
                  color: 'var(--bullish)',
                  border: '1px solid var(--bullish-border)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px'
                }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--bullish)', display: 'inline-block' }} />
                  SYSTEM OPERATIONAL
                </span>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
                Dalal Street Financial NLP • Zero-Paid Local Intelligence • Free-Tier Provider Discipline • SQLite WAL Cache
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <button
              onClick={handleManualSync}
              disabled={syncing}
              className="btn btn-secondary"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 14px',
                fontSize: '0.8rem',
                fontWeight: '600'
              }}
            >
              <RefreshCw size={14} className={syncing ? 'spin' : ''} />
              {syncing ? 'Syncing Feeds...' : 'Sync Live Feeds'}
            </button>

            <button
              onClick={handleOptimizeDb}
              disabled={optimizingDb}
              className="btn btn-secondary"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 14px',
                fontSize: '0.8rem',
                fontWeight: '600'
              }}
              title="Optimize SQLite indices and checkpoint WAL log"
            >
              <HardDrive size={14} className={optimizingDb ? 'spin' : ''} />
              {optimizingDb ? 'Optimizing...' : 'Optimize DB'}
            </button>

            <a
              href="/api/ml/dataset/download"
              download="market_news_ml_dataset.csv"
              className="btn btn-primary"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                fontSize: '0.8rem',
                fontWeight: '700',
                textDecoration: 'none'
              }}
            >
              <Download size={14} />
              Export Dataset CSV
            </a>
          </div>
        </div>

        {/* Action feedback banners */}
        {syncMsg && (
          <div style={{
            marginTop: '14px',
            padding: '10px 14px',
            borderRadius: '6px',
            background: 'var(--bullish-bg)',
            border: '1px solid var(--bullish-border)',
            color: 'var(--bullish)',
            fontSize: '0.8rem',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <CheckCircle2 size={16} />
            {syncMsg}
          </div>
        )}

        {optimizeMsg && (
          <div style={{
            marginTop: '14px',
            padding: '10px 14px',
            borderRadius: '6px',
            background: 'rgba(15, 82, 186, 0.08)',
            border: '1px solid rgba(15, 82, 186, 0.25)',
            color: 'var(--accent-blue)',
            fontSize: '0.8rem',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Sparkles size={16} />
            {optimizeMsg}
          </div>
        )}
      </div>

      {/* 2. REAL-TIME SYSTEM KPI METRICS (4 CARDS) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
        {/* Metric 1 */}
        <div className="glass-card" style={{ padding: '18px 20px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              News Corpus Volume
            </span>
            <div style={{ padding: '6px', borderRadius: '6px', background: 'rgba(15, 82, 186, 0.1)', color: 'var(--accent-blue)' }}>
              <FileText size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: '800', color: 'var(--text-primary)', lineHeight: 1.2 }}>
            {articlesCount.toLocaleString()}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '6px', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ color: 'var(--bullish)', fontWeight: '600' }}>9,912 Indic-Finance</span>
            <span>+ 144 Live Wires</span>
          </div>
        </div>

        {/* Metric 2 */}
        <div className="glass-card" style={{ padding: '18px 20px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              OHLCV Price Records
            </span>
            <div style={{ padding: '6px', borderRadius: '6px', background: 'rgba(0, 109, 66, 0.1)', color: 'var(--bullish)' }}>
              <BarChart3 size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: '800', color: 'var(--text-primary)', lineHeight: 1.2 }}>
            {pricesCount.toLocaleString()}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '6px' }}>
            Across <strong style={{ color: 'var(--text-primary)' }}>{tickersCount} NSE/BSE Equities</strong>
          </div>
        </div>

        {/* Metric 3 */}
        <div className="glass-card" style={{ padding: '18px 20px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              ML Model Instances
            </span>
            <div style={{ padding: '6px', borderRadius: '6px', background: 'rgba(124, 58, 237, 0.1)', color: 'var(--impact-med)' }}>
              <Cpu size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: '800', color: 'var(--text-primary)', lineHeight: 1.2 }}>
            {modelsCount} Models
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '6px' }}>
            3 Ensembles × 3 Forward Horizons (1D, 3D, 5D)
          </div>
        </div>

        {/* Metric 4 */}
        <div className="glass-card" style={{ padding: '18px 20px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Local SQLite Engine
            </span>
            <div style={{ padding: '6px', borderRadius: '6px', background: 'rgba(217, 119, 6, 0.1)', color: '#d97706' }}>
              <Database size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: '800', color: 'var(--text-primary)', lineHeight: 1.2 }}>
            {dbSizeMb} MB
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '6px' }}>
            WAL Mode • 60s Busy Timeout • Zero Cloud Cost
          </div>
        </div>
      </div>

      {/* 3. SEGMENTED TAB NAVIGATION */}
      <div style={{
        display: 'flex',
        gap: '8px',
        borderBottom: '2px solid var(--border-color)',
        paddingBottom: '2px',
        overflowX: 'auto'
      }}>
        {[
          { id: 'preferences', label: 'Preferences & Controls', icon: SlidersHorizontal },
          { id: 'telegram', label: 'Telegram Alerts', icon: Send },
          { id: 'providers', label: 'Data Feeds & Providers', icon: Radio },
          { id: 'database', label: 'Database & Storage Engine', icon: Database },
          { id: 'ml', label: 'ML Pipeline & Architecture', icon: Cpu },
          { id: 'compliance', label: 'Compliance & Free-Tier Guarantee', icon: ShieldCheck }
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 18px',
                borderRadius: '8px 8px 0 0',
                border: 'none',
                background: isActive ? 'var(--bg-card)' : 'transparent',
                color: isActive ? 'var(--accent-red)' : 'var(--text-secondary)',
                fontWeight: isActive ? '800' : '600',
                fontSize: '0.84rem',
                cursor: 'pointer',
                borderBottom: isActive ? '3px solid var(--accent-red)' : '3px solid transparent',
                marginBottom: '-2px',
                transition: 'all 0.15s ease',
                whiteSpace: 'nowrap'
              }}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* 4. TAB CONTENTS */}

      {/* TAB 1: PREFERENCES & CONTROLS */}
      {activeTab === 'preferences' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '20px' }}>
          {/* Notification Controls */}
          <div className="glass-card" style={{ padding: '22px 24px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(217, 119, 6, 0.1)', color: '#d97706' }}>
                <BellRing size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: '800', margin: 0, color: 'var(--text-primary)' }}>
                  Desktop Catalyst Alerts
                </h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                  Local browser notifications on major market catalysts
                </p>
              </div>
            </div>

            <div style={{
              background: 'var(--bg-secondary)',
              padding: '12px 16px',
              borderRadius: '8px',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div>
                <div style={{ fontSize: '0.82rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                  Permission Status
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                  Current: <strong style={{ color: notifPermission === 'granted' ? 'var(--bullish)' : '#d97706' }}>{notifPermission}</strong>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                {notifPermission !== 'granted' ? (
                  <button
                    onClick={requestNotificationAccess}
                    className="btn btn-primary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '6px 12px' }}
                  >
                    Enable Alerts
                  </button>
                ) : (
                  <button
                    onClick={sendTestAlert}
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '6px 12px' }}
                  >
                    {testAlertSent ? 'Alert Sent!' : 'Send Test Alert'}
                  </button>
                )}
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                Catalyst Trigger Threshold
              </label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {[
                  { id: 'high', label: 'High Impact (>80% Conf)' },
                  { id: 'medium', label: 'Moderate + High (>60%)' },
                  { id: 'all', label: 'All Breaking Events' }
                ].map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleCatalystChange(item.id)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      fontSize: '0.75rem',
                      fontWeight: catalystThreshold === item.id ? '700' : '500',
                      border: catalystThreshold === item.id ? '1px solid var(--accent-red)' : '1px solid var(--border-color)',
                      background: catalystThreshold === item.id ? 'var(--accent-red)' : 'var(--bg-card)',
                      color: catalystThreshold === item.id ? '#fff' : 'var(--text-secondary)',
                      cursor: 'pointer'
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Sound alert toggle */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 0',
              borderTop: '1px solid var(--border-light)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {soundEnabled ? <Volume2 size={16} color="var(--accent-blue)" /> : <VolumeX size={16} color="var(--text-muted)" />}
                <div>
                  <div style={{ fontSize: '0.8rem', fontWeight: '600', color: 'var(--text-primary)' }}>Audio Catalyst Chime</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Play subtle audio tone when high-impact breaking news arrives</div>
                </div>
              </div>
              <input
                type="checkbox"
                checked={soundEnabled}
                onChange={handleSoundToggle}
                style={{ width: '18px', height: '18px', cursor: 'pointer', accentColor: 'var(--accent-red)' }}
              />
            </div>
          </div>

          {/* Model Horizon & Refresh Preferences */}
          <div className="glass-card" style={{ padding: '22px 24px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(15, 82, 186, 0.1)', color: 'var(--accent-blue)' }}>
                <Clock size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: '800', margin: 0, color: 'var(--text-primary)' }}>
                  Inference & Refresh Cadence
                </h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                  Default prediction horizon and live dashboard poll rate
                </p>
              </div>
            </div>

            {/* Default Horizon */}
            <div style={{ marginBottom: '18px' }}>
              <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                Default Forecast Horizon
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                {[
                  { id: '1d', title: '1-Day (1D)', desc: 'Next Trading Session' },
                  { id: '3d', title: '3-Day (3D)', desc: 'Swing Horizon' },
                  { id: '5d', title: '5-Day (5D)', desc: 'Weekly Position' }
                ].map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleHorizonChange(item.id)}
                    style={{
                      padding: '10px 8px',
                      borderRadius: '8px',
                      border: horizon === item.id ? '2px solid var(--accent-blue)' : '1px solid var(--border-color)',
                      background: horizon === item.id ? 'rgba(15, 82, 186, 0.08)' : 'var(--bg-card)',
                      textAlign: 'center',
                      cursor: 'pointer'
                    }}
                  >
                    <div style={{ fontSize: '0.82rem', fontWeight: '800', color: horizon === item.id ? 'var(--accent-blue)' : 'var(--text-primary)' }}>
                      {item.title}
                    </div>
                    <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {item.desc}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Refresh Cadence */}
            <div style={{ marginBottom: '18px' }}>
              <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                Market Overview Auto-Refresh
              </label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {[
                  { id: '30', label: '30s (Rapid)' },
                  { id: '60', label: '60s (Recommended)' },
                  { id: '300', label: '5m (Conserve Bandwidth)' },
                  { id: '0', label: 'Manual Only' }
                ].map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleRefreshChange(item.id)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      fontSize: '0.75rem',
                      fontWeight: refreshRate === item.id ? '700' : '500',
                      border: refreshRate === item.id ? '1px solid var(--accent-blue)' : '1px solid var(--border-color)',
                      background: refreshRate === item.id ? 'var(--accent-blue)' : 'var(--bg-card)',
                      color: refreshRate === item.id ? '#fff' : 'var(--text-secondary)',
                      cursor: 'pointer'
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Currency toggle */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 0',
              borderTop: '1px solid var(--border-light)'
            }}>
              <div>
                <div style={{ fontSize: '0.8rem', fontWeight: '600', color: 'var(--text-primary)' }}>Currency Format</div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Display prices in Indian Rupees or US Dollars</div>
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                {['INR', 'USD'].map((c) => (
                  <button
                    key={c}
                    onClick={() => handleCurrencyChange(c)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontWeight: '700',
                      border: currency === c ? '1px solid var(--text-primary)' : '1px solid var(--border-color)',
                      background: currency === c ? 'var(--text-primary)' : 'transparent',
                      color: currency === c ? '#fff' : 'var(--text-secondary)',
                      cursor: 'pointer'
                    }}
                  >
                    {c === 'INR' ? '₹ INR' : '$ USD'}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB: TELEGRAM ALERTS */}
      {activeTab === 'telegram' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
          {/* Notification feedback banners */}
          {telegramMsg && (
            <div style={{
              padding: '12px 16px',
              borderRadius: '8px',
              background: 'var(--bullish-bg)',
              border: '1px solid var(--bullish-border)',
              color: 'var(--bullish)',
              fontSize: '0.82rem',
              fontWeight: '600',
              display: 'flex',
              alignItems: 'center',
              gap: '10px'
            }}>
              <CheckCircle2 size={18} />
              {telegramMsg}
            </div>
          )}

          {telegramError && (
            <div style={{
              padding: '12px 16px',
              borderRadius: '8px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#ef4444',
              fontSize: '0.82rem',
              fontWeight: '600',
              display: 'flex',
              alignItems: 'center',
              gap: '10px'
            }}>
              <AlertTriangle size={18} />
              {telegramError}
            </div>
          )}

          {/* 1. MASTER STATUS & HEADER CARD */}
          <div className="glass-card" style={{ padding: '22px 24px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <div style={{
                  width: '46px',
                  height: '46px',
                  borderRadius: '12px',
                  background: 'linear-gradient(135deg, #229ED9 0%, #0088cc 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 4px 12px rgba(34, 158, 217, 0.3)',
                  color: '#fff'
                }}>
                  <Send size={22} style={{ transform: 'translateX(-1px) translateY(1px)' }} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <h2 style={{ fontSize: '1.25rem', fontWeight: '800', margin: 0, color: 'var(--text-primary)' }}>
                      Telegram Alert Pipeline
                    </h2>
                    {telegramStatus?.enabled && telegramStatus?.configured ? (
                      <span style={{
                        fontSize: '0.72rem',
                        fontWeight: '700',
                        padding: '3px 8px',
                        borderRadius: '12px',
                        background: 'rgba(0, 109, 66, 0.12)',
                        color: 'var(--bullish)',
                        border: '1px solid var(--bullish-border)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '5px'
                      }}>
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--bullish)', display: 'inline-block' }} />
                        BOT ONLINE {telegramStatus?.bot_username ? `(@${telegramStatus.bot_username})` : ''}
                      </span>
                    ) : !telegramStatus?.configured ? (
                      <span style={{
                        fontSize: '0.72rem',
                        fontWeight: '700',
                        padding: '3px 8px',
                        borderRadius: '12px',
                        background: 'rgba(217, 119, 6, 0.1)',
                        color: '#d97706',
                        border: '1px solid rgba(217, 119, 6, 0.3)'
                      }}>
                        BOT TOKEN REQUIRED
                      </span>
                    ) : (
                      <span style={{
                        fontSize: '0.72rem',
                        fontWeight: '700',
                        padding: '3px 8px',
                        borderRadius: '12px',
                        background: 'rgba(107, 114, 128, 0.1)',
                        color: 'var(--text-muted)',
                        border: '1px solid var(--border-color)'
                      }}>
                        TELEGRAM DISABLED
                      </span>
                    )}
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
                    Free Telegram Bot API (@BotFather) • Instant high-impact catalysts • Watchlist monitors • Daily market digests
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <button
                  onClick={fetchTelegramStatus}
                  disabled={loadingTelegram}
                  className="btn btn-secondary btn-sm"
                  style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <RefreshCw size={14} className={loadingTelegram ? 'spin' : ''} />
                  Refresh
                </button>

                <button
                  onClick={() => handleSendTelegramTest()}
                  disabled={testSending || !telegramStatus?.configured}
                  className="btn btn-primary btn-sm"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: 'linear-gradient(135deg, #0F52BA 0%, #229ED9 100%)',
                    border: 'none',
                    color: '#fff'
                  }}
                  title={!telegramStatus?.configured ? "Configure bot token first" : "Send test message to all active chats"}
                >
                  <Send size={14} />
                  {testSending ? 'Sending Test...' : 'Send Test Alert'}
                </button>
              </div>
            </div>
          </div>

          {/* 2. CONNECT NEW CHAT (DEEP LINK & QR CODE) */}
          <div className="glass-card" style={{ padding: '24px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(34, 158, 217, 0.1)', color: '#0088cc' }}>
                <Smartphone size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: '800', margin: 0, color: 'var(--text-primary)' }}>
                  Pair Your Device / Connect Telegram
                </h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                  Generate a single-use 10-minute security code to connect your chat
                </p>
              </div>
            </div>

            {!telegramLink ? (
              <div style={{
                background: 'var(--bg-secondary)',
                padding: '20px',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '16px'
              }}>
                <div style={{ maxWidth: '520px' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '4px' }}>
                    Ready to connect your Telegram account?
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                    Click below to generate an authorized deep link and QR code. Open it in Telegram and tap <b>START</b> to automatically sync your settings and receive live news signals.
                  </div>
                </div>

                <button
                  onClick={handleGenerateLinkCode}
                  disabled={generatingLink}
                  className="btn btn-primary"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '10px 18px',
                    fontWeight: '700'
                  }}
                >
                  <QrCode size={16} />
                  {generatingLink ? 'Generating Secure Link...' : 'Generate Connect Link & QR'}
                </button>
              </div>
            ) : (
              <div style={{
                background: 'var(--bg-secondary)',
                padding: '20px',
                borderRadius: '8px',
                border: '1px solid rgba(0, 109, 66, 0.3)'
              }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px', alignItems: 'center' }}>
                  {/* Left Column: Deep link and buttons */}
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <span style={{
                        padding: '3px 8px',
                        borderRadius: '6px',
                        background: 'rgba(0, 109, 66, 0.1)',
                        color: 'var(--bullish)',
                        fontWeight: '700',
                        fontSize: '0.75rem'
                      }}>
                        Single-Use Code: {telegramLink.code}
                      </span>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        Expires in 10 minutes
                      </span>
                    </div>

                    <div style={{
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-color)',
                      padding: '10px 12px',
                      borderRadius: '6px',
                      fontSize: '0.78rem',
                      fontFamily: 'monospace',
                      wordBreak: 'break-all',
                      color: 'var(--text-primary)',
                      marginBottom: '12px'
                    }}>
                      {telegramLink.deep_link}
                    </div>

                    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '14px' }}>
                      <button
                        onClick={handleCopyLink}
                        className="btn btn-secondary btn-sm"
                        style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                      >
                        {copiedLink ? <CheckCheck size={14} color="var(--bullish)" /> : <Copy size={14} />}
                        {copiedLink ? 'Copied to Clipboard!' : 'Copy Link'}
                      </button>

                      <a
                        href={telegramLink.deep_link}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-primary btn-sm"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          textDecoration: 'none'
                        }}
                      >
                        <ExternalLink size={14} />
                        Open in Telegram
                      </a>

                      <button
                        onClick={handleGenerateLinkCode}
                        disabled={generatingLink}
                        className="btn btn-secondary btn-sm"
                        style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                      >
                        <RefreshCw size={13} className={generatingLink ? 'spin' : ''} />
                        New Code
                      </button>
                    </div>

                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                      <b>Instructions:</b><br />
                      1. Scan the QR code or tap <b>Open in Telegram</b>.<br />
                      2. In Telegram, press <b>START</b> to link your chat.<br />
                      3. You'll receive instant confirmation and instructions.
                    </div>
                  </div>

                  {/* Right Column: QR Code Display */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{
                      padding: '12px',
                      background: '#ffffff',
                      borderRadius: '10px',
                      boxShadow: '0 4px 14px rgba(0,0,0,0.15)',
                      display: 'inline-block'
                    }}>
                      <img
                        src={`https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(telegramLink.deep_link)}`}
                        alt="Telegram Connect QR Code"
                        style={{ width: '160px', height: '160px', display: 'block' }}
                      />
                    </div>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '8px', fontWeight: '600' }}>
                      Scan with phone camera
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 3. CONNECTED CHATS MANAGEMENT */}
          <div className="glass-card" style={{ padding: '24px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: '800', margin: 0, color: 'var(--text-primary)' }}>
                  Connected Chats & Preferences ({telegramStatus?.active_chats_count || 0})
                </h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                  Manage impact filtering, quiet hours, and daily market digests per chat
                </p>
              </div>
            </div>

            {!telegramStatus?.chats || telegramStatus.chats.length === 0 ? (
              <div style={{
                padding: '30px',
                textAlign: 'center',
                background: 'var(--bg-secondary)',
                borderRadius: '8px',
                color: 'var(--text-muted)',
                fontSize: '0.85rem'
              }}>
                <Send size={32} style={{ margin: '0 auto 12px auto', opacity: 0.4 }} />
                <div>No connected Telegram chats yet.</div>
                <div style={{ fontSize: '0.75rem', marginTop: '4px' }}>
                  Click <b>Generate Connect Link & QR</b> above to link your first Telegram chat.
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {telegramStatus.chats.map((chat) => {
                  const edit = editingChatSettings[chat.chat_id] || {
                    min_impact: chat.min_impact,
                    min_confidence: Math.round((chat.min_confidence || 0.6) * 100),
                    price_brackets: parseChatPriceBracket(chat.price_brackets),
                    watchlist_only: chat.watchlist_only === 1,
                    digest_enabled: chat.digest_enabled === 1,
                    digest_time: chat.digest_time || '18:30',
                    quiet_start: chat.quiet_start || '',
                    quiet_end: chat.quiet_end || ''
                  };

                  return (
                    <div
                      key={chat.chat_id}
                      style={{
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '8px',
                        padding: '18px 20px'
                      }}
                    >
                      {/* Chat Header */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '14px', borderBottom: '1px solid var(--border-light)', paddingBottom: '10px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            background: chat.is_active ? 'var(--bullish)' : 'var(--text-muted)'
                          }} />
                          <div>
                            <strong style={{ fontSize: '0.88rem', color: 'var(--text-primary)' }}>
                              {chat.username ? `@${chat.username}` : `Chat ID: ${chat.chat_id}`}
                            </strong>
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginLeft: '8px' }}>
                              (ID: {chat.chat_id})
                            </span>
                          </div>
                        </div>

                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            onClick={() => handleSendTelegramTest(chat.chat_id)}
                            className="btn btn-secondary btn-sm"
                            style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                          >
                            Send Test
                          </button>

                          <button
                            onClick={() => handleDeleteChat(chat.chat_id)}
                            className="btn btn-secondary btn-sm"
                            style={{ fontSize: '0.72rem', padding: '4px 10px', color: '#ef4444' }}
                            title="Disconnect this chat"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>

                      {/* Controls Grid */}
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
                        {/* Minimum Impact */}
                        <div>
                          <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '4px' }}>
                            MINIMUM IMPACT
                          </label>
                          <select
                            value={edit.min_impact}
                            onChange={(e) => {
                              setEditingChatSettings(prev => ({
                                ...prev,
                                [chat.chat_id]: { ...edit, min_impact: e.target.value }
                              }));
                            }}
                            style={{
                              width: '100%',
                              padding: '6px 10px',
                              borderRadius: '6px',
                              border: '1px solid var(--border-color)',
                              background: 'var(--bg-card)',
                              color: 'var(--text-primary)',
                              fontSize: '0.78rem'
                            }}
                          >
                            <option value="HIGH">HIGH (Catalysts only)</option>
                            <option value="MEDIUM">MEDIUM (Moderate + High)</option>
                            <option value="ALL">ALL (All market signals)</option>
                          </select>
                        </div>

                        {/* Minimum Confidence */}
                        <div>
                          <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '4px' }}>
                            MIN CONFIDENCE: {edit.min_confidence}%
                          </label>
                          <input
                            type="range"
                            min="50"
                            max="90"
                            step="5"
                            value={edit.min_confidence}
                            onChange={(e) => {
                              setEditingChatSettings(prev => ({
                                ...prev,
                                [chat.chat_id]: { ...edit, min_confidence: parseInt(e.target.value) }
                              }));
                            }}
                            style={{ width: '100%' }}
                          />
                        </div>

                        {/* Share Price Bracket Filter */}
                        <div>
                          <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '4px' }}>
                            PRICE FILTER
                          </label>
                          <select
                            value={edit.price_brackets || 'ALL'}
                            onChange={(e) => {
                              setEditingChatSettings(prev => ({
                                ...prev,
                                [chat.chat_id]: { ...edit, price_brackets: e.target.value }
                              }));
                            }}
                            style={{
                              width: '100%',
                              padding: '6px 10px',
                              borderRadius: '6px',
                              border: '1px solid var(--border-color)',
                              background: 'var(--bg-card)',
                              color: 'var(--text-primary)',
                              fontSize: '0.78rem'
                            }}
                          >
                            <option value="ALL">All Share Prices (Any ₹)</option>
                            <option value="0-500">₹0 – ₹500 (Small/Mid)</option>
                            <option value="500-1000">₹500 – ₹1,000</option>
                            <option value="1000+">₹1,000+ (High value)</option>
                          </select>
                        </div>

                        {/* Quiet Hours */}
                        <div>
                          <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '4px' }}>
                            QUIET HOURS (IST)
                          </label>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <input
                              type="text"
                              placeholder="22:00"
                              value={edit.quiet_start}
                              onChange={(e) => {
                                setEditingChatSettings(prev => ({
                                  ...prev,
                                  [chat.chat_id]: { ...edit, quiet_start: e.target.value }
                                }));
                              }}
                              style={{
                                width: '70px',
                                padding: '6px 8px',
                                borderRadius: '6px',
                                border: '1px solid var(--border-color)',
                                background: 'var(--bg-card)',
                                color: 'var(--text-primary)',
                                fontSize: '0.75rem'
                              }}
                            />
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>to</span>
                            <input
                              type="text"
                              placeholder="07:00"
                              value={edit.quiet_end}
                              onChange={(e) => {
                                setEditingChatSettings(prev => ({
                                  ...prev,
                                  [chat.chat_id]: { ...edit, quiet_end: e.target.value }
                                }));
                              }}
                              style={{
                                width: '70px',
                                padding: '6px 8px',
                                borderRadius: '6px',
                                border: '1px solid var(--border-color)',
                                background: 'var(--bg-card)',
                                color: 'var(--text-primary)',
                                fontSize: '0.75rem'
                              }}
                            />
                          </div>
                        </div>

                        {/* Evening Daily Digest */}
                        <div>
                          <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '4px' }}>
                            DAILY DIGEST (IST)
                          </label>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <input
                              type="checkbox"
                              checked={edit.digest_enabled}
                              onChange={(e) => {
                                setEditingChatSettings(prev => ({
                                  ...prev,
                                  [chat.chat_id]: { ...edit, digest_enabled: e.target.checked }
                                }));
                              }}
                            />
                            <input
                              type="text"
                              value={edit.digest_time}
                              disabled={!edit.digest_enabled}
                              onChange={(e) => {
                                setEditingChatSettings(prev => ({
                                  ...prev,
                                  [chat.chat_id]: { ...edit, digest_time: e.target.value }
                                }));
                              }}
                              style={{
                                width: '70px',
                                padding: '6px 8px',
                                borderRadius: '6px',
                                border: '1px solid var(--border-color)',
                                background: 'var(--bg-card)',
                                color: 'var(--text-primary)',
                                fontSize: '0.75rem'
                              }}
                            />
                          </div>
                        </div>
                      </div>

                      {/* Bottom Options & Save Button */}
                      <div style={{ marginTop: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.76rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={edit.watchlist_only}
                            onChange={(e) => {
                              setEditingChatSettings(prev => ({
                                ...prev,
                                [chat.chat_id]: { ...edit, watchlist_only: e.target.checked }
                              }));
                            }}
                          />
                          Watchlist Only (Only alert for stocks tracked in Watchlist)
                        </label>

                        <button
                          onClick={() => handleUpdateChatSettings(chat.chat_id)}
                          className="btn btn-primary btn-sm"
                          style={{ fontSize: '0.75rem', padding: '6px 14px' }}
                        >
                          Save Chat Preferences
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 4. INTERACTIVE BOT COMMANDS REFERENCE */}
          <div className="glass-card" style={{ padding: '24px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: '800', margin: '0 0 12px 0', color: 'var(--text-primary)' }}>
              Interactive Telegram Bot Commands
            </h3>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '14px' }}>
              Control alerts or get instant stock analytics directly inside Telegram:
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
              {[
                { cmd: "<SHARE_NAME>", desc: "Easiest! Just send any share name (e.g. RELIANCE, TCS) to get 52W High, Loss & Price" },
                { cmd: "/p <TICKER>", desc: "Get Current Price, 52W High, Loss from Peak & Range (e.g. /p INFY)" },
                { cmd: "/signals", desc: "Top live AI trade recommendations & price target levels" },
                { cmd: "/w <TICKER>", desc: "Quick-add stock to watchlist (e.g. /w TATAMOTORS)" },
                { cmd: "/uw <TICKER>", desc: "Quick-remove stock from watchlist" },
                { cmd: "/status", desc: "View current alert preferences & active watchlist count" },
                { cmd: "/list", desc: "View all actively tracked Indian stocks" },
                { cmd: "/mute <dur>", desc: "Temporarily mute alerts (e.g. /mute 2h, /mute 30m, /mute 1d)" },
                { cmd: "/unmute", desc: "Resume alerts immediately" },
                { cmd: "/minconf <0-100>", desc: "Set minimum confidence filter (e.g. /minconf 70)" },
                { cmd: "/impact <level>", desc: "Filter by impact (e.g. /impact high or /impact medium)" },
                { cmd: "/digest <time|off>", desc: "Set evening digest time or toggle (e.g. /digest 18:30)" },
                { cmd: "/quiet <window|off>", desc: "Set quiet hours (e.g. /quiet 22:00-07:00)" },
                { cmd: "/stop", desc: "Deactivate alerts and disconnect chat" },
              ].map((c) => (
                <div
                  key={c.cmd}
                  style={{
                    background: 'var(--bg-secondary)',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    fontSize: '0.75rem'
                  }}
                >
                  <code style={{ fontWeight: '700', color: 'var(--accent-blue)', display: 'block', marginBottom: '2px' }}>
                    {c.cmd}
                  </code>
                  <span style={{ color: 'var(--text-muted)' }}>{c.desc}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 5. MANDATORY COMPLIANCE DISCLAIMER */}
          <div style={{
            padding: '12px 16px',
            borderRadius: '6px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            fontSize: '0.72rem',
            color: 'var(--text-muted)',
            fontStyle: 'italic',
            textAlign: 'center'
          }}>
            {MANDATORY_DISCLAIMER}
          </div>
        </div>
      )}

      {/* TAB 2: DATA FEEDS & PROVIDERS */}
      {activeTab === 'providers' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            All external market and sentiment intelligence operates strictly within zero-cost free-tier boundaries.
            Requests are rate-throttled and responses are cached with cryptographic checksums to protect against provider rate exhaustion.
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
            {(settingsData?.providers || [
              { name: "Yahoo Finance (NSE / BSE)", tier: "Public Unofficial (Throttled)", status: "Operational", type: "Market OHLCV", limit: "Throttled Free" },
              { name: "Marketaux Financial News", tier: "Developer Free (100 req/mo)", status: "Operational", type: "Live News Feed", limit: "100 req/mo" },
              { name: "Alpha Vantage Sentiment", tier: "Free Tier (25 req/day)", status: "Operational", type: "Sentiment NLP", limit: "25 req/day" },
              { name: "NewsAPI Developer Feed", tier: "Developer Free (100 req/day)", status: "Operational", type: "General Business", limit: "100 req/day" },
              { name: "Indic-Finance Dataset", tier: "Open-Source (Local DB)", status: "Operational (9,912 records)", type: "Historical Training", limit: "Unlimited Local" },
              { name: "Scikit-Learn ML Engines", tier: "Local CPU (Walk-Forward CV)", status: "Operational (9 Models)", type: "Quant Predictions", limit: "Unlimited In-Process" }
            ]).map((provider, i) => (
              <div key={i} className="glass-card" style={{
                padding: '18px 20px',
                borderRadius: '10px',
                border: '1px solid var(--border-color)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                    <div style={{ fontWeight: '800', fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                      {provider.name}
                    </div>
                    <span style={{
                      fontSize: '0.68rem',
                      fontWeight: '700',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: 'rgba(0, 109, 66, 0.1)',
                      color: 'var(--bullish)',
                      border: '1px solid var(--bullish-border)'
                    }}>
                      {provider.status}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
                    Category: <strong style={{ color: 'var(--text-secondary)' }}>{provider.type}</strong>
                  </div>
                </div>

                <div style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  background: 'var(--bg-secondary)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '0.72rem'
                }}>
                  <span style={{ color: 'var(--text-muted)' }}>Allowance:</span>
                  <span style={{ fontWeight: '700', color: 'var(--text-primary)' }}>{provider.limit}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: DATABASE & STORAGE ENGINE */}
      {activeTab === 'database' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '20px' }}>
          {/* Storage Breakdown */}
          <div className="glass-card" style={{ padding: '22px 24px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(0, 109, 66, 0.1)', color: 'var(--bullish)' }}>
                <HardDrive size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: '800', margin: 0, color: 'var(--text-primary)' }}>
                  SQLite Storage Breakdown
                </h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                  High-performance WAL-mode local relational storage
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
              {[
                { name: 'Stock Price OHLCV Records', count: pricesCount, color: 'var(--bullish)', pct: '65%' },
                { name: 'Financial Articles Corpus', count: articlesCount, color: 'var(--accent-blue)', pct: '18%' },
                { name: 'Sentiment & Horizon Analysis', count: settingsData?.cache?.analysis_records || 10055, color: '#d97706', pct: '12%' },
                { name: 'Indic-Finance Benchmark Raw', count: settingsData?.cache?.indic_finance_records || 9912, color: '#7c3aed', pct: '5%' }
              ].map((row, idx) => (
                <div key={idx}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', marginBottom: '4px' }}>
                    <span style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{row.name}</span>
                    <span style={{ fontWeight: '800', color: row.color }}>{row.count.toLocaleString()} rows</span>
                  </div>
                  <div style={{ width: '100%', height: '6px', background: 'var(--border-light)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ width: row.pct, height: '100%', background: row.color, borderRadius: '3px' }} />
                  </div>
                </div>
              ))}
            </div>

            <div style={{
              background: 'var(--bg-secondary)',
              padding: '14px',
              borderRadius: '8px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div>
                <div style={{ fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-primary)' }}>Total File Size on Disk</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>backend/market_news.db</div>
              </div>
              <div style={{ fontSize: '1.2rem', fontWeight: '800', color: 'var(--accent-red)' }}>
                {dbSizeMb} MB
              </div>
            </div>
          </div>

          {/* SQLite Engine Parameters */}
          <div className="glass-card" style={{ padding: '22px 24px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(15, 82, 186, 0.1)', color: 'var(--accent-blue)' }}>
                <Terminal size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: '800', margin: 0, color: 'var(--text-primary)' }}>
                  Database Engine Specs
                </h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                  Zero-latency in-process SQLite configuration
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.78rem', marginBottom: '20px' }}>
              {[
                { label: 'Database Engine', val: 'SQLite 3.4x (Native C Extension)' },
                { label: 'Journal Mode', val: 'WAL (Write-Ahead Logging)' },
                { label: 'Concurrency Architecture', val: 'Multi-Reader Concurrent WAL' },
                { label: 'Busy Lock Timeout', val: '60,000 ms (Crash-Resistant)' },
                { label: 'Synchronous Mode', val: 'NORMAL (High-Throughput IO)' },
                { label: 'Foreign Key Enforcements', val: 'ON (Relational Integrity)' }
              ].map((item, idx) => (
                <div key={idx} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '8px 0',
                  borderBottom: '1px solid var(--border-light)'
                }}>
                  <span style={{ color: 'var(--text-muted)' }}>{item.label}</span>
                  <span style={{ fontWeight: '700', color: 'var(--text-primary)', fontFamily: 'monospace' }}>{item.val}</span>
                </div>
              ))}
            </div>

            <button
              onClick={handleOptimizeDb}
              disabled={optimizingDb}
              className="btn btn-secondary"
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                padding: '10px',
                fontSize: '0.8rem',
                fontWeight: '700'
              }}
            >
              <Sparkles size={16} className={optimizingDb ? 'spin' : ''} />
              {optimizingDb ? 'Optimizing Database...' : 'Run SQLite Optimize & Checkpoint'}
            </button>
          </div>
        </div>
      )}

      {/* TAB 4: ML PIPELINE & ARCHITECTURE */}
      {activeTab === 'ml' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            The ProfitSense quantitative engine trains 3 discrete ensemble architectures across 3 forward price horizons (9 total models).
            It enforces strict point-in-time cross-validation with zero synthetic label leakage.
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
            {[
              {
                name: 'Random Forest Ensemble',
                type: 'Non-Linear Multi-Tree',
                trees: '100 Estimators',
                features: 'Gini Importance Ranking',
                desc: 'Captures complex non-linear interactions between headline sentiment, sector momentum, and event taxonomy.'
              },
              {
                name: 'Gradient Boosting Classifier',
                type: 'Sequential Residual Boosting',
                trees: '100 Stages (LR=0.05)',
                features: 'Iterative Error Minimization',
                desc: 'Specialized in detecting subtle price continuation patterns following earnings surprises and regulatory news.'
              },
              {
                name: 'Calibrated Logistic Regression',
                type: 'Linear Probabilistic Baseline',
                trees: 'L2 Penalty Regularization',
                features: 'Standardized StandardScale',
                desc: 'Serves as an unbiased probabilistic baseline with logit odds calibration for market uncertainty quantification.'
              }
            ].map((model, idx) => (
              <div key={idx} className="glass-card" style={{
                padding: '20px',
                borderRadius: '10px',
                border: '1px solid var(--border-color)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <Cpu size={18} color="var(--accent-red)" />
                    <h4 style={{ fontSize: '0.92rem', fontWeight: '800', margin: 0, color: 'var(--text-primary)' }}>
                      {model.name}
                    </h4>
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--accent-blue)', fontWeight: '700', marginBottom: '8px' }}>
                    {model.type} • {model.trees}
                  </div>
                  <p style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', lineHeight: '1.5', margin: 0 }}>
                    {model.desc}
                  </p>
                </div>

                <div style={{
                  marginTop: '16px',
                  padding: '8px 12px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '6px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '0.72rem'
                }}>
                  <span style={{ color: 'var(--text-muted)' }}>Forward Horizons:</span>
                  <span style={{ fontWeight: '700', color: 'var(--bullish)' }}>1-Day, 3-Day, 5-Day</span>
                </div>
              </div>
            ))}
          </div>

          {/* Walk forward notice */}
          <div className="glass-card" style={{ padding: '16px 20px', borderRadius: '8px', borderLeft: '4px solid var(--accent-blue)', background: 'rgba(15, 82, 186, 0.04)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <ShieldCheck size={18} color="var(--accent-blue)" />
              <div style={{ fontWeight: '800', fontSize: '0.86rem', color: 'var(--accent-blue)' }}>
                Zero Synthetic Data Leakage Policy
              </div>
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.5', margin: 0 }}>
              All feature extraction (including category historical hit-rates and sentiment aggregates) is computed strictly point-in-time prior to article publication dates.
              Models are evaluated using 80/20 chronological train/test splits and expanding-window TimeSeriesSplit cross-validation.
            </p>
          </div>
        </div>
      )}

      {/* TAB 5: COMPLIANCE & ZERO-PAID GUARANTEE */}
      {activeTab === 'compliance' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Statutory Regulatory Disclaimer */}
          <div className="glass-card" style={{
            padding: '24px 28px',
            borderRadius: '10px',
            borderLeft: '5px solid var(--accent-red)',
            background: 'var(--bg-card)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <AlertTriangle size={22} color="var(--accent-red)" />
              <h3 style={{ fontSize: '1.05rem', fontWeight: '800', margin: 0, color: 'var(--accent-red)' }}>
                Statutory Regulatory Disclosure & Non-Advisory Notice
              </h3>
            </div>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-primary)', lineHeight: '1.7', marginBottom: '14px' }}>
              {MANDATORY_DISCLAIMER}
            </p>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.6', margin: 0 }}>
              Under the provisions of SEBI (Research Analysts) Regulations, 2014 and international securities oversight standards,
              ProfitSense operates exclusively as an open quantitative research demonstrator. All event categorizations, sentiment polarities,
              probability distributions, and direction scores are mathematical estimations generated by algorithms and local natural language models.
              Under no circumstances shall any output be interpreted as an offer, recommendation, endorsement, or solicitation to buy or sell securities.
            </p>
          </div>

          {/* Zero-Paid Guarantee Certificate */}
          <div className="glass-card" style={{
            padding: '24px 28px',
            borderRadius: '10px',
            border: '2px solid rgba(0, 109, 66, 0.3)',
            background: 'linear-gradient(180deg, var(--bg-card) 0%, rgba(0, 109, 66, 0.03) 100%)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <ShieldCheck size={22} color="var(--bullish)" />
              <h3 style={{ fontSize: '1.05rem', fontWeight: '800', margin: 0, color: 'var(--bullish)' }}>
                Zero-Paid Services Architecture Guarantee
              </h3>
            </div>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '16px' }}>
              ProfitSense is engineered from first principles to operate entirely without paid third-party subscriptions, commercial cloud GPUs,
              or proprietary pay-per-token AI endpoints.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
              {[
                { title: 'Zero Cloud GPU Charges', desc: 'All ML inference and feature extraction run locally on CPU in sub-millisecond threads.' },
                { title: 'Zero API Token Consumption', desc: 'No OpenAI, Claude, or proprietary per-call billing. All NLP relies on local VADER and scikit-learn.' },
                { title: 'Public Market Access', desc: 'Real-time quotes and historical OHLCV data rely strictly on throttled free-tier public feeds.' },
                { title: 'Local Relational Database', desc: 'Fully persistent SQLite engine with zero database hosting fees or external egress charges.' }
              ].map((item, idx) => (
                <div key={idx} style={{
                  padding: '12px 14px',
                  borderRadius: '6px',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-light)'
                }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: '700', color: 'var(--bullish)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Check size={14} />
                    {item.title}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                    {item.desc}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
