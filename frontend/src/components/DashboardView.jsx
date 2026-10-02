import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, TrendingDown, Minus, AlertCircle, Sparkles, 
  Layers, ArrowUpRight, ArrowDownRight, Activity, Clock, 
  ShieldAlert, ChevronRight, BarChart2, Zap, Target, Search,
  CheckCircle, Globe, RefreshCw
} from 'lucide-react';

const MANDATORY_DISCLAIMER = "AI/model estimate — not investment advice.";

export default function DashboardView({ onSelectArticle, onExploreTicker, onNavigate, onSelectPriceBracket }) {
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState(null);
  const [recentNews, setRecentNews] = useState([]);
  const [categories, setCategories] = useState([]);
  const [priceGroups, setPriceGroups] = useState(null);
  const [activeBracketTab, setActiveBracketTab] = useState('UNDER_500');
  const [searchQuery, setSearchQuery] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [syncNotice, setSyncNotice] = useState(null);

  const fetchDashboardData = async () => {
    try {
      const [ovRes, newsRes, catRes, pbRes] = await Promise.all([
        fetch('/api/market/overview').then(r => r.json()).catch(() => null),
        fetch('/api/news?page=1&limit=10&sort_by=priority').then(r => r.json()).catch(() => ({ items: [] })),
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
    fetchDashboardData();

    // Check for fresh incoming news on page load/refresh
    fetch('/api/news/sync', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
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

  const highImpactArticles = recentNews.filter(n => n.analysis?.impact_level === 'HIGH');
  const marketImpactingNews = highImpactArticles.length > 0 ? highImpactArticles : recentNews.slice(0, 5);

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
      </div>      {/* Market Status & Sentiment KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
        {/* Signal: Positive */}
        <div className="glass-card" style={{ padding: '16px 18px', borderLeft: '4px solid #006D42' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: '800', color: '#5A403D', textTransform: 'uppercase', letterSpacing: '0.04em' }}>POSITIVE SIGNALS</span>
            <TrendingUp size={16} color="#006D42" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: '900', color: '#006D42', fontFamily: 'var(--font-mono)' }}>{posCount}</div>
          <div style={{ fontSize: '0.72rem', color: '#736B63', marginTop: '4px' }}>
            {totalArticles > 0 ? `${Math.round((posCount / totalArticles) * 100)}% of analyzed news` : 'Tracking...'}
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
            {totalArticles > 0 ? `${Math.round((neuCount / totalArticles) * 100)}% of analyzed news` : 'Tracking...'}
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
            {totalArticles > 0 ? `${Math.round((negCount / totalArticles) * 100)}% of analyzed news` : 'Tracking...'}
          </div>
        </div>

        {/* Overall Sentiment */}
        <div className="glass-card" style={{ padding: '16px 18px', borderLeft: '4px solid #A71919' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: '800', color: '#5A403D', textTransform: 'uppercase', letterSpacing: '0.04em' }}>MARKET BIAS</span>
            <Activity size={16} color="#A71919" />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: '900', color: '#A71919', fontFamily: 'var(--font-serif)' }}>
            {posCount > negCount ? 'Mildly Bullish' : negCount > posCount ? 'Defensive' : 'Balanced'}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#736B63', marginTop: '4px' }}>
            {totalArticles} dispatches synthesized
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
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
        {/* Left Column: High-Impact Catalyst Events */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div className="glass-card" style={{ padding: '20px 22px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', borderBottom: '2px solid #171717', pb: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Zap size={18} color="#A71919" />
                <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.15rem', fontWeight: '800', color: '#171717', margin: 0 }}>
                  High-Impact Catalyst Dispatches
                </h3>
              </div>
              <button 
                className="btn btn-secondary btn-sm" 
                onClick={() => onNavigate && onNavigate('feed')}
                style={{ fontSize: '0.72rem' }}
              >
                View Live Wire →
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {marketImpactingNews.map((art) => {
                const an = art.analysis || {};
                const isPos = an.sentiment === 'Positive';
                const isNeg = an.sentiment === 'Negative';
                const dirColor = isPos ? '#006D42' : isNeg ? '#B42318' : '#59544C';

                return (
                  <div 
                    key={art.id} 
                    className="glass-card" 
                    style={{ 
                      padding: '14px 16px', 
                      background: '#FFFDF8', 
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      border: '1px solid #EAE3D7',
                      borderLeft: `4px solid ${dirColor}`
                    }}
                    onClick={() => onSelectArticle && onSelectArticle(art.id)}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', marginBottom: '6px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        {an.ticker && (
                          <span 
                            className="badge-ticker" 
                            style={{ cursor: 'pointer', fontSize: '0.72rem' }}
                            onClick={(e) => { e.stopPropagation(); onExploreTicker && onExploreTicker(an.ticker); }}
                          >
                            {an.ticker}
                          </span>
                        )}
                        <span className="badge-sector" style={{ fontSize: '0.68rem' }}>
                          {an.event_display || an.event_type || 'CATALYST'}
                        </span>
                        <span 
                          style={{ 
                            fontSize: '0.68rem', 
                            padding: '2px 6px', 
                            borderRadius: '2px',
                            fontWeight: '700',
                            background: an.impact_level === 'HIGH' ? '#A71919' : '#EAE7E7',
                            color: an.impact_level === 'HIGH' ? '#FFFDF8' : '#171717',
                            textTransform: 'uppercase',
                            letterSpacing: '0.04em'
                          }}
                        >
                          {an.impact_level || 'MEDIUM'} IMPACT
                        </span>

                        {/* Stock Price Badge */}
                        {art.stock_price && (
                          <span style={{
                            fontSize: '0.68rem',
                            fontWeight: '800',
                            padding: '2px 6px',
                            borderRadius: '2px',
                            background: art.price_bracket_bg || '#ECFDF5',
                            color: art.price_bracket_color || '#059669',
                            border: `1px solid ${art.price_bracket_border || '#A7F3D0'}`
                          }}>
                            ₹{Number(art.stock_price).toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 2 })}
                          </span>
                        )}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: dirColor, fontWeight: '800', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                        {isPos ? <ArrowUpRight size={14} /> : isNeg ? <ArrowDownRight size={14} /> : <Minus size={14} />}
                        <span>{an.direction || 'NEUTRAL'}</span>
                        {an.confidence && <span style={{ opacity: 0.8 }}>({Math.round(an.confidence)}%)</span>}
                      </div>
                    </div>

                    <h4 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.05rem', fontWeight: '800', margin: '0 0 6px 0', lineHeight: '1.35', color: '#171717' }}>
                      {art.title}
                    </h4>

                    {an.reason_explanation && (
                      <p style={{ fontSize: '0.80rem', color: '#5A403D', margin: '0 0 8px 0', lineHeight: '1.45' }}>
                        {an.reason_explanation.length > 140 ? `${an.reason_explanation.slice(0, 140)}...` : an.reason_explanation}
                      </p>
                    )}

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem', color: '#736B63', borderTop: '1px solid #F5F1E8', paddingTop: '6px' }}>
                      <span>{art.source || 'News Wire'} • {art.published_at ? art.published_at.slice(0, 10) : 'Recent'}</span>
                      <span style={{ color: '#8E706C', fontStyle: 'italic' }}>
                        {MANDATORY_DISCLAIMER}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Top Stocks & Affected Sectors */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {/* Top Analyzed Stocks */}
          <div className="glass-card" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', borderBottom: '1px solid #C9C1B5', paddingBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Target size={16} color="#A71919" />
                <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1rem', fontWeight: '800', color: '#171717', margin: 0 }}>
                  Top Active Tickers
                </h3>
              </div>
              <button 
                className="btn btn-secondary btn-sm" 
                onClick={() => onNavigate && onNavigate('intelligence')}
                style={{ fontSize: '0.70rem' }}
              >
                Intel →
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {topStocks.slice(0, 6).map((stk, idx) => (
                <div 
                  key={`${stk.ticker}-${idx}`}
                  className="glass-card" 
                  style={{ 
                    padding: '8px 12px', 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    cursor: 'pointer',
                    background: '#FBF9F5',
                    border: '1px solid #EAE3D7'
                  }}
                  onClick={() => onExploreTicker && onExploreTicker(stk.ticker)}
                >
                  <div>
                    <span className="font-mono" style={{ fontWeight: '800', fontSize: '0.85rem', color: '#171717' }}>
                      {stk.ticker}
                    </span>
                    <span style={{ fontSize: '0.72rem', color: '#736B63', marginLeft: '8px' }}>
                      {stk.company || stk.name || ''}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '0.7rem', color: '#736B63', fontWeight: '600' }}>
                      {stk.count || stk.mentions || 1} articles
                    </span>
                    <ChevronRight size={14} color="#736B63" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Key Factors Affecting Indian Shares */}
          <div className="glass-card" style={{ padding: '18px 20px', borderTop: '3px solid #A71919' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', borderBottom: '1px solid #C9C1B5', paddingBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={16} color="#A71919" />
                <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1rem', fontWeight: '800', color: '#171717', margin: 0 }}>
                  Factors Affecting Indian Market
                </h3>
              </div>
              <span className="badge badge-sector" style={{ fontSize: '0.65rem' }}>MACRO DRIVERS</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { factor: 'RBI Repo Rate & MPC Policy', impact: 'Banking, NBFCs, Real Estate', status: 'Policy Stance: Neutral / Cautious', color: '#006D42' },
                { factor: 'FII / DII Net Flow Momentum', impact: 'Broad Market Equity Drift', status: 'DII Net Buyers / FPI Selective', color: '#006D42' },
                { factor: 'Brent Crude Oil Price ($/bbl)', impact: 'OMCs, Paints, Aviation, Rupee', status: 'Commodity Pressure Monitor', color: '#B42318' },
                { factor: 'USD / INR Rupee Valuation', impact: 'IT Exporters, Pharma, Imports', status: 'Forex Volatility Tracked', color: '#59544C' },
                { factor: 'SEBI Regulatory Actions', impact: 'F&O Derivatives, Liquidity', status: 'Risk Oversight Active', color: '#171717' }
              ].map(f => (
                <div 
                  key={f.factor}
                  style={{ padding: '8px 10px', background: '#FBF9F5', borderRadius: '4px', border: '1px solid #EAE3D7' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                    <span style={{ fontSize: '0.78rem', fontWeight: '700', color: '#171717' }}>{f.factor}</span>
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: f.color }}></span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.68rem', color: '#736B63' }}>
                    <span>Impact: {f.impact}</span>
                    <span style={{ fontStyle: 'italic', color: f.color, fontWeight: '600' }}>{f.status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Affected Sectors */}
          <div className="glass-card" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', borderBottom: '1px solid #C9C1B5', paddingBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Layers size={16} color="#A71919" />
                <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1rem', fontWeight: '800', color: '#171717', margin: 0 }}>
                  Indian Sectoral Catalysts
                </h3>
              </div>
              <button 
                className="btn btn-secondary btn-sm" 
                onClick={() => onNavigate && onNavigate('market')}
                style={{ fontSize: '0.70rem' }}
              >
                Sectors →
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { name: 'Banking & Financial Services', count: 32, bias: 'Positive', color: '#006D42' },
                { name: 'IT Services & Exporters', count: 28, bias: 'Neutral', color: '#59544C' },
                { name: 'Automobile & EVs', count: 18, bias: 'Positive', color: '#006D42' },
                { name: 'Energy & Petrochemicals', count: 14, bias: 'Neutral', color: '#59544C' },
                { name: 'Consumer Goods (FMCG)', count: 16, bias: 'Positive', color: '#006D42' },
                { name: 'Macro, RBI & Policy Catalysts', count: 42, bias: 'Positive', color: '#006D42' },
              ].map(sec => (
                <div 
                  key={sec.name}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.78rem', padding: '6px 0', borderBottom: '1px solid #EAE3D7' }}
                >
                  <span style={{ color: '#171717', fontWeight: '600' }}>{sec.name}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ color: '#736B63', fontSize: '0.72rem' }}>{sec.count} news</span>
                    <span style={{ color: sec.color, fontWeight: '700', fontSize: '0.72rem', textTransform: 'uppercase' }}>{sec.bias}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Editorial Broadsheet Compliance Card */}
          <div style={{ padding: '14px 16px', borderRadius: '4px', background: '#F5F1E8', border: '1px solid #C9C1B5', borderLeft: '4px solid #A71919' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
              <ShieldAlert size={14} color="#A71919" />
              <span style={{ fontSize: '0.74rem', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.04em', color: '#A71919' }}>
                Algorithmic Disclaimer
              </span>
            </div>
            <p style={{ fontSize: '0.72rem', color: '#5A403D', margin: 0, lineHeight: '1.45', fontStyle: 'italic' }}>
              Market News AI estimates are probabilistic algorithmic outputs for educational and analytical research purposes only. Not investment, trading, or financial advice.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
