import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, TrendingDown, Layers, BarChart2, ShieldCheck, Gauge } from 'lucide-react';

export default function MarketPulseView({ overview }) {
  const [sectors, setSectors] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/market/sectors')
      .then((res) => res.json())
      .then((data) => {
        setSectors(data || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  const mood = overview?.market_mood;
  const indices = overview?.indices || [];

  return (
    <div>
      {/* Top Banner: Market Mood Gauge */}
      <div className="glass-card" style={{ marginBottom: '24px', padding: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px', alignItems: 'center' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <Gauge size={20} color="#60a5fa" />
              <h2 style={{ fontSize: '1.25rem', fontWeight: '800' }}>Overall Market Mood & Volatility</h2>
            </div>
            <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', lineHeight: '1.5', marginBottom: '14px' }}>
              {mood?.summary || 'Algorithmic market sentiment derived from index breadth, VIX implied volatility, and catalyst news frequency.'}
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{
                fontSize: '1.5rem',
                fontWeight: '800',
                color: (mood?.score || 50) > 60 ? 'var(--bullish)' : ((mood?.score || 50) < 40 ? 'var(--bearish)' : 'var(--neutral)')
              }}>
                {mood?.label || 'Neutral'}
              </span>
              <span className="font-mono" style={{ fontSize: '1.1rem', color: 'var(--text-muted)' }}>
                ({mood?.score || 50}/100)
              </span>
            </div>
          </div>

          {/* Visual Gauge Bar */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
              <span>EXTREME FEAR / RISK-OFF (0)</span>
              <span>NEUTRAL (50)</span>
              <span>EXTREME GREED / RISK-ON (100)</span>
            </div>
            <div style={{ width: '100%', height: '14px', borderRadius: '7px', background: 'linear-gradient(90deg, #f43f5e, #f59e0b 50%, #10b981)', position: 'relative' }}>
              <div style={{
                position: 'absolute',
                top: '-4px',
                left: `${Math.min(Math.max(mood?.score || 50, 2), 98)}%`,
                transform: 'translateX(-50%)',
                width: '22px',
                height: '22px',
                borderRadius: '50%',
                backgroundColor: '#ffffff',
                border: '3px solid #111827',
                boxShadow: '0 0 10px rgba(0,0,0,0.6)'
              }}></div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '10px', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              <span>VIX Volatility: <strong className="font-mono" style={{ color: '#f3f4f6' }}>{mood?.vix?.toFixed(1) || '17.5'}</strong></span>
              <span>Data source: Yahoo Finance API (Free)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Major Indices Grid */}
      <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Activity size={18} color="#60a5fa" />
        <span>Benchmark Indices</span>
      </h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px', marginBottom: '28px' }}>
        {indices.map((idx) => {
          const isUp = idx.change_pct >= 0;
          return (
            <div key={idx.symbol} className="glass-card" style={{ padding: '16px' }}>
              <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                {idx.name}
              </span>
              <div className="font-mono" style={{ fontSize: '1.3rem', fontWeight: '800', marginBottom: '6px' }}>
                {idx.short === '10Y YIELD' ? `${idx.value.toFixed(2)}%` : idx.value.toLocaleString()}
              </div>
              <div
                className="font-mono"
                style={{
                  fontSize: '0.85rem',
                  fontWeight: '700',
                  color: isUp ? 'var(--bullish)' : 'var(--bearish)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                {isUp ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {isUp ? '+' : ''}{idx.change_pct.toFixed(2)}%
                <span style={{ color: 'var(--text-muted)', fontWeight: '400', marginLeft: '4px' }}>
                  ({isUp ? '+' : ''}{idx.change.toFixed(2)})
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Sector Heatmap & Performance */}
      <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Layers size={18} color="#a78bfa" />
        <span>NSE / Sector Performance & Rotation</span>
      </h3>

      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <div className="pulse-dot" style={{ width: '18px', height: '18px', backgroundColor: '#3b82f6' }}></div>
          <p style={{ marginTop: '12px', color: 'var(--text-secondary)' }}>Loading sector metrics...</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '14px' }}>
          {sectors.map((sec) => {
            const isUp = sec.change_pct >= 0;
            return (
              <div key={sec.symbol} className="glass-card" style={{ padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <span style={{ fontSize: '0.9rem', fontWeight: '700', color: 'var(--text-primary)' }}>{sec.sector}</span>
                  <span className="badge-ticker">{sec.symbol}</span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '8px' }}>
                  <span className="font-mono" style={{ fontSize: '1.15rem', fontWeight: '700' }}>
                    ₹{sec.price ? sec.price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '0.00'}
                  </span>
                  <span
                    className="font-mono"
                    style={{
                      fontSize: '0.95rem',
                      fontWeight: '800',
                      color: isUp ? 'var(--bullish)' : 'var(--bearish)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    {isUp ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                    {isUp ? '+' : ''}{sec.change_pct.toFixed(2)}%
                  </span>
                </div>

                {/* Progress bar indication */}
                <div style={{ width: '100%', height: '5px', background: '#1e293b', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${Math.min(Math.abs(sec.change_pct) * 20, 100)}%`,
                    height: '100%',
                    backgroundColor: isUp ? 'var(--bullish)' : 'var(--bearish)',
                    borderRadius: '3px'
                  }}></div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
