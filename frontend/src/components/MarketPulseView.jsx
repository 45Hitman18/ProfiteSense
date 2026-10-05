import React, { useState, useEffect, useMemo } from 'react';
import {
  Activity, TrendingUp, TrendingDown, Layers, BarChart2, ShieldCheck, Gauge,
  Landmark, Cpu, Car, Flame, ShoppingBag, Pill, Pickaxe, HardHat, Radio,
  Building2, Zap, CreditCard, ArrowUpRight, ArrowDownRight, RefreshCw, Filter
} from 'lucide-react';

const SECTOR_ICONS = {
  'Banking & Finance': Landmark,
  'Information Technology': Cpu,
  'Automobile & Auto Ancillary': Car,
  'Energy & Petrochemicals': Flame,
  'Consumer Goods (FMCG)': ShoppingBag,
  'Pharmaceuticals & Healthcare': Pill,
  'Metals & Mining': Pickaxe,
  'Engineering & Infrastructure': HardHat,
  'Telecommunications': Radio,
  'Real Estate & Realty': Building2,
  'Power & Renewable Energy': Zap,
  'NBFC & Financial Services': CreditCard,
};

export default function MarketPulseView({ overview }) {
  const [sectors, setSectors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL'); // 'ALL' | 'GAINERS' | 'LOSERS'
  const [refreshing, setRefreshing] = useState(false);

  const fetchSectors = () => {
    setRefreshing(true);
    fetch('/api/market/sectors')
      .then((res) => res.json())
      .then((data) => {
        setSectors(data || []);
        setLoading(false);
        setRefreshing(false);
      })
      .catch((err) => {
        console.error('Error fetching sectors:', err);
        setLoading(false);
        setRefreshing(false);
      });
  };

  useEffect(() => {
    fetchSectors();
  }, []);

  const mood = overview?.market_mood;
  const indices = overview?.indices || [];

  // Filtered sectors
  const filteredSectors = useMemo(() => {
    if (filter === 'GAINERS') {
      return [...sectors].filter((s) => s.change_pct > 0).sort((a, b) => b.change_pct - a.change_pct);
    }
    if (filter === 'LOSERS') {
      return [...sectors].filter((s) => s.change_pct < 0).sort((a, b) => a.change_pct - b.change_pct);
    }
    return sectors;
  }, [sectors, filter]);

  // Sector breadth stats
  const advCount = sectors.filter((s) => s.change_pct > 0).length;
  const decCount = sectors.filter((s) => s.change_pct < 0).length;
  const flatCount = sectors.filter((s) => s.change_pct === 0).length;

  const score = mood?.score || 50;
  const vixVal = mood?.vix || 15.0;

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
      {/* ── TOP HERO: OVERALL MARKET MOOD & VOLATILITY ── */}
      <div
        className="glass-card"
        style={{
          marginBottom: '28px',
          padding: '24px 28px',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          background: 'var(--bg-card)',
          boxShadow: 'var(--shadow-sm)'
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '28px',
            alignItems: 'center'
          }}
        >
          {/* Left Column: Sentiment Label & Description */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  background: 'rgba(15, 82, 186, 0.08)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Gauge size={18} color="var(--accent-blue)" />
              </div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '800', margin: 0 }}>
                Overall Market Mood & Volatility
              </h2>
            </div>

            <p
              style={{
                fontSize: '0.86rem',
                color: 'var(--text-secondary)',
                lineHeight: '1.5',
                marginBottom: '16px'
              }}
            >
              {mood?.summary ||
                'Real-time synthesis of India VIX implied volatility, index market breadth, and catalyst news impact scores.'}
            </p>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              <span
                style={{
                  fontSize: '1.45rem',
                  fontWeight: '800',
                  color:
                    score > 60
                      ? 'var(--bullish)'
                      : score < 40
                      ? 'var(--bearish)'
                      : 'var(--neutral)'
                }}
              >
                {mood?.label || 'Neutral'}
              </span>
              <span
                className="font-mono"
                style={{
                  fontSize: '1.05rem',
                  fontWeight: '700',
                  color: 'var(--text-secondary)',
                  background: 'var(--bg-secondary)',
                  padding: '3px 10px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-light)'
                }}
              >
                {score}/100
              </span>

              {/* Volatility Regime Pill */}
              <span
                style={{
                  fontSize: '0.78rem',
                  fontWeight: '600',
                  padding: '3px 10px',
                  borderRadius: '6px',
                  background: vixVal < 18 ? 'var(--bullish-bg)' : vixVal < 24 ? 'var(--neutral-bg)' : 'var(--bearish-bg)',
                  color: vixVal < 18 ? 'var(--bullish)' : vixVal < 24 ? 'var(--neutral)' : 'var(--bearish)',
                  border: `1px solid ${vixVal < 18 ? 'var(--bullish-border)' : vixVal < 24 ? 'var(--neutral-border)' : 'var(--bearish-border)'}`
                }}
              >
                {vixVal < 18 ? 'Low Volatility Regime' : vixVal < 24 ? 'Moderate Volatility' : 'Elevated Volatility'}
              </span>
            </div>
          </div>

          {/* Right Column: Visual Gauge Slider & VIX Stats */}
          <div style={{ background: 'var(--bg-primary)', padding: '18px 20px', borderRadius: '8px', border: '1px solid var(--border-light)' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '0.72rem',
                fontWeight: '700',
                color: 'var(--text-muted)',
                marginBottom: '8px',
                letterSpacing: '0.03em'
              }}
            >
              <span style={{ color: 'var(--bearish)' }}>EXTREME FEAR (0)</span>
              <span style={{ color: 'var(--neutral)' }}>NEUTRAL (50)</span>
              <span style={{ color: 'var(--bullish)' }}>EXTREME GREED (100)</span>
            </div>

            {/* Slider Bar */}
            <div
              style={{
                width: '100%',
                height: '10px',
                borderRadius: '5px',
                background: 'linear-gradient(90deg, #dc2626 0%, #ea580c 25%, #d97706 45%, #059669 80%, #047857 100%)',
                position: 'relative',
                marginBottom: '14px',
                boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.1)'
              }}
            >
              {/* Slider Pin Marker */}
              <div
                style={{
                  position: 'absolute',
                  top: '-5px',
                  left: `${Math.min(Math.max(score, 3), 97)}%`,
                  transform: 'translateX(-50%)',
                  width: '20px',
                  height: '20px',
                  borderRadius: '50%',
                  backgroundColor: '#ffffff',
                  border: '3px solid var(--text-primary)',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.25)',
                  transition: 'left 0.4s ease'
                }}
              />
            </div>

            {/* Bottom Meta Row with Clear Contrast */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '0.8rem',
                color: 'var(--text-secondary)'
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>India VIX:</span>
                <strong
                  className="font-mono"
                  style={{
                    color: 'var(--text-primary)',
                    fontSize: '0.92rem',
                    fontWeight: '800'
                  }}
                >
                  {vixVal.toFixed(1)}
                </strong>
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>pts</span>
              </span>

              <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                Live Stream via Yahoo Finance
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── BENCHMARK INDICES ── */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h3
            style={{
              fontSize: '1.1rem',
              fontWeight: '800',
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <Activity size={18} color="var(--accent-blue)" />
            <span>Benchmark Indices & Macro Anchors</span>
          </h3>
          <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
            Real-time quotes & day movement
          </span>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '14px'
          }}
        >
          {indices.map((idx) => {
            const isUp = idx.change_pct > 0;
            const isDown = idx.change_pct < 0;
            const statusColor = isUp ? 'var(--bullish)' : isDown ? 'var(--bearish)' : 'var(--neutral)';
            const statusBg = isUp ? 'var(--bullish-bg)' : isDown ? 'var(--bearish-bg)' : 'var(--neutral-bg)';

            return (
              <div
                key={idx.symbol}
                className="glass-card"
                style={{
                  padding: '18px 20px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-card)',
                  boxShadow: 'var(--shadow-sm)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  transition: 'transform 0.15s ease, box-shadow 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-secondary)' }}>
                    {idx.name}
                  </span>
                  <span
                    style={{
                      fontSize: '0.7rem',
                      fontWeight: '600',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: 'var(--bg-secondary)',
                      color: 'var(--text-muted)'
                    }}
                  >
                    {idx.short}
                  </span>
                </div>

                <div
                  className="font-mono"
                  style={{
                    fontSize: '1.45rem',
                    fontWeight: '800',
                    color: 'var(--text-primary)',
                    marginBottom: '8px',
                    letterSpacing: '-0.02em'
                  }}
                >
                  {idx.short === '10Y YIELD'
                    ? `${idx.value.toFixed(2)}%`
                    : idx.value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span
                    className="font-mono"
                    style={{
                      fontSize: '0.82rem',
                      fontWeight: '700',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: statusBg,
                      color: statusColor,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    {isUp ? <ArrowUpRight size={13} /> : isDown ? <ArrowDownRight size={13} /> : null}
                    {isUp ? '+' : ''}{idx.change_pct.toFixed(2)}%
                  </span>

                  <span
                    className="font-mono"
                    style={{
                      fontSize: '0.78rem',
                      color: 'var(--text-muted)'
                    }}
                  >
                    {isUp ? '+' : ''}{idx.change.toFixed(2)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── SECTOR ROTATION & HEATMAP ── */}
      <div style={{ marginBottom: '20px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px',
            flexWrap: 'wrap',
            gap: '12px'
          }}
        >
          <div>
            <h3
              style={{
                fontSize: '1.1rem',
                fontWeight: '800',
                margin: '0 0 4px 0',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <Layers size={18} color="var(--accent-blue)" />
              <span>NSE / Sector Performance & Rotation</span>
            </h3>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', gap: '12px' }}>
              <span>Total Sectors: <strong>{sectors.length}</strong></span>
              <span style={{ color: 'var(--bullish)' }}>Advancing: <strong>{advCount}</strong></span>
              <span style={{ color: 'var(--bearish)' }}>Declining: <strong>{decCount}</strong></span>
              {flatCount > 0 && <span>Unchanged: <strong>{flatCount}</strong></span>}
            </div>
          </div>

          {/* Filter Pills & Refresh */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                display: 'inline-flex',
                background: 'var(--bg-secondary)',
                padding: '3px',
                borderRadius: '6px',
                border: '1px solid var(--border-light)',
                fontSize: '0.75rem'
              }}
            >
              <button
                onClick={() => setFilter('ALL')}
                style={{
                  padding: '4px 10px',
                  borderRadius: '4px',
                  border: 'none',
                  background: filter === 'ALL' ? '#ffffff' : 'transparent',
                  color: filter === 'ALL' ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontWeight: filter === 'ALL' ? '700' : '500',
                  boxShadow: filter === 'ALL' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                  cursor: 'pointer'
                }}
              >
                All ({sectors.length})
              </button>
              <button
                onClick={() => setFilter('GAINERS')}
                style={{
                  padding: '4px 10px',
                  borderRadius: '4px',
                  border: 'none',
                  background: filter === 'GAINERS' ? '#ffffff' : 'transparent',
                  color: filter === 'GAINERS' ? 'var(--bullish)' : 'var(--text-secondary)',
                  fontWeight: filter === 'GAINERS' ? '700' : '500',
                  boxShadow: filter === 'GAINERS' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                  cursor: 'pointer'
                }}
              >
                Gainers ({advCount})
              </button>
              <button
                onClick={() => setFilter('LOSERS')}
                style={{
                  padding: '4px 10px',
                  borderRadius: '4px',
                  border: 'none',
                  background: filter === 'LOSERS' ? '#ffffff' : 'transparent',
                  color: filter === 'LOSERS' ? 'var(--bearish)' : 'var(--text-secondary)',
                  fontWeight: filter === 'LOSERS' ? '700' : '500',
                  boxShadow: filter === 'LOSERS' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                  cursor: 'pointer'
                }}
              >
                Laggards ({decCount})
              </button>
            </div>

            <button
              onClick={fetchSectors}
              title="Refresh sector quotes"
              disabled={refreshing}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '6px 10px',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                background: 'var(--bg-card)',
                color: 'var(--text-secondary)',
                fontSize: '0.75rem',
                cursor: refreshing ? 'wait' : 'pointer'
              }}
            >
              <RefreshCw size={12} className={refreshing ? 'spin' : ''} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Loading State */}
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', background: 'var(--bg-card)', borderRadius: '8px', border: '1px solid var(--border-light)' }}>
            <div className="pulse-dot" style={{ width: '18px', height: '18px', backgroundColor: 'var(--accent-blue)', margin: '0 auto' }}></div>
            <p style={{ marginTop: '14px', fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
              Fetching real-time quotes for all 12 key NSE industry sectors...
            </p>
          </div>
        ) : (
          /* Balanced 12-Card Grid (4 cols on desktop, 3 on tablet, 2 on mobile) */
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: '16px'
            }}
          >
            {filteredSectors.map((sec) => {
              const isUp = sec.change_pct > 0;
              const isDown = sec.change_pct < 0;
              const IconComp = SECTOR_ICONS[sec.sector] || Layers;

              const statusColor = isUp ? 'var(--bullish)' : isDown ? 'var(--bearish)' : 'var(--neutral)';
              const statusBg = isUp ? 'var(--bullish-bg)' : isDown ? 'var(--bearish-bg)' : 'var(--neutral-bg)';
              const statusBorder = isUp ? 'var(--bullish-border)' : isDown ? 'var(--bearish-border)' : 'var(--neutral-border)';

              return (
                <div
                  key={sec.symbol}
                  className="glass-card"
                  style={{
                    padding: '16px 18px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-color)',
                    background: 'var(--bg-card)',
                    boxShadow: 'var(--shadow-sm)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    position: 'relative',
                    transition: 'transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = isUp ? 'var(--bullish)' : isDown ? 'var(--bearish)' : 'var(--border-color)';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                    e.currentTarget.style.boxShadow = 'var(--shadow-md)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-color)';
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                  }}
                >
                  {/* Card Header: Sector Name & Ticker Badge */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div
                        style={{
                          width: '28px',
                          height: '28px',
                          borderRadius: '6px',
                          background: 'var(--bg-secondary)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'var(--text-secondary)'
                        }}
                      >
                        <IconComp size={15} />
                      </div>
                      <span
                        style={{
                          fontSize: '0.88rem',
                          fontWeight: '700',
                          color: 'var(--text-primary)',
                          lineHeight: '1.2'
                        }}
                      >
                        {sec.sector}
                      </span>
                    </div>

                    <span
                      style={{
                        fontSize: '0.68rem',
                        fontWeight: '700',
                        color: 'var(--text-secondary)',
                        background: 'var(--bg-secondary)',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        border: '1px solid var(--border-light)',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {sec.symbol}
                    </span>
                  </div>

                  {/* Price & Change Pill */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '12px' }}>
                    <div className="font-mono" style={{ fontSize: '1.3rem', fontWeight: '800', color: 'var(--text-primary)' }}>
                      ₹{sec.price ? sec.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'}
                    </div>

                    <span
                      className="font-mono"
                      style={{
                        fontSize: '0.85rem',
                        fontWeight: '800',
                        color: statusColor,
                        background: statusBg,
                        border: `1px solid ${statusBorder}`,
                        padding: '3px 8px',
                        borderRadius: '5px',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '3px'
                      }}
                    >
                      {isUp ? <ArrowUpRight size={13} /> : isDown ? <ArrowDownRight size={13} /> : null}
                      {isUp ? '+' : ''}{sec.change_pct.toFixed(2)}%
                    </span>
                  </div>

                  {/* Clean Relative Momentum Bar (Light & subtle, NO thick black bar!) */}
                  <div>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        fontSize: '0.68rem',
                        color: 'var(--text-muted)',
                        marginBottom: '4px'
                      }}
                    >
                      <span>Momentum</span>
                      <span style={{ fontWeight: '600', color: statusColor }}>
                        {isUp ? 'Outperforming' : isDown ? 'Underperforming' : 'Consolidating'}
                      </span>
                    </div>

                    {/* Subtle micro-bar */}
                    <div
                      style={{
                        width: '100%',
                        height: '4px',
                        background: 'var(--border-light)',
                        borderRadius: '2px',
                        overflow: 'hidden'
                      }}
                    >
                      <div
                        style={{
                          width: `${Math.min(Math.max(Math.abs(sec.change_pct) * 25, 8), 100)}%`,
                          height: '100%',
                          backgroundColor: statusColor,
                          borderRadius: '2px',
                          transition: 'width 0.4s ease'
                        }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
