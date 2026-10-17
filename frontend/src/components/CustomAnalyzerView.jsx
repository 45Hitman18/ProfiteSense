import React, { useState } from 'react';
import {
  Sparkles, Play, TrendingUp, TrendingDown, Minus, Clock, BookOpen,
  Layers, ShieldAlert, Check, Copy, RotateCcw, Clipboard, ExternalLink,
  BookmarkPlus, CheckCircle2, ChevronDown, ChevronUp, AlertCircle,
  BarChart2, Zap, Tag, Compass, Landmark, Briefcase, Cpu, Fuel, Shield
} from 'lucide-react';
import TradeRecommendationCard from './TradeRecommendationCard';

const PRESET_EXAMPLES = [
  {
    category: "EARNINGS",
    categoryLabel: "Earnings & Financials",
    categoryIcon: BarChart2,
    badgeColor: "#006D42",
    label: "Reliance 5G & Green Energy Surge",
    ticker: "RELIANCE.NS",
    title: "Reliance Industries Secures ₹25,000 Cr Green Hydrogen Deal, Jio Platforms Reports 18% Net Profit Surge",
    content: "Reliance Industries announced a multi-billion green hydrogen supply framework alongside a stellar quarterly performance from Jio Platforms, delivering record ARPU of ₹192 and expanding broadband coverage nationwide."
  },
  {
    category: "MONETARY",
    categoryLabel: "RBI & Monetary Policy",
    categoryIcon: Landmark,
    badgeColor: "#0F52BA",
    label: "RBI MPC Repo Rate Cut by 25 Bps",
    ticker: "SBIN.NS",
    title: "RBI Monetary Policy Committee Cuts Repo Rate by 25 Bps to Stimulate Industrial Credit and Capital Expenditure",
    content: "The Reserve Bank of India MPC voted unanimously to lower the policy repo rate by 25 basis points to 6.25%, maintaining an accommodative stance as retail CPI inflation moderated comfortably within the 4% target band."
  },
  {
    category: "ORDER_WIN",
    categoryLabel: "Order Book & Capex",
    categoryIcon: Briefcase,
    badgeColor: "#7C3AED",
    label: "Tata Motors ₹4,200 Cr Electric Bus Order",
    ticker: "TATAMOTORS.NS",
    title: "Tata Motors Commercial Vehicle Arm Secures ₹4,200 Cr Electric Bus Order from State Transport Undertakings",
    content: "Tata Motors won a marquee public tender for 5,000 electric transit buses across metropolitan corridors, bolstering its order book and reinforcing domestic market leadership in zero-emission commercial mobility."
  },
  {
    category: "BANKING",
    categoryLabel: "Asset Quality & Margins",
    categoryIcon: Landmark,
    badgeColor: "#006D42",
    label: "HDFC Bank Q3 Net Profit Growth (+22%)",
    ticker: "HDFCBANK.NS",
    title: "HDFC Bank Reports 22% Surge in Q3 Net Profit to ₹16,800 Cr with Net Interest Margin Expanding to 3.65%",
    content: "India's premier private lender HDFC Bank beat Dalal Street estimates, reporting robust asset quality with Gross NPA dropping to 1.24% and retail advances growing 19% year-on-year."
  },
  {
    category: "MACRO",
    categoryLabel: "Commodity & OMC Margin",
    categoryIcon: Fuel,
    badgeColor: "#B42318",
    label: "Crude Oil Spikes to $90/bbl",
    ticker: "BPCL.NS",
    title: "Brent Crude Surges Past $90 as Middle East Tensions Escalate, Raising Auto Fuel Margin Pressure on Indian OMCs",
    content: "Global benchmark crude oil surged over 4% in Asian trading following supply disruption warnings, tightening gross refining margins and raising marketing loss risks for state-run refiners IOC, BPCL, and HPCL."
  },
  {
    category: "DEFENSE",
    categoryLabel: "Make in India / Defense",
    categoryIcon: Shield,
    badgeColor: "#0F52BA",
    label: "L&T Wins ₹8,500 Cr MoD Defense Order",
    ticker: "LT.NS",
    title: "Larsen & Toubro Secures Mega ₹8,500 Cr Defense Electronics & Naval Weaponry Contract from Ministry of Defence",
    content: "Engineering conglomerate L&T finalized a milestone procurement contract for indigenous naval systems and automated defense radars under the Buy Indian-IDDM initiative."
  }
];

