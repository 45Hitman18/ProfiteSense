import React, { useState, useEffect } from 'react';
import { 
  Search, RefreshCw, Filter, TrendingUp, TrendingDown, Minus, 
  ArrowUpRight, Clock, Bookmark, BookmarkCheck, ExternalLink, Zap
} from 'lucide-react';

// Safely parse a value that may be a JSON string or already an array
const safeArr = (v) => {
  if (Array.isArray(v)) return v;
  if (typeof v === 'string' && v.startsWith('[')) {
    try { return JSON.parse(v); } catch { return []; }
  }
  return [];
};


const SECTORS = [
  'All Sectors',
  'Banking & Finance',
  'Information Technology',
  'Automobile',
  'Energy & Petrochemicals',
  'Consumer Goods (FMCG)',
  'Pharmaceuticals',
  'Metals & Mining',
  'Engineering & Construction',
  'Telecommunications',
  'Power & Utilities',
  'Macro & Monetary Policy (RBI)',
  'Institutional Liquidity & Flows',
  'Commodities & Energy Shock',
  'Forex & Currency Valuation',
  'Regulatory & Market Oversight (SEBI)'
];

export default function LiveFeedView({ 
  onSelectArticle, 
  onAddToWatchlist, 
  watchlist = [],
  selectedPriceBracket: propBracket = 'ALL',
  onSelectPriceBracket
}) {
  const [news, setNews] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncNotice, setSyncNotice] = useState(null);
  const [sortBy, setSortBy] = useState('priority');
  const [internalBracket, setInternalBracket] = useState(propBracket);
  
  const activePriceBracket = onSelectPriceBracket ? propBracket : internalBracket;
  const setPriceBracket = (b) => {
    if (onSelectPriceBracket) onSelectPriceBracket(b);
    setInternalBracket(b);
  };
  
  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSentiment, setSelectedSentiment] = useState('ALL');
  const [selectedImpact, setSelectedImpact] = useState('ALL');
  const [selectedDirection, setSelectedDirection] = useState('ALL');
  const [selectedSector, setSelectedSector] = useState('All Sectors');

  const fetchNews = (currentPage = 1) => {
    setLoading(true);
    let url = `/api/news?page=${currentPage}&limit=15&sort_by=${sortBy}`;
    if (activePriceBracket && activePriceBracket !== 'ALL') url += `&price_bracket=${activePriceBracket}`;
    if (searchQuery) url += `&query=${encodeURIComponent(searchQuery)}`;
    if (selectedSentiment !== 'ALL') url += `&sentiment=${selectedSentiment}`;
    if (selectedImpact !== 'ALL') url += `&impact_level=${selectedImpact}`;
    if (selectedDirection !== 'ALL') url += `&direction=${selectedDirection}`;
    if (selectedSector !== 'All Sectors') url += `&sector=${encodeURIComponent(selectedSector)}`;

    fetch(url)
      .then((res) => res.json())
      .then((data) => {
        setNews(data.items || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 1);
        setPage(data.page || 1);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error fetching news:', err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchNews(1);
  }, [selectedSentiment, selectedImpact, selectedDirection, selectedSector, searchQuery, sortBy, activePriceBracket]);

  // Check for incoming news on initial mount/refresh
  useEffect(() => {
    fetch('/api/news/sync', { method: 'POST' })
      .then((res) => res.json())
      .then((res) => {
        if (res && res.new_articles_ingested > 0) {
          fetchNews(1);
          setSyncNotice(`⚡ ${res.new_articles_ingested} new articles found and prioritized by impact!`);
          setTimeout(() => setSyncNotice(null), 6000);
        }
      })
      .catch(() => {});
  }, []);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchNews(1);
  };

  const handleSyncNews = () => {
    setSyncing(true);
    fetch('/api/news/sync', { method: 'POST' })
      .then((res) => res.json())
      .then((res) => {
        setSyncing(false);
        if (res && res.new_articles_ingested > 0) {
          setSyncNotice(`⚡ Ingested ${res.new_articles_ingested} new market catalysts — sorted by priority!`);
        } else {
          setSyncNotice('✓ RSS & News feeds are up to date. Showing high-priority catalysts first.');
        }
        setTimeout(() => setSyncNotice(null), 5000);
        fetchNews(1);
      })
      .catch(() => setSyncing(false));
  };

  const isTickerWatchlisted = (ticker) => {
    return watchlist.some((w) => w.ticker === ticker);
  };

  return (
    <div>
      {/* 1. SHARE PRICE BRACKET SELECTOR */}
      <div className="glass-card" style={{
        marginBottom: '16px',
        padding: '14px 20px',
        background: '#FFFDF8',
        border: '1px solid #C9C1B5',
        borderLeft: '5px solid #A71919',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ background: '#F5EBE6', padding: '8px', borderRadius: '4px', border: '1px solid #E5D5CD' }}>
            <TrendingUp size={18} color="#A71919" />
          </div>
          <div>
            <div style={{ fontSize: '11px', fontWeight: '800', letterSpacing: '0.12em', color: '#A71919', textTransform: 'uppercase' }}>
              DIVIDE BY SHARE PRICE TIER
            </div>
            <div style={{ fontSize: '13px', fontWeight: '800', color: '#171717', fontFamily: 'var(--font-serif)' }}>
              Catch Up by Stock Budget: ₹0–₹500 · ₹500–₹2,000 · ₹2,000+
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {[
            { id: 'ALL', label: 'All Shares', desc: 'Full Market' },
            { id: 'UNDER_500', label: '₹0 to ₹500', desc: 'Budget & Small/Mid', color: '#059669', bg: '#ECFDF5', border: '#A7F3D0' },
            { id: '500_TO_2000', label: '₹500 to ₹2,000', desc: 'Core & Momentum', color: '#2563EB', bg: '#EFF6FF', border: '#BFDBFE' },
            { id: 'ABOVE_2000', label: '₹2,000 & Above', desc: 'Bluechips & Leaders', color: '#7C3AED', bg: '#F5F3FF', border: '#DDD6FE' }
          ].map((b) => {
            const active = activePriceBracket === b.id;
            return (
              <button
                key={b.id}
                onClick={() => setPriceBracket(b.id)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '4px',
                  border: `1.5px solid ${active ? (b.color || '#171717') : '#D1C7B7'}`,
                  background: active ? (b.id === 'ALL' ? '#171717' : b.bg) : '#FFFDF8',
                  color: active ? (b.id === 'ALL' ? '#FFFDF8' : b.color) : '#413D36',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  textAlign: 'left',
                  boxShadow: active ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                <span style={{ fontSize: '12px', fontWeight: '800' }}>{b.label}</span>
                <span style={{ fontSize: '10px', opacity: 0.8, fontWeight: '500' }}>{b.desc}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Top Filter and Actions Toolbar */}
      <div className="glass-card" style={{ marginBottom: '20px', padding: '16px 20px' }}>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
          {/* Search Box */}
          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', flex: '1', minWidth: '280px', maxWidth: '420px', position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '12px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              className="input-field"
              placeholder="Search companies, tickers, keywords..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: '100%', paddingLeft: '38px' }}
            />
          </form>

          {/* Quick Filter Buttons */}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
            {/* Direction Filter */}
            <div style={{ display: 'flex', gap: '4px', background: 'var(--bg-input)', padding: '3px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              {['ALL', 'UP', 'DOWN', 'NEUTRAL'].map((dir) => (
                <button
                  key={dir}
                  onClick={() => setSelectedDirection(dir)}
                  style={{
                    padding: '4px 10px',
                    fontSize: '0.74rem',
                    fontWeight: '700',
                    border: 'none',
                    borderRadius: '2px',
                    cursor: 'pointer',
                    background: selectedDirection === dir ? '#171717' : 'transparent',
                    color: selectedDirection === dir ? '#FFFDF8' : '#5A403D'
                  }}
                >
                  {dir}
                </button>
              ))}
            </div>

            {/* Impact Filter */}
            <div style={{ display: 'flex', gap: '4px', background: 'var(--bg-input)', padding: '3px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((imp) => (
                <button
                  key={imp}
                  onClick={() => setSelectedImpact(imp)}
                  style={{
                    padding: '4px 10px',
                    fontSize: '0.74rem',
                    fontWeight: '700',
                    border: 'none',
                    borderRadius: '2px',
                    cursor: 'pointer',
                    background: selectedImpact === imp ? '#A71919' : 'transparent',
                    color: selectedImpact === imp ? '#FFFDF8' : '#5A403D'
                  }}
                >
                  {imp}
                </button>
              ))}
            </div>

            {/* Sector Dropdown */}
            <select
              className="input-field"
              value={selectedSector}
              onChange={(e) => setSelectedSector(e.target.value)}
              style={{ fontSize: '0.78rem', padding: '6px 12px' }}
            >
              {SECTORS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            {/* Priority / Sort Selector */}
            <select
              className="input-field"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              style={{ fontSize: '0.78rem', padding: '6px 12px', fontWeight: '700', border: '1px solid #A71919', color: '#A71919' }}
            >
              <option value="priority">⚡ Priority (High Impact First)</option>
              <option value="latest">⏱️ Latest Published Time</option>
              <option value="impact">🎯 Maximum Impact</option>
              <option value="confidence">🧠 Highest Confidence</option>
            </select>

            {/* Live Sync Button */}
            <button
              className="btn btn-primary btn-sm"
              onClick={handleSyncNews}
              disabled={syncing}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <RefreshCw size={13} className={syncing ? 'animate-spin' : ''} />
              <span>{syncing ? 'Ingesting Feeds...' : 'Sync Live'}</span>
            </button>
          </div>
        </div>

        {syncNotice && (
          <div style={{
            marginTop: '12px',
            background: '#ECFDF5',
            border: '1px solid #A7F3D0',
            color: '#065F46',
            padding: '8px 14px',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <span>{syncNotice}</span>
            <span style={{ fontSize: '11px', opacity: 0.8 }}>Sorted by Catalyst Impact</span>
          </div>
        )}

        {/* Quick Indian Market & Factor Filter Pills */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '12px', paddingTop: '10px', borderTop: '1px dashed #C9C1B5', alignItems: 'center' }}>
          <span style={{ fontSize: '0.70rem', fontWeight: '800', color: '#A71919', textTransform: 'uppercase', marginRight: '4px' }}>
            INDIAN CATALYSTS:
          </span>
          {[
            { label: 'All Indian News', query: '', sector: 'All Sectors' },
            { label: 'NIFTY & Sensex', query: 'Nifty', sector: 'All Sectors' },
            { label: 'RBI & Rates', query: 'RBI', sector: 'All Sectors' },
            { label: 'FII / DII Flows', query: 'FII', sector: 'All Sectors' },
            { label: 'Crude & Rupee', query: 'Crude', sector: 'All Sectors' },
            { label: 'Reliance', query: 'Reliance', sector: 'All Sectors' },
            { label: 'TCS & IT', query: 'TCS', sector: 'Information Technology' },
            { label: 'Tata Motors', query: 'Tata Motors', sector: 'Automobile' },
            { label: 'HDFC & Banking', query: 'HDFC', sector: 'Banking & Finance' },
          ].map(pill => {
            const active = searchQuery === pill.query && (pill.sector === 'All Sectors' || selectedSector === pill.sector);
            return (
              <button
                key={pill.label}
                onClick={() => {
                  setSearchQuery(pill.query);
                  setSelectedSector(pill.sector);
                }}
                style={{
                  fontSize: '0.70rem',
                  padding: '3px 8px',
                  borderRadius: '3px',
                  border: '1px solid #D5CFC5',
                  background: active ? '#171717' : '#FFFDF8',
                  color: active ? '#FFFDF8' : '#171717',
                  cursor: 'pointer',
                  fontWeight: active ? '700' : '600'
                }}
              >
                {pill.label}
              </button>
            );
          })}
        </div>

        {/* Status Bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '14px', paddingTop: '12px', borderTop: '1px solid var(--border-color)', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
          <div>
            Showing <span className="font-mono" style={{ color: 'var(--text-primary)', fontWeight: '700' }}>{news.length}</span> of <span className="font-mono" style={{ color: 'var(--text-primary)', fontWeight: '700' }}>{total}</span> analyzed market events
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Zap size={13} color="#f59e0b" />
              <span>Real-Time NLP Pipeline Active</span>
            </span>
          </div>
        </div>
      </div>

      {/* Feed List */}
      {loading ? (
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <div className="pulse-dot" style={{ width: '22px', height: '22px', backgroundColor: '#3b82f6' }}></div>
          <p style={{ marginTop: '16px', color: 'var(--text-secondary)' }}>Analyzing market headlines with NLP...</p>
        </div>
      ) : news.length === 0 ? (
        <div className="glass-card" style={{ padding: '50px', textAlign: 'center' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '1rem', marginBottom: '14px' }}>
            No market events match your selected filters.
          </p>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setSelectedDirection('ALL');
              setSelectedImpact('ALL');
              setSelectedSentiment('ALL');
              setSelectedSector('All Sectors');
              setSearchQuery('');
            }}
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {news.map((item) => {
            const an = item.analysis;
            const isWatchlisted = isTickerWatchlisted(an.ticker);

            return (
              <div
                key={item.id}
                className="glass-card"
                style={{
                  padding: '20px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '14px',
                  borderLeft: `4px solid ${
                    an.direction === 'UP' ? 'var(--bullish)' : (an.direction === 'DOWN' ? 'var(--bearish)' : 'var(--neutral)')
                  }`
                }}
              >
                {/* Card Top Row: Meta info & badges */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span className={`badge ${
                      an.impact_level === 'HIGH' ? 'badge-impact-high' : (an.impact_level === 'MEDIUM' ? 'badge-impact-medium' : 'badge-impact-low')
                    }`}>
                      {an.impact_level} IMPACT
                    </span>
                    <span className="badge-sector">{(an.event_display || an.event_type || '').replace(/_/g,' ')}</span>
                    {an.scope && (
                      <span style={{
                        fontSize: '0.68rem', fontWeight: '700', padding: '2px 7px',
                        borderRadius: '999px', border: '1px solid rgba(167,139,250,0.3)',
                        background: 'rgba(167,139,250,0.08)', color: '#c4b5fd'
                      }}>
                        {an.scope.replace(/_/g,' ')}
                      </span>
                    )}

                    {/* Stock Price & Bracket Tier Badge */}
                    {an.stock_price ? (
                      <span 
                        onClick={() => setPriceBracket(an.price_bracket)}
                        style={{
                          fontSize: '0.72rem',
                          fontWeight: '800',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          background: an.price_bracket_bg || '#ECFDF5',
                          border: `1px solid ${an.price_bracket_border || '#A7F3D0'}`,
                          color: an.price_bracket_color || '#059669',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          cursor: 'pointer'
                        }}
                        title={`Filter by ${an.price_bracket_label} tier`}
                      >
                        <span>₹{Number(an.stock_price).toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 2 })}</span>
                        <span style={{ opacity: 0.8, fontSize: '0.66rem' }}>({an.price_bracket_label})</span>
                      </span>
                    ) : (an.price_bracket_label && (
                      <span style={{
                        fontSize: '0.68rem',
                        fontWeight: '700',
                        padding: '2px 6px',
                        borderRadius: '3px',
                        background: '#F5F5F4',
                        color: '#78716C',
                        border: '1px solid #E7E5E4'
                      }}>
                        {an.price_bracket_label}
                      </span>
                    ))}
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>•</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{item.source}</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>•</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {new Date(item.published_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>

                  {/* Bookmark Button */}
                  <button
                    onClick={() => onAddToWatchlist(an.ticker)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: isWatchlisted ? '#60a5fa' : 'var(--text-muted)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '0.75rem'
                    }}
                    title="Track in Watchlist"
                  >
                    {isWatchlisted ? <BookmarkCheck size={16} /> : <Bookmark size={16} />}
                    <span>{isWatchlisted ? 'Tracked' : 'Watchlist'}</span>
                  </button>
                </div>

                {/* Article Title & Summary */}
                <div>
                  <h3
                    onClick={() => onSelectArticle(item.id)}
                    style={{
                      fontFamily: 'var(--font-serif)',
                      fontSize: '1.25rem',
                      fontWeight: '800',
                      color: '#171717',
                      cursor: 'pointer',
                      lineHeight: '1.35',
                      marginBottom: '6px'
                    }}
                  >
                    {item.title}
                  </h3>
                  {item.summary && (
                    <p style={{ fontSize: '0.86rem', color: '#5A403D', lineHeight: '1.5' }}>
                      {item.summary.length > 220 ? `${item.summary.slice(0, 220)}...` : item.summary}
                    </p>
                  )}
                </div>

                {/* Affected Asset & AI Estimate Bar */}
                <div style={{
                  background: 'var(--bg-primary)',
                  borderRadius: 'var(--radius-md)',
                  padding: '12px 16px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '12px',
                  border: '1px solid var(--border-color)'
                }}>
                  {/* Entity Tag */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <span className="badge-ticker" style={{ fontSize: '0.9rem', padding: '3px 8px' }}>
                      {an.ticker}
                    </span>
                    <div>
                      <span style={{ fontSize: '0.88rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                        {an.company_name}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>
                        {an.sector}
                      </span>
                    </div>
                    {/* Extra entity mentions */}
                    {safeArr(an.all_entities).slice(1,3).map(e => (
                      <span key={e.ticker} style={{
                        fontSize: '0.68rem', padding: '2px 6px', borderRadius: '4px',
                        background: 'rgba(96,165,250,0.07)', border: '1px solid rgba(96,165,250,0.15)',
                        color: '#93c5fd', fontFamily: 'monospace'
                      }}>
                        +{e.ticker}
                      </span>
                    ))}
                  </div>

                  {/* AI Prediction Box */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '18px', flexWrap: 'wrap' }}>
                    {/* Direction */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>DIRECTION:</span>
                      <span className={`badge ${
                        an.direction === 'UP' ? 'badge-bullish' : (an.direction === 'DOWN' ? 'badge-bearish' : 'badge-neutral')
                      }`}>
                        {an.direction === 'UP' && <TrendingUp size={12} />}
                        {an.direction === 'DOWN' && <TrendingDown size={12} />}
                        {an.direction === 'NEUTRAL' && <Minus size={12} />}
                        {an.direction}
                      </span>
                    </div>

                    {/* Confidence */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>CONFIDENCE:</span>
                      <span className="font-mono" style={{ fontSize: '0.85rem', fontWeight: '700', color: '#60a5fa' }}>
                        {an.confidence}%
                      </span>
                    </div>

                    {/* Sentiment */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>SENTIMENT:</span>
                      <span style={{
                        fontSize: '0.82rem',
                        fontWeight: '700',
                        color: an.sentiment === 'Positive' ? 'var(--bullish)' : (an.sentiment === 'Negative' ? 'var(--bearish)' : 'var(--neutral)')
                      }}>
                        {an.sentiment}
                      </span>
                    </div>

                    {/* 3D Horizon Quick Peek */}
                    {an.time_horizons?.['3d'] && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>3D EST:</span>
                        <span className="font-mono" style={{
                          fontSize: '0.85rem',
                          fontWeight: '700',
                          color: an.direction === 'UP' ? 'var(--bullish)' : (an.direction === 'DOWN' ? 'var(--bearish)' : 'var(--neutral)')
                        }}>
                          {an.time_horizons['3d'].projected_change_pct}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Deep Dive Action */}
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => onSelectArticle(item.id)}
                    style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    <span>Full Analysis</span>
                    <ArrowUpRight size={14} />
                  </button>
                </div>

                {/* Mandatory Prediction Surface Disclaimer */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.73rem', color: 'var(--text-muted)', paddingTop: '2px' }}>
                  <span className="pulse-dot" style={{ width: '6px', height: '6px', backgroundColor: '#f59e0b' }}></span>
                  <span style={{ fontWeight: '500' }}>AI/model estimate — not investment advice.</span>
                </div>
              </div>
            );

          })}
        </div>
      )}

      {/* Pagination Bar */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px', marginTop: '28px' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => fetchNews(page - 1)}
            disabled={page <= 1}
          >
            Previous
          </button>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Page <span className="font-mono" style={{ color: 'var(--text-primary)', fontWeight: '700' }}>{page}</span> of <span className="font-mono">{totalPages}</span>
          </span>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => fetchNews(page + 1)}
            disabled={page >= totalPages}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
