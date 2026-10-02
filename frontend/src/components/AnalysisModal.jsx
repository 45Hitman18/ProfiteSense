import React, { useState, useEffect } from 'react';
import { 
  X, ExternalLink, TrendingUp, TrendingDown, Minus, 
  Clock, ShieldAlert, BookOpen, Layers, BarChart3, Copy, Check, BookmarkPlus
} from 'lucide-react';
import InteractiveChart from './InteractiveChart';
import TradeRecommendationCard from './TradeRecommendationCard';

// Safely parse a value that may be a JSON string or already an array
const safeArr = (v) => {
  if (Array.isArray(v)) return v;
  if (typeof v === 'string' && v.startsWith('[')) {
    try { return JSON.parse(v); } catch { return []; }
  }
  return [];
};
// Safely parse an object that may be a JSON string
const safeObj = (v) => {
  if (v && typeof v === 'object' && !Array.isArray(v)) return v;
  if (typeof v === 'string' && v.startsWith('{')) {
    try { return JSON.parse(v); } catch { return {}; }
  }
  return {};
};


export default function AnalysisModal({ articleId, onClose, onAddToWatchlist }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [chartData, setChartData] = useState([]);

  useEffect(() => {
    if (!articleId) return;
    setLoading(true);
    fetch(`/api/news/${articleId}`)
      .then((res) => res.json())
      .then((detail) => {
        setData(detail);
        setLoading(false);
        // Also fetch ticker chart if available
        if (detail.analysis?.ticker) {
          fetch(`/api/tickers/${detail.analysis.ticker}`)
            .then((r) => r.json())
            .then((tData) => {
              if (tData.chart) setChartData(tData.chart);
            })
            .catch(() => {});
        }
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, [articleId]);

  if (!articleId) return null;

  const handleCopyMarkdown = () => {
    if (!data) return;
    const an = data.analysis;
    const md = `### Market News AI Catalyst Estimate
**Headline:** ${data.title}
**Affected Company:** ${an.company_name} (${an.ticker})
**Sector:** ${an.sector}
**Event Type:** ${an.event_type}
**Sentiment:** ${an.sentiment} (Compound: ${an.sentiment_score})
**Direction:** ${an.direction} | **Confidence:** ${an.confidence}% | **Impact:** ${an.impact_level}

**Time Horizon Projections:**
- 1-Day: ${an.time_horizons?.['1d']?.projected_change_pct || 'N/A'} (Target: ${an.time_horizons?.['1d']?.target_price_range || 'N/A'})
- 3-Day: ${an.time_horizons?.['3d']?.projected_change_pct || 'N/A'} (Target: ${an.time_horizons?.['3d']?.target_price_range || 'N/A'})
- 5-Day: ${an.time_horizons?.['5d']?.projected_change_pct || 'N/A'} (Target: ${an.time_horizons?.['5d']?.target_price_range || 'N/A'})

**Plain-Language Rationale:**
${an.reason_explanation}

**Historical Precedent:**
${an.historical_precedents?.summary || 'Empirical historical drift alignment.'}
Source: ${data.url}`;

    navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const an = data?.analysis;
  const quote = data?.market_context;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid var(--border-color)',
            color: 'var(--text-secondary)',
            borderRadius: '50%',
            width: '36px',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'background 0.2s'
          }}
        >
          <X size={18} />
        </button>

        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center' }}>
            <div className="pulse-dot" style={{ width: '20px', height: '20px', backgroundColor: '#3b82f6' }}></div>
            <p style={{ marginTop: '16px', color: 'var(--text-secondary)' }}>Loading AI Catalyst Deep Dive...</p>
          </div>
        ) : !data ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Unable to load article details.
          </div>
        ) : (
          <div>
            {/* Header: Impact + Category + Scope + Source */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
              <span className={`badge ${
                an.impact_level === 'HIGH' ? 'badge-impact-high' : (an.impact_level === 'MEDIUM' ? 'badge-impact-medium' : 'badge-impact-low')
              }`}>
                {an.impact_level} IMPACT
              </span>
              <span className="badge-sector">{an.event_display || an.event_type?.replace(/_/g,' ')}</span>
              {an.scope && (
                <span style={{
                  fontSize: '0.72rem', fontWeight: '700', padding: '3px 9px',
                  borderRadius: '999px', border: '1px solid #C9C1B5',
                  background: '#F0EDED', color: '#171717'
                }}>
                  {an.scope.replace(/_/g, ' ')}
                </span>
              )}
              {(safeArr(an.secondary_categories)).slice(0,2).map(s => (
                <span key={s} style={{
                  fontSize: '0.68rem', fontWeight: '600', padding: '2px 7px',
                  borderRadius: '999px', border: '1px solid #D5CFC5',
                  background: '#FBF9F5', color: '#5A403D'
                }}>
                  {s.replace(/_/g,' ')}
                </span>
              ))}
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>•</span>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{data.source}</span>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>•</span>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {new Date(data.published_at).toLocaleString()}
              </span>
            </div>

            {/* Article Headline */}
            <h2 style={{ fontSize: '1.45rem', fontWeight: '800', lineHeight: '1.35', marginBottom: '14px', color: '#171717', fontFamily: 'var(--font-serif)' }}>
              {data.title}
            </h2>

            {/* Link to Source */}
            {data.url && (
              <a
                href={data.url}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '0.82rem',
                  color: 'var(--accent-blue)',
                  textDecoration: 'none',
                  marginBottom: '24px'
                }}
              >
                <span>Read Full Original Article on {data.source}</span>
                <ExternalLink size={13} />
              </a>
            )}

            {/* Affected Ticker & Quote Banner */}
            <div style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-lg)',
              padding: '16px 20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '24px',
              flexWrap: 'wrap',
              gap: '16px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
                <span className="badge-ticker" style={{ fontSize: '1.1rem', padding: '6px 12px' }}>
                  {an.ticker}
                </span>
                <div>
                  <h4 style={{ fontSize: '1.05rem', fontWeight: '700' }}>{an.company_name}</h4>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    Sector: {an.sector} | Beta: {an.beta?.toFixed(2) || '1.10'}
                  </span>
                </div>
                {/* Secondary entity pills */}
                {safeArr(an.all_entities).slice(1, 4).map(e => (
                  <span key={e.ticker} style={{
                    fontSize: '0.72rem', padding: '3px 8px', borderRadius: '4px',
                    background: '#F0EDED', border: '1px solid #D5CFC5',
                    color: '#171717', fontFamily: 'monospace', fontWeight: '700'
                  }}>
                    {e.ticker}
                  </span>
                ))}
              </div>

              {quote && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                  <div>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>CURRENT PRICE</span>
                    <span className="font-mono" style={{ fontSize: '1.2rem', fontWeight: '700' }}>
                      ₹{quote.price ? quote.price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '---'}
                    </span>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>24H CHANGE</span>
                    <span
                      className="font-mono"
                      style={{
                        fontSize: '1.1rem',
                        fontWeight: '700',
                        color: quote.change_pct >= 0 ? 'var(--bullish)' : 'var(--bearish)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      {quote.change_pct >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                      {quote.change_pct >= 0 ? '+' : ''}{quote.change_pct?.toFixed(2)}%
                    </span>
                  </div>
                </div>
              )}

              <button
                className="btn btn-secondary btn-sm"
                onClick={() => onAddToWatchlist(an.ticker)}
                style={{ marginLeft: 'auto' }}
              >
                <BookmarkPlus size={14} />
                <span>Track in Watchlist</span>
              </button>
            </div>

            {/* Real-Time Buy / Sell / Hold Trade Guidance */}
            <TradeRecommendationCard
              ticker={an.ticker}
              companyName={an.company_name}
              currentPrice={quote?.price}
              direction={an.direction}
              confidence={an.confidence}
              sentimentScore={an.sentiment_score}
              beta={an.beta || 1.05}
              dayHigh={quote?.day_high}
              dayLow={quote?.day_low}
            />

            {/* 3 Core Metric Highlights */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px', marginBottom: '24px' }}>
              {/* Direction Card */}
              <div style={{
                background: 'var(--bg-primary)',
                border: `1px solid ${an.direction === 'UP' ? 'var(--bullish-border)' : (an.direction === 'DOWN' ? 'var(--bearish-border)' : 'var(--neutral-border)')}`,
                borderRadius: 'var(--radius-md)',
                padding: '16px'
              }}>
                <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)' }}>POTENTIAL DIRECTION</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                  {an.direction === 'UP' && <TrendingUp size={24} color="#10b981" />}
                  {an.direction === 'DOWN' && <TrendingDown size={24} color="#f43f5e" />}
                  {an.direction === 'NEUTRAL' && <Minus size={24} color="#f59e0b" />}
                  <span style={{
                    fontSize: '1.4rem',
                    fontWeight: '800',
                    color: an.direction === 'UP' ? 'var(--bullish)' : (an.direction === 'DOWN' ? 'var(--bearish)' : 'var(--neutral)')
                  }}>
                    {an.direction}
                  </span>
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px', display: 'block' }}>
                  Statistical directional bias
                </span>
              </div>

              {/* Confidence Card */}
              <div style={{
                background: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                padding: '16px'
              }}>
                <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)' }}>ESTIMATED CONFIDENCE</span>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '6px' }}>
                  <span className="font-mono" style={{ fontSize: '1.6rem', fontWeight: '800', color: '#60a5fa' }}>
                    {an.confidence}%
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>algorithmic probability</span>
                </div>
                {/* Confidence Bar */}
                <div style={{ width: '100%', height: '5px', background: '#1e293b', borderRadius: '3px', marginTop: '8px', overflow: 'hidden' }}>
                  <div style={{ width: `${an.confidence}%`, height: '100%', background: 'linear-gradient(90deg, #3b82f6, #06b6d4)' }}></div>
                </div>
              </div>

              {/* Sentiment Card with VADER breakdown */}
              <div style={{
                background: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                padding: '16px'
              }}>
                <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)' }}>FINANCIAL SENTIMENT</span>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '6px' }}>
                  <span style={{
                    fontSize: '1.3rem', fontWeight: '800',
                    color: an.sentiment === 'Positive' ? 'var(--bullish)' : (an.sentiment === 'Negative' ? 'var(--bearish)' : 'var(--neutral)')
                  }}>
                    {an.sentiment}
                  </span>
                  <span className="font-mono" style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                    {an.sentiment_score > 0 ? '+' : ''}{an.sentiment_score}
                  </span>
                </div>
                {safeObj(an.sentiment_breakdown) && Object.keys(safeObj(an.sentiment_breakdown)).length > 0 && (
                  <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    {[['pos','#10b981'],['neg','#f43f5e'],['neu','#94a3b8']].map(([k,col]) => {
                      const bd = safeObj(an.sentiment_breakdown);
                      return (
                        <div key={k} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontSize: '0.65rem', color: col, fontWeight: '700', width: '24px', textTransform: 'uppercase' }}>{k}</span>
                          <div style={{ flex: 1, height: '4px', background: '#1e293b', borderRadius: '2px', overflow: 'hidden' }}>
                            <div style={{ width: `${Math.round((bd[k]||0)*100)}%`, height: '100%', background: col }} />
                          </div>
                          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'monospace', width: '28px', textAlign: 'right' }}>
                            {Math.round((bd[k]||0)*100)}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px', display: 'block' }}>LM-Lexicon + VADER</span>
              </div>
            </div>

            {/* Time Horizon Projections (1D / 3D / 5D) */}
            <div style={{ marginBottom: '28px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <Clock size={16} color="#60a5fa" />
                <h3 style={{ fontSize: '1rem', fontWeight: '700' }}>Time-Horizon Impact Estimations</h3>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
                {['1d', '3d', '5d'].map((hzKey) => {
                  const hz = an.time_horizons?.[hzKey];
                  if (!hz) return null;
                  const isUp = hz.direction === 'UP';

                  // Calibrate target price range to the live stock quote if available
                  let targetDisplay = hz.target_price_range;
                  if (quote?.price && quote.price > 0 && typeof hz.low_pct === 'number' && typeof hz.high_pct === 'number') {
                    const pMin = quote.price * (1 + hz.low_pct / 100);
                    const pMax = quote.price * (1 + hz.high_pct / 100);
                    targetDisplay = `₹${pMin.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} – ₹${pMax.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                  }

                  return (
                    <div
                      key={hzKey}
                      style={{
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-md)',
                        padding: '14px'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-secondary)' }}>
                          {hz.horizon_label}
                        </span>
                        <span className="badge" style={{
                          background: isUp ? 'var(--bullish-bg)' : 'var(--bearish-bg)',
                          color: isUp ? 'var(--bullish)' : 'var(--bearish)',
                          fontSize: '0.68rem'
                        }}>
                          {hz.horizon_confidence}% CONF
                        </span>
                      </div>

                      <div className="font-mono" style={{
                        fontSize: '1.25rem',
                        fontWeight: '800',
                        color: isUp ? 'var(--bullish)' : 'var(--bearish)',
                        marginBottom: '6px'
                      }}>
                        {hz.projected_change_pct}
                      </div>

                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        Target Price Range: <span className="font-mono" style={{ color: 'var(--text-primary)', fontWeight: '600' }}>{targetDisplay}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Plain-Language Explanation */}
            <div style={{
              background: '#F0F4F8',
              border: '1px solid #C4D7E8',
              borderLeft: '4px solid #1D4ED8',
              borderRadius: 'var(--radius-md)',
              padding: '18px 20px',
              marginBottom: '24px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <BookOpen size={17} color="#1D4ED8" />
                <h3 style={{ fontSize: '1rem', fontWeight: '800', color: '#0F172A', fontFamily: 'var(--font-serif)', margin: 0 }}>
                  AI Plain-Language Rationale
                </h3>
              </div>
              <p style={{ fontSize: '0.90rem', lineHeight: '1.65', color: '#1E293B', fontWeight: '500', margin: 0 }}>
                {an.reason_explanation}
              </p>
            </div>

            {/* Historical Precedent Box */}
            {an.historical_precedents && (
              <div style={{
                background: '#FBF9F5',
                border: '1px solid #D5CFC5',
                borderLeft: '4px solid #5A403D',
                borderRadius: 'var(--radius-md)',
                padding: '16px 20px',
                marginBottom: '24px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <Layers size={16} color="#5A403D" />
                  <h4 style={{ fontSize: '0.92rem', fontWeight: '800', color: '#171717', fontFamily: 'var(--font-serif)', margin: 0 }}>
                    Empirical Historical Precedent
                  </h4>
                </div>
                <p style={{ fontSize: '0.86rem', color: '#2C201E', lineHeight: '1.55', margin: '6px 0 8px 0' }}>
                  {an.historical_precedents.summary}
                </p>
                <div style={{ display: 'flex', gap: '16px', fontSize: '0.74rem', color: '#5A403D', flexWrap: 'wrap', fontWeight: '600' }}>
                  <span>Sample: {an.historical_precedents.sample_size}</span>
                  <span>•</span>
                  <span>Tested: {an.historical_precedents.benchmark_tested}</span>
                </div>
              </div>
            )}

            {/* Interactive Stock Chart */}
            {chartData.length > 0 && (
              <div style={{
                background: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-lg)',
                padding: '18px',
                marginBottom: '24px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                  <BarChart3 size={16} color="#34d399" />
                  <h4 style={{ fontSize: '0.9rem', fontWeight: '700' }}>
                    Historical Price Trajectory & Catalyst Marker
                  </h4>
                </div>
                <InteractiveChart
                  data={chartData}
                  ticker={an.ticker}
                  direction={an.direction}
                />
              </div>
            )}

            {/* Modal Bottom Actions */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-color)', paddingTop: '18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: '#f59e0b', fontWeight: '600' }}>
                <ShieldAlert size={15} color="#f59e0b" />
                <span>AI/model estimate — not investment advice.</span>
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>

                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleCopyMarkdown}
                >
                  {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
                  <span>{copied ? 'Copied Markdown!' : 'Copy Summary'}</span>
                </button>
                <button className="btn btn-primary btn-sm" onClick={onClose}>
                  Done
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
