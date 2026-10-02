import React, { useState } from 'react';
import { Sparkles, Play, TrendingUp, TrendingDown, Minus, Clock, BookOpen, Layers, ShieldAlert, Check, Copy } from 'lucide-react';
import TradeRecommendationCard from './TradeRecommendationCard';

const PRESET_EXAMPLES = [
  {
    label: "Reliance 5G & Green Energy Expansion",
    title: "Reliance Industries Secures ₹25,000 Cr Green Hydrogen Deal, Jio Platforms Reports 18% Net Profit Surge",
    content: "Reliance Industries announced a multi-billion green hydrogen supply framework alongside a stellar quarterly performance from Jio Platforms, delivering record ARPU of ₹192 and expanding broadband coverage nationwide."
  },
  {
    label: "RBI MPC Repo Rate Decision",
    title: "RBI Monetary Policy Committee Cuts Repo Rate by 25 Bps to Stimulate Industrial Credit and Capital Expenditure",
    content: "The Reserve Bank of India MPC voted unanimously to lower the policy repo rate by 25 basis points to 6.25%, maintaining an accommodative stance as retail CPI inflation moderated comfortably within the 4% target band."
  },
  {
    label: "Tata Motors Global EV Order",
    title: "Tata Motors Commercial Vehicle Arm Secures ₹4,200 Cr Electric Bus Order from State Transport Undertakings",
    content: "Tata Motors won a marquee public tender for 5,000 electric transit buses across metropolitan corridors, bolstering its order book and reinforcing domestic market leadership in zero-emission commercial mobility."
  },
  {
    label: "HDFC Bank Q3 Net Profit Growth",
    title: "HDFC Bank Reports 22% Surge in Q3 Net Profit to ₹16,800 Cr with Net Interest Margin Expanding to 3.65%",
    content: "India's premier private lender HDFC Bank beat Dalal Street estimates, reporting robust asset quality with Gross NPA dropping to 1.24% and retail advances growing 19% year-on-year."
  }
];

