import React, { useState } from 'react';
import { Bookmark, Trash2, ArrowUpRight, Plus, TrendingUp, TrendingDown } from 'lucide-react';

export default function WatchlistView({ watchlist = [], onRemoveFromWatchlist, onAddToWatchlist, onExploreTicker }) {
  const [newTicker, setNewTicker] = useState('');
  const [notes, setNotes] = useState('');

  const handleAdd = (e) => {
    e.preventDefault();
    if (newTicker.trim()) {
      onAddToWatchlist(newTicker.trim().toUpperCase(), notes);
      setNewTicker('');
      setNotes('');
    }
  };

  return (
    <div>
      {/* Header and Add Form */}
      <div className="glass-card" style={{ marginBottom: '24px', padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
          <Bookmark size={20} color="#60a5fa" />
          <h2 style={{ fontSize: '1.25rem', fontWeight: '800' }}>Portfolio Catalyst Watchlist</h2>
        </div>

        <form onSubmit={handleAdd} style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            type="text"
            className="input-field font-mono"
            placeholder="Add ticker (e.g. NVDA, AAPL)..."
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            style={{ width: '200px' }}
          />
          <input
            type="text"
            className="input-field"
            placeholder="Optional thesis/notes..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            style={{ flex: 1, minWidth: '240px' }}
          />
          <button type="submit" className="btn btn-primary btn-sm">
            <Plus size={14} />
            <span>Add Stock</span>
          </button>
        </form>
      </div>

      {/* Watchlist Cards */}
      {watchlist.length === 0 ? (
        <div className="glass-card" style={{ padding: '60px', textAlign: 'center' }}>
          <Bookmark size={36} color="var(--text-muted)" style={{ margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '8px' }}>Your Watchlist is Empty</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.86rem', marginBottom: '20px' }}>
            Star tickers from news articles or add symbols above to track their live catalyst updates.
          </p>
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap' }}>
            {['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'TATAMOTORS.NS'].map((sym) => (
              <button
                key={sym}
                className="btn btn-secondary btn-sm font-mono"
                onClick={() => onAddToWatchlist(sym)}
              >
                + {sym}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
          {watchlist.map((item) => {
            const quote = item.quote || {};
            const isUp = (quote.change_pct || 0) >= 0;

            return (
              <div key={item.ticker} className="glass-card" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <span className="badge-ticker" style={{ fontSize: '1rem', padding: '4px 10px' }}>
                        {item.ticker}
                      </span>
                      <h4 style={{ fontSize: '1rem', fontWeight: '700' }}>{item.company_name}</h4>
                    </div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Sector: {item.sector}
                    </span>
                  </div>

                  <button
                    onClick={() => onRemoveFromWatchlist(item.ticker)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      padding: '4px'
                    }}
                    title="Remove from watchlist"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>

                {/* Price Row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '14px', background: 'var(--bg-primary)', padding: '12px 14px', borderRadius: 'var(--radius-md)' }}>
                  <div>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>PRICE</span>
                    <span className="font-mono" style={{ fontSize: '1.25rem', fontWeight: '800' }}>
                      ₹{quote.price ? quote.price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '---'}
                    </span>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>24H RETURN</span>
                    <span
                      className="font-mono"
                      style={{
                        fontSize: '1rem',
                        fontWeight: '700',
                        color: isUp ? 'var(--bullish)' : 'var(--bearish)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px'
                      }}
                    >
                      {isUp ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                      {isUp ? '+' : ''}{quote.change_pct ? quote.change_pct.toFixed(2) : '0.00'}%
                    </span>
                  </div>
                </div>

                {item.notes && (
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '14px', fontStyle: 'italic' }}>
                    "{item.notes}"
                  </p>
                )}

                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => onExploreTicker(item.ticker)}
                  style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                >
                  <span>View Ticker Intelligence & News</span>
                  <ArrowUpRight size={14} />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
