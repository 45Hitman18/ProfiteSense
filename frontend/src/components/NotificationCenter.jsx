import React, { useState, useEffect, useRef } from 'react';
import { 
  Bell, Check, CheckCheck, RefreshCw, X, TrendingUp, AlertTriangle, 
  ExternalLink, ChevronRight, ShieldCheck, Sparkles, Filter, Clock
} from 'lucide-react';

export default function NotificationCenter({ onExploreTicker }) {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState('all'); // 'all' | 'buy' | 'sell' | 'hold' | 'unread'
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
    // Auto-refresh notifications every 60 seconds
    const timer = setInterval(() => {
      fetchNotifications(false);
    }, 60000);
    return () => clearInterval(timer);
  }, []);

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
    if (activeFilter === 'buy') return n.category === 'buy';
    if (activeFilter === 'sell') return n.category === 'sell';
    if (activeFilter === 'hold') return n.category === 'hold';
    if (activeFilter === 'unread') return !n.read;
    return true;
  });

  const buyCount = notifications.filter(n => n.category === 'buy').length;
  const sellCount = notifications.filter(n => n.category === 'sell').length;

  return (
    <div style={{ position: 'relative' }} ref={popoverRef}>
      {/* BELL TRIGGER BUTTON */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '6px 12px',
          background: isOpen ? 'var(--bg-card)' : 'transparent',
          border: isOpen ? '1px solid var(--border-color)' : '1px solid #C9C1B5',
          borderRadius: '4px',
          cursor: 'pointer',
          color: 'var(--text-primary)',
          fontSize: '11px',
          fontWeight: '700',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          position: 'relative',
          transition: 'all 0.15s ease'
        }}
        title="Live Market Trade Advice & Signals"
        aria-label="Market Notifications"
      >
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Bell size={15} color={unreadCount > 0 ? '#A71919' : 'currentColor'} />
          {unreadCount > 0 && (
            <span style={{
              position: 'absolute',
              top: '-6px',
              right: '-8px',
              background: '#A71919',
              color: '#FFFDF8',
              fontSize: '9px',
              fontWeight: '900',
              padding: '1px 5px',
              borderRadius: '10px',
              minWidth: '15px',
              textAlign: 'center',
              lineHeight: '1.2',
              boxShadow: '0 1px 3px rgba(167, 25, 25, 0.4)',
              animation: 'pulse 2s infinite'
            }}>
              {unreadCount}
            </span>
          )}
        </div>
        <span style={{ marginLeft: unreadCount > 0 ? '4px' : '0' }}>Signals</span>
      </button>

      {/* NOTIFICATIONS DROPDOWN POPOVER */}
      {isOpen && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 8px)',
          right: 0,
          width: '460px',
          maxWidth: '92vw',
          maxHeight: '620px',
          background: 'var(--bg-card)',
          border: '2px solid #171717',
          borderRadius: '8px',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.25)',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'toastSlideIn 0.2s ease',
        }}>
          {/* Popover Header */}
          <div style={{
            padding: '14px 16px',
            background: 'var(--bg-secondary)',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '8px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Bell size={18} color="#A71919" />
              <div>
                <div style={{ fontSize: '0.92rem', fontWeight: '800', color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
                  Live Market Signals & Advice
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  Trained ML Models • Technical Trade Levels • Real Live News
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                onClick={() => fetchNotifications(true)}
                disabled={refreshing}
                title="Force refresh live market signals"
                style={{
                  background: 'none',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px',
                  padding: '4px 8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '0.7rem',
                  fontWeight: '600',
                  color: 'var(--text-secondary)'
                }}
              >
                <RefreshCw size={12} className={refreshing ? 'spin' : ''} />
                {refreshing ? 'Syncing...' : 'Refresh'}
              </button>

              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  title="Mark all signals as read"
                  style={{
                    background: 'none',
                    border: '1px solid var(--border-color)',
                    borderRadius: '4px',
                    padding: '4px 8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '0.7rem',
                    fontWeight: '600',
                    color: 'var(--text-secondary)'
                  }}
                >
                  <CheckCheck size={12} />
                  Read All
                </button>
              )}

              <button
                onClick={() => setIsOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--text-muted)',
                  padding: '2px',
                  display: 'flex'
                }}
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Filter Pills */}
          <div style={{
            display: 'flex',
            gap: '6px',
            padding: '8px 12px',
            background: 'var(--bg-primary)',
            borderBottom: '1px solid var(--border-light)',
            overflowX: 'auto',
            whiteSpace: 'nowrap'
          }}>
            {[
              { id: 'all', label: `All (${notifications.length})` },
              { id: 'buy', label: `🟢 Buy (${buyCount})` },
              { id: 'sell', label: `🔴 Don't Hold (${sellCount})` },
              { id: 'unread', label: `Unread (${unreadCount})` }
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setActiveFilter(f.id)}
                style={{
                  padding: '4px 10px',
                  borderRadius: '12px',
                  border: activeFilter === f.id ? '1px solid var(--text-primary)' : '1px solid var(--border-color)',
                  background: activeFilter === f.id ? 'var(--text-primary)' : 'var(--bg-card)',
                  color: activeFilter === f.id ? '#fff' : 'var(--text-secondary)',
                  fontSize: '0.72rem',
                  fontWeight: activeFilter === f.id ? '700' : '500',
                  cursor: 'pointer',
                  transition: 'all 0.1s ease'
                }}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Notifications Scrollable List */}
          <div style={{
            overflowY: 'auto',
            flex: 1,
            maxHeight: '440px',
            padding: '8px 12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}>
            {loading && notifications.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '36px 12px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                <RefreshCw size={24} className="spin" style={{ margin: '0 auto 8px', display: 'block', color: 'var(--accent-red)' }} />
                Scanning live market feeds & running trained ML models...
              </div>
            ) : filteredNotifications.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '36px 12px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                <Check size={24} style={{ margin: '0 auto 8px', display: 'block', color: 'var(--bullish)' }} />
                No {activeFilter !== 'all' ? activeFilter : ''} signals found at this moment.
              </div>
            ) : (
              filteredNotifications.map((notif) => {
                const isBuy = notif.category === 'buy';
                const isSell = notif.category === 'sell';

                const cardBorder = isBuy
                  ? 'rgba(0, 109, 66, 0.35)'
                  : isSell
                  ? 'rgba(180, 35, 24, 0.35)'
                  : 'var(--border-color)';

                const badgeBg = isBuy
                  ? 'var(--bullish-bg)'
                  : isSell
                  ? 'var(--bearish-bg)'
                  : 'rgba(89, 84, 76, 0.08)';

                const badgeColor = isBuy
                  ? 'var(--bullish)'
                  : isSell
                  ? 'var(--bearish)'
                  : 'var(--neutral)';

                return (
                  <div
                    key={notif.id}
                    onClick={() => handleCardClick(notif)}
                    style={{
                      background: notif.read ? 'var(--bg-card)' : 'rgba(255, 255, 255, 0.95)',
                      border: `1px solid ${cardBorder}`,
                      borderRadius: '8px',
                      padding: '12px 14px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      boxShadow: notif.read ? 'none' : '0 2px 6px rgba(0,0,0,0.06)',
                      position: 'relative'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'var(--bg-card-hover)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = notif.read ? 'var(--bg-card)' : 'rgba(255, 255, 255, 0.95)';
                    }}
                  >
                    {/* Unread indicator dot */}
                    {!notif.read && (
                      <span style={{
                        position: 'absolute',
                        top: '12px',
                        right: '12px',
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        background: '#A71919'
                      }} />
                    )}

                    {/* Card Top Strip */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px', paddingRight: notif.read ? '0' : '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span style={{
                          fontFamily: 'monospace',
                          fontWeight: '800',
                          fontSize: '0.82rem',
                          color: 'var(--text-primary)',
                          background: 'var(--bg-secondary)',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          border: '1px solid var(--border-light)'
                        }}>
                          {notif.ticker}
                        </span>

                        <span style={{
                          fontSize: '0.68rem',
                          fontWeight: '800',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          background: badgeBg,
                          color: badgeColor,
                          border: `1px solid ${badgeColor}40`,
                          textTransform: 'uppercase',
                          letterSpacing: '0.04em'
                        }}>
                          {notif.badge}
                        </span>

                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          • {notif.time_ago}
                        </span>
                      </div>
                    </div>

                    {/* Main Headline */}
                    <div style={{
                      fontWeight: '800',
                      fontSize: '0.88rem',
                      color: isBuy ? 'var(--bullish)' : (isSell ? 'var(--bearish)' : 'var(--text-primary)'),
                      marginBottom: '4px',
                      lineHeight: '1.3'
                    }}>
                      {notif.headline}
                    </div>

                    {/* News Context */}
                    <div style={{
                      fontSize: '0.75rem',
                      color: 'var(--text-muted)',
                      marginBottom: '8px',
                      lineHeight: '1.4',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden'
                    }}>
                      {notif.news_title}
                    </div>

                    {/* Written Advice Box */}
                    <div style={{
                      padding: '8px 10px',
                      background: isBuy ? 'rgba(0, 109, 66, 0.05)' : (isSell ? 'rgba(180, 35, 24, 0.05)' : 'var(--bg-secondary)'),
                      borderLeft: `3px solid ${badgeColor}`,
                      borderRadius: '4px',
                      fontSize: '0.76rem',
                      color: 'var(--text-primary)',
                      lineHeight: '1.45',
                      marginBottom: '8px'
                    }}>
                      {notif.advice}
                    </div>

                    {/* Trade Levels Strip */}
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.72rem',
                      paddingTop: '6px',
                      borderTop: '1px solid var(--border-light)',
                      color: 'var(--text-muted)',
                      flexWrap: 'wrap',
                      gap: '6px'
                    }}>
                      <div>
                        Price: <strong style={{ color: 'var(--text-primary)' }}>₹{notif.current_price?.toFixed(1) || '—'}</strong>
                        {notif.target_price && (
                          <span style={{ marginLeft: '6px' }}>
                            Target: <strong style={{ color: 'var(--bullish)' }}>₹{notif.target_price?.toFixed(1)}</strong>
                          </span>
                        )}
                        {notif.stop_loss && (
                          <span style={{ marginLeft: '6px' }}>
                            Stop: <strong style={{ color: 'var(--bearish)' }}>₹{notif.stop_loss?.toFixed(1)}</strong>
                          </span>
                        )}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{
                          fontSize: '0.68rem',
                          background: 'rgba(0,0,0,0.05)',
                          padding: '1px 6px',
                          borderRadius: '3px',
                          color: 'var(--text-secondary)'
                        }}>
                          Model: {notif.ml_signal_1d}
                        </span>

                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '2px',
                          color: 'var(--accent-blue)',
                          fontWeight: '700',
                          fontSize: '0.72rem'
                        }}>
                          Analyze <ChevronRight size={12} />
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Popover Footer */}
          <div style={{
            padding: '10px 14px',
            background: 'var(--bg-secondary)',
            borderTop: '1px solid var(--border-color)',
            fontSize: '0.68rem',
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ShieldCheck size={14} color="var(--bullish)" />
              <span>Real Live Market Inference • Zero Demo Data</span>
            </div>
            <span>SEBI Non-Advisory Research</span>
          </div>
        </div>
      )}
    </div>
  );
}
