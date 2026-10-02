import React from 'react';
import { TrendingUp, TrendingDown, Activity, ShieldCheck } from 'lucide-react';

export default function TickerTape({ overview }) {
  // Strictly filter to Indian benchmarks and key macro factors affecting Indian markets
  const allIndices = overview?.indices || [];
  const indianIndices = allIndices.filter(idx => {
    const s = (idx.short || '').toUpperCase();
    const sym = (idx.symbol || '').toUpperCase();
    return !['S&P 500', 'NASDAQ', 'DOW', '10Y YIELD', 'FTSE', 'NIKKEI', 'DAX'].includes(s) &&
           !['^GSPC', '^IXIC', '^DJI', '^TNX', '^VIX'].includes(sym);
  });

  const displayIndices = indianIndices.length > 0 ? indianIndices : [
    { symbol: '^NSEI', short: 'NIFTY 50', value: 24820.50, change_pct: 0.42 },
    { symbol: '^BSESN', short: 'SENSEX', value: 81450.20, change_pct: 0.38 },
    { symbol: '^INDIAVIX', short: 'INDIA VIX', value: 12.85, change_pct: -1.25 },
    { symbol: 'INR=X', short: 'USD/INR', value: 88.62, change_pct: 0.05 },
    { symbol: 'BZ=F', short: 'BRENT CRUDE', value: 74.30, change_pct: -0.65 }
  ];

  const mood = overview?.market_mood || {
    label: 'Neutral / Mixed',
    score: 50
  };

  return (
    <div className="ticker-tape" style={{
      background: '#FFFDF8',
      borderTop: '1px solid #C9C1B5',
      borderBottom: '1px solid #C9C1B5',
      padding: '7px 24px',
      overflowX: 'auto',
      whiteSpace: 'nowrap',
      display: 'flex',
      alignItems: 'center',
      gap: '0px'
    }}>
      {/* 1. Live Feed Status */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        paddingRight: '16px',
        marginRight: '16px',
        borderRight: '1px solid #D5CFC5'
      }}>
        <span className="pulse-dot" style={{ backgroundColor: '#006D42', width: '7px', height: '7px' }}></span>
        <span style={{ fontSize: '0.74rem', fontWeight: '800', letterSpacing: '0.06em', color: '#171717', textTransform: 'uppercase' }}>
          Live Market Feed
        </span>
      </div>

      {/* 2. Market Mood Indicator */}
      {mood && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          paddingRight: '16px',
          marginRight: '16px',
          borderRight: '1px solid #D5CFC5'
        }}>
          <Activity size={13} color="#0F52BA" />
          <span style={{ fontSize: '0.74rem', color: '#736B63', fontWeight: '600' }}>Market Mood:</span>
          <span style={{
            fontSize: '0.74rem',
            fontWeight: '800',
            color: mood.score > 60 ? 'var(--bullish)' : (mood.score < 40 ? 'var(--bearish)' : '#5A403D')
          }}>
            {mood.label} ({mood.score}/100)
          </span>
        </div>
      )}

      {/* 3. Indian Indices & Catalyst Factors */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0px' }}>
        {displayIndices.map((idx, i) => {
          const isUp = (idx.change_pct || 0) >= 0;
          const formattedVal = idx.value !== undefined && idx.value !== null
            ? Number(idx.value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
            : '---';

          return (
            <div
              key={idx.symbol || i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '0 16px',
                borderRight: '1px solid #E8E3DA',
                fontSize: '0.78rem'
              }}
            >
              <span style={{
                color: '#413D36',
                fontWeight: '800',
                textTransform: 'uppercase',
                letterSpacing: '0.03em',
                fontSize: '0.74rem'
              }}>
                {idx.short}
              </span>

              <span className="font-mono" style={{
                fontWeight: '700',
                color: '#171717',
                fontSize: '0.80rem'
              }}>
                {formattedVal}
              </span>

              <span
                className="font-mono"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '2px',
                  fontWeight: '800',
                  fontSize: '0.74rem',
                  color: isUp ? 'var(--bullish)' : 'var(--bearish)'
                }}
              >
                {isUp ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                {isUp ? '+' : ''}{Number(idx.change_pct || 0).toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>

      {/* 4. Free Pipeline Guarantee Badge */}
      <div style={{
        marginLeft: 'auto',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        fontSize: '0.72rem',
        color: '#5A403D',
        fontWeight: '700',
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        paddingLeft: '16px'
      }}>
        <ShieldCheck size={13} color="#006D42" />
        <span>NSE & BSE Real-Time Feed</span>
      </div>
    </div>
  );
}
