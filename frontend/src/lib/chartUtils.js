/**
 * chartUtils.js — Core data-mapping and helper functions for TradingView / Lightweight Charts
 */

export const ALLOWED_INTERVALS = ['1m', '5m', '15m', '1h', '1d', '1wk'];

export const INTERVAL_ALLOWED_RANGES = {
  '1m': ['1d', '5d', '7d'],
  '5m': ['1d', '5d', '1mo', '60d'],
  '15m': ['1d', '5d', '1mo', '60d'],
  '1h': ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y'],
  '1d': ['1d', '5d', '1mo', '3mo', '6mo', '1y', '5y', 'max'],
  '1wk': ['1mo', '3mo', '6mo', '1y', '5y', 'max'],
};

export const DEFAULT_RANGE_MAP = {
  '1m': '1d',
  '5m': '5d',
  '15m': '5d',
  '1h': '1mo',
  '1d': '1y',
  '1wk': '5y',
};

// TradingView standard display names (m for minutes, D for Day, W for Week)
export const INTERVAL_DISPLAY_MAP = {
  '1m': '1m',
  '5m': '5m',
  '15m': '15m',
  '1h': '1h',
  '1d': '1D',
  '1wk': '1W',
};

// Universal time range options available in TradingView
export const RANGE_OPTIONS = [
  { value: '1d', label: '1D' },
  { value: '5d', label: '5D' },
  { value: '1mo', label: '1M' },
  { value: '3mo', label: '3M' },
  { value: '6mo', label: '6M' },
  { value: '1y', label: '1Y' },
  { value: '5y', label: '5Y' },
  { value: 'max', label: 'All' },
];

// Fallback interval map if current interval cannot display target range
export const RANGE_DEFAULT_INTERVAL_MAP = {
  '1d': '5m',
  '5d': '15m',
  '7d': '1m',
  '1mo': '1h',
  '60d': '15m',
  '3mo': '1d',
  '6mo': '1d',
  '1y': '1d',
  '2y': '1h',
  '5y': '1d',
  'max': '1d',
};

// Bottom range bar presets matching TradingView (1D, 5D, 1M, 3M, 6M, 1Y, 5Y, All)
export const TIME_RANGE_PRESETS = [
  { label: '1D', range: '1d' },
  { label: '5D', range: '5d' },
  { label: '1M', range: '1mo' },
  { label: '3M', range: '3mo' },
  { label: '6M', range: '6mo' },
  { label: '1Y', range: '1y' },
  { label: '5Y', range: '5y' },
  { label: 'All', range: 'max' },
];

/**
 * Returns the best interval for a requested target range.
 * If currentInterval supports targetRange, KEEP IT (e.g. 15m on 1d).
 * Otherwise, fall back to the most appropriate standard interval.
 */
export function getCompatibleIntervalForRange(currentInterval, targetRange) {
  const allowedForCurrent = INTERVAL_ALLOWED_RANGES[currentInterval] || [];
  if (allowedForCurrent.includes(targetRange)) {
    return currentInterval; // Keep user's active interval!
  }
  return RANGE_DEFAULT_INTERVAL_MAP[targetRange] || '1d';
}

// Progression map when scrolling left to load more historical candles
export const NEXT_EXPANDED_RANGE = {
  '1d': {
    '1d': '5d',
    '5d': '1mo',
    '1mo': '6mo',
    '3mo': '1y',
    '6mo': '1y',
    '1y': '5y',
    '5y': 'max',
  },
  '1h': {
    '1d': '5d',
    '5d': '1mo',
    '1mo': '3mo',
    '3mo': '6mo',
    '6mo': '1y',
    '1y': '2y',
  },
  '15m': {
    '1d': '5d',
    '5d': '1mo',
    '1mo': '60d',
  },
  '5m': {
    '1d': '5d',
    '5d': '1mo',
    '1mo': '60d',
  },
  '1m': {
    '1d': '5d',
    '5d': '7d',
  },
  '1wk': {
    '1mo': '6mo',
    '6mo': '1y',
    '1y': '5y',
    '5y': 'max',
  },
};

/**
 * Validates and adjusts range when user switches interval.
 */
export function getValidRangeForInterval(interval, currentRange) {
  const allowed = INTERVAL_ALLOWED_RANGES[interval] || ['1y'];
  if (allowed.includes(currentRange)) {
    return currentRange;
  }
  return DEFAULT_RANGE_MAP[interval] || allowed[0];
}

/**
 * Checks whether the National Stock Exchange (NSE) of India is currently open.
 * Trading hours: Monday to Friday, 09:15 to 15:30 IST (Indian Standard Time).
 */
export function isNseSessionOpen(date = new Date()) {
  try {
    // Get time in Asia/Kolkata
    const istString = date.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' });
    const istDate = new Date(istString);
    const day = istDate.getDay(); // 0 is Sunday, 6 is Saturday
    if (day === 0 || day === 6) return false;

    const hours = istDate.getHours();
    const minutes = istDate.getMinutes();
    const currentMinute = hours * 60 + minutes;

    const marketOpen = 9 * 60 + 15;   // 09:15 IST
    const marketClose = 15 * 60 + 30; // 15:30 IST

    return currentMinute >= marketOpen && currentMinute <= marketClose;
  } catch {
    return false;
  }
}

/**
 * Formats a bar's time into Asia/Kolkata locale string for tooltip/legend.
 */
export function formatIstTime(timeVal, isIntraday = false) {
  if (!timeVal) return '';
  if (typeof timeVal === 'string') return timeVal;

  try {
    const d = new Date(timeVal * 1000);
    if (isIntraday) {
      return d.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      });
    }
    return d.toLocaleDateString('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return String(timeVal);
  }
}

/**
 * Calculate difference and percentage change between Open and Close or Close and Prev Close.
 */
export function calculateBarChange(bar, prevClose = null) {
  if (!bar) return { change: 0, changePct: 0 };
  const base = prevClose != null ? prevClose : bar.open;
  if (!base || base === 0) return { change: 0, changePct: 0 };
  const change = bar.close - base;
  const changePct = (change / base) * 100;
  return {
    change: Number(change.toFixed(2)),
    changePct: Number(changePct.toFixed(2)),
  };
}

/**
 * Converts standard OHLC bars into Heikin-Ashi candlestick bars.
 * Formula:
 *   haClose = (Open + High + Low + Close) / 4
 *   haOpen = [haOpen(prev) + haClose(prev)] / 2   (or (Open + Close) / 2 for first bar)
 *   haHigh = Max(High, haOpen, haClose)
 *   haLow = Min(Low, haOpen, haClose)
 */
export function toHeikinAshi(bars = []) {
  if (!bars || bars.length === 0) return [];

  const haBars = [];
  let prevHaOpen = null;
  let prevHaClose = null;

  for (let i = 0; i < bars.length; i++) {
    const b = bars[i];
    const haClose = Number(((b.open + b.high + b.low + b.close) / 4).toFixed(2));
    const haOpen = Number(
      (prevHaOpen === null
        ? (b.open + b.close) / 2
        : (prevHaOpen + prevHaClose) / 2
      ).toFixed(2)
    );
    const haHigh = Number(Math.max(b.high, haOpen, haClose).toFixed(2));
    const haLow = Number(Math.min(b.low, haOpen, haClose).toFixed(2));

    haBars.push({
      time: b.time,
      open: haOpen,
      high: haHigh,
      low: haLow,
      close: haClose,
      volume: b.volume || 0,
    });

    prevHaOpen = haOpen;
    prevHaClose = haClose;
  }

  return haBars;
}
