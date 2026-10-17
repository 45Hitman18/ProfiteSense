import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  TrendingUp, TrendingDown, Minus, AlertCircle, Sparkles, 
  Layers, ArrowUpRight, ArrowDownRight, Activity, Clock, 
  ShieldAlert, ChevronRight, BarChart2, Zap, Target, Search,
  CheckCircle, Globe, RefreshCw, List, LayoutGrid, ArrowUp, Filter
} from 'lucide-react';

const MANDATORY_DISCLAIMER = "AI/model estimate — not investment advice.";

// Clean HTML entities like &nbsp;, &amp;, etc.
function cleanHtml(str) {
  if (!str) return '';
  return str
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/\s+/g, ' ')
    .trim();
}

// Format dispatch summary to eliminate repetitive boilerplate
function formatDispatchSummary(art) {
  const an = art.analysis || {};
  
  // 1. If explicit summary exists and isn't just the title
  if (art.summary && art.summary.trim() && art.summary.trim().toLowerCase() !== art.title?.trim().toLowerCase()) {
    const s = cleanHtml(art.summary);
    return s.length > 165 ? `${s.slice(0, 165).trim()}...` : s;
  }
  
  // 2. Clean reason_explanation from nlp_engine
  if (an.reason_explanation) {
    let exp = cleanHtml(an.reason_explanation);
    // Pattern: "The headline '...' has been classified as a [EventType] event..."
    const headlinePattern = /^The headline\s+['"][^'"]*['"]\s+has been classified as\s+(?:an?|the)?\s*([a-zA-Z\s_-]+)?\s*event/i;
    if (headlinePattern.test(exp)) {
      const remnant = exp.replace(headlinePattern, '').trim();
      const cleanRemnant = remnant.replace(/^[.,;:\s-]+/, '').trim();
      if (cleanRemnant.length > 15 && !cleanRemnant.toLowerCase().startsWith('with ')) {
        return cleanRemnant.length > 165 ? `${cleanRemnant.slice(0, 165).trim()}...` : cleanRemnant;
      }
      
      const eventLabel = an.event_display || an.event_type || 'Market Catalyst';
      const dirText = an.direction ? an.direction.toLowerCase() : (an.sentiment === 'Positive' ? 'bullish' : an.sentiment === 'Negative' ? 'bearish' : 'neutral');
      const confText = an.confidence ? ` with ${Math.round(an.confidence)}% model confidence` : '';
      return `${eventLabel} development indicating ${dirText} price action${confText}.`;
    }
    return exp.length > 165 ? `${exp.slice(0, 165).trim()}...` : exp;
  }
  
  return 'Dalal Street live wire intelligence analyzed for market & ticker impact.';
}


