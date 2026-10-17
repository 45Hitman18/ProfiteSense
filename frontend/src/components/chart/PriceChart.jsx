import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  AreaSeries,
  BarSeries,
  HistogramSeries,
  CrosshairMode,
  PriceScaleMode,
} from 'lightweight-charts';
import {
  ALLOWED_INTERVALS,
  INTERVAL_ALLOWED_RANGES,
  DEFAULT_RANGE_MAP,
  INTERVAL_DISPLAY_MAP,
  TIME_RANGE_PRESETS,
  NEXT_EXPANDED_RANGE,
  getValidRangeForInterval,
  getCompatibleIntervalForRange,
  RANGE_OPTIONS,
  isNseSessionOpen,
  formatIstTime,
  calculateBarChange,
  toHeikinAshi,
} from '../../lib/chartUtils';

// Local storage key for persistent user chart preferences
const STORAGE_KEY = 'profitsense_chart_settings';

export default function PriceChart({
  ticker = 'RELIANCE.NS',
  height = 480,
  initialInterval = '1d',
  initialRange = '1y',
  initialChartType = 'candles', // 'candles' | 'line' | 'area' | 'heikin-ashi' | 'bars'
  className = '',
  style = {},
  showToolbar = true,
  onCrosshairMove = null,
}) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const abortControllerRef = useRef(null);

  // Restore preferences from localStorage if available
  const getSavedSetting = (key, fallback) => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed[key] !== undefined) return parsed[key];
      }
    } catch {}
    return fallback;
  };

  const [interval, setInterval] = useState(() => getSavedSetting('interval', initialInterval));
  const [range, setRange] = useState(() => getSavedSetting('range', initialRange));
  const [chartType, setChartType] = useState(() => getSavedSetting('chartType', initialChartType));
  const [scaleMode, setScaleMode] = useState(() => getSavedSetting('scaleMode', 'normal')); // 'normal' | 'log' | 'percent'

  const [bars, setBars] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isExpandingHistory, setIsExpandingHistory] = useState(false);
  const [error, setError] = useState(null);
  const [marketStatus, setMarketStatus] = useState(() => isNseSessionOpen());
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Refs to avoid stale closures in chart event callbacks
  const intervalRef = useRef(interval);
  intervalRef.current = interval;
  const rangeRef = useRef(range);
  rangeRef.current = range;
  const isExpandingRef = useRef(false);

  // Hovered / Active bar for Legend display
  const [legendData, setLegendData] = useState(null);
  const latestBarRef = useRef(null);

  // Save settings to localStorage on change
  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ interval, range, chartType, scaleMode })
      );
    } catch {}
  }, [interval, range, chartType, scaleMode]);

  // Update market open/closed status periodically
  useEffect(() => {
    const timer = window.setInterval(() => {
      setMarketStatus(isNseSessionOpen());
    }, 30000);
    return () => window.clearInterval(timer);
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // 1. CHART INITIALIZATION & DISPOSAL
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    // Dispose any previous instance
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      seriesRef.current = null;
      volumeSeriesRef.current = null;
    }

    const container = containerRef.current;
    const clientWidth = container.clientWidth || 700;

    // TradingView Dark Palette
    const chart = createChart(container, {
      width: clientWidth,
      height: height,
      layout: {
        background: { type: 'solid', color: '#131722' },
        textColor: '#D1D4DC',
        fontSize: 11,
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#758696',
          width: 1,
          style: 3, // dashed
          labelBackgroundColor: '#2A2E39',
        },
        horzLine: {
          color: '#758696',
          width: 1,
          style: 3,
          labelBackgroundColor: '#2A2E39',
        },
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
        scaleMargins: {
          top: 0.1,
          bottom: 0.25, // Leaves bottom space for volume histogram
        },
        mode:
          scaleMode === 'log'
            ? PriceScaleMode.Logarithmic
            : scaleMode === 'percent'
            ? PriceScaleMode.Percentage
            : PriceScaleMode.Normal,
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
        timeVisible: interval.includes('m') || interval.includes('h'),
        secondsVisible: false,
        shiftVisibleRangeOnNewBar: false,
      },
      handleScroll: {
        vertTouchDrag: false,
      },
    });

    chartRef.current = chart;

    // Create Main Series based on chartType
    let mainSeries;
    if (chartType === 'line') {
      mainSeries = chart.addSeries(LineSeries, {
        color: '#2962FF',
        lineWidth: 2,
        priceFormat: { type: 'price', precision: 2, minMove: 0.05 },
      });
    } else if (chartType === 'area') {
      mainSeries = chart.addSeries(AreaSeries, {
        topColor: 'rgba(41, 98, 255, 0.35)',
        bottomColor: 'rgba(41, 98, 255, 0.0)',
        lineColor: '#2962FF',
        lineWidth: 2,
        priceFormat: { type: 'price', precision: 2, minMove: 0.05 },
      });
    } else if (chartType === 'bars') {
      mainSeries = chart.addSeries(BarSeries, {
        upColor: '#089981',
        downColor: '#F23645',
        priceFormat: { type: 'price', precision: 2, minMove: 0.05 },
      });
    } else {
      // 'candles' or 'heikin-ashi'
      mainSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#089981',
        downColor: '#F23645',
        borderVisible: false,
        wickUpColor: '#089981',
        wickDownColor: '#F23645',
        priceFormat: { type: 'price', precision: 2, minMove: 0.05 },
      });
    }
    seriesRef.current = mainSeries;

    // Create Volume Series (Bottom 20% of pane)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.82,
        bottom: 0.0,
      },
    });
    volumeSeriesRef.current = volumeSeries;

    // Crosshair movement subscription for Legend Overlay
    chart.subscribeCrosshairMove((param) => {
      if (onCrosshairMove) onCrosshairMove(param);

      if (!param || !param.time || !param.seriesData || !param.seriesData.has(mainSeries)) {
        // Cursor left chart: restore latest bar
        setLegendData(latestBarRef.current);
        return;
      }

      const pointData = param.seriesData.get(mainSeries);
      const volData = volumeSeries ? param.seriesData.get(volumeSeries) : null;

      if (pointData) {
        const isOHLC = pointData.open !== undefined;
        const barObj = isOHLC
          ? {
              time: param.time,
              open: pointData.open,
              high: pointData.high,
              low: pointData.low,
              close: pointData.close,
              volume: volData ? volData.value : pointData.volume || 0,
            }
          : {
              time: param.time,
              open: pointData.value,
              high: pointData.value,
              low: pointData.value,
              close: pointData.value,
              volume: volData ? volData.value : 0,
            };

        const changeInfo = calculateBarChange(barObj);
        setLegendData({
          ...barObj,
          ...changeInfo,
        });
      }
    });

    // ─────────────────────────────────────────────────────────────────
    // INFINITE SCROLL: Automatically load older candles when scrolling left
    // ─────────────────────────────────────────────────────────────────
    const handleLogicalRangeChange = (logicalRange) => {
      if (!logicalRange) return;
      // When user scrolls near the left boundary (logicalRange.from <= 2)
      if (logicalRange.from <= 2 && !isExpandingRef.current) {
        const curInt = intervalRef.current;
        const curRng = rangeRef.current;
        const nextRng = NEXT_EXPANDED_RANGE[curInt]?.[curRng];

        if (nextRng && nextRng !== curRng) {
          isExpandingRef.current = true;
          setIsExpandingHistory(true);
          setRange(nextRng);
        }
      }
    };
    chart.timeScale?.()?.subscribeVisibleLogicalRangeChange?.(handleLogicalRangeChange);

    // ResizeObserver for responsive sizing
    const resizeObserver = new ResizeObserver((entries) => {
      if (!entries || entries.length === 0) return;
      const { width: newWidth, height: newHeight } = entries[0].contentRect;
      if (chart && newWidth > 50) {
        chart.applyOptions({
          width: newWidth,
          height: isFullscreen ? newHeight : height,
        });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
        volumeSeriesRef.current = null;
      }
    };
  }, [chartType, height, isFullscreen]);

  // Apply Price Scale Mode toggles
  useEffect(() => {
    if (!chartRef.current) return;
    const mode =
      scaleMode === 'log'
        ? PriceScaleMode.Logarithmic
        : scaleMode === 'percent'
        ? PriceScaleMode.Percentage
        : PriceScaleMode.Normal;

    chartRef.current.priceScale('right').applyOptions({ mode });
  }, [scaleMode]);

  // ─────────────────────────────────────────────────────────────────────────
  // 2. FETCH OHLCV DATA
  // ─────────────────────────────────────────────────────────────────────────
  const loadChartData = useCallback(
    async (isLiveIncremental = false, isExpansion = false) => {
      if (!isLiveIncremental && !isExpansion) {
        setLoading(true);
        setError(null);
      }

      // Cancel previous pending request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const validRange = getValidRangeForInterval(interval, range);
        const res = await fetch(
          `/api/chart/${encodeURIComponent(ticker)}?interval=${interval}&range=${validRange}`,
          { signal: controller.signal }
        );

        if (!res.ok) {
          const errPayload = await res.json().catch(() => ({ detail: 'Failed to fetch' }));
          throw new Error(errPayload.detail || `Server returned ${res.status}`);
        }

        const data = await res.json();
        const rawBars = data.bars || [];

        if (rawBars.length === 0) {
          if (!isLiveIncremental && !isExpansion) {
            setBars([]);
            setError(`No price bars returned for ${ticker} (${interval}, ${validRange}).`);
            setLoading(false);
          }
          isExpandingRef.current = false;
          setIsExpandingHistory(false);
          return;
        }

        // Apply Heikin-Ashi if selected
        const displayBars = chartType === 'heikin-ashi' ? toHeikinAshi(rawBars) : rawBars;

        // Map series data
        if (seriesRef.current && volumeSeriesRef.current && chartRef.current) {
          if (isLiveIncremental && rawBars.length > 0) {
            // Live update the last bar with series.update()
            const lastBar = displayBars[displayBars.length - 1];
            if (chartType === 'line' || chartType === 'area') {
              seriesRef.current.update({ time: lastBar.time, value: lastBar.close });
            } else {
              seriesRef.current.update(lastBar);
            }

            volumeSeriesRef.current.update({
              time: lastBar.time,
              value: lastBar.volume || 0,
              color:
                lastBar.close >= lastBar.open
                  ? 'rgba(8, 153, 129, 0.45)'
                  : 'rgba(242, 54, 69, 0.45)',
            });
          } else {
            // Remember visible range before setting expanded data so user position is preserved
            const prevLogicalRange = isExpansion ? chartRef.current.timeScale().getVisibleLogicalRange() : null;

            // Full series setData
            if (chartType === 'line' || chartType === 'area') {
              const lineData = displayBars.map((b) => ({ time: b.time, value: b.close }));
              seriesRef.current.setData(lineData);
            } else {
              seriesRef.current.setData(displayBars);
            }

            const volumeData = displayBars.map((b) => ({
              time: b.time,
              value: b.volume || 0,
              color:
                b.close >= b.open
                  ? 'rgba(8, 153, 129, 0.45)'
                  : 'rgba(242, 54, 69, 0.45)',
            }));
            volumeSeriesRef.current.setData(volumeData);

            // If it wasn't a scroll-expansion, fit the content nicely
            if (!isExpansion) {
              chartRef.current.timeScale().fitContent();
            } else if (prevLogicalRange) {
              // Maintain user view smoothly
              chartRef.current.timeScale().setVisibleLogicalRange(prevLogicalRange);
            }
          }
        }

        setBars(rawBars);

        // Update default legend to latest bar
        const latest = displayBars[displayBars.length - 1];
        const prev = displayBars.length > 1 ? displayBars[displayBars.length - 2] : null;
        const changeInfo = calculateBarChange(latest, prev ? prev.close : null);
        const latestLegend = {
          ...latest,
          ...changeInfo,
        };
        latestBarRef.current = latestLegend;
        setLegendData(latestLegend);

        setLoading(false);
        isExpandingRef.current = false;
        setIsExpandingHistory(false);
      } catch (err) {
        if (err.name === 'AbortError') return;
        loggerError(err);
        isExpandingRef.current = false;
        setIsExpandingHistory(false);
        if (!isLiveIncremental && !isExpansion) {
          setError(err.message || 'Error loading chart data');
          setLoading(false);
        }
      }
    },
    [ticker, interval, range, chartType]
  );

  function loggerError(e) {
    if (process.env.NODE_ENV !== 'production') {
      console.warn('[PriceChart]', e);
    }
  }

  // Reload data on ticker, interval, or range change
  useEffect(() => {
    const isExpanding = isExpandingRef.current;
    loadChartData(false, isExpanding);
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [loadChartData]);

  // ─────────────────────────────────────────────────────────────────────────
  // 3. LIVE POLLING DURING NSE MARKET HOURS
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    // Only poll intraday intervals while market is open
    const isIntraday = interval.includes('m') || interval.includes('h');
    if (!isIntraday || !isNseSessionOpen()) return;

    const pollInterval = window.setInterval(() => {
      // Pause if browser tab is hidden
      if (document.visibilityState === 'hidden') return;
      loadChartData(true);
    }, 10000); // Poll every 10 seconds

    return () => window.clearInterval(pollInterval);
  }, [interval, loadChartData]);

  // ─────────────────────────────────────────────────────────────────────────
  // 4. TOOLBAR ACTIONS
  // ─────────────────────────────────────────────────────────────────────────
  const handleIntervalChange = (newInterval) => {
    if (newInterval === interval) return;
    const allowed = INTERVAL_ALLOWED_RANGES[newInterval] || [];
    // If the active range is already supported by the new interval (e.g. range is 1d and user clicks 15m), KEEP IT!
    let newRange = range;
    if (!allowed.includes(range)) {
      newRange = DEFAULT_RANGE_MAP[newInterval] || allowed[0];
    }
    setInterval(newInterval);
    setRange(newRange);
  };

  const handleRangePresetClick = (targetRangeInput) => {
    const targetRange = typeof targetRangeInput === 'object' ? targetRangeInput.range : targetRangeInput;
    const allowed = INTERVAL_ALLOWED_RANGES[interval] || [];
    if (allowed.includes(targetRange)) {
      // Current interval is fully compatible (e.g. 15m with 1d)! Keep active interval!
      setRange(targetRange);
    } else {
      // Current interval cannot display this range (e.g. 1m with 1y). Gracefully switch to standard interval.
      const newInterval = getCompatibleIntervalForRange(interval, targetRange);
      if (newInterval !== interval) {
        setInterval(newInterval);
      }
      setRange(targetRange);
    }
  };

  const handleFitContent = () => {
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  };

  const handleScreenshot = () => {
    if (!chartRef.current) return;
    try {
      const canvas = chartRef.current.takeScreenshot();
      const dataURL = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.download = `${ticker}_${interval}_${new Date().toISOString().slice(0, 10)}.png`;
      link.href = dataURL;
      link.click();
    } catch (e) {
      console.error('Screenshot error:', e);
    }
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    const el = containerRef.current.parentElement;
    if (!document.fullscreenElement) {
      el.requestFullscreen?.().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.().catch(() => {});
      setIsFullscreen(false);
    }
  };

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        backgroundColor: '#131722',
        borderRadius: '8px',
        border: '1px solid #2B2B43',
        overflow: 'hidden',
        color: '#D1D4DC',
        fontFamily: "'Inter', sans-serif",
        display: 'flex',
        flexDirection: 'column',
        ...style,
      }}
      className={`tradingview-price-chart ${className}`}
    >
      {/* ── TOP TOOLBAR ───────────────────────────────────────────────────── */}
      {showToolbar && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 12px',
            backgroundColor: '#1E222D',
            borderBottom: '1px solid #2B2B43',
            gap: '8px',
            fontSize: '0.78rem',
          }}
        >
          {/* Left: Ticker + Market Status + Intervals */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span
              style={{
                fontWeight: '800',
                color: '#FFFFFF',
                fontSize: '0.90rem',
                letterSpacing: '0.03em',
                marginRight: '4px',
              }}
            >
              {ticker}
            </span>

            {/* Market Session Status Badge */}
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '2px 6px',
                borderRadius: '4px',
                fontSize: '0.68rem',
                fontWeight: '700',
                backgroundColor: marketStatus ? 'rgba(8, 153, 129, 0.2)' : 'rgba(117, 134, 150, 0.2)',
                color: marketStatus ? '#089981' : '#758696',
              }}
              title={marketStatus ? 'NSE session active (09:15 - 15:30 IST)' : 'NSE session closed'}
            >
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: marketStatus ? '#089981' : '#758696',
                }}
              />
              {marketStatus ? 'NSE LIVE' : 'NSE CLOSED'}
            </span>

            <span style={{ color: '#434651', margin: '0 2px' }}>|</span>

            {/* Intervals with TradingView labels (1m, 5m, 15m, 1h, 1D, 1W) */}
            {ALLOWED_INTERVALS.map((intVal) => {
              const label = INTERVAL_DISPLAY_MAP[intVal] || intVal;
              const isMinute = intVal.endsWith('m');
              const tooltip = isMinute
                ? `${intVal.replace('m', '')} Minute${intVal !== '1m' ? 's' : ''}`
                : intVal === '1h'
                ? '1 Hour'
                : intVal === '1d'
                ? '1 Day'
                : '1 Week';
              return (
                <button
                  key={intVal}
                  type="button"
                  onClick={() => handleIntervalChange(intVal)}
                  style={{
                    background: interval === intVal ? '#2962FF' : 'transparent',
                    color: interval === intVal ? '#FFFFFF' : '#787B86',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '3px 7px',
                    cursor: 'pointer',
                    fontWeight: interval === intVal ? '700' : '500',
                    fontSize: '0.75rem',
                  }}
                  title={tooltip}
                >
                  {label}
                </button>
              );
            })}

            <span style={{ color: '#434651', margin: '0 2px' }}>|</span>

            {/* Range Selectors (1D, 5D, 1M, 3M, 6M, 1Y, 5Y, All) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
              <span style={{ color: '#787B86', fontSize: '0.68rem', fontWeight: '700', marginRight: '2px' }}>
                RANGE:
              </span>
              {TIME_RANGE_PRESETS.map((preset) => {
                const isActive = range === preset.range;
                return (
                  <button
                    key={`top-${preset.label}`}
                    type="button"
                    onClick={() => handleRangePresetClick(preset.range)}
                    style={{
                      background: isActive ? '#2962FF' : 'transparent',
                      color: isActive ? '#FFFFFF' : '#787B86',
                      border: 'none',
                      borderRadius: '4px',
                      padding: '3px 6px',
                      cursor: 'pointer',
                      fontWeight: isActive ? '700' : '500',
                      fontSize: '0.73rem',
                    }}
                    title={`View ${preset.label} range (compatible with ${interval})`}
                  >
                    {preset.label}
                  </button>
                );
              })}
            </div>

            <span style={{ color: '#434651', margin: '0 2px' }}>|</span>

            {/* Chart Type Selector */}
            <select
              value={chartType}
              onChange={(e) => setChartType(e.target.value)}
              style={{
                background: '#131722',
                color: '#D1D4DC',
                border: '1px solid #2B2B43',
                borderRadius: '4px',
                padding: '3px 6px',
                fontSize: '0.72rem',
                cursor: 'pointer',
              }}
            >
              <option value="candles">Candles</option>
              <option value="line">Line</option>
              <option value="area">Area</option>
              <option value="heikin-ashi">Heikin-Ashi</option>
              <option value="bars">Bars</option>
            </select>
          </div>

          {/* Right: Scale modes & Actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            {/* Price Scale Toggles */}
            <button
              type="button"
              onClick={() => setScaleMode(scaleMode === 'percent' ? 'normal' : 'percent')}
              style={{
                background: scaleMode === 'percent' ? '#2962FF' : 'transparent',
                color: scaleMode === 'percent' ? '#FFFFFF' : '#787B86',
                border: '1px solid #2B2B43',
                borderRadius: '4px',
                padding: '3px 6px',
                cursor: 'pointer',
                fontSize: '0.70rem',
              }}
              title="Toggle Percentage Scale"
            >
              %
            </button>
            <button
              type="button"
              onClick={() => setScaleMode(scaleMode === 'log' ? 'normal' : 'log')}
              style={{
                background: scaleMode === 'log' ? '#2962FF' : 'transparent',
                color: scaleMode === 'log' ? '#FFFFFF' : '#787B86',
                border: '1px solid #2B2B43',
                borderRadius: '4px',
                padding: '3px 6px',
                cursor: 'pointer',
                fontSize: '0.70rem',
              }}
              title="Toggle Logarithmic Scale"
            >
              LOG
            </button>

            {/* Fit Content */}
            <button
              type="button"
              onClick={handleFitContent}
              style={{
                background: 'transparent',
                color: '#787B86',
                border: '1px solid #2B2B43',
                borderRadius: '4px',
                padding: '3px 6px',
                cursor: 'pointer',
                fontSize: '0.70rem',
              }}
              title="Fit chart contents"
            >
              FIT
            </button>

            {/* Screenshot */}
            <button
              type="button"
              onClick={handleScreenshot}
              style={{
                background: 'transparent',
                color: '#787B86',
                border: '1px solid #2B2B43',
                borderRadius: '4px',
                padding: '3px 6px',
                cursor: 'pointer',
                fontSize: '0.70rem',
              }}
              title="Save Chart Screenshot (PNG)"
            >
              📷
            </button>

            {/* Fullscreen */}
            <button
              type="button"
              onClick={toggleFullscreen}
              style={{
                background: 'transparent',
                color: '#787B86',
                border: '1px solid #2B2B43',
                borderRadius: '4px',
                padding: '3px 6px',
                cursor: 'pointer',
                fontSize: '0.70rem',
              }}
              title="Toggle Fullscreen"
            >
              {isFullscreen ? '✕' : '⛶'}
            </button>
          </div>
        </div>
      )}

      {/* ── LEGEND OVERLAY ──────────────────────────────────────────────── */}
      <div
        style={{
          position: 'absolute',
          top: showToolbar ? '44px' : '8px',
          left: '12px',
          zIndex: 10,
          pointerEvents: 'none',
          fontSize: '0.74rem',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '10px',
          alignItems: 'center',
          backgroundColor: 'rgba(19, 23, 34, 0.75)',
          padding: '4px 8px',
          borderRadius: '4px',
          backdropFilter: 'blur(4px)',
        }}
      >
        {legendData ? (
          <>
            <span style={{ color: '#D1D4DC', fontWeight: '700' }}>
              {formatIstTime(legendData.time, interval.includes('m') || interval.includes('h'))}
            </span>
            <span>
              O: <strong style={{ color: '#FFFFFF' }}>₹{legendData.open?.toFixed(2)}</strong>
            </span>
            <span>
              H: <strong style={{ color: '#FFFFFF' }}>₹{legendData.high?.toFixed(2)}</strong>
            </span>
            <span>
              L: <strong style={{ color: '#FFFFFF' }}>₹{legendData.low?.toFixed(2)}</strong>
            </span>
            <span>
              C: <strong style={{ color: '#FFFFFF' }}>₹{legendData.close?.toFixed(2)}</strong>
            </span>
            {legendData.change !== undefined && (
              <span
                style={{
                  color: legendData.change >= 0 ? '#089981' : '#F23645',
                  fontWeight: '700',
                }}
              >
                {legendData.change >= 0 ? '+' : ''}
                {legendData.change.toFixed(2)} ({legendData.changePct >= 0 ? '+' : ''}
                {legendData.changePct.toFixed(2)}%)
              </span>
            )}
            {legendData.volume > 0 && (
              <span style={{ color: '#787B86' }}>
                Vol: <strong style={{ color: '#D1D4DC' }}>{legendData.volume.toLocaleString('en-IN')}</strong>
              </span>
            )}
          </>
        ) : (
          <span style={{ color: '#787B86' }}>Loading quote metrics...</span>
        )}
      </div>

      {/* ── MAIN CHART CONTAINER ────────────────────────────────────────── */}
      <div
        ref={containerRef}
        style={{
          position: 'relative',
          width: '100%',
          height: isFullscreen ? '100%' : `${height}px`,
          minHeight: '260px',
        }}
      >
        {loading && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'rgba(19, 23, 34, 0.6)',
              zIndex: 20,
              gap: '8px',
              fontSize: '0.85rem',
            }}
          >
            <span className="pulse-dot" style={{ width: '8px', height: '8px', backgroundColor: '#2962FF' }} />
            <span>Loading {ticker} price candles...</span>
          </div>
        )}

        {isExpandingHistory && !loading && (
          <div
            style={{
              position: 'absolute',
              top: '8px',
              right: '12px',
              backgroundColor: 'rgba(41, 98, 255, 0.85)',
              color: '#FFFFFF',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.70rem',
              fontWeight: '600',
              zIndex: 15,
            }}
          >
            Loading older history...
          </div>
        )}

        {error && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'rgba(19, 23, 34, 0.9)',
              color: '#F23645',
              padding: '20px',
              textAlign: 'center',
              zIndex: 20,
              gap: '8px',
            }}
          >
            <strong>Chart Data Notice</strong>
            <span style={{ color: '#D1D4DC', fontSize: '0.80rem', maxWidth: '420px' }}>{error}</span>
            <button
              type="button"
              onClick={() => loadChartData(false)}
              style={{
                marginTop: '8px',
                background: '#2962FF',
                color: '#fff',
                border: 'none',
                padding: '6px 14px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '0.78rem',
              }}
            >
              Retry
            </button>
          </div>
        )}
      </div>

      {/* ── TRADINGVIEW BOTTOM TIME-RANGE BAR ─────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '5px 12px',
          backgroundColor: '#1E222D',
          borderTop: '1px solid #2B2B43',
          fontSize: '0.72rem',
          flexWrap: 'wrap',
          gap: '6px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '3px', flexWrap: 'wrap' }}>
          <span style={{ color: '#787B86', fontSize: '0.68rem', marginRight: '4px', fontWeight: '700' }}>
            RANGE:
          </span>
          {TIME_RANGE_PRESETS.map((preset) => {
            const isActive = range === preset.range;
            return (
              <button
                key={preset.label}
                type="button"
                onClick={() => handleRangePresetClick(preset.range)}
                style={{
                  background: isActive ? '#2962FF' : 'transparent',
                  color: isActive ? '#FFFFFF' : '#787B86',
                  border: isActive ? '1px solid #2962FF' : '1px solid transparent',
                  borderRadius: '3px',
                  padding: '2px 8px',
                  cursor: 'pointer',
                  fontWeight: isActive ? '700' : '500',
                  fontSize: '0.70rem',
                }}
                title={`View ${preset.label} range (keeps ${interval} candles if supported)`}
              >
                {preset.label}
              </button>
            );
          })}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#787B86', fontSize: '0.68rem' }}>
          <span>{bars.length > 0 ? `${bars.length.toLocaleString('en-IN')} candles loaded` : ''}</span>
          <span>•</span>
          <span>Scroll / Drag to navigate history</span>
        </div>
      </div>

      {/* ── COMPLIANCE & ATTRIBUTION FOOTER ─────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '4px 12px',
          backgroundColor: '#171B26',
          borderTop: '1px solid #2B2B43',
          fontSize: '0.68rem',
          color: '#787B86',
        }}
      >
        {/* Compliance Label (MANDATORY) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#F23645' }} />
          <span>AI/model estimate — not investment advice. Delayed/unofficial data.</span>
        </div>

        {/* Required Open-Source Attribution to TradingView per library license */}
        <div>
          Chart powered by{' '}
          <a
            href="https://www.tradingview.com/lightweight-charts/"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#2962FF', textDecoration: 'none', fontWeight: '600' }}
          >
            TradingView Lightweight Charts™
          </a>
        </div>
      </div>
    </div>
  );
}
