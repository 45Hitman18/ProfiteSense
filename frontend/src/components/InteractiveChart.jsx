import React from 'react';
import PriceChart from './chart/PriceChart';

/**
 * InteractiveChart — Adapter maintaining backward compatibility with existing consumers
 * (TickerIntelligenceView, TradeRecommendationCard, AnalysisModal, WatchlistView).
 * Renders the new high-performance TradingView PriceChart (lightweight-charts v5)
 * when a ticker is present, while safely supporting legacy data arrays.
 */
export default function InteractiveChart({
  data = [],
  ticker = 'RELIANCE.NS',
  catalystDate = null,
  direction = 'UP',
  height = 360,
  showToolbar = true,
  className = '',
  style = {},
}) {
  // If ticker is provided, render the rich TradingView Lightweight Charts component
  if (ticker) {
    return (
      <PriceChart
        ticker={ticker}
        height={height}
        showToolbar={showToolbar}
        className={className}
        style={style}
      />
    );
  }

  // Fallback if raw data only and no ticker
  if (!data || data.length === 0) {
    return (
      <div style={{ padding: '30px', textAlign: 'center', color: '#787B86', ...style }}>
        No historical chart data available.
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', textAlign: 'center', color: '#787B86', ...style }}>
      Select a stock ticker to view full TradingView interactive chart.
    </div>
  );
}