export default function CustomAnalyzerView({ onAddToWatchlist }) {
  const [headline, setHeadline] = useState('');
  const [content, setContent] = useState('');
  const [tickerHint, setTickerHint] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleAnalyze = (e) => {
    e.preventDefault();
    if (!headline.trim()) {
      setError('Please provide a news headline or announcement title.');
      return;
    }

    setError(null);
    setLoading(true);

    fetch('/api/news/analyze-custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: headline,
        content: content,
        ticker_hint: tickerHint || undefined
      })
    })
      .then((res) => {
        if (!res.ok) throw new Error('Analysis failed.');
        return res.json();
      })
      .then((data) => {
        setResult(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Error executing AI analysis pipeline.');
        setLoading(false);
      });
  };

  const loadPreset = (preset) => {
    setHeadline(preset.title);
    setContent(preset.content);
    setTickerHint('');
    setResult(null);
    setError(null);
  };

  const an = result?.analysis;
  const quote = result?.market_context;

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
      {/* Intro Header */}
      <div className="glass-card" style={{ marginBottom: '24px', padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'rgba(59, 130, 246, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Sparkles size={20} color="#60a5fa" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: '800' }}>Interactive AI Catalyst Analyzer</h2>
            <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)' }}>
              Paste any custom breaking news, earnings release, regulatory filing, or tweet to test the NLP impact model.
            </p>
          </div>
        </div>

        {/* Example Presets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '16px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Try an example:</span>
          {PRESET_EXAMPLES.map((ex, i) => (
            <button
              key={i}
              className="btn btn-secondary btn-sm"
              onClick={() => loadPreset(ex)}
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <form onSubmit={handleAnalyze} className="glass-card" style={{ marginBottom: '28px', padding: '24px' }}>
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '700', marginBottom: '6px' }}>
            Headline / News Title <span style={{ color: 'var(--bearish)' }}>*</span>
          </label>
          <input
            type="text"
            className="input-field"
            placeholder="e.g. Apple Reports Record Services Revenue, Signs Major AI Multi-Year Partnership"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            style={{ width: '100%' }}
            required
          />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '700', marginBottom: '6px' }}>
              Full Text or Summary (Optional)
            </label>
            <textarea
              className="input-field"
              rows={4}
              placeholder="Paste article paragraphs, press release quotes, or context..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              style={{ width: '100%', resize: 'vertical' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '700', marginBottom: '6px' }}>
              Ticker Hint (Optional override)
            </label>
            <input
              type="text"
              className="input-field"
              placeholder="e.g. AAPL, NVDA, TSLA (Auto-detected if empty)"
              value={tickerHint}
              onChange={(e) => setTickerHint(e.target.value.toUpperCase())}
              style={{ width: '100%', marginBottom: '12px' }}
            />
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
              If left blank, the NLP entity recognition algorithm will automatically extract the primary company and ticker symbol from the text.
            </div>
          </div>
        </div>

        {error && (
          <div style={{ padding: '10px 14px', background: 'var(--bearish-bg)', border: '1px solid var(--bearish-border)', color: '#fca5a5', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '16px' }}>
            {error}
          </div>
        )}

        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading}
          style={{ width: '100%', padding: '12px', fontSize: '0.95rem' }}
        >
          {loading ? (
            <>
              <div className="pulse-dot" style={{ width: '12px', height: '12px', backgroundColor: '#ffffff' }}></div>
              <span>Processing NLP & Financial Model...</span>
            </>
          ) : (
            <>
              <Play size={16} />
              <span>Run AI Impact Model</span>
            </>
          )}
        </button>
      </form>

      {/* Analysis Results Display */}
      {result && an && (
        <div className="glass-card" style={{ padding: '28px', border: '1px solid var(--border-light)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className={`badge ${
                an.impact_level === 'HIGH' ? 'badge-impact-high' : (an.impact_level === 'MEDIUM' ? 'badge-impact-medium' : 'badge-impact-low')
              }`}>
                {an.impact_level} IMPACT
              </span>
              <span className="badge-sector">{an.event_type.replace('_', ' ')}</span>
            </div>

            <button
              className="btn btn-secondary btn-sm"
              onClick={() => {
                const md = `AI Catalyst Analysis: ${result.title} -> ${an.direction} (${an.confidence}% conf, Impact: ${an.impact_level}, 3D: ${an.time_horizons?.['3d']?.projected_change_pct || 'N/A'})`;
                navigator.clipboard.writeText(md);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
            >
              {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
              <span>{copied ? 'Copied!' : 'Copy Result'}</span>
            </button>
          </div>

          <h3 style={{ fontSize: '1.3rem', fontWeight: '800', marginBottom: '18px', color: '#ffffff' }}>
            {result.title}
          </h3>

          {/* Affected Entity Banner */}
          <div style={{
            background: 'var(--bg-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-md)',
            padding: '16px 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '24px',
            flexWrap: 'wrap',
            gap: '14px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span className="badge-ticker" style={{ fontSize: '1.1rem', padding: '6px 12px' }}>
                {an.ticker}
              </span>
              <div>
                <h4 style={{ fontSize: '1rem', fontWeight: '700' }}>{an.company_name}</h4>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  Sector: {an.sector} | Beta: {an.beta?.toFixed(2) || '1.00'}
                </span>
              </div>
            </div>

            {quote && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '18px' }}>
                <div>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>PRICE</span>
                  <span className="font-mono" style={{ fontSize: '1.1rem', fontWeight: '700' }}>
                    ₹{quote.price ? quote.price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '---'}
                  </span>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>DAY CHG</span>
                  <span
                    className="font-mono"
                    style={{
                      fontSize: '1rem',
                      fontWeight: '700',
                      color: quote.change_pct >= 0 ? 'var(--bullish)' : 'var(--bearish)'
                    }}
                  >
                    {quote.change_pct >= 0 ? '+' : ''}{quote.change_pct?.toFixed(2)}%
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Real-Time Buy / Sell / Hold Trade Guidance */}
          <TradeRecommendationCard
            ticker={an.ticker}
            companyName={an.company_name}
            currentPrice={quote?.price}
            direction={an.direction}
            confidence={an.confidence}
            sentimentScore={an.sentiment_score}
            beta={an.beta || 1.0}
            dayHigh={quote?.day_high}
            dayLow={quote?.day_low}
          />

          {/* 3 Metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', marginBottom: '24px' }}>
            <div style={{ background: 'var(--bg-primary)', padding: '16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>POTENTIAL DIRECTION</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                {an.direction === 'UP' && <TrendingUp size={20} color="#10b981" />}
                {an.direction === 'DOWN' && <TrendingDown size={20} color="#f43f5e" />}
                {an.direction === 'NEUTRAL' && <Minus size={20} color="#f59e0b" />}
                <span style={{
                  fontSize: '1.3rem',
                  fontWeight: '800',
                  color: an.direction === 'UP' ? 'var(--bullish)' : (an.direction === 'DOWN' ? 'var(--bearish)' : 'var(--neutral)')
                }}>
                  {an.direction}
                </span>
              </div>
            </div>

            <div style={{ background: 'var(--bg-primary)', padding: '16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>CONFIDENCE PROBABILITY</span>
              <div className="font-mono" style={{ fontSize: '1.4rem', fontWeight: '800', color: '#60a5fa', marginTop: '6px' }}>
                {an.confidence}%
              </div>
            </div>

            <div style={{ background: 'var(--bg-primary)', padding: '16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>FINANCIAL SENTIMENT</span>
              <div style={{ fontSize: '1.2rem', fontWeight: '800', marginTop: '6px', color: an.sentiment === 'Positive' ? 'var(--bullish)' : (an.sentiment === 'Negative' ? 'var(--bearish)' : 'var(--neutral)') }}>
                {an.sentiment} <span className="font-mono" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>({an.sentiment_score > 0 ? '+' : ''}{an.sentiment_score})</span>
              </div>
            </div>
          </div>

          {/* Time Horizons */}
          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Clock size={16} color="#60a5fa" />
              <h4 style={{ fontSize: '0.95rem', fontWeight: '700' }}>Time-Horizon Forecasts (1 / 3 / 5 Trading Days)</h4>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              {['1d', '3d', '5d'].map((k) => {
                const hz = an.time_horizons?.[k];
                if (!hz) return null;
                const isUp = hz.direction === 'UP';
                return (
                  <div key={k} style={{ background: 'var(--bg-primary)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <span style={{ fontSize: '0.78rem', fontWeight: '700', color: 'var(--text-secondary)' }}>{hz.horizon_label}</span>
                      <span style={{ fontSize: '0.72rem', color: '#60a5fa' }}>{hz.horizon_confidence}% conf</span>
                    </div>
                    <div className="font-mono" style={{ fontSize: '1.15rem', fontWeight: '800', color: isUp ? 'var(--bullish)' : 'var(--bearish)' }}>
                      {hz.projected_change_pct}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Target: <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{hz.target_price_range}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Plain Rationale */}
          <div style={{ background: 'rgba(59, 130, 246, 0.06)', border: '1px solid rgba(59, 130, 246, 0.25)', borderRadius: 'var(--radius-md)', padding: '16px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <BookOpen size={16} color="#60a5fa" />
              <span style={{ fontSize: '0.88rem', fontWeight: '700', color: '#93c5fd' }}>Plain-Language Rationale</span>
            </div>
            <p style={{ fontSize: '0.86rem', lineHeight: '1.6', color: '#e2e8f0' }}>
              {an.reason_explanation}
            </p>
          </div>

          {/* Precedents */}
          {an.historical_precedents && (
            <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '16px', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <Layers size={16} color="#a78bfa" />
                <span style={{ fontSize: '0.88rem', fontWeight: '700', color: '#c4b5fd' }}>Historical Precedents</span>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                {an.historical_precedents.summary}
              </p>
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#f59e0b', fontWeight: '600' }}>
            <ShieldAlert size={16} color="#f59e0b" />
            <span>AI/model estimate — not investment advice.</span>
          </div>
        </div>
      )}
    </div>
  );
}

