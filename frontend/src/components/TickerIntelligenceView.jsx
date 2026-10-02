import React, { useState, useEffect } from 'react';
import { Search, TrendingUp, TrendingDown, Minus, BookmarkPlus, ArrowUpRight, BarChart3, AlertCircle } from 'lucide-react';
import InteractiveChart from './InteractiveChart';
import TradeRecommendationCard from './TradeRecommendationCard';

const POPULAR_TICKERS = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'TATAMOTORS.NS', 'ICICIBANK.NS', 'SBIN.NS', 'ITC.NS', 'BHARTIARTL.NS', 'LT.NS', 'ZOMATO.NS', '^NSEI'];

export default function TickerIntelligenceView({ initialTicker = 'RELIANCE.NS', onSelectArticle, onAddToWatchlist }) {
  const [tickerInput, setTickerInput] = useState(initialTicker);
  const [activeTicker, setActiveTicker] = useState(initialTicker);
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTickerData = (symbol) => {
    setLoading(true);
    setError(null);
    fetch(`/api/tickers/${encodeURIComponent(symbol)}`)
      .then((res) => {
        if (!res.ok) throw new Error('Ticker data not found.');
        return res.json();
      })
      .then((data) => {
        setDetails(data);
        setActiveTicker(symbol);
        setTickerInput(symbol);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Error fetching ticker data.');
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchTickerData(activeTicker);
  }, []);

  // Sync when initialTicker changes from global search bar
  useEffect(() => {
    if (initialTicker && initialTicker !== activeTicker) {
      setTickerInput(initialTicker);
      setActiveTicker(initialTicker);
      fetchTickerData(initialTicker);
    }
  }, [initialTicker]);

  const handleSearch = (e) => {
    e.preventDefault();
    if (tickerInput.trim()) {
      fetchTickerData(tickerInput.trim().toUpperCase());
    }
  };

  const quote = details?.quote;
  const chart = details?.chart || [];
  const relatedNews = details?.related_news || [];
  const sentimentSummary = details?.sentiment_summary;

  const isUp = (quote?.change_pct || 0) >= 0;

  return (
    <div>
      {/* Search & Popular Tickers Bar */}
      <div className="glass-card" style={{ marginBottom: '24px', padding: '18px 20px' }}>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
          <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px', flex: '1', maxWidth: '360px' }}>
            <input
              type="text"
              className="input-field font-mono"
              placeholder="Enter ticker (e.g. AAPL, NVDA, TSLA)..."
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
              style={{ flex: 1 }}
            />
            <button type="submit" className="btn btn-primary btn-sm">
              <Search size={14} />
              <span>Explore</span>
            </button>
          </form>

          {/* Quick Select Buttons */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Quick Select:</span>
            {POPULAR_TICKERS.map((sym) => (
              <button
                key={sym}
                onClick={() => {
                  setTickerInput(sym);
                  fetchTickerData(sym);
                }}
                className="badge-ticker"
                style={{
                  cursor: 'pointer',
                  border: activeTicker === sym ? '1px solid #60a5fa' : '1px solid rgba(59, 130, 246, 0.2)',
                  background: activeTicker === sym ? 'rgba(59, 130, 246, 0.3)' : 'rgba(59, 130, 246, 0.1)'
                }}
              >
                {sym}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <div className="pulse-dot" style={{ width: '22px', height: '22px', backgroundColor: '#3b82f6' }}></div>
          <p style={{ marginTop: '16px', color: 'var(--text-secondary)' }}>Loading intelligence for {activeTicker}...</p>
        </div>
      ) : error ? (
        <div className="glass-card" style={{ padding: '40px', textAlign: 'center' }}>
          <AlertCircle size={32} color="#f43f5e" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-primary)', fontWeight: '700' }}>{error}</p>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
            Please try another ticker symbol like RELIANCE.NS, TCS.NS, INFY.NS, or TATAMOTORS.NS.
          </p>
        </div>
      ) : (
        <div>
          {/* Main Ticker Card */}
          <div className="glass-card" style={{ marginBottom: '24px', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '20px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                  <span className="badge-ticker" style={{ fontSize: '1.25rem', padding: '6px 14px' }}>
                    {quote?.ticker}
                  </span>
                  <h2 style={{ fontSize: '1.4rem', fontWeight: '800' }}>{quote?.company_name}</h2>
                </div>
                <div style={{ display: 'flex', gap: '12px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  <span>Sector: <strong>{quote?.sector}</strong></span>
                  <span>•</span>
                  <span>Free Data Stream via Yahoo Finance</span>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                <div style={{ textAlign: 'right' }}>
                  <div className="font-mono" style={{ fontSize: '1.8rem', fontWeight: '800' }}>
                    ₹{quote?.price ? quote.price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '0.00'}
                  </div>
                  <div
                    className="font-mono"
                    style={{
                      fontSize: '1rem',
                      fontWeight: '700',
                      color: isUp ? 'var(--bullish)' : 'var(--bearish)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'flex-end',
                      gap: '4px'
                    }}
                  >
                    {isUp ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                    {isUp ? '+' : ''}{quote?.change_pct?.toFixed(2)}% ({quote?.change_amount > 0 ? '+' : ''}₹{Math.abs(quote?.change_amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})})
                  </div>
                </div>

                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => onAddToWatchlist(quote.ticker)}
                  style={{ alignSelf: 'center' }}
                >
                  <BookmarkPlus size={14} />
                  <span>Watchlist</span>
                </button>
              </div>
            </div>

            {/* Key Statistics Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', background: 'var(--bg-primary)', padding: '16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', marginBottom: '24px' }}>
              <div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>52W HIGH</span>
                <span className="font-mono" style={{ fontSize: '0.95rem', fontWeight: '700' }}>
                  ₹{quote?.high_52w ? quote.high_52w.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : 'N/A'}
                </span>
              </div>
              <div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>52W LOW</span>
                <span className="font-mono" style={{ fontSize: '0.95rem', fontWeight: '700' }}>
                  ₹{quote?.low_52w ? quote.low_52w.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : 'N/A'}
                </span>
              </div>
              <div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>P/E RATIO</span>
                <span className="font-mono" style={{ fontSize: '0.95rem', fontWeight: '700' }}>{quote?.pe_ratio ? quote.pe_ratio.toFixed(2) : 'N/A'}</span>
              </div>
              <div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>MARKET CAP</span>
                <span className="font-mono" style={{ fontSize: '0.95rem', fontWeight: '700' }}>
                  {quote?.market_cap ? `₹${(quote.market_cap / 1e7).toLocaleString('en-IN', {maximumFractionDigits: 2})} Cr` : 'N/A'}
                </span>
              </div>
              <div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>VOLUME</span>
                <span className="font-mono" style={{ fontSize: '0.95rem', fontWeight: '700' }}>
                  {quote?.volume ? quote.volume.toLocaleString() : 'N/A'}
                </span>
              </div>
            </div>

            {/* Aggregated AI Catalyst Sentiment Bar */}
            {sentimentSummary && (
              <div style={{ background: '#F5F1E8', border: '1px solid #C9C1B5', borderRadius: '4px', padding: '16px', marginBottom: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <div>
                    <span style={{ fontSize: '0.84rem', fontWeight: '800', color: '#171717', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Aggregated Catalyst Sentiment Signal</span>
                    <span style={{ fontSize: '0.75rem', color: '#736B63', marginLeft: '8px' }}>(Analyzed from news volume)</span>
                  </div>
                  <span className={`badge ${
                    sentimentSummary.signal === 'BULLISH' ? 'badge-bullish' : (sentimentSummary.signal === 'BEARISH' ? 'badge-bearish' : 'badge-neutral')
                  }`}>
                    {sentimentSummary.signal}
                  </span>
                </div>

                {/* 3-Part Bar */}
                <div style={{ display: 'flex', width: '100%', height: '10px', borderRadius: '2px', overflow: 'hidden', marginBottom: '8px', border: '1px solid #C9C1B5' }}>
                  <div style={{ width: `${sentimentSummary.bullish_pct}%`, background: 'var(--bullish)' }} title={`Bullish: ${sentimentSummary.bullish_pct}%`}></div>
                  <div style={{ width: `${sentimentSummary.neutral_pct}%`, background: 'var(--neutral)' }} title={`Neutral: ${sentimentSummary.neutral_pct}%`}></div>
                  <div style={{ width: `${sentimentSummary.bearish_pct}%`, background: 'var(--bearish)' }} title={`Bearish: ${sentimentSummary.bearish_pct}%`}></div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#413D36', fontWeight: '600' }}>
                  <span>Bullish: <strong style={{ color: 'var(--bullish)' }}>{sentimentSummary.bullish_pct}%</strong></span>
                  <span>Neutral: <strong style={{ color: 'var(--neutral)' }}>{sentimentSummary.neutral_pct}%</strong></span>
                  <span>Bearish: <strong style={{ color: 'var(--bearish)' }}>{sentimentSummary.bearish_pct}%</strong></span>
                </div>

                <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #C9C1B5', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem', color: '#A71919', fontWeight: '600' }}>
                  <span className="pulse-dot" style={{ width: '6px', height: '6px', backgroundColor: '#A71919' }}></span>
                  <span>AI/model estimate — not investment advice.</span>
                </div>
              </div>
            )}

            {/* Real-Time Buy / Sell / Hold Trade Guidance Card */}
            {quote?.price && (
              <TradeRecommendationCard
                ticker={quote?.ticker}
                companyName={quote?.company_name}
                currentPrice={quote?.price}
                direction={sentimentSummary?.signal === 'BULLISH' ? 'UP' : (sentimentSummary?.signal === 'BEARISH' ? 'DOWN' : 'NEUTRAL')}
                confidence={sentimentSummary?.signal === 'BULLISH' ? Math.max(72, sentimentSummary.bullish_pct || 75) : 74}
                sentimentScore={sentimentSummary ? ((sentimentSummary.bullish_pct - sentimentSummary.bearish_pct) / 100) : 0.4}
                beta={quote?.beta || 1.05}
                dayHigh={quote?.day_high}
                dayLow={quote?.day_low}
              />
            )}

            {/* Interactive Price Chart */}
            <div style={{ background: 'var(--bg-primary)', padding: '18px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <InteractiveChart
                data={chart}
                ticker={quote?.ticker}
                direction={isUp ? 'UP' : 'DOWN'}
              />
            </div>
          </div>

          {/* Related News Catalysts Analyzed for this Stock */}
          <div className="glass-card" style={{ padding: '24px' }}>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', fontWeight: '800', color: '#171717', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '2px solid #171717', paddingBottom: '8px' }}>
              <BarChart3 size={20} color="#A71919" />
              <span>Recent Analyzed Catalysts for {activeTicker}</span>
            </h3>

            {relatedNews.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                No recent specific headlines ingested for {activeTicker} yet. Try syncing news or running a custom analysis.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {relatedNews.map((n) => (
                  <div
                    key={n.id}
                    onClick={() => onSelectArticle(n.id)}
                    style={{
                      background: '#FFFDF8',
                      border: '1px solid #EAE3D7',
                      borderRadius: 'var(--radius-sm)',
                      padding: '14px 18px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                      gap: '14px',
                      transition: 'border-color 0.15s ease'
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span className={`badge ${
                          n.direction === 'UP' ? 'badge-bullish' : (n.direction === 'DOWN' ? 'badge-bearish' : 'badge-neutral')
                        }`}>
                          {n.direction}
                        </span>
                        <span className={`badge ${
                          n.impact_level === 'HIGH' ? 'badge-impact-high' : 'badge-impact-medium'
                        }`}>
                          {n.impact_level}
                        </span>
                        <span style={{ fontSize: '0.74rem', color: '#736B63' }}>{n.source}</span>
                      </div>
                      <h4 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.05rem', fontWeight: '800', color: '#171717' }}>
                        {n.title}
                      </h4>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span className="font-mono" style={{ fontSize: '0.84rem', color: '#60a5fa', fontWeight: '700' }}>
                        {n.confidence}% conf
                      </span>
                      <ArrowUpRight size={16} color="var(--text-secondary)" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