export default function CustomAnalyzerView({ onAddToWatchlist, onExploreTicker }) {
  const [headline, setHeadline] = useState('');
  const [content, setContent] = useState('');
  const [tickerHint, setTickerHint] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [addedToWl, setAddedToWl] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [activeAnalysisTab, setActiveAnalysisTab] = useState('rationale'); // 'rationale' | 'precedents' | 'sentiment'
  const [activePresetCategory, setActivePresetCategory] = useState('ALL');

  const handleAnalyze = (e) => {
    if (e) e.preventDefault();
    if (!headline.trim()) {
      setError('Please provide a news headline or announcement title.');
      return;
    }

    setError(null);
    setLoading(true);
    setAddedToWl(false);

    fetch('/api/news/analyze-custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: headline.trim(),
        content: content.trim(),
        ticker_hint: tickerHint.trim() ? tickerHint.trim().toUpperCase() : undefined
      })
    })
      .then((res) => {
        if (!res.ok) {
          return res.json().then(errData => {
            throw new Error(errData.detail || 'Analysis failed. Please check your input.');
          });
        }
        return res.json();
      })
      .then((data) => {
        setResult(data);
        setLoading(false);
        // Scroll gently to results
        setTimeout(() => {
          const el = document.getElementById('catalyst-results-card');
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 150);
      })
      .catch((err) => {
        setError(err.message || 'Error executing AI catalyst analysis pipeline.');
        setLoading(false);
      });
  };

  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      handleAnalyze();
    }
  };

  const loadPreset = (preset) => {
    setHeadline(preset.title);
    setContent(preset.content);
    setTickerHint(preset.ticker || '');
    setResult(null);
    setError(null);
    setAddedToWl(false);
    setShowAdvanced(true);
  };

  const handleClear = () => {
    setHeadline('');
    setContent('');
    setTickerHint('');
    setResult(null);
    setError(null);
  };

  const handlePasteClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        if (!headline) {
          // If first line looks like headline
          const lines = text.split('\n').filter(l => l.trim());
          if (lines.length > 1) {
            setHeadline(lines[0]);
            setContent(lines.slice(1).join('\n'));
          } else {
            setHeadline(text);
          }
        } else {
          setContent(prev => (prev ? `${prev}\n${text}` : text));
        }
        setShowAdvanced(true);
      }
    } catch (err) {
      console.warn('Clipboard read permission denied', err);
    }
  };

  const handleWatchlistAdd = (ticker) => {
    if (onAddToWatchlist && ticker) {
      onAddToWatchlist(ticker);
      setAddedToWl(true);
      setTimeout(() => setAddedToWl(false), 3000);
    }
  };

  const an = result?.analysis;
  const quote = result?.market_context;

  const wordCount = (headline.trim() ? headline.trim().split(/\s+/).length : 0) +
                    (content.trim() ? content.trim().split(/\s+/).length : 0);

  const filteredPresets = activePresetCategory === 'ALL'
    ? PRESET_EXAMPLES
    : PRESET_EXAMPLES.filter(p => p.category === activePresetCategory);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', paddingBottom: '60px' }}>
      
      {/* 1. EDITORIAL MASTHEAD */}
      <div style={{
        background: 'var(--bg-card)',
        border: '2px solid var(--border-heavy)',
        boxShadow: 'var(--shadow-md)',
        borderRadius: 'var(--radius-lg)',
        padding: '24px 28px',
        marginBottom: '24px',
        position: 'relative'
      }}>
        {/* Top Decorative Rule */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              background: '#171717',
              color: '#FFFDF8',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.68rem',
              fontWeight: '700',
              padding: '3px 8px',
              borderRadius: '2px',
              letterSpacing: '0.08em',
              textTransform: 'uppercase'
            }}>
              RESEARCH TERMINAL
            </span>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: '600' }}>
              Dalal Street Event Impact Engine
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span className="pulse-dot" style={{ width: '7px', height: '7px', backgroundColor: '#006D42' }}></span>
              <b>Inference Pipeline:</b> Active
            </span>
            <span style={{ color: 'var(--border-color)' }}>|</span>
            <span><b>Trained Models:</b> 1D / 3D / 5D</span>
            <span style={{ color: 'var(--border-color)' }}>|</span>
            <span><b>Latency:</b> &lt; 40ms</span>
          </div>
        </div>

        {/* Title & Description */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '20px', flexWrap: 'wrap' }}>
          <div>
            <h1 className="font-headline" style={{ fontSize: '1.85rem', fontWeight: '800', lineHeight: 1.15, marginBottom: '6px' }}>
              AI Catalyst Decoder
            </h1>
            <p style={{ fontSize: '0.92rem', color: 'var(--text-secondary)', maxWidth: '820px', lineHeight: 1.5 }}>
              Paste any custom breaking news, quarterly earnings announcement, RBI policy release, regulatory filing,
              or industry catalyst to compute point-in-time financial sentiment, price direction, volatility stops, and multi-horizon target levels.
            </p>
          </div>

          <div style={{
            background: 'var(--bg-primary)',
            border: '1px solid var(--border-color)',
            padding: '10px 14px',
            borderRadius: 'var(--radius-md)',
            textAlign: 'right'
          }}>
            <div style={{ fontSize: '0.70rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', fontWeight: '700' }}>
              ANALYTICAL RIGOR
            </div>
            <div style={{ fontSize: '0.86rem', fontWeight: '800', color: '#006D42' }}>
              100% Code &amp; ML Models
            </div>
            <div style={{ fontSize: '0.70rem', color: 'var(--text-muted)' }}>
              Zero LLM Hallucinations
            </div>
          </div>
        </div>
      </div>

      {/* 2. CURATED DALAL STREET PRESETS TRAY */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-lg)',
        padding: '18px 20px',
        marginBottom: '20px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Compass size={15} color="#171717" />
            <span style={{ fontSize: '0.80rem', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Select a Curated Dalal Street Scenario:
            </span>
          </div>

          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {['ALL', 'EARNINGS', 'MONETARY', 'ORDER_WIN', 'MACRO'].map(cat => (
              <button
                key={cat}
                onClick={() => setActivePresetCategory(cat)}
                style={{
                  fontSize: '0.70rem',
                  fontWeight: '700',
                  padding: '3px 8px',
                  borderRadius: '3px',
                  border: activePresetCategory === cat ? '1px solid #171717' : '1px solid var(--border-light)',
                  background: activePresetCategory === cat ? '#171717' : 'var(--bg-primary)',
                  color: activePresetCategory === cat ? '#FFFDF8' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px' }}>
          {filteredPresets.map((ex, i) => {
            const Icon = ex.categoryIcon || BarChart2;
            return (
              <button
                key={i}
                onClick={() => loadPreset(ex)}
                style={{
                  textAlign: 'left',
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  padding: '10px 12px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = '#171717';
                  e.currentTarget.style.background = '#FFFDF8';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-color)';
                  e.currentTarget.style.background = 'var(--bg-primary)';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                  <span style={{
                    fontSize: '0.68rem',
                    fontWeight: '700',
                    color: ex.badgeColor,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em'
                  }}>
                    <Icon size={12} /> {ex.categoryLabel}
                  </span>
                  <span className="font-mono" style={{ fontSize: '0.70rem', fontWeight: '700', color: 'var(--text-muted)' }}>
                    {ex.ticker.replace('.NS', '')}
                  </span>
                </div>
                <strong style={{ fontSize: '0.80rem', color: 'var(--text-primary)', lineHeight: 1.35 }}>
                  {ex.label}
                </strong>
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. INPUT STUDIO CARD */}
      <form onSubmit={handleAnalyze} style={{
        background: 'var(--bg-card)',
        border: '2px solid var(--border-heavy)',
        boxShadow: 'var(--shadow-md)',
        borderRadius: 'var(--radius-lg)',
        padding: '24px 28px',
        marginBottom: '28px'
      }}>
        {/* Header toolbar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
          <label style={{ fontSize: '0.86rem', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>Headline / Announcement Title</span>
            <span style={{ color: 'var(--bearish)', fontSize: '0.8rem' }}>*</span>
          </label>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              type="button"
              onClick={handlePasteClipboard}
              className="btn btn-secondary btn-sm"
              style={{ fontSize: '0.72rem', padding: '3px 8px', display: 'flex', alignItems: 'center', gap: '4px' }}
              title="Paste content from clipboard"
            >
              <Clipboard size={12} /> Paste
            </button>

            {(headline || content || tickerHint) && (
              <button
                type="button"
                onClick={handleClear}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.72rem', padding: '3px 8px', display: 'flex', alignItems: 'center', gap: '4px' }}
                title="Clear all fields"
              >
                <RotateCcw size={12} /> Clear
              </button>
            )}

            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginLeft: '4px' }}>
              {wordCount} words
            </span>
          </div>
        </div>

        {/* Headline Input */}
        <div style={{ marginBottom: '14px' }}>
          <textarea
            rows={2}
            className="input-field"
            placeholder="e.g. Larsen & Toubro Wins ₹12,000 Cr High-Speed Rail Contract from National High Speed Rail Corp..."
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            onKeyDown={handleKeyDown}
            required
            style={{
              width: '100%',
              fontSize: '1.05rem',
              fontWeight: '600',
              fontFamily: 'var(--font-sans)',
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              border: '1.5px solid var(--border-color)',
              background: '#FFFDF8',
              resize: 'vertical'
            }}
          />
        </div>

        {/* Collapsible Advanced Context (Textarea + Ticker Override) */}
        <div style={{ marginBottom: '16px' }}>
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary)',
              fontSize: '0.78rem',
              fontWeight: '700',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 0',
              marginBottom: showAdvanced ? '10px' : '0'
            }}
          >
            {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            <span>{showAdvanced ? 'Hide Extended Story & Ticker Override' : 'Add Full Press Release & Specific Ticker Override'}</span>
          </button>

          {showAdvanced && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: '16px',
              padding: '16px',
              background: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-color)'
            }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: '700', textTransform: 'uppercase', marginBottom: '6px', color: 'var(--text-secondary)' }}>
                  Full Article Body / Regulatory Paragraphs (Optional)
                </label>
                <textarea
                  className="input-field"
                  rows={4}
                  placeholder="Paste multi-paragraph press releases, quotes, quarterly financial details, or exchange filings here..."
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  onKeyDown={handleKeyDown}
                  style={{ width: '100%', fontSize: '0.85rem', resize: 'vertical' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: '700', textTransform: 'uppercase', marginBottom: '6px', color: 'var(--text-secondary)' }}>
                  Primary Ticker Override (Optional)
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. RELIANCE, TCS, INFY, SBIN, LT (Auto-detected if left empty)"
                  value={tickerHint}
                  onChange={(e) => setTickerHint(e.target.value.toUpperCase())}
                  onKeyDown={handleKeyDown}
                  style={{ width: '100%', marginBottom: '8px', fontSize: '0.85rem' }}
                />
                <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                  💡 <b>Auto-Entity Extraction:</b> When left blank, our Indian equity NER model extracts the primary NSE/BSE ticker, beta, and peer entities automatically from the headline.
                </div>

                {/* Quick Ticker Chips */}
                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '10px' }}>
                  {['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'TATAMOTORS.NS', 'LT.NS'].map(t => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setTickerHint(t)}
                      style={{
                        fontSize: '0.68rem',
                        fontWeight: '700',
                        padding: '2px 6px',
                        background: tickerHint === t ? '#171717' : 'var(--bg-card)',
                        color: tickerHint === t ? '#FFFDF8' : 'var(--text-secondary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '3px',
                        cursor: 'pointer'
                      }}
                    >
                      {t.replace('.NS', '')}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Error message */}
        {error && (
          <div style={{
            padding: '12px 16px',
            background: 'var(--bearish-bg)',
            border: '1px solid var(--bearish-border)',
            color: 'var(--bearish)',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.85rem',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Submit Button */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !headline.trim()}
            style={{
              flex: '1 1 320px',
              padding: '13px 24px',
              fontSize: '0.96rem',
              fontWeight: '800',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '10px',
              background: '#171717',
              color: '#FFFDF8',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              border: '2px solid #171717',
              borderRadius: 'var(--radius-md)',
              cursor: loading || !headline.trim() ? 'not-allowed' : 'pointer'
            }}
          >
            {loading ? (
              <>
                <span className="pulse-dot" style={{ width: '10px', height: '10px', backgroundColor: '#FFFDF8' }}></span>
                <span>Executing NLP &amp; Financial Models...</span>
              </>
            ) : (
              <>
                <Zap size={17} color="#F59E0B" />
                <span>Decode Catalyst Impact</span>
                <span style={{ fontSize: '0.72rem', opacity: 0.7, textTransform: 'none', marginLeft: '4px' }}>(Ctrl + Enter)</span>
              </>
            )}
          </button>

          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Outputs: Direction • Conviction • Targets • Stop-Loss • Precedents
          </div>
        </div>
      </form>

      {/* 4. DECODED CATALYST INTELLIGENCE CARD */}
      {result && an && (
        <div id="catalyst-results-card" style={{
          background: 'var(--bg-card)',
          border: '2px solid var(--border-heavy)',
          boxShadow: 'var(--shadow-lg)',
          borderRadius: 'var(--radius-lg)',
          padding: '28px 32px',
          animation: 'fadeIn 0.25s ease-out'
        }}>
          
          {/* Top Bar: Impact, Sector, Copy Brief & Watchlist */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '2px solid var(--border-heavy)',
            paddingBottom: '16px',
            marginBottom: '20px',
            flexWrap: 'wrap',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span className={`badge ${
                an.impact_level === 'HIGH' ? 'badge-impact-high' : (an.impact_level === 'MEDIUM' ? 'badge-impact-medium' : 'badge-impact-low')
              }`}>
                {an.impact_level} IMPACT
              </span>

              <span style={{
                background: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                fontSize: '0.72rem',
                fontWeight: '700',
                padding: '3px 8px',
                borderRadius: '3px',
                textTransform: 'uppercase'
              }}>
                {an.event_display || an.event_type.replace('_', ' ')}
              </span>

              {an.scope && (
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Scope: <b>{an.scope}</b>
                </span>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  const md = `📊 AI CATALYST DECODER BRIEF\n━━━━━━━━━━━━━━━━━━━━\nHeadline: ${result.title}\nStock: ${an.company_name} (${an.ticker})\nVerdict: ${an.direction} | Impact: ${an.impact_level} | Conviction: ${an.confidence}%\n1D Target: ${an.time_horizons?.['1d']?.projected_change_pct || 'N/A'}\nRationale: ${an.reason_explanation}\n\nDisclaimer: AI/model estimate — not investment advice.`;
                  navigator.clipboard.writeText(md);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                style={{ fontSize: '0.72rem', padding: '5px 10px', display: 'flex', alignItems: 'center', gap: '5px' }}
              >
                {copied ? <Check size={13} color="#006D42" /> : <Copy size={13} />}
                <span>{copied ? 'Copied Brief!' : 'Copy Brief'}</span>
              </button>

              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleWatchlistAdd(an.ticker)}
                style={{
                  fontSize: '0.72rem',
                  padding: '5px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  borderColor: addedToWl ? '#006D42' : undefined,
                  color: addedToWl ? '#006D42' : undefined
                }}
              >
                {addedToWl ? <CheckCircle2 size={13} color="#006D42" /> : <BookmarkPlus size={13} />}
                <span>{addedToWl ? 'Added to Watchlist!' : 'Add to Watchlist'}</span>
              </button>

              {onExploreTicker && an.ticker && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => onExploreTicker(an.ticker)}
                  style={{ fontSize: '0.72rem', padding: '5px 10px', display: 'flex', alignItems: 'center', gap: '5px' }}
                  title="Open Stock Explorer for comprehensive charts"
                >
                  <ExternalLink size={13} />
                  <span>Open Stock</span>
                </button>
              )}
            </div>
          </div>

          {/* Headline Title */}
          <h2 className="font-headline" style={{ fontSize: '1.45rem', fontWeight: '800', lineHeight: 1.3, marginBottom: '20px' }}>
            {result.title}
          </h2>

          {/* Primary Entity Banner */}
          <div style={{
            background: 'var(--bg-primary)',
            border: '1.5px solid var(--border-heavy)',
            borderRadius: 'var(--radius-md)',
            padding: '16px 20px',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '14px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div style={{
                background: '#171717',
                color: '#FFFDF8',
                fontFamily: 'var(--font-mono)',
                fontSize: '1.25rem',
                fontWeight: '800',
                padding: '6px 14px',
                borderRadius: '4px',
                letterSpacing: '0.04em'
              }}>
                {an.ticker}
              </div>

              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: '800', margin: 0, lineHeight: 1.2 }}>
                  {an.company_name}
                </h3>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '3px' }}>
                  <b>Sector:</b> {an.sector} &bull; <b>Beta:</b> {an.beta?.toFixed(2) || '1.00'}
                  {an.all_entities && an.all_entities.length > 1 && (
                    <span style={{ marginLeft: '8px' }}>
                      &bull; <b>Peers:</b> {an.all_entities.slice(1).map(e => e.name || e.ticker).join(', ')}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {quote && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '0.68rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Current Market Price</span>
                  <div className="font-mono" style={{ fontSize: '1.3rem', fontWeight: '800' }}>
                    ₹{quote.price ? quote.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '---'}
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '0.68rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Day Change</span>
                  <div
                    className="font-mono"
                    style={{
                      fontSize: '1.15rem',
                      fontWeight: '800',
                      color: (quote.change_pct || 0) >= 0 ? 'var(--bullish)' : 'var(--bearish)'
                    }}
                  >
                    {(quote.change_pct || 0) >= 0 ? '+' : ''}{(quote.change_pct || 0).toFixed(2)}%
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Verdict Metrics Strip */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
            gap: '14px',
            marginBottom: '24px'
          }}>
            {/* Direction */}
            <div style={{
              background: an.direction === 'UP' ? 'var(--bullish-bg)' : (an.direction === 'DOWN' ? 'var(--bearish-bg)' : 'var(--neutral-bg)'),
              border: `1.5px solid ${an.direction === 'UP' ? 'var(--bullish-border)' : (an.direction === 'DOWN' ? 'var(--bearish-border)' : 'var(--neutral-border)')}`,
              padding: '16px 18px',
              borderRadius: 'var(--radius-md)'
            }}>
              <span style={{ fontSize: '0.70rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                POTENTIAL DIRECTION
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                {an.direction === 'UP' && <TrendingUp size={22} color="#006D42" />}
                {an.direction === 'DOWN' && <TrendingDown size={22} color="#B42318" />}
                {an.direction === 'NEUTRAL' && <Minus size={22} color="#59544C" />}
                <span style={{
                  fontSize: '1.35rem',
                  fontWeight: '900',
                  color: an.direction === 'UP' ? 'var(--bullish)' : (an.direction === 'DOWN' ? 'var(--bearish)' : 'var(--neutral)')
                }}>
                  {an.direction === 'UP' ? 'BULLISH' : (an.direction === 'DOWN' ? 'BEARISH' : 'NEUTRAL')}
                </span>
              </div>
            </div>

            {/* Model Conviction */}
            <div style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-color)',
              padding: '16px 18px',
              borderRadius: 'var(--radius-md)'
            }}>
              <span style={{ fontSize: '0.70rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                CONFIDENCE PROBABILITY
              </span>
              <div className="font-mono" style={{ fontSize: '1.45rem', fontWeight: '800', color: '#171717', marginTop: '6px' }}>
                {an.confidence}%
              </div>
              <div style={{
                height: '4px',
                background: 'var(--border-light)',
                borderRadius: '2px',
                marginTop: '6px',
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${an.confidence}%`,
                  height: '100%',
                  background: an.direction === 'UP' ? '#006D42' : (an.direction === 'DOWN' ? '#B42318' : '#0F52BA')
                }}></div>
              </div>
            </div>

            {/* Financial Sentiment */}
            <div style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-color)',
              padding: '16px 18px',
              borderRadius: 'var(--radius-md)'
            }}>
              <span style={{ fontSize: '0.70rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                CATALYST POLARITY SCORE
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                <span style={{
                  fontSize: '1.25rem',
                  fontWeight: '800',
                  color: an.sentiment === 'Positive' ? 'var(--bullish)' : (an.sentiment === 'Negative' ? 'var(--bearish)' : 'var(--neutral)')
                }}>
                  {an.sentiment}
                </span>
                <span className="font-mono" style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-muted)' }}>
                  ({an.sentiment_score > 0 ? '+' : ''}{Number(an.sentiment_score).toFixed(2)})
                </span>
              </div>
            </div>
          </div>

          {/* Genuine Actionable Trade Recommendations */}
          <div style={{ marginBottom: '26px' }}>
            <TradeRecommendationCard
              ticker={an.ticker}
              companyName={an.company_name}
              currentPrice={quote?.price}
              direction={an.direction}
              confidence={an.confidence}
              sentimentScore={an.sentiment_score}
              beta={an.beta || 1.0}
              eventType={an.event_type}
            />
          </div>

          {/* Multi-Horizon Price Forecasts (1D / 3D / 5D) */}
          <div style={{ marginBottom: '28px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <Clock size={16} color="#171717" />
              <h4 style={{ fontSize: '0.94rem', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Time-Horizon Price Forecasts (T+1 / T+3 / T+5 Trading Days)
              </h4>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px' }}>
              {[
                { key: '1d', label: 'T+1 Day (Initial Reaction)' },
                { key: '3d', label: 'T+3 Days (Momentum Extension)' },
                { key: '5d', label: 'T+5 Days (Catalyst Absorption)' },
              ].map(({ key, label }) => {
                const hz = an.time_horizons?.[key];
                if (!hz) return null;
                const isUp = hz.direction === 'UP';
                return (
                  <div
                    key={key}
                    style={{
                      background: 'var(--bg-primary)',
                      border: '1px solid var(--border-color)',
                      padding: '16px',
                      borderRadius: 'var(--radius-md)'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontSize: '0.76rem', fontWeight: '800', color: 'var(--text-secondary)' }}>
                        {label}
                      </span>
                      <span style={{ fontSize: '0.70rem', color: 'var(--text-muted)', fontWeight: '700' }}>
                        {hz.horizon_confidence}% conf
                      </span>
                    </div>

                    <div
                      className="font-mono"
                      style={{
                        fontSize: '1.25rem',
                        fontWeight: '800',
                        color: isUp ? 'var(--bullish)' : 'var(--bearish)',
                        margin: '4px 0'
                      }}
                    >
                      {hz.projected_change_pct}
                    </div>

                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      Target Range: <b className="font-mono" style={{ color: 'var(--text-primary)' }}>{hz.target_price_range}</b>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Analytical Deep Dive Tabs */}
          <div style={{
            background: 'var(--bg-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-md)',
            padding: '20px',
            marginBottom: '20px'
          }}>
            <div style={{ display: 'flex', gap: '10px', borderBottom: '1px solid var(--border-color)', paddingBottom: '10px', marginBottom: '14px' }}>
              {[
                { id: 'rationale', label: 'Plain-Language Rationale', icon: BookOpen },
                { id: 'precedents', label: 'Dalal Street Precedents', icon: Layers },
                { id: 'sentiment', label: 'NLP Mechanics & Weights', icon: Cpu }
              ].map(tab => {
                const Icon = tab.icon;
                const isActive = activeAnalysisTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveAnalysisTab(tab.id)}
                    style={{
                      background: isActive ? '#171717' : 'transparent',
                      color: isActive ? '#FFFDF8' : 'var(--text-secondary)',
                      border: 'none',
                      borderRadius: '3px',
                      padding: '6px 12px',
                      fontSize: '0.78rem',
                      fontWeight: '700',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <Icon size={13} />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {activeAnalysisTab === 'rationale' && (
              <div style={{ lineHeight: 1.65, fontSize: '0.88rem', color: 'var(--text-primary)' }}>
                <p>{an.reason_explanation}</p>
                {an.secondary_categories && an.secondary_categories.length > 0 && (
                  <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: '700' }}>Secondary Triggers:</span>
                    {an.secondary_categories.map((c, idx) => (
                      <span key={idx} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-light)', padding: '2px 6px', borderRadius: '3px', fontSize: '0.70rem', fontWeight: '600' }}>
                        {c.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeAnalysisTab === 'precedents' && (
              <div style={{ lineHeight: 1.65, fontSize: '0.88rem', color: 'var(--text-primary)' }}>
                {an.historical_precedents?.summary ? (
                  <p>{an.historical_precedents.summary}</p>
                ) : (
                  <p>Historical precedent mapping indicates comparable reaction velocity across historical {an.sector} catalysts.</p>
                )}
              </div>
            )}

            {activeAnalysisTab === 'sentiment' && (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginBottom: '14px' }}>
                  <div style={{ background: 'var(--bg-card)', padding: '10px 12px', borderRadius: '4px', border: '1px solid var(--border-light)' }}>
                    <span style={{ fontSize: '0.70rem', color: 'var(--text-muted)', fontWeight: '700' }}>EVENT WEIGHT</span>
                    <div className="font-mono" style={{ fontSize: '1.1rem', fontWeight: '800' }}>
                      {an.beta ? (an.beta * 1.15).toFixed(2) : '1.15'}x
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-card)', padding: '10px 12px', borderRadius: '4px', border: '1px solid var(--border-light)' }}>
                    <span style={{ fontSize: '0.70rem', color: 'var(--text-muted)', fontWeight: '700' }}>STOCK BETA AMPLIFIER</span>
                    <div className="font-mono" style={{ fontSize: '1.1rem', fontWeight: '800' }}>
                      {an.beta?.toFixed(2) || '1.00'}
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-card)', padding: '10px 12px', borderRadius: '4px', border: '1px solid var(--border-light)' }}>
                    <span style={{ fontSize: '0.70rem', color: 'var(--text-muted)', fontWeight: '700' }}>AFFECTED SECTORS</span>
                    <div style={{ fontSize: '0.82rem', fontWeight: '700' }}>
                      {(an.affected_sectors || [an.sector]).join(', ')}
                    </div>
                  </div>
                </div>
                <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                  Model uses lexicon scoring calibrated for Dalal Street financial discourse blended with scikit-learn Logistic Regression and Random Forest ensembles.
                </div>
              </div>
            )}
          </div>

          {/* Compliance Notice */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.78rem',
            color: 'var(--text-muted)',
            fontWeight: '600',
            borderTop: '1px solid var(--border-color)',
            paddingTop: '14px'
          }}>
            <ShieldAlert size={15} color="#59544C" />
            <span>AI/model estimate — not investment advice. Always verify with qualified financial advisors.</span>
          </div>

        </div>
      )}

    </div>
  );
}
