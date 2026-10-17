import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import InteractiveChart from '../components/InteractiveChart';

// Mock lightweight-charts createChart
vi.mock('lightweight-charts', () => {
  return {
    createChart: vi.fn(() => ({
      addSeries: vi.fn(() => ({
        setData: vi.fn(),
        update: vi.fn(),
        priceScale: vi.fn(() => ({
          applyOptions: vi.fn(),
        })),
      })),
      remove: vi.fn(),
      applyOptions: vi.fn(),
      timeScale: vi.fn(() => ({
        fitContent: vi.fn(),
        subscribeVisibleLogicalRangeChange: vi.fn(),
        getVisibleLogicalRange: vi.fn(),
        setVisibleLogicalRange: vi.fn(),
      })),
      priceScale: vi.fn(() => ({
        applyOptions: vi.fn(),
      })),
      subscribeCrosshairMove: vi.fn(),
      takeScreenshot: vi.fn(() => ({
        toDataURL: vi.fn(() => 'data:image/png;base64,...'),
      })),
    })),
    CandlestickSeries: 'CandlestickSeries',
    LineSeries: 'LineSeries',
    AreaSeries: 'AreaSeries',
    BarSeries: 'BarSeries',
    HistogramSeries: 'HistogramSeries',
    CrosshairMode: { Normal: 0 },
    PriceScaleMode: { Normal: 0, Logarithmic: 1, Percentage: 2 },
  };
});

// Mock ResizeObserver
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

describe('PriceChart & InteractiveChart Adapter', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            ticker: 'RELIANCE.NS',
            bars: [
              { time: '2024-04-01', open: 2900, high: 2950, low: 2880, close: 2940, volume: 10000 },
              { time: '2024-04-02', open: 2940, high: 2980, low: 2930, close: 2970, volume: 12000 },
            ],
            meta: {
              source: 'yfinance',
              data_disclaimer: 'AI/model estimate — not investment advice.',
              bars_count: 2,
            },
          }),
      })
    ));
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders InteractiveChart adapter with ticker and compliance disclaimer', async () => {
    let rendered;
    await React.act(async () => {
      rendered = render(<InteractiveChart ticker="RELIANCE.NS" height={400} />);
    });
    
    // Ticker title in toolbar
    expect(screen.getByText('RELIANCE.NS')).toBeDefined();

    // Mandatory compliance disclaimer
    expect(
      screen.getByText(/AI\/model estimate — not investment advice/i)
    ).toBeDefined();

    // TradingView attribution
    expect(
      screen.getByText(/TradingView Lightweight Charts™/i)
    ).toBeDefined();
  });

  it('renders fallback when no ticker and empty data provided', () => {
    render(<InteractiveChart ticker="" data={[]} />);
    expect(screen.getByText(/No historical chart data available/i)).toBeDefined();
  });
});
