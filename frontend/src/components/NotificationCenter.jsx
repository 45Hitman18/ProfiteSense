import React, { useState, useEffect, useRef } from 'react';
import { 
  Bell, Check, CheckCheck, RefreshCw, X, TrendingUp, AlertTriangle, 
  ChevronRight, ShieldCheck, Clock
} from 'lucide-react';

export default function NotificationCenter({ onExploreTicker }) {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState('all'); // 'all' | 'buy' | 'sell' | 'hold' | 'unread'
  const [activePriceFilter, setActivePriceFilter] = useState('all'); // 'all' | '0-500' | '500-1000' | '1000+'
  const popoverRef = useRef(null);

  const fetchNotifications = async (force = false) => {
    if (force) setRefreshing(true);
    else setLoading(true);
    try {
      const url = force ? '/api/notifications?force=true' : '/api/notifications';
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.notifications || []);
        setUnreadCount(data.unread_count || 0);
      }
    } catch (err) {
      console.error('Failed to fetch notifications:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchNotifications();

    // Listen for market data sync events from Dashboard or other views
    const handleMarketSync = () => {
      fetchNotifications(false);
    };
    window.addEventListener('market-data-updated', handleMarketSync);

    // Auto-refresh notifications every 30 seconds
    const timer = setInterval(() => {
      fetchNotifications(false);
    }, 30000);

    return () => {
      clearInterval(timer);
      window.removeEventListener('market-data-updated', handleMarketSync);
    };
  }, []);

  // Auto-refresh whenever the user opens the dropdown
  useEffect(() => {
    if (isOpen) {
      fetchNotifications(false);
    }
  }, [isOpen]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleMarkRead = async (id, e) => {
    if (e) e.stopPropagation();
    try {
      await fetch('/api/notifications/mark-read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
      });
      setNotifications(prev =>
        prev.map(n => (n.id === id ? { ...n, read: true } : n))
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (err) {
      console.error('Failed to mark read:', err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await fetch('/api/notifications/mark-read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ all: true })
      });
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Failed to mark all read:', err);
    }
  };

  const handleCardClick = (notif) => {
    if (!notif.read) {
      handleMarkRead(notif.id);
    }
    if (onExploreTicker && notif.ticker) {
      onExploreTicker(notif.ticker);
      setIsOpen(false);
    }
  };

  const filteredNotifications = notifications.filter(n => {
    // 1. Action Category Filter (Buy / Sell / Hold / Unread)
    if (activeFilter === 'buy' && n.category !== 'buy') return false;
    if (activeFilter === 'sell' && n.category !== 'sell') return false;
    if (activeFilter === 'hold' && n.category !== 'hold') return false;
    if (activeFilter === 'unread' && n.read) return false;

    // 2. Share Price Bracket Filter (0-500, 500-1000, 1000+)
    const price = n.current_price || 0;
    const bracket = n.price_bracket || (price <= 500 ? '0-500' : (price <= 1000 ? '500-1000' : '1000+'));
    if (activePriceFilter === '0-500') {
      return bracket === '0-500' || (price > 0 && price <= 500);
    }
    if (activePriceFilter === '500-1000') {
      return bracket === '500-1000' || (price > 500 && price <= 1000);
    }
    if (activePriceFilter === '1000+') {
      return bracket === '1000+' || price > 1000;
    }

    return true;
  });

  const buyCount = notifications.filter(n => n.category === 'buy').length;
  const sellCount = notifications.filter(n => n.category === 'sell').length;
  const holdCount = notifications.filter(n => n.category === 'hold').length;

  const countUnder500 = notifications.filter(n => {
    const p = n.current_price || 0;
    return n.price_bracket === '0-500' || (p > 0 && p <= 500);
  }).length;
  const count500To1000 = notifications.filter(n => {
    const p = n.current_price || 0;
    return n.price_bracket === '500-1000' || (p > 500 && p <= 1000);
  }).length;
  const countAbove1000 = notifications.filter(n => {
    const p = n.current_price || 0;
    return n.price_bracket === '1000+' || p > 1000;
  }).length;

  return (
    <div style={{ position: 'relative' }} ref={popoverRef}>
      {/* ── BELL TRIGGER BUTTON ── */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '7px',
          padding: '6px 14px',
          background: isOpen ? '#171717' : '#F5F1E8',
          border: '1.5px solid #171717',
          borderRadius: '4px',
          cursor: 'pointer',
          color: isOpen ? '#FFFDF8' : '#171717',
          fontSize: '11px',
          fontWeight: '800',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          position: 'relative',
          transition: 'all 0.15s ease',
          boxShadow: isOpen ? '0 2px 6px rgba(0,0,0,0.15)' : 'none'
        }}
        title="Live Market Trade Advice & Signals"
        aria-label="Market Notifications"
      >
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Bell size={15} color={isOpen ? '#FFFDF8' : (unreadCount > 0 ? '#A71919' : '#171717')} />
          {unreadCount > 0 && (
            <span style={{
              position: 'absolute',
              top: '-7px',
              right: '-9px',
              background: '#A71919',
              color: '#FFFDF8',
              fontSize: '9px',
              fontWeight: '900',
              padding: '1px 5px',
              borderRadius: '10px',
              minWidth: '15px',
              textAlign: 'center',
              lineHeight: '1.2',
              boxShadow: '0 1px 4px rgba(167, 25, 25, 0.45)',
            }}>
              {unreadCount}
            </span>
          )}
        </div>
        <span>Signals</span>
      </button>

      {/* ── NOTIFICATIONS DROPDOWN POPOVER ── */}
      {isOpen && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 8px)',
          right: 0,
          width: '500px',
          maxWidth: 'min(500px, calc(100vw - 20px))',
          maxHeight: 'min(700px, 86vh)',
          background: 'var(--bg-card, #FFFDF8)',
          border: '2px solid #171717',
          borderRadius: '6px',
          boxShadow: '0 20px 48px -8px rgba(0, 0, 0, 0.28), 0 0 0 1px #171717',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'toastSlideIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        }}>
          
          {/* 1. UNIFIED PINNED HEADER & FILTER CONTROLS */}
          <div style={{
            flexShrink: 0,
            background: '#F5F1E8',
            borderBottom: '1.5px solid #171717',
            zIndex: 10,
            position: 'relative',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)'
          }}>
            {/* Top Row: Title + Live Badge + Header Actions */}
            <div style={{
              padding: '12px 16px 8px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '12px'
            }}>
              {/* Title & Live Feed Badge */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                <div style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '4px',
                  background: '#A7191915',
                  border: '1px solid #A7191940',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  <Bell size={15} color="#A71919" />
                </div>
                <div>
                  <div style={{
                    fontFamily: 'var(--font-serif, "Playfair Display", Georgia, serif)',
                    fontSize: '1.02rem',
                    fontWeight: '900',
                    color: '#171717',
                    letterSpacing: '-0.01em',
                    lineHeight: '1.2'
                  }}>
                    Live Market Signals
                  </div>
                </div>
              </div>

              {/* Action Buttons: Sync, Read All, Close */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                <button
                  onClick={() => fetchNotifications(true)}
                  disabled={refreshing}
                  title="Force refresh live market signals"
                  style={{
                    background: '#FFFDF8',
                    border: '1px solid #C9C1B5',
                    borderRadius: '4px',
                    padding: '4px 9px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '0.72rem',
                    fontWeight: '700',
                    color: '#171717',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#EAE4D6'}
                  onMouseLeave={(e) => e.currentTarget.style.background = '#FFFDF8'}
                >
                  <RefreshCw size={11} className={refreshing ? 'spin' : ''} />
                  <span>{refreshing ? 'Syncing...' : 'Sync'}</span>
                </button>

                {unreadCount > 0 && (
                  <button
                    onClick={handleMarkAllRead}
                    title="Mark all signals as read"
                    style={{
                      background: '#FFFDF8',
                      border: '1px solid #C9C1B5',
                      borderRadius: '4px',
                      padding: '4px 9px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '0.72rem',
                      fontWeight: '700',
                      color: '#171717',
                      transition: 'all 0.15s ease'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = '#EAE4D6'}
                    onMouseLeave={(e) => e.currentTarget.style.background = '#FFFDF8'}
                  >
                    <CheckCheck size={12} color="#006D42" />
                    <span>Read All</span>
                  </button>
                )}

                <button
                  onClick={() => setIsOpen(false)}
                  style={{
                    background: 'transparent',
                    border: '1px solid transparent',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    color: '#736B63',
                    padding: '3px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = '#EAE4D6';
                    e.currentTarget.style.color = '#171717';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = '#736B63';
                  }}
                  title="Close signals window"
                >
                  <X size={17} />
                </button>
              </div>
            </div>

            {/* Subtitle Status Strip */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.68rem',
              color: '#736B63',
              padding: '0 16px 8px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <span style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: '#006D42',
                  display: 'inline-block',
                  boxShadow: '0 0 0 2px rgba(0, 109, 66, 0.2)'
                }} />
                <span style={{ fontWeight: '800', color: '#006D42', letterSpacing: '0.04em' }}>AUTO-SYNC ACTIVE</span>
                <span>• NSE/BSE ML Models</span>
              </div>
              <span style={{ fontWeight: '600' }}>{notifications.length} Signals</span>
            </div>

            {/* Filter Pills Bar: Vertically Centered, Immune to Clipping */}
            <div style={{
              padding: '6px 14px 10px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              overflowX: 'auto',
              overflowY: 'hidden',
              whiteSpace: 'nowrap',
              scrollbarWidth: 'none',
              boxSizing: 'border-box'
            }}>
              {/* Action Filter Pills Bar */}
              {[
                { id: 'all', label: `All (${notifications.length})`, dot: null },
                { id: 'buy', label: `Buy (${buyCount})`, dot: '#006D42' },
                { id: 'hold', label: `Hold (${holdCount})`, dot: '#736B63' },
                { id: 'sell', label: `Don't Hold (${sellCount})`, dot: '#A71919' },
                { id: 'unread', label: `Unread (${unreadCount})`, dot: unreadCount > 0 ? '#A71919' : null }
              ].map((f) => {
                const isActive = activeFilter === f.id;
                return (
                  <button
                    key={f.id}
                    onClick={() => setActiveFilter(f.id)}
                    style={{
                      height: '27px',
                      boxSizing: 'border-box',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '5px',
                      padding: '0 11px',
                      borderRadius: '14px',
                      border: isActive ? '1.5px solid #171717' : '1px solid #C9C1B5',
                      background: isActive ? '#171717' : '#FFFDF8',
                      color: isActive ? '#FFFDF8' : '#3D3833',
                      fontSize: '0.72rem',
                      fontWeight: isActive ? '800' : '600',
                      cursor: 'pointer',
                      transition: 'all 0.12s ease',
                      flexShrink: 0,
                      outline: 'none',
                      boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.2)' : 'none'
                    }}
                  >
                    {f.dot && (
                      <span style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        background: isActive ? '#FFFDF8' : f.dot,
                        flexShrink: 0,
                        display: 'inline-block'
                      }} />
                    )}
                    <span>{f.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Share Price Filter Row: 0-500, 500-1000, 1000+ */}
            <div style={{
              padding: '0 14px 10px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              overflowX: 'auto',
              scrollbarWidth: 'none',
              boxSizing: 'border-box',
              borderTop: '1px dashed #DDD7CE',
              paddingTop: '7px'
            }}>
              <span style={{
                fontSize: '0.67rem',
                fontWeight: '800',
                color: '#736B63',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                marginRight: '2px',
                flexShrink: 0
              }}>
                Price:
              </span>
              {[
                { id: 'all', label: `All Prices (${notifications.length})`, color: null },
                { id: '0-500', label: `₹0 – ₹500 (${countUnder500})`, color: '#059669' },
                { id: '500-1000', label: `₹500 – ₹1,000 (${count500To1000})`, color: '#2563EB' },
                { id: '1000+', label: `₹1,000+ (${countAbove1000})`, color: '#7C3AED' },
              ].map((p) => {
                const isActive = activePriceFilter === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => setActivePriceFilter(p.id)}
                    style={{
                      height: '24px',
                      boxSizing: 'border-box',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '0 9px',
                      borderRadius: '12px',
                      border: isActive ? '1.5px solid #171717' : '1px solid #D5CFC5',
                      background: isActive ? '#171717' : '#FFFDF8',
                      color: isActive ? '#FFFDF8' : '#413D36',
                      fontSize: '0.69rem',
                      fontWeight: isActive ? '800' : '600',
                      cursor: 'pointer',
                      flexShrink: 0,
                      transition: 'all 0.12s ease',
                      outline: 'none',
                    }}
                  >
                    {p.color && (
                      <span style={{
                        width: '5px',
                        height: '5px',
                        borderRadius: '50%',
                        background: isActive ? '#FFFDF8' : p.color,
                        display: 'inline-block',
                      }} />
                    )}
                    <span>{p.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 2. SCROLLABLE NOTIFICATIONS FEED */}
          <div style={{
            overflowY: 'auto',
            overflowX: 'hidden',
            flex: 1,
            minHeight: 0,
            padding: '12px 14px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            background: 'var(--bg-primary, #FAF7F0)',
            scrollPaddingTop: '8px'
          }}>
            {loading && notifications.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 16px', color: '#736B63', fontSize: '0.82rem' }}>
                <RefreshCw size={24} className="spin" style={{ margin: '0 auto 10px', display: 'block', color: '#A71919' }} />
                <span>Scanning live market feeds & running trained ML models...</span>
              </div>
            ) : filteredNotifications.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 16px', color: '#736B63', fontSize: '0.82rem' }}>
                <Check size={26} style={{ margin: '0 auto 8px', display: 'block', color: '#006D42' }} />
                <span>No {activeFilter !== 'all' ? activeFilter : ''} signals found at this moment.</span>
              </div>
            ) : (
              filteredNotifications.map((notif) => {
                const isBuy = notif.category === 'buy';
                const isSell = notif.category === 'sell';

                const cardBorder = isBuy
                  ? '#006D4235'
                  : isSell
                  ? '#A7191935'
                  : '#C9C1B5';

                const accentColor = isBuy
                  ? '#006D42'
                  : isSell
                  ? '#A71919'
                  : '#736B63';

                const badgeBg = isBuy
                  ? '#006D4212'
                  : isSell
                  ? '#A7191912'
                  : '#736B6312';

                // Clean ticker string
                const cleanTicker = (notif.ticker || '').trim().replace(/\s+/g, '');

                return (
                  <div
                    key={notif.id}
                    onClick={() => handleCardClick(notif)}
                    style={{
                      flexShrink: 0,
                      boxSizing: 'border-box',
                      width: '100%',
                      background: notif.read ? '#FFFDF8' : '#FFFFFE',
                      border: `1px solid ${cardBorder}`,
                      borderLeft: `4px solid ${accentColor}`,
                      borderRadius: '6px',
                      padding: '12px 14px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      boxShadow: notif.read ? '0 1px 3px rgba(0,0,0,0.04)' : '0 2px 8px rgba(0,0,0,0.08)',
                      position: 'relative',
                      overflow: 'hidden'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#F7F3E9';
                      e.currentTarget.style.transform = 'translateY(-1px)';
                      e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = notif.read ? '#FFFDF8' : '#FFFFFE';
                      e.currentTarget.style.transform = 'none';
                      e.currentTarget.style.boxShadow = notif.read ? '0 1px 3px rgba(0,0,0,0.04)' : '0 2px 8px rgba(0,0,0,0.08)';
                    }}
                  >
                    {/* Unread indicator dot */}
                    {!notif.read && (
                      <span
                        title="Unread signal"
                        style={{
                          position: 'absolute',
                          top: '12px',
                          right: '12px',
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          background: '#A71919',
                          boxShadow: '0 0 0 3px rgba(167, 25, 25, 0.2)'
                        }}
                      />
                    )}

                    {/* Card Top Strip: Ticker, Badge, Time */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '7px',
                      paddingRight: notif.read ? '0' : '16px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span style={{
                          fontFamily: 'monospace',
                          fontWeight: '800',
                          fontSize: '0.80rem',
                          color: '#171717',
                          background: '#EAE5D9',
                          padding: '2px 7px',
                          borderRadius: '3px',
                          border: '1px solid #D5CEBE',
                          letterSpacing: '0.02em'
                        }}>
                          {cleanTicker}
                        </span>

                        <span style={{
                          fontSize: '0.68rem',
                          fontWeight: '800',
                          padding: '2px 8px',
                          borderRadius: '3px',
                          background: badgeBg,
                          color: accentColor,
                          border: `1px solid ${accentColor}35`,
                          textTransform: 'uppercase',
                          letterSpacing: '0.04em'
                        }}>
                          {notif.badge}
                        </span>

                        {/* Price Bracket Badge */}
                        <span style={{
                          fontSize: '0.66rem',
                          fontWeight: '700',
                          padding: '2px 6px',
                          borderRadius: '3px',
                          background: '#F0ECE1',
                          color: '#413D36',
                          border: '1px solid #DDD7CE',
                          letterSpacing: '0.02em'
                        }}>
                          {notif.price_bracket_label || (notif.current_price <= 500 ? '₹0–₹500' : (notif.current_price <= 1000 ? '₹500–₹1,000' : '₹1,000+'))}
                        </span>

                        <span style={{ fontSize: '0.70rem', color: '#736B63', display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                          <Clock size={10} />
                          {notif.time_ago}
                        </span>
                      </div>
                    </div>

                    {/* Main Headline */}
                    <div style={{
                      fontWeight: '800',
                      fontSize: '0.88rem',
                      color: isBuy ? '#006D42' : (isSell ? '#A71919' : '#171717'),
                      marginBottom: '4px',
                      lineHeight: '1.3'
                    }}>
                      {notif.headline}
                    </div>

                    {/* News Context Headline */}
                    {notif.news_title && (
                      <div style={{
                        fontSize: '0.74rem',
                        color: '#655F56',
                        marginBottom: '8px',
                        lineHeight: '1.4',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        fontStyle: 'italic'
                      }}>
                        "{notif.news_title}"
                      </div>
                    )}

                    {/* Actionable Advice Box */}
                    <div style={{
                      padding: '8px 10px',
                      background: isBuy ? '#006D420a' : (isSell ? '#A719190a' : '#F5F1E8'),
                      borderLeft: `3px solid ${accentColor}`,
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      color: '#171717',
                      lineHeight: '1.45',
                      marginBottom: '8px',
                      border: `1px solid ${cardBorder}`
                    }}>
                      {notif.advice}
                    </div>

                    {/* Institutional 4-Column Execution Matrix */}
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(4, 1fr)',
                      gap: '6px',
                      padding: '8px 10px',
                      background: '#F5F1E8',
                      borderRadius: '4px',
                      border: '1px solid #E2DCCF',
                      marginBottom: '8px'
                    }}>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '0.60rem', color: '#736B63', textTransform: 'uppercase', fontWeight: '800', letterSpacing: '0.04em' }}>
                          LTP / Price
                        </span>
                        <span style={{ fontSize: '0.82rem', fontWeight: '800', color: '#171717' }}>
                          ₹{notif.current_price > 0 ? notif.current_price.toFixed(1) : '—'}
                        </span>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '0.60rem', color: '#736B63', textTransform: 'uppercase', fontWeight: '800', letterSpacing: '0.04em' }}>
                          Target (T1)
                        </span>
                        <span style={{ fontSize: '0.82rem', fontWeight: '800', color: notif.target_pct >= 0 ? '#006D42' : '#A71919' }}>
                          ₹{notif.target_price ? notif.target_price.toFixed(1) : '—'}
                          {notif.target_pct !== undefined && notif.target_pct !== null && (
                            <small style={{ fontSize: '0.66rem', marginLeft: '3px' }}>
                              ({notif.target_pct >= 0 ? '+' : ''}{notif.target_pct.toFixed(1)}%)
                            </small>
                          )}
                        </span>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '0.60rem', color: '#736B63', textTransform: 'uppercase', fontWeight: '800', letterSpacing: '0.04em' }}>
                          Stop Loss
                        </span>
                        <span style={{ fontSize: '0.82rem', fontWeight: '800', color: '#A71919' }}>
                          ₹{notif.stop_loss ? notif.stop_loss.toFixed(1) : '—'}
                        </span>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '0.60rem', color: '#736B63', textTransform: 'uppercase', fontWeight: '800', letterSpacing: '0.04em' }}>
                          RSI / R:R
                        </span>
                        <span style={{ fontSize: '0.76rem', fontWeight: '700', color: '#4A453E', whiteSpace: 'nowrap' }}>
                          {notif.rsi ? `${notif.rsi.toFixed(0)} RSI` : '—'} • {notif.risk_reward || '1:1.5'}
                        </span>
                      </div>
                    </div>

                    {/* Bottom Metadata & Action Link */}
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.70rem',
                      paddingTop: '2px',
                      color: '#736B63',
                      flexWrap: 'wrap',
                      gap: '6px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <span style={{
                          fontSize: '0.64rem',
                          fontWeight: '800',
                          background: notif.ml_signal_1d === 'Positive' ? '#006D4215' : (notif.ml_signal_1d === 'Negative' ? '#A7191915' : '#736B6315'),
                          color: notif.ml_signal_1d === 'Positive' ? '#006D42' : (notif.ml_signal_1d === 'Negative' ? '#A71919' : '#736B63'),
                          padding: '1px 6px',
                          borderRadius: '3px',
                          border: `1px solid ${notif.ml_signal_1d === 'Positive' ? '#006D4230' : (notif.ml_signal_1d === 'Negative' ? '#A7191930' : '#736B6330')}`,
                        }}>
                          1D: {notif.ml_signal_1d}
                        </span>

                        <span style={{
                          fontSize: '0.64rem',
                          fontWeight: '800',
                          background: notif.ml_signal_3d === 'Positive' ? '#006D4215' : (notif.ml_signal_3d === 'Negative' ? '#A7191915' : '#736B6315'),
                          color: notif.ml_signal_3d === 'Positive' ? '#006D42' : (notif.ml_signal_3d === 'Negative' ? '#A71919' : '#736B63'),
                          padding: '1px 6px',
                          borderRadius: '3px',
                          border: `1px solid ${notif.ml_signal_3d === 'Positive' ? '#006D4230' : (notif.ml_signal_3d === 'Negative' ? '#A7191930' : '#736B6330')}`,
                        }}>
                          3D: {notif.ml_signal_3d}
                        </span>

                        <span style={{ fontSize: '0.66rem', color: '#736B63', fontWeight: '600' }}>
                          Conf: {notif.confidence}%
                        </span>
                      </div>

                      <div style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '2px',
                        color: '#A71919',
                        fontWeight: '800',
                        fontSize: '0.72rem',
                        letterSpacing: '0.02em',
                        textTransform: 'uppercase'
                      }}>
                        <span>Explore Stock</span>
                        <ChevronRight size={13} />
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* 3. PINNED BROADSHEET FOOTER */}
          <div style={{
            flexShrink: 0,
            padding: '9px 14px',
            background: '#F5F1E8',
            borderTop: '1px solid #D5CEBE',
            fontSize: '0.68rem',
            color: '#736B63',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            zIndex: 10
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ShieldCheck size={13} color="#006D42" />
              <span>Real Live Market Feeds • Non-Advisory Research</span>
            </div>
            <span style={{ fontWeight: '700' }}>SEBI Analytics</span>
          </div>

        </div>
      )}
    </div>
  );
}