export default function DashboardView({ onSelectArticle, onExploreTicker, onNavigate, onSelectPriceBracket }) {
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState(null);
  const [overviewScope, setOverviewScope] = useState('live');
  const [recentNews, setRecentNews] = useState([]);
  const [categories, setCategories] = useState([]);
  const [priceGroups, setPriceGroups] = useState(null);
  const [activeBracketTab, setActiveBracketTab] = useState('UNDER_500');
  const [searchQuery, setSearchQuery] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [syncNotice, setSyncNotice] = useState(null);
  const [dispatchFilter, setDispatchFilter] = useState('ALL');
  const [isCompact, setIsCompact] = useState(false);
  const [hasScrolled, setHasScrolled] = useState(false);
  const newsScrollRef = useRef(null);

  const fetchDashboardData = async (scope = overviewScope) => {
    try {
      const [ovRes, newsRes, catRes, pbRes] = await Promise.all([
        fetch(`/api/market/overview?scope=${scope}`).then(r => r.json()).catch(() => null),
        fetch('/api/news?page=1&limit=25&sort_by=priority').then(r => r.json()).catch(() => ({ items: [] })),
        fetch('/api/news/categories').then(r => r.json()).catch(() => ({ categories: [] })),
        fetch('/api/stocks/price-brackets').then(r => r.json()).catch(() => null)
      ]);
      setOverview(ovRes);
      setRecentNews(newsRes?.items || []);
      setCategories(catRes?.categories || []);
      if (pbRes?.groups) setPriceGroups(pbRes.groups);
    } catch (e) {
      console.error("Dashboard fetch error:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData(overviewScope);

    // Check for fresh incoming news on page load/refresh
    fetch('/api/news/sync', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        window.dispatchEvent(new CustomEvent('market-data-updated'));
        if (data && data.new_articles_ingested > 0) {
          fetchDashboardData();
          setSyncNotice({
            type: 'success',
            text: `⚡ Ingested ${data.new_articles_ingested} new catalyst stories — prioritized by impact!`
          });
          setTimeout(() => setSyncNotice(null), 6000);
        }
      })
      .catch(() => {});

    const interval = setInterval(fetchDashboardData, 45000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const syncRes = await fetch('/api/news/sync', { method: 'POST' }).then(r => r.json()).catch(() => null);
      window.dispatchEvent(new CustomEvent('market-data-updated'));
      if (syncRes && syncRes.new_articles_ingested > 0) {
        setSyncNotice({
          type: 'success',
          text: `⚡ ${syncRes.new_articles_ingested} new catalyst stories ingested & prioritized!`
        });
      } else {
        setSyncNotice({
          type: 'info',
          text: `✓ Market feed refreshed — high priority catalysts displayed first.`
        });
      }
      setTimeout(() => setSyncNotice(null), 5000);
      await fetchDashboardData();
    } catch (e) {
      console.error("Refresh error:", e);
    } finally {
      setRefreshing(false);
    }
  };

  // Derive sentiment stats
  const totalArticles = overview?.total_analyzed || recentNews.length || 0;
  const posCount = overview?.sentiment_distribution?.positive || recentNews.filter(n => n.analysis?.sentiment === 'Positive').length;
  const neuCount = overview?.sentiment_distribution?.neutral || recentNews.filter(n => n.analysis?.sentiment === 'Neutral').length;
  const negCount = overview?.sentiment_distribution?.negative || recentNews.filter(n => n.analysis?.sentiment === 'Negative').length;

  // Dynamic filtering for dispatches
  const filteredDispatches = useMemo(() => {
    let list = recentNews;
    if (dispatchFilter === 'HIGH') {
      list = list.filter(n => n.analysis?.impact_level === 'HIGH');
    } else if (dispatchFilter === 'EARNINGS') {
      list = list.filter(n => {
        const ev = ((n.analysis?.event_type || '') + ' ' + (n.analysis?.event_display || '')).toUpperCase();
        return ev.includes('EARN') || ev.includes('RESULT') || ev.includes('PROFIT') || ev.includes('REVENUE');
      });
    } else if (dispatchFilter === 'REGULATORY') {
      list = list.filter(n => {
        const ev = ((n.analysis?.event_type || '') + ' ' + (n.analysis?.event_display || '')).toUpperCase();
        return ev.includes('REGULAT') || ev.includes('SEBI') || ev.includes('RBI') || ev.includes('POLICY') || ev.includes('GOV');
      });
    } else if (dispatchFilter === 'BULLISH') {
      list = list.filter(n => n.analysis?.sentiment === 'Positive' || n.analysis?.direction === 'UP');
    } else if (dispatchFilter === 'BEARISH') {
      list = list.filter(n => n.analysis?.sentiment === 'Negative' || n.analysis?.direction === 'DOWN');
    }
    // Fallback if specific filter has 0 items
    if (list.length === 0 && dispatchFilter === 'HIGH') {
      return recentNews.slice(0, 10);
    }
    return list;
  }, [recentNews, dispatchFilter]);

  const handleDispatchesScroll = (e) => {
    if (e.target.scrollTop > 80) {
      if (!hasScrolled) setHasScrolled(true);
    } else {
      if (hasScrolled) setHasScrolled(false);
    }
  };

  const scrollToDispatchesTop = () => {
    if (newsScrollRef.current) {
      newsScrollRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  // Top Indian stocks & benchmarks
  const topStocks = (overview?.top_tickers && overview.top_tickers.length > 0) ? overview.top_tickers : [
    { ticker: 'RELIANCE', company: 'Reliance Industries Ltd', count: 18, sentiment: 'Positive' },
    { ticker: 'TCS', company: 'Tata Consultancy Services', count: 15, sentiment: 'Positive' },
    { ticker: 'HDFCBANK', company: 'HDFC Bank Ltd', count: 14, sentiment: 'Neutral' },
    { ticker: 'INFY', company: 'Infosys Ltd', count: 12, sentiment: 'Positive' },
    { ticker: 'TATAMOTORS', company: 'Tata Motors Ltd', count: 11, sentiment: 'Positive' },
    { ticker: '^NSEI', company: 'NIFTY 50 Benchmark', count: 28, sentiment: 'Neutral' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner / Editorial Wire Bar */}
      <div className="glass-card" style={{ padding: '22px 26px', background: '#FFFDF8', border: '1px solid #C9C1B5', borderTop: '3px solid #171717' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginBottom: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span className="badge badge-impact-high" style={{ fontSize: '0.68rem' }}>DALAL STREET WIRE</span>
              <span style={{ fontSize: '0.74rem', color: '#006D42', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: '700' }}>
                <span className="pulse-dot" style={{ width: '7px', height: '7px', backgroundColor: '#006D42' }}></span>
                Zero-Paid Real-Time Feeds Connected
              </span>
            </div>
            <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.75rem', fontWeight: '900', color: '#171717', margin: 0, letterSpacing: '-0.02em' }}>
              Executive Dalal Street Market Cockpit
            </h2>
            <p style={{ fontSize: '0.84rem', color: '#5A403D', margin: '4px 0 0 0', fontStyle: 'italic', fontFamily: 'var(--font-serif)' }}>
              Real-time Indian equity catalyst detection, linguistic NLP sentiment quantification & ML forecasts
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button 
              className="btn btn-secondary btn-sm" 
              onClick={handleRefresh}
              disabled={refreshing}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              <span>{refreshing ? 'Refreshing...' : 'Sync News'}</span>
            </button>
            <button 
              className="btn btn-primary btn-sm" 
              onClick={() => onNavigate && onNavigate('analyzer')}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Sparkles size={14} />
              <span>AI Catalyst Decoder</span>
            </button>
          </div>
        </div>

        {syncNotice && (
          <div style={{
            background: syncNotice.type === 'success' ? '#ECFDF5' : '#EFF6FF',
            border: `1px solid ${syncNotice.type === 'success' ? '#A7F3D0' : '#BFDBFE'}`,
            color: syncNotice.type === 'success' ? '#065F46' : '#1E40AF',
            padding: '8px 14px',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: '600',
            marginBottom: '14px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <span>{syncNotice.text}</span>
            <span style={{ fontSize: '11px', opacity: 0.75 }}>Auto-sorted: High Priority First</span>
          </div>
        )}

        {/* Search quick bar */}
        <div style={{ position: 'relative', maxWidth: '640px' }}>
          <Search size={16} color="#736B63" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
          <input
            type="text"
            className="input-field"
            placeholder="Search company, NSE ticker (e.g. RELIANCE, TCS), sector or topic (RBI, Inflation)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && searchQuery.trim()) {
                if (onExploreTicker && searchQuery.trim().length <= 15) {
                  onExploreTicker(searchQuery.trim().toUpperCase());
                } else if (onNavigate) {
                  onNavigate('feed');
                }
              }
            }}
            style={{ width: '100%', paddingLeft: '38px', borderRadius: '4px', fontSize: '0.85rem' }}
          />
        </div>
      </div>      {/* Market Status & Sentiment KPI Section Header with Scope Selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '-6px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={16} color="#A71919" />
          <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.05rem', fontWeight: '800', color: '#171717', margin: 0 }}>
            Market Pulse & Catalyst Signal Radar
          </h3>
          <span style={{ 
            fontSize: '0.68rem', 
            fontFamily: 'var(--font-mono)', 
            fontWeight: '700', 
            background: overviewScope === 'live' ? 'rgba(0, 109, 66, 0.1)' : '#F5F1E8', 
            color: overviewScope === 'live' ? '#006D42' : '#5A403D', 
            padding: '2px 8px', 
            borderRadius: '10px',
            border: `1px solid ${overviewScope === 'live' ? 'rgba(0, 109, 66, 0.25)' : '#DDD7CE'}` 
          }}>
            {overviewScope === 'live' ? `⚡ Active Live Feed (${totalArticles} stories)` : `Historical Archive (${totalArticles} stories)`}
          </span>
        </div>

        {/* Scope Switcher: Live Wire vs All-Time Historical */}
        <div style={{ display: 'flex', gap: '4px', background: '#F5F1E8', padding: '3px', borderRadius: '4px', border: '1px solid #C9C1B5' }}>
          <button
            onClick={() => setOverviewScope('live')}
            style={{
              padding: '3px 10px',
              borderRadius: '3px',
              border: 'none',
              background: overviewScope === 'live' ? '#171717' : 'transparent',
              color: overviewScope === 'live' ? '#FFFDF8' : '#5A403D',
              fontSize: '0.70rem',
              fontWeight: '700',
              cursor: 'pointer',
              transition: 'all 0.12s ease'
            }}
          >
            Live Wire Signals
          </button>
          <button
            onClick={() => setOverviewScope('all')}
            style={{
              padding: '3px 10px',
              borderRadius: '3px',
              border: 'none',
              background: overviewScope === 'all' ? '#171717' : 'transparent',
              color: overviewScope === 'all' ? '#FFFDF8' : '#5A403D',
              fontSize: '0.70rem',
              fontWeight: '700',
              cursor: 'pointer',
              transition: 'all 0.12s ease'
            }}
          >
            All-Time Corpus (10k+)
          </button>
        </div>
      </div>

      {/* Market Status & Sentiment KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
        {/* Signal: Positive */}
        <div className="glass-card" style={{ padding: '16px 18px', borderLeft: '4px solid #006D42' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: '800', color: '#5A403D', textTransform: 'uppercase', letterSpacing: '0.04em' }}>POSITIVE SIGNALS</span>
            <TrendingUp size={16} color="#006D42" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: '900', color: '#006D42', fontFamily: 'var(--font-mono)' }}>{posCount}</div>
          <div style={{ fontSize: '0.72rem', color: '#736B63', marginTop: '4px' }}>
            {totalArticles > 0 ? `${Math.round((posCount / totalArticles) * 100)}% of ${overviewScope === 'live' ? 'live news' : 'corpus'}` : 'Tracking...'}
          </div>
        </div>

        {/* Signal: Neutral */}
        <div className="glass-card" style={{ padding: '16px 18px', borderLeft: '4px solid #59544C' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: '800', color: '#5A403D', textTransform: 'uppercase', letterSpacing: '0.04em' }}>NEUTRAL SIGNALS</span>
            <Minus size={16} color="#59544C" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: '900', color: '#59544C', fontFamily: 'var(--font-mono)' }}>{neuCount}</div>
          <div style={{ fontSize: '0.72rem', color: '#736B63', marginTop: '4px' }}>
            {totalArticles > 0 ? `${Math.round((neuCount / totalArticles) * 100)}% of ${overviewScope === 'live' ? 'live news' : 'corpus'}` : 'Tracking...'}
          </div>
        </div>

        {/* Signal: Negative */}
        <div className="glass-card" style={{ padding: '16px 18px', borderLeft: '4px solid #B42318' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: '800', color: '#5A403D', textTransform: 'uppercase', letterSpacing: '0.04em' }}>NEGATIVE SIGNALS</span>
            <TrendingDown size={16} color="#B42318" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: '900', color: '#B42318', fontFamily: 'var(--font-mono)' }}>{negCount}</div>
          <div style={{ fontSize: '0.72rem', color: '#736B63', marginTop: '4px' }}>
            {totalArticles > 0 ? `${Math.round((negCount / totalArticles) * 100)}% of ${overviewScope === 'live' ? 'live news' : 'corpus'}` : 'Tracking...'}
          </div>
        </div>

        {/* Overall Sentiment */}
        <div className="glass-card" style={{ padding: '16px 18px', borderLeft: '4px solid #A71919' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: '800', color: '#5A403D', textTransform: 'uppercase', letterSpacing: '0.04em' }}>MARKET BIAS</span>
            <Activity size={16} color="#A71919" />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: '900', color: '#A71919', fontFamily: 'var(--font-serif)' }}>
            {posCount > negCount ? (posCount / (totalArticles || 1) > 0.6 ? 'Strongly Bullish' : 'Mildly Bullish') : negCount > posCount ? 'Defensive' : 'Balanced'}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#736B63', marginTop: '4px' }}>
            {totalArticles} {overviewScope === 'live' ? 'live dispatches synthesized' : 'historical records synthesized'}
          </div>
        </div>
      </div>

      {/* ── SHARE PRICE BRACKET DIVISION SECTION ── */}
      <div className="glass-card" style={{ padding: '22px 24px', borderTop: '3px solid #171717' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px', marginBottom: '16px', borderBottom: '1px solid #C9C1B5', paddingBottom: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span className="badge badge-impact-high" style={{ fontSize: '0.66rem' }}>PRICE TIER RADAR</span>
              <span style={{ fontSize: '0.74rem', color: '#5A403D', fontWeight: '700' }}>
                ₹0–₹500 · ₹500–₹2,000 · ₹2,000+
              </span>
            </div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', fontWeight: '900', color: '#171717', margin: 0 }}>
              Indian Equities by Share Price Bracket
            </h3>
            <p style={{ fontSize: '0.80rem', color: '#5A403D', margin: '3px 0 0 0', fontStyle: 'italic' }}>
              Track stocks and market catalysts tailored to your capital budget and portfolio tier.
            </p>
          </div>

          {/* Bracket Selector Tabs */}
          <div style={{ display: 'flex', gap: '6px', background: '#F5F1E8', padding: '4px', borderRadius: '4px', border: '1px solid #C9C1B5' }}>
            {[
              { id: 'UNDER_500', label: '₹0 to ₹500', badge: 'Budget / Mid', color: '#059669', bg: '#ECFDF5' },
              { id: '500_TO_2000', label: '₹500 to ₹2,000', badge: 'Core Momentum', color: '#2563EB', bg: '#EFF6FF' },
              { id: 'ABOVE_2000', label: '₹2,000+', badge: 'Bluechips & Leaders', color: '#7C3AED', bg: '#F5F3FF' }
            ].map(b => {
              const active = activeBracketTab === b.id;
              return (
                <button
                  key={b.id}
                  onClick={() => setActiveBracketTab(b.id)}
                  style={{
                    padding: '6px 14px',
                    fontSize: '0.78rem',
                    fontWeight: '800',
                    border: 'none',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    background: active ? '#171717' : 'transparent',
                    color: active ? '#FFFDF8' : '#5A403D',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <span>{b.label}</span>
                  <span style={{
                    fontSize: '0.64rem',
                    padding: '1px 5px',
                    borderRadius: '2px',
                    background: active ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.06)',
                    color: active ? '#FFFDF8' : '#736B63'
                  }}>
                    {b.badge}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Selected Bracket Cards Grid */}
        {priceGroups && priceGroups[activeBracketTab] ? (
          <div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))',
              gap: '12px',
              marginBottom: '16px'
            }}>
              {(priceGroups[activeBracketTab].stocks || []).slice(0, 8).map(stk => (
                <div
                  key={stk.ticker}
                  onClick={() => onExploreTicker && onExploreTicker(stk.ticker)}
                  className="glass-card"
                  style={{
                    padding: '12px 14px',
                    background: '#FFFDF8',
                    border: '1px solid #EAE3D7',
                    borderLeft: `4px solid ${
                      activeBracketTab === 'UNDER_500' ? '#059669' : (activeBracketTab === '500_TO_2000' ? '#2563EB' : '#7C3AED')
                    }`,
                    cursor: 'pointer',
                    transition: 'transform 0.15s ease, box-shadow 0.15s ease'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                    <span className="font-mono" style={{ fontWeight: '800', fontSize: '0.88rem', color: '#171717' }}>
                      {stk.symbol || stk.ticker.replace('.NS', '')}
                    </span>
                    {stk.news_count > 0 && (
                      <span style={{
                        fontSize: '0.64rem',
                        fontWeight: '800',
                        padding: '1px 5px',
                        borderRadius: '2px',
                        background: '#FEF3F2',
                        color: '#B42318',
                        border: '1px solid #FECDCA'
                      }}>
                        ⚡ {stk.news_count} {stk.news_count === 1 ? 'Alert' : 'Alerts'}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#736B63', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginBottom: '8px' }}>
                    {stk.name}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px dashed #EAE3D7', paddingTop: '6px' }}>
                    <span className="font-mono" style={{ fontWeight: '900', fontSize: '0.92rem', color: '#171717' }}>
                      ₹{Number(stk.price || 0).toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 2 })}
                    </span>
                    <span style={{
                      fontSize: '0.72rem',
                      fontWeight: '700',
                      color: (stk.change_pct || 0) >= 0 ? '#006D42' : '#B42318'
                    }}>
                      {(stk.change_pct || 0) >= 0 ? `+${stk.change_pct}%` : `${stk.change_pct}%`}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Action Bar: Jump to Live Feed with this price bracket filter */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '10px', borderTop: '1px solid #EAE3D7', flexWrap: 'wrap', gap: '8px' }}>
              <span style={{ fontSize: '0.76rem', color: '#5A403D', fontStyle: 'italic' }}>
                Showing top active shares in {priceGroups[activeBracketTab].title} bracket
              </span>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => onSelectPriceBracket && onSelectPriceBracket(activeBracketTab)}
                style={{ fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <span>Filter Live News by {priceGroups[activeBracketTab].range_label}</span>
                <ChevronRight size={13} />
              </button>
            </div>
          </div>
        ) : (
          <div style={{ padding: '24px', textAlign: 'center', color: '#736B63', fontSize: '0.82rem' }}>
            Loading stock price brackets...
          </div>
        )}
      </div>

      {/* Main Grid: High-Impact Events & Market Highlights */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.85fr) minmax(320px, 1.15fr)', gap: '20px', alignItems: 'stretch' }}>
        {/* Left Column: High-Impact Catalyst Dispatches */}
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
          <div className="glass-card" style={{ 
            padding: '20px 22px', 
            background: '#FFFDF8', 
            border: '1px solid #C9C1B5', 
            display: 'flex', 
            flexDirection: 'column',
            height: '100%',
            minHeight: 0,
            boxSizing: 'border-box'
          }}>
            {/* Header: Title, Live Status & Action Buttons */}
            <div style={{ flexShrink: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', borderBottom: '2px solid #171717', paddingBottom: '10px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Zap size={18} color="#A71919" />
                <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.18rem', fontWeight: '800', color: '#171717', margin: 0 }}>
                  High-Impact Catalyst Dispatches
                </h3>
                <span style={{ 
                  fontSize: '0.68rem', 
                  fontFamily: 'var(--font-mono)', 
                  fontWeight: '700', 
                  background: '#F5F1E8', 
                  color: '#413D36', 
                  padding: '2px 8px', 
                  borderRadius: '10px',
                  border: '1px solid #DDD7CE' 
                }}>
                  {filteredDispatches.length} active
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  type="button"
                  title={isCompact ? "Switch to Detailed View" : "Switch to Compact View"}
                  onClick={() => setIsCompact(!isCompact)}
                  style={{
                    background: isCompact ? '#171717' : '#F5F1E8',
                    color: isCompact ? '#FFFDF8' : '#413D36',
                    border: '1px solid #C9C1B5',
                    borderRadius: '4px',
                    padding: '4px 8px',
                    fontSize: '0.72rem',
                    fontWeight: '700',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  {isCompact ? <List size={13} /> : <LayoutGrid size={13} />}
                  <span>{isCompact ? 'Compact' : 'Detailed'}</span>
                </button>
                <button 
                  className="btn btn-secondary btn-sm" 
                  onClick={() => onNavigate && onNavigate('feed')}
                  style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                >
                  View Live Wire →
                </button>
              </div>
            </div>

            {/* Category & Sentiment Filter Pills */}
            <div style={{ 
              flexShrink: 0,
              display: 'flex', 
              alignItems: 'center', 
              gap: '6px', 
              overflowX: 'auto', 
              paddingBottom: '10px', 
              marginBottom: '10px',
              borderBottom: '1px solid #EAE3D7'
            }}>
              {[
                { id: 'ALL', label: 'All Dispatches' },
                { id: 'HIGH', label: '🔥 High Impact' },
                { id: 'EARNINGS', label: '📊 Earnings' },
                { id: 'REGULATORY', label: '⚖️ Regulatory' },
                { id: 'BULLISH', label: '📈 Bullish' },
                { id: 'BEARISH', label: '📉 Bearish' }
              ].map(f => {
                const isActive = dispatchFilter === f.id;
                return (
                  <button
                    key={f.id}
                    onClick={() => setDispatchFilter(f.id)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '14px',
                      fontSize: '0.72rem',
                      fontWeight: isActive ? '800' : '600',
                      cursor: 'pointer',
                      border: isActive ? '1px solid #171717' : '1px solid #DDD7CE',
                      background: isActive ? '#171717' : '#FFFDF8',
                      color: isActive ? '#FFFDF8' : '#59544C',
                      whiteSpace: 'nowrap',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {f.label}
                  </button>
                );
              })}
            </div>

            {/* Scrollable Feed Container - Stretches to match exact height of Right Column */}
            <div 
              ref={newsScrollRef}
              onScroll={handleDispatchesScroll}
              className="broadsheet-news-scroll" 
              style={{ 
                flex: '1 1 0px',
                minHeight: 0,
                overflowY: 'auto',
                paddingRight: '6px',
                display: 'flex', 
                flexDirection: 'column', 
                gap: '10px'
              }}
            >
              {filteredDispatches.length === 0 ? (
                <div style={{ padding: '36px 20px', textAlign: 'center', color: '#736B63', background: '#FBF9F5', borderRadius: '4px', border: '1px dashed #DDD7CE' }}>
                  <p style={{ margin: 0, fontWeight: '600', fontSize: '0.86rem' }}>No catalyst stories matching "{dispatchFilter}"</p>
                  <button 
                    onClick={() => setDispatchFilter('ALL')} 
                    style={{ marginTop: '8px', background: 'transparent', border: 'none', color: '#A71919', fontWeight: '700', cursor: 'pointer', textDecoration: 'underline', fontSize: '0.78rem' }}
                  >
                    Reset filter to view all
                  </button>
                </div>
              ) : (
                filteredDispatches.map((art) => {
                  const an = art.analysis || {};
                  const isPos = an.sentiment === 'Positive' || an.direction === 'UP';
                  const isNeg = an.sentiment === 'Negative' || an.direction === 'DOWN';
                  const dirColor = isPos ? '#006D42' : isNeg ? '#B42318' : '#59544C';
                  const dirBg = isPos ? 'rgba(0, 109, 66, 0.08)' : isNeg ? 'rgba(180, 35, 24, 0.08)' : 'rgba(89, 84, 76, 0.08)';
                  const formattedSummary = formatDispatchSummary(art);

                  return (
                    <div 
                      key={art.id} 
                      className="glass-card" 
                      style={{ 
                        padding: isCompact ? '10px 14px' : '14px 16px', 
                        background: '#FFFDF8', 
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                        border: '1px solid #EAE3D7',
                        borderLeft: `4px solid ${dirColor}`,
                        boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = '#C9C1B5';
                        e.currentTarget.style.transform = 'translateY(-1px)';
                        e.currentTarget.style.boxShadow = '0 3px 8px rgba(0,0,0,0.06)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = '#EAE3D7';
                        e.currentTarget.style.transform = 'translateY(0)';
                        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.03)';
                      }}
                      onClick={() => onSelectArticle && onSelectArticle(art.id)}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: isCompact ? '4px' : '8px', flexWrap: 'wrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                          {an.ticker && (
                            <span 
                              className="badge-ticker" 
                              style={{ 
                                cursor: 'pointer', 
                                fontSize: '0.72rem', 
                                padding: '2px 7px',
                                fontWeight: '800'
                              }}
                              onClick={(e) => { e.stopPropagation(); onExploreTicker && onExploreTicker(an.ticker); }}
                              title={`Explore ${an.ticker} technicals & news`}
                            >
                              {an.ticker}
                            </span>
                          )}

                          {/* Stock Price Bracket Badge */}
                          {art.stock_price && (
                            <span style={{
                              fontSize: '0.68rem',
                              fontWeight: '800',
                              padding: '2px 6px',
                              borderRadius: '2px',
                              background: art.price_bracket_bg || '#ECFDF5',
                              color: art.price_bracket_color || '#059669',
                              border: `1px solid ${art.price_bracket_border || '#A7F3D0'}`,
                              fontFamily: 'var(--font-mono)'
                            }}>
                              ₹{Number(art.stock_price).toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 2 })}
                            </span>
                          )}

                          <span className="badge-sector" style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
                            {an.event_display || an.event_type || 'CATALYST'}
                          </span>

                          <span 
                            style={{ 
                              fontSize: '0.66rem', 
                              padding: '2px 6px', 
                              borderRadius: '2px',
                              fontWeight: '800',
                              background: an.impact_level === 'HIGH' ? '#A71919' : '#EDE8DF',
                              color: an.impact_level === 'HIGH' ? '#FFFDF8' : '#413D36',
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em'
                            }}
                          >
                            {an.impact_level || 'MEDIUM'} IMPACT
                          </span>
                        </div>

                        {/* Direction & Confidence Pill */}
                        <div style={{ 
                          display: 'inline-flex', 
                          alignItems: 'center', 
                          gap: '4px', 
                          color: dirColor, 
                          background: dirBg,
                          padding: '2px 8px',
                          borderRadius: '12px',
                          fontWeight: '800', 
                          fontSize: '0.72rem', 
                          fontFamily: 'var(--font-mono)',
                          border: `1px solid ${dirColor}33`
                        }}>
                          {isPos ? <ArrowUpRight size={13} /> : isNeg ? <ArrowDownRight size={13} /> : <Minus size={13} />}
                          <span>{an.direction || (isPos ? 'UP' : isNeg ? 'DOWN' : 'NEUTRAL')}</span>
                          {an.confidence && <span style={{ opacity: 0.85 }}>({Math.round(an.confidence)}%)</span>}
                        </div>
                      </div>

                      <h4 style={{ 
                        fontFamily: 'var(--font-serif)', 
                        fontSize: isCompact ? '0.94rem' : '1.04rem', 
                        fontWeight: '800', 
                        margin: isCompact ? '0 0 3px 0' : '0 0 6px 0', 
                        lineHeight: '1.35', 
                        color: '#171717' 
                      }}>
                        {cleanHtml(art.title)}
                      </h4>

                      {!isCompact && formattedSummary && (
                        <p style={{ fontSize: '0.79rem', color: '#5A403D', margin: '0 0 8px 0', lineHeight: '1.45' }}>
                          {cleanHtml(formattedSummary)}
                        </p>
                      )}

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.68rem', color: '#736B63', borderTop: '1px solid #F5F1E8', paddingTop: '6px' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontWeight: '600', color: '#413D36' }}>{art.source || 'News Wire'}</span>
                          <span>•</span>
                          <span>{art.published_at ? art.published_at.slice(0, 10) : 'Recent'}</span>
                        </span>
                        <span style={{ color: '#8E706C', fontStyle: 'italic', fontSize: '0.66rem' }}>
                          {MANDATORY_DISCLAIMER}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Bottom Status & Scroll Action Bar */}
            <div style={{ 
              flexShrink: 0,
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              paddingTop: '10px', 
              marginTop: '10px', 
              borderTop: '1px solid #EAE3D7',
              fontSize: '0.72rem',
              color: '#736B63'
            }}>
              <span>
                Showing <strong>{filteredDispatches.length}</strong> dispatches • Auto-sync every 45s
              </span>
              {hasScrolled && (
                <button
                  onClick={scrollToDispatchesTop}
                  style={{
                    background: '#F5F1E8',
                    border: '1px solid #DDD7CE',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    fontSize: '0.70rem',
                    fontWeight: '700',
                    color: '#171717',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <ArrowUp size={12} /> Top
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Top Stocks, Factors & Sectors */}
        <div style={{ 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '14px' 
        }}>
          {/* Top Analyzed Stocks */}
          <div className="glass-card" style={{ padding: '16px 18px', background: '#FFFDF8', border: '1px solid #C9C1B5' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', borderBottom: '1px solid #C9C1B5', paddingBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Target size={16} color="#A71919" />
                <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '0.98rem', fontWeight: '800', color: '#171717', margin: 0 }}>
                  Top Active Tickers
                </h3>
              </div>
              <button 
                className="btn btn-secondary btn-sm" 
                onClick={() => onNavigate && onNavigate('intelligence')}
                style={{ fontSize: '0.70rem', padding: '2px 8px' }}
              >
                Intel →
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {topStocks.slice(0, 6).map((stk, idx) => {
                const isPos = stk.sentiment === 'Positive';
                const isNeg = stk.sentiment === 'Negative';
                const dotColor = isPos ? '#006D42' : isNeg ? '#B42318' : '#736B63';

                return (
                  <div 
                    key={`${stk.ticker}-${idx}`}
                    className="glass-card" 
                    style={{ 
                      padding: '7px 10px', 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center', 
                      cursor: 'pointer',
                      background: '#FBF9F5',
                      border: '1px solid #EAE3D7',
                      transition: 'all 0.12s ease'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#F5F1E8';
                      e.currentTarget.style.borderColor = '#C9C1B5';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = '#FBF9F5';
                      e.currentTarget.style.borderColor = '#EAE3D7';
                    }}
                    onClick={() => onExploreTicker && onExploreTicker(stk.ticker)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: dotColor, flexShrink: 0 }}></span>
                      <div style={{ minWidth: 0 }}>
                        <span className="font-mono" style={{ fontWeight: '800', fontSize: '0.82rem', color: '#171717' }}>
                          {stk.ticker}
                        </span>
                        <span style={{ fontSize: '0.70rem', color: '#736B63', marginLeft: '6px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {stk.company || stk.name || ''}
                        </span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                      <span style={{ 
                        fontSize: '0.68rem', 
                        color: '#413D36', 
                        fontWeight: '700',
                        background: '#EAE3D7',
                        padding: '1px 6px',
                        borderRadius: '3px'
                      }}>
                        {stk.count || stk.mentions || 1} articles
                      </span>
                      <ChevronRight size={13} color="#736B63" />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Key Factors Affecting Indian Shares */}
          <div className="glass-card" style={{ padding: '16px 18px', background: '#FFFDF8', border: '1px solid #C9C1B5', borderTop: '3px solid #A71919' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', borderBottom: '1px solid #C9C1B5', paddingBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={16} color="#A71919" />
                <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '0.98rem', fontWeight: '800', color: '#171717', margin: 0 }}>
                  Factors Affecting Indian Market
                </h3>
              </div>
              <span className="badge badge-sector" style={{ fontSize: '0.65rem' }}>MACRO DRIVERS</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
              {[
                { factor: 'RBI Repo Rate & MPC Policy', impact: 'Banking, NBFCs, Real Estate', status: 'Policy Stance: Neutral / Cautious', color: '#006D42' },
                { factor: 'FII / DII Net Flow Momentum', impact: 'Broad Market Equity Drift', status: 'DII Net Buyers / FPI Selective', color: '#006D42' },
                { factor: 'Brent Crude Oil Price ($/bbl)', impact: 'OMCs, Paints, Aviation, Rupee', status: 'Commodity Pressure Monitor', color: '#B42318' },
                { factor: 'USD / INR Rupee Valuation', impact: 'IT Exporters, Pharma, Imports', status: 'Forex Volatility Tracked', color: '#59544C' },
                { factor: 'SEBI Regulatory Actions', impact: 'F&O Derivatives, Liquidity', status: 'Risk Oversight Active', color: '#171717' }
              ].map(f => (
                <div 
                  key={f.factor}
                  style={{ padding: '7px 9px', background: '#FBF9F5', borderRadius: '4px', border: '1px solid #EAE3D7' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                    <span style={{ fontSize: '0.76rem', fontWeight: '700', color: '#171717' }}>{f.factor}</span>
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: f.color }}></span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.67rem', color: '#736B63' }}>
                    <span>Impact: {f.impact}</span>
                    <span style={{ fontStyle: 'italic', color: f.color, fontWeight: '700' }}>{f.status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Affected Sectors */}
          <div className="glass-card" style={{ padding: '16px 18px', background: '#FFFDF8', border: '1px solid #C9C1B5' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', borderBottom: '1px solid #C9C1B5', paddingBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Layers size={16} color="#A71919" />
                <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '0.98rem', fontWeight: '800', color: '#171717', margin: 0 }}>
                  Indian Sectoral Catalysts
                </h3>
              </div>
              <button 
                className="btn btn-secondary btn-sm" 
                onClick={() => onNavigate && onNavigate('market')}
                style={{ fontSize: '0.70rem', padding: '2px 8px' }}
              >
                Sectors →
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {[
                { name: 'Banking & Financial Services', count: 32, bias: 'POSITIVE', color: '#006D42', bg: 'rgba(0, 109, 66, 0.08)' },
                { name: 'IT Services & Exporters', count: 28, bias: 'NEUTRAL', color: '#59544C', bg: 'rgba(89, 84, 76, 0.08)' },
                { name: 'Automobile & EVs', count: 18, bias: 'POSITIVE', color: '#006D42', bg: 'rgba(0, 109, 66, 0.08)' },
                { name: 'Energy & Petrochemicals', count: 14, bias: 'NEUTRAL', color: '#59544C', bg: 'rgba(89, 84, 76, 0.08)' },
                { name: 'Consumer Goods (FMCG)', count: 16, bias: 'POSITIVE', color: '#006D42', bg: 'rgba(0, 109, 66, 0.08)' },
                { name: 'Macro, RBI & Policy Catalysts', count: 42, bias: 'POSITIVE', color: '#006D42', bg: 'rgba(0, 109, 66, 0.08)' },
              ].map(sec => (
                <div 
                  key={sec.name}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.76rem', padding: '5px 0', borderBottom: '1px solid #EAE3D7' }}
                >
                  <span style={{ color: '#171717', fontWeight: '600' }}>{sec.name}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ color: '#736B63', fontSize: '0.70rem' }}>{sec.count} news</span>
                    <span style={{ 
                      color: sec.color, 
                      background: sec.bg,
                      padding: '1px 6px',
                      borderRadius: '3px',
                      fontWeight: '800', 
                      fontSize: '0.68rem', 
                      letterSpacing: '0.04em' 
                    }}>
                      {sec.bias}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Editorial Broadsheet Compliance Card */}
          <div style={{ padding: '12px 14px', borderRadius: '4px', background: '#F5F1E8', border: '1px solid #C9C1B5', borderLeft: '4px solid #A71919' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '3px' }}>
              <ShieldAlert size={13} color="#A71919" />
              <span style={{ fontSize: '0.72rem', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.04em', color: '#A71919' }}>
                Algorithmic Disclaimer
              </span>
            </div>
            <p style={{ fontSize: '0.70rem', color: '#5A403D', margin: 0, lineHeight: '1.4', fontStyle: 'italic' }}>
              Market News AI estimates are probabilistic algorithmic outputs for educational and analytical research purposes only. Not investment, trading, or financial advice.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
