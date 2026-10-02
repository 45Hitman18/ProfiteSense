import React, { useState, useEffect, useRef } from 'react';
import { Search, X, TrendingUp, TrendingDown, Minus, ArrowRight, CornerDownLeft } from 'lucide-react';

export default function StockSearchBar({ onSelectStock }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  // Debounced search query (250ms)
  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/stocks/search?q=${encodeURIComponent(trimmed)}&limit=7`);
        const data = await res.json();
        setSuggestions(data.results || []);
        setIsOpen(true);
        setSelectedIndex(-1);
      } catch (err) {
        console.error('Search fetch error:', err);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query]);

  // Click outside listener
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (stock) => {
    if (!stock) return;
    setIsOpen(false);
    setQuery('');
    setSelectedIndex(-1);
    if (onSelectStock) {
      onSelectStock(stock.ticker);
    }
  };

  const handleKeyDown = (e) => {
    if (!isOpen && e.key === 'ArrowDown' && suggestions.length > 0) {
      setIsOpen(true);
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
        handleSelect(suggestions[selectedIndex]);
      } else if (suggestions.length > 0) {
        handleSelect(suggestions[0]);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      setSelectedIndex(-1);
    }
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', maxWidth: '460px' }}>
      {/* Input Field */}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        <Search
          size={16}
          color="var(--text-muted)"
          style={{ position: 'absolute', left: '12px', pointerEvents: 'none', zIndex: 1 }}
        />
        <input
          ref={inputRef}
          type="text"
          className="input-field"
          placeholder="Search Indian stocks (TCS, Reliance, HDFC)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => { if (suggestions.length > 0) setIsOpen(true); }}
          onKeyDown={handleKeyDown}
          style={{
            width: '100%',
            paddingLeft: '38px',
            paddingRight: query ? '34px' : '14px',
            paddingTop: '7px',
            paddingBottom: '7px',
            fontSize: '0.84rem',
            background: '#FFFDF8',
            color: '#171717',
            borderColor: isOpen ? '#171717' : '#C9C1B5',
            borderRadius: isOpen ? '4px 4px 0 0' : '4px',
            transition: 'border-color 0.15s ease',
          }}
        />
        {query && (
          <button
            type="button"
            onClick={() => { setQuery(''); setSuggestions([]); setIsOpen(false); inputRef.current?.focus(); }}
            style={{
              position: 'absolute',
              right: '10px',
              background: 'none',
              border: 'none',
              color: '#736B63',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              padding: '2px',
            }}
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* Autocomplete Dropdown */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            background: '#FFFDF8',
            border: '2px solid #171717',
            borderTop: 'none',
            borderRadius: '0 0 6px 6px',
            boxShadow: '0 12px 28px rgba(0, 0, 0, 0.18)',
            zIndex: 1000,
            overflow: 'hidden',
            maxHeight: '440px',
          }}
        >
          {/* Loading Skeleton */}
          {loading && (
            <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[1, 2, 3].map((n) => (
                <div
                  key={n}
                  style={{
                    height: '42px',
                    borderRadius: '4px',
                    background: '#F0EDED',
                  }}
                />
              ))}
            </div>
          )}

          {/* Suggestions List */}
          {!loading && suggestions.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <div
                style={{
                  padding: '6px 14px',
                  fontSize: '0.68rem',
                  fontWeight: '700',
                  color: '#5A403D',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  background: '#F5F1E8',
                  borderBottom: '1px solid #C9C1B5',
                  display: 'flex',
                  justifyContent: 'space-between',
                }}
              >
                <span>Matching Indian Stocks (NSE/BSE)</span>
                <span>Live Quote (INR ₹)</span>
              </div>

              {suggestions.map((stock, idx) => {
                const isSelected = idx === selectedIndex;
                const isUp = stock.change_pct > 0;
                const isDown = stock.change_pct < 0;
                const changeColor = isUp ? '#006D42' : isDown ? '#B42318' : '#59544C';

                return (
                  <div
                    key={stock.ticker}
                    onClick={() => handleSelect(stock)}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    style={{
                      padding: '10px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                      background: isSelected ? '#F0EDED' : '#FFFDF8',
                      borderLeft: isSelected ? '3px solid #A71919' : '3px solid transparent',
                      borderBottom: '1px solid #EAE3D7',
                      transition: 'background 0.12s ease',
                    }}
                  >
                    {/* Left: Ticker, Name, Sector */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          className="font-mono"
                          style={{
                            fontWeight: '800',
                            fontSize: '0.86rem',
                            color: '#171717',
                            letterSpacing: '0.02em',
                          }}
                        >
                          {stock.symbol}
                        </span>
                        <span
                          style={{
                            fontSize: '0.64rem',
                            padding: '1px 6px',
                            borderRadius: '2px',
                            background: '#F0EDED',
                            border: '1px solid #C9C1B5',
                            color: '#5A403D',
                            fontWeight: '700',
                          }}
                        >
                          {stock.is_index ? 'INDEX' : 'NSE'}
                        </span>
                        {stock.sector && (
                          <span
                            style={{
                              fontSize: '0.68rem',
                              color: '#736B63',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              maxWidth: '160px',
                            }}
                          >
                            • {stock.sector}
                          </span>
                        )}
                      </div>
                      <div
                        style={{
                          fontSize: '0.74rem',
                          color: '#5A403D',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          maxWidth: '260px',
                        }}
                      >
                        {stock.name}
                      </div>
                    </div>

                    {/* Right: Live Price & Day Change */}
                    <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                      <div
                        className="font-mono"
                        style={{
                          fontWeight: '800',
                          fontSize: '0.90rem',
                          color: '#171717',
                        }}
                      >
                        {stock.formatted_price}
                      </div>
                      <div
                        style={{
                          fontSize: '0.72rem',
                          fontWeight: '700',
                          color: changeColor,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px',
                        }}
                      >
                        {isUp && <TrendingUp size={12} />}
                        {isDown && <TrendingDown size={12} />}
                        {!isUp && !isDown && <Minus size={12} />}
                        <span>{stock.formatted_change}</span>
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Keyboard Navigation Tip */}
              <div
                style={{
                  padding: '6px 14px',
                  background: '#F5F1E8',
                  borderTop: '1px solid #C9C1B5',
                  fontSize: '0.65rem',
                  color: '#736B63',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span>Navigate: ↑ ↓ • Select: <CornerDownLeft size={10} style={{ display: 'inline', verticalAlign: 'middle' }} /> Enter • Dismiss: Esc</span>
                <span style={{ color: '#A71919', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '2px' }}>
                  Explore full chart & news <ArrowRight size={10} />
                </span>
              </div>
            </div>
          )}

          {/* Empty State */}
          {!loading && suggestions.length === 0 && query.trim() && (
            <div style={{ padding: '24px 16px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
                No matching Indian stocks found for "{query}"
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Try searching by NSE symbol (e.g. <code>TCS</code>, <code>RELIANCE</code>, <code>INFY</code>) or company name (e.g. <code>Tata Motors</code>, <code>HDFC</code>).
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
