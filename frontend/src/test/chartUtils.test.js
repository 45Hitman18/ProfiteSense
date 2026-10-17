import { describe, it, expect } from 'vitest';
import {
  getValidRangeForInterval,
  getCompatibleIntervalForRange,
  isNseSessionOpen,
  formatIstTime,
  calculateBarChange,
  toHeikinAshi,
} from '../lib/chartUtils';

describe('chartUtils tests', () => {
  it('validates ranges for intervals correctly', () => {
    expect(getValidRangeForInterval('1m', '1d')).toBe('1d');
    // 1m with 1y should fallback to 1d
    expect(getValidRangeForInterval('1m', '1y')).toBe('1d');
    // 15m with 1d MUST be kept (25 intraday bars)
    expect(getValidRangeForInterval('15m', '1d')).toBe('1d');
    // 15m with 1mo should be kept
    expect(getValidRangeForInterval('15m', '1mo')).toBe('1mo');
    // 15m with 5y should fallback to 5d
    expect(getValidRangeForInterval('15m', '5y')).toBe('5d');
  });

  it('resolves compatible interval for target ranges without overriding active interval', () => {
    // When on 15m and clicking 1D, KEEP 15m!
    expect(getCompatibleIntervalForRange('15m', '1d')).toBe('15m');
    // When on 15m and clicking 5D, KEEP 15m!
    expect(getCompatibleIntervalForRange('15m', '5d')).toBe('15m');
    // When on 15m and clicking 1M, KEEP 15m!
    expect(getCompatibleIntervalForRange('15m', '1mo')).toBe('15m');
    // When on 15m and clicking 1Y, fallback to 1d (Daily)
    expect(getCompatibleIntervalForRange('15m', '1y')).toBe('1d');
    // When on 1d and clicking All, KEEP 1d!
    expect(getCompatibleIntervalForRange('1d', 'max')).toBe('1d');
  });

  it('determines NSE market session accurately', () => {
    // Mon 11:00 AM IST (Open) -> UTC is 05:30 AM
    const mondayOpen = new Date('2024-04-08T05:30:00Z');
    expect(isNseSessionOpen(mondayOpen)).toBe(true);

    // Mon 08:30 AM IST (Before open) -> UTC 03:00 AM
    const mondayPre = new Date('2024-04-08T03:00:00Z');
    expect(isNseSessionOpen(mondayPre)).toBe(false);

    // Saturday 11:00 AM IST (Weekend closed)
    const weekend = new Date('2024-04-13T05:30:00Z');
    expect(isNseSessionOpen(weekend)).toBe(false);
  });

  it('calculates bar price change and percentage', () => {
    const bar = { open: 100, close: 105, high: 107, low: 99 };
    const res = calculateBarChange(bar);
    expect(res.change).toBe(5);
    expect(res.changePct).toBe(5);

    const downBar = { open: 200, close: 190, high: 205, low: 185 };
    const downRes = calculateBarChange(downBar);
    expect(downRes.change).toBe(-10);
    expect(downRes.changePct).toBe(-5);
  });

  it('converts bars to Heikin-Ashi correctly', () => {
    const rawBars = [
      { time: '2024-04-01', open: 100, high: 110, low: 95, close: 105, volume: 1000 },
      { time: '2024-04-02', open: 106, high: 115, low: 102, close: 112, volume: 1200 },
    ];

    const ha = toHeikinAshi(rawBars);
    expect(ha).toHaveLength(2);

    // Bar 0:
    // haClose = (100 + 110 + 95 + 105) / 4 = 102.5
    // haOpen = (100 + 105) / 2 = 102.5
    expect(ha[0].close).toBe(102.5);
    expect(ha[0].open).toBe(102.5);
    expect(ha[0].high).toBe(110);
    expect(ha[0].low).toBe(95);

    // Bar 1:
    // haClose = (106 + 115 + 102 + 112) / 4 = 108.75
    // haOpen = (102.5 + 102.5) / 2 = 102.5
    expect(ha[1].close).toBe(108.75);
    expect(ha[1].open).toBe(102.5);
    expect(ha[1].high).toBe(115);
    expect(ha[1].low).toBe(102);
  });
});
