import React, { useState, useEffect } from 'react';
import {
  TrendingUp, TrendingDown, Minus, Target, ShieldAlert,
  ArrowUpRight, ArrowDownRight, Compass, CheckCircle2,
  AlertTriangle, ShieldCheck, Activity, BarChart2,
  RefreshCw, Loader2, TrendingUpIcon, Zap
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

/**
 * TradeRecommendationCard
 *
 * Fetches REAL analytical trade guidance from the backend trade_engine.py:
 * - ATR-14 based stop-loss anchored to real volatility
 * - EMA-20 / EMA-50 trend alignment
 * - RSI-14 for momentum / overbought / oversold
 * - Swing Pivot Support & Resistance from actual OHLCV history
 * - Precise buy zone, targets anchored to real price levels
 *
 * No more random multipliers. All levels are data-driven.
 */
export default function TradeRecommendationCard({
  ticker,
  companyName,
  currentPrice,
  direction = 'NEUTRAL',
  confidence = 70,
  sentimentScore = 0.5,
  beta = 1.0,
  eventType = '',
  style = {}
}) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastFetched, setLastFetched] = useState(null);

  const fmtRupees = (val) => {
    if (!val || isNaN(val)) return '---';
    return `₹${Number(val).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const fetchAnalysis = async () => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        direction: direction || 'NEUTRAL',
        confidence: String(confidence || 70),
        sentiment_score: String(sentimentScore || 0.5),
        event_type: eventType || ''
      });
      const res = await fetch(`${API_BASE}/api/stocks/trade-analysis/${encodeURIComponent(ticker)}?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAnalysis(data);
      setLastFetched(new Date().toLocaleTimeString('en-IN'));
    } catch (err) {
      setError(`Could not fetch analytical data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (ticker) fetchAnalysis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker, direction, confidence]);

  // ── Derive colours ──────────────────────────────────────────────────────────
  const action = analysis?.action || 'HOLD';
  const isUp = direction?.toUpperCase() === 'UP' || direction?.toUpperCase() === 'BULLISH';
  const isDown = direction?.toUpperCase() === 'DOWN' || direction?.toUpperCase() === 'BEARISH';
  const isNeutral = !isUp && !isDown;

  const isBullishAction = ['STRONG_BUY', 'BUY_DIPS', 'WATCHLIST'].includes(action);
  const isBearishAction = ['SELL', 'BOOK_PROFIT', 'HOLD_CAUTIOUS'].includes(action);

  const actionBadge = isBullishAction ? '#006D42' : isBearishAction ? '#A71919' : '#5A403D';
  const actionBg    = isBullishAction ? '#006D4212' : isBearishAction ? '#A7191912' : '#5A403D12';

  const actionLabel = analysis?.action_label || (isUp ? 'ACCUMULATE ON PULLBACK' : isDown ? 'BOOK PROFITS / TRIM' : 'HOLD & AWAIT BREAKOUT');

  // ── Technicals ──────────────────────────────────────────────────────────────
  const tech = analysis?.technicals;
  const trend = tech?.trend || '—';
  const trendColor = trend.includes('UP') ? '#006D42' : trend.includes('DOWN') ? '#A71919' : '#736B63';

  const trendLabel = {
    STRONG_UPTREND:   '↑↑ Strong Uptrend',
    UPTREND:          '↑ Uptrend',
    SIDEWAYS:         '→ Sideways / Consolidating',
    DOWNTREND:        '↓ Downtrend',
    STRONG_DOWNTREND: '↓↓ Strong Downtrend',
  }[trend] || trend;

  const rsi = tech?.rsi || null;
  const rsiColor = rsi ? (rsi > 70 ? '#A71919' : rsi < 30 ? '#006D42' : '#0F52BA') : '#736B63';
  const rsiLabel = rsi ? (rsi > 70 ? 'Overbought' : rsi < 30 ? 'Oversold' : 'Neutral') : '—';

  return (
    <div style={{
      background: '#FFFDF8',
      border: `2px solid ${actionBadge}`,
      borderRadius: '6px',
      padding: '20px 22px',
      boxShadow: '0 4px 14px rgba(0,0,0,0.06)',
      position: 'relative',
      overflow: 'hidden',
      marginBottom: '24px',
      ...style
    }}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        borderBottom: '1px solid #C9C1B5',
        paddingBottom: '14px',
        marginBottom: '16px',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            background: actionBg,
            border: `1px solid ${actionBadge}`,
            borderRadius: '4px',
            padding: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {isUp    && <TrendingUp size={20} color={actionBadge} />}
            {isDown  && <TrendingDown size={20} color={actionBadge} />}
            {isNeutral && <Minus size={20} color={actionBadge} />}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.70rem', fontWeight: '800', letterSpacing: '0.12em', textTransform: 'uppercase', color: '#736B63' }}>
                Analytical Trade Guidance
              </span>
              {ticker && (
                <span style={{
                  background: '#171717',
                  color: '#FFFDF8',
                  padding: '1px 6px',
                  borderRadius: '3px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.70rem',
                  fontWeight: '700'
                }}>
                  {ticker.replace('.NS', '').replace('.BO', '')}
                </span>
              )}
              {/* Data-backed badge */}
              <span style={{
                background: '#0F52BA14',
                border: '1px solid #0F52BA',
                color: '#0F52BA',
                padding: '1px 6px',
                borderRadius: '3px',
                fontSize: '0.65rem',
                fontWeight: '700',
                letterSpacing: '0.06em'
              }}>
                ATR · EMA · RSI · Pivots
              </span>
            </div>
            <h3 style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.25rem',
              fontWeight: '900',
              color: '#171717',
              margin: '2px 0 0 0'
            }}>
              {actionLabel}
            </h3>
          </div>
        </div>

        {/* Right: price + refresh */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {(analysis?.current_price || currentPrice) && (
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: '0.68rem', color: '#736B63', display: 'block', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Live Price
              </span>
              <span className="font-mono" style={{ fontSize: '1.25rem', fontWeight: '800', color: '#171717' }}>
                {fmtRupees(analysis?.current_price || currentPrice)}
              </span>
            </div>
          )}
          <div style={{
            background: actionBg,
            border: `1px solid ${actionBadge}`,
            borderRadius: '4px',
            padding: '6px 12px',
            textAlign: 'center'
          }}>
            <span style={{ fontSize: '0.66rem', color: actionBadge, display: 'block', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Conviction
            </span>
            <span className="font-mono" style={{ fontSize: '1.1rem', fontWeight: '800', color: actionBadge }}>
              {analysis?.conviction ?? confidence}%
            </span>
          </div>
          <button
            onClick={fetchAnalysis}
            disabled={loading}
            title="Refresh analytical data"
            style={{
              background: 'none',
              border: '1px solid #D5CFC5',
              borderRadius: '4px',
              padding: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              color: '#736B63',
              opacity: loading ? 0.5 : 1
            }}
          >
            {loading
              ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
              : <RefreshCw size={16} />
            }
          </button>
        </div>
      </div>

      {/* ── Loading State ─────────────────────────────────────────────────────── */}
      {loading && !analysis && (
        <div style={{ textAlign: 'center', padding: '32px 0', color: '#736B63' }}>
          <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', marginBottom: '8px' }} />
          <div style={{ fontSize: '0.85rem', fontWeight: '600' }}>
            Fetching live OHLCV data & computing ATR · EMA · Pivots…
          </div>
          <div style={{ fontSize: '0.75rem', marginTop: '4px' }}>This may take a few seconds</div>
        </div>
      )}

      {/* ── Error State ───────────────────────────────────────────────────────── */}
      {error && !analysis && (
        <div style={{
          background: '#FEF2F2', border: '1px solid #FECACA',
          borderRadius: '4px', padding: '12px', marginBottom: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#A71919' }}>
            <AlertTriangle size={14} />
            <span style={{ fontSize: '0.82rem', fontWeight: '700' }}>{error}</span>
          </div>
        </div>
      )}

      {/* ── 4-Box Trade Metrics ───────────────────────────────────────────────── */}
      {analysis && !loading && (
        <>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '12px',
            marginBottom: '16px'
          }}>
            {/* 1. Buy Zone */}
            <div style={{ background: '#F9F7F2', border: '1px solid #D5CFC5', borderRadius: '4px', padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <Compass size={14} color="#006D42" />
                <span style={{ fontSize: '0.70rem', fontWeight: '800', color: '#413D36', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Suggested Entry Zone
                </span>
              </div>
              {analysis.buy_zone ? (
                <div className="font-mono" style={{ fontSize: '1.00rem', fontWeight: '800', color: '#006D42', lineHeight: 1.3 }}>
                  {fmtRupees(analysis.buy_zone.low)}
                  <span style={{ color: '#736B63', fontWeight: 400 }}> – </span>
                  {fmtRupees(analysis.buy_zone.high)}
                </div>
              ) : (
                <div style={{ fontSize: '0.85rem', fontWeight: '700', color: '#A71919' }}>
                  No Fresh Buying Advised
                </div>
              )}
              <span style={{ fontSize: '0.70rem', color: '#736B63', marginTop: '4px', display: 'block' }}>
                {isUp ? 'Accumulation zone near support' : isDown ? 'Wait for support stabilisation' : 'Range-bound entry band'}
              </span>
              {tech?.support && (
                <span style={{ fontSize: '0.68rem', color: '#736B63', display: 'block', marginTop: '2px' }}>
                  Pivot Support: <strong style={{ color: '#171717' }}>{fmtRupees(tech.support)}</strong>
                </span>
              )}
            </div>

            {/* 2. Target 1 */}
            <div style={{ background: '#F9F7F2', border: '1px solid #D5CFC5', borderRadius: '4px', padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <Target size={14} color="#0F52BA" />
                <span style={{ fontSize: '0.70rem', fontWeight: '800', color: '#413D36', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Target 1 (1–3 Days)
                </span>
              </div>
              <div className="font-mono" style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0F52BA' }}>
                {fmtRupees(analysis.target1?.price)}
              </div>
              <span style={{ fontSize: '0.70rem', color: '#736B63', marginTop: '4px', display: 'block' }}>
                {analysis.target1?.pct >= 0
                  ? `+${analysis.target1?.pct?.toFixed(1)}% projected return`
                  : `${analysis.target1?.pct?.toFixed(1)}% downside target`}
              </span>
              {tech?.resistance && (
                <span style={{ fontSize: '0.68rem', color: '#736B63', display: 'block', marginTop: '2px' }}>
                  Pivot Resistance: <strong style={{ color: '#171717' }}>{fmtRupees(tech.resistance)}</strong>
                </span>
              )}
            </div>

            {/* 3. Target 2 */}
            <div style={{ background: '#F9F7F2', border: '1px solid #D5CFC5', borderRadius: '4px', padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <ArrowUpRight size={14} color="#006D42" />
                <span style={{ fontSize: '0.70rem', fontWeight: '800', color: '#413D36', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Target 2 (5–10 Days)
                </span>
              </div>
              <div className="font-mono" style={{ fontSize: '1.05rem', fontWeight: '800', color: '#006D42' }}>
                {fmtRupees(analysis.target2?.price)}
              </div>
              <span style={{ fontSize: '0.70rem', color: '#736B63', marginTop: '4px', display: 'block' }}>
                {analysis.target2?.pct >= 0
                  ? `+${analysis.target2?.pct?.toFixed(1)}% swing target`
                  : `${analysis.target2?.pct?.toFixed(1)}% extended support`}
              </span>
            </div>

            {/* 4. Stop Loss & RR */}
            <div style={{ background: '#F9F7F2', border: '1px solid #D5CFC5', borderRadius: '4px', padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <ShieldAlert size={14} color="#A71919" />
                <span style={{ fontSize: '0.70rem', fontWeight: '800', color: '#413D36', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  ATR Stop-Loss
                </span>
              </div>
              <div className="font-mono" style={{ fontSize: '1.05rem', fontWeight: '800', color: '#A71919' }}>
                {fmtRupees(analysis.stop_loss?.price)}
              </div>
              <span style={{ fontSize: '0.70rem', color: '#736B63', marginTop: '4px', display: 'block' }}>
                Risk–Reward: <strong style={{ color: '#171717' }}>{analysis.risk_reward}</strong>
              </span>
              {tech?.atr && (
                <span style={{ fontSize: '0.68rem', color: '#736B63', display: 'block', marginTop: '2px' }}>
                  ATR-14: <strong style={{ color: '#171717' }}>{fmtRupees(tech.atr)}</strong>
                </span>
              )}
            </div>
          </div>

          {/* ── Technical Indicators Strip ────────────────────────────────────── */}
          {tech && (
            <div style={{
              display: 'flex',
              gap: '8px',
              flexWrap: 'wrap',
              marginBottom: '14px',
              padding: '10px 14px',
              background: '#F4F1EB',
              borderRadius: '4px',
              border: '1px solid #D5CFC5'
            }}>
              <span style={{ fontSize: '0.68rem', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.06em', color: '#736B63', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Activity size={12} /> Technicals:
              </span>

              {/* Trend */}
              <span style={{
                background: `${trendColor}18`,
                border: `1px solid ${trendColor}`,
                color: trendColor,
                padding: '2px 8px',
                borderRadius: '3px',
                fontSize: '0.72rem',
                fontWeight: '700'
              }}>
                {trendLabel}
              </span>

              {/* RSI */}
              {rsi && (
                <span style={{
                  background: `${rsiColor}18`,
                  border: `1px solid ${rsiColor}`,
                  color: rsiColor,
                  padding: '2px 8px',
                  borderRadius: '3px',
                  fontSize: '0.72rem',
                  fontWeight: '700'
                }}>
                  RSI {rsi} ({rsiLabel})
                </span>
              )}

              {/* EMA */}
              {tech.ema20 && (
                <span style={{
                  background: '#0F52BA12',
                  border: '1px solid #0F52BA40',
                  color: '#0F52BA',
                  padding: '2px 8px',
                  borderRadius: '3px',
                  fontSize: '0.72rem',
                  fontWeight: '700'
                }}>
                  EMA20 {fmtRupees(tech.ema20)}
                </span>
              )}
              {tech.ema50 && (
                <span style={{
                  background: '#0F52BA08',
                  border: '1px solid #0F52BA30',
                  color: '#0F52BA',
                  padding: '2px 8px',
                  borderRadius: '3px',
                  fontSize: '0.72rem',
                  fontWeight: '700'
                }}>
                  EMA50 {fmtRupees(tech.ema50)}
                </span>
              )}

              {/* 52W Position */}
              {tech.range_position_pct !== undefined && (
                <span style={{
                  background: '#5A403D12',
                  border: '1px solid #5A403D40',
                  color: '#5A403D',
                  padding: '2px 8px',
                  borderRadius: '3px',
                  fontSize: '0.72rem',
                  fontWeight: '700'
                }}>
                  52W Position: {tech.range_position_pct}%
                </span>
              )}

              {/* Volume */}
              {tech.volume_ratio && (
                <span style={{
                  background: tech.volume_ratio > 1.4 ? '#006D4214' : '#E8E3DA',
                  border: `1px solid ${tech.volume_ratio > 1.4 ? '#006D42' : '#C9C1B5'}`,
                  color: tech.volume_ratio > 1.4 ? '#006D42' : '#5A403D',
                  padding: '2px 8px',
                  borderRadius: '3px',
                  fontSize: '0.72rem',
                  fontWeight: '700'
                }}>
                  Vol {tech.volume_ratio}x avg
                </span>
              )}
            </div>
          )}

          {/* ── Strategy Narrative ────────────────────────────────────────────── */}
          {analysis.strategy_narrative && (
            <div style={{
              background: '#F0F4F8',
              borderLeft: '4px solid #0F52BA',
              padding: '12px 16px',
              borderRadius: '0 4px 4px 0',
              marginBottom: '12px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <CheckCircle2 size={14} color="#0F52BA" />
                <span style={{ fontSize: '0.75rem', fontWeight: '800', color: '#0F172A', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Analytical Strategy
                </span>
                {lastFetched && (
                  <span style={{ fontSize: '0.65rem', color: '#736B63', marginLeft: 'auto' }}>
                    Updated {lastFetched}
                  </span>
                )}
              </div>
              <p style={{
                fontSize: '0.84rem',
                lineHeight: '1.6',
                color: '#1E293B',
                fontWeight: '500',
                margin: 0
              }}>
                {analysis.strategy_narrative}
              </p>
            </div>
          )}

          {/* ── 52W Range Bar ─────────────────────────────────────────────────── */}
          {tech && tech.high_52w && tech.low_52w && (
            <div style={{ marginBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ fontSize: '0.68rem', color: '#736B63' }}>
                  52W Low: <strong>{fmtRupees(tech.low_52w)}</strong>
                </span>
                <span style={{ fontSize: '0.68rem', color: '#736B63' }}>
                  52W High: <strong>{fmtRupees(tech.high_52w)}</strong>
                </span>
              </div>
              <div style={{ background: '#E8E3DA', borderRadius: '999px', height: '6px', position: 'relative' }}>
                <div style={{
                  position: 'absolute',
                  left: `${tech.range_position_pct}%`,
                  top: '-3px',
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  background: actionBadge,
                  border: '2px solid #FFFDF8',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.2)',
                  transform: 'translateX(-50%)'
                }} />
                <div style={{
                  background: `linear-gradient(to right, #E8E3DA, ${actionBadge})`,
                  borderRadius: '999px',
                  height: '6px',
                  width: `${tech.range_position_pct}%`,
                  opacity: 0.35
                }} />
              </div>
              <div style={{ textAlign: 'center', marginTop: '4px' }}>
                <span style={{ fontSize: '0.68rem', color: '#736B63' }}>
                  Current position in 52-week range: <strong style={{ color: '#171717' }}>{tech.range_position_pct}%</strong>
                </span>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Data Source & Disclaimer ──────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '6px',
        fontSize: '0.65rem',
        color: '#736B63',
        borderTop: '1px solid #E8E3DA',
        paddingTop: '8px'
      }}>
        <ShieldCheck size={11} color="#006D42" style={{ flexShrink: 0, marginTop: '1px' }} />
        <span>
          <strong>Data-Driven Research:</strong> Levels derived from {analysis?.data_source || 'ATR-14 · EMA-20/50 · RSI-14 · Swing Pivot S/R from 90-day OHLCV history'}.
          Not SEBI-registered investment advice. Maintain strict risk management.
        </span>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
