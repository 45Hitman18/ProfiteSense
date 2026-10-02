import React, { useState } from 'react';

export default function InteractiveChart({ data = [], ticker = 'AAPL', catalystDate = null, direction = 'UP' }) {
  const [hoverIndex, setHoverIndex] = useState(null);

  if (!data || data.length === 0) {
    return (
      <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
        No historical chart data available for {ticker}.
      </div>
    );
  }

  const width = 760;
  const height = 280;
  const padding = { top: 20, right: 30, bottom: 40, left: 60 };

  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const closes = data.map((d) => d.close);
  const minPrice = Math.min(...closes) * 0.98;
  const maxPrice = Math.max(...closes) * 1.02;
  const priceRange = maxPrice - minPrice || 1;

  const getX = (index) => padding.left + (index / (data.length - 1)) * chartWidth;
  const getY = (price) => padding.top + chartHeight - ((price - minPrice) / priceRange) * chartHeight;

  // Generate SVG path for line and area fill
  const linePoints = data.map((d, i) => `${getX(i)},${getY(d.close)}`).join(' ');
  const areaPoints = `${getX(0)},${padding.top + chartHeight} ${linePoints} ${getX(data.length - 1)},${padding.top + chartHeight}`;

  const isOverallUp = data[data.length - 1].close >= data[0].close;
  const lineColor = isOverallUp ? '#006D42' : '#B42318';
  const gradientId = `gradient-${ticker}-${isOverallUp ? 'up' : 'down'}`;

  // Y-axis ticks
  const yTicks = 5;
  const tickPrices = Array.from({ length: yTicks }, (_, i) => minPrice + (i / (yTicks - 1)) * priceRange);

  const activePoint = hoverIndex !== null ? data[hoverIndex] : data[data.length - 1];
  const activeX = hoverIndex !== null ? getX(hoverIndex) : getX(data.length - 1);
  const activeY = hoverIndex !== null ? getY(data[hoverIndex].close) : getY(data[data.length - 1].close);

  return (
    <div style={{ position: 'relative', width: '100%', overflow: 'hidden' }}>
      {/* Chart Top Bar with Current Hovered Info */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', padding: '0 4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: '800', color: '#171717', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{ticker} 30-Day Trend</span>
          {activePoint && (
            <span className="font-mono" style={{ fontSize: '0.90rem', fontWeight: '800', color: lineColor }}>
              ₹{activePoint.close.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
            </span>
          )}
          {activePoint && (
            <span style={{ fontSize: '0.75rem', color: '#736B63' }}>
              Date: {activePoint.date}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem', color: '#5A403D', fontWeight: '600' }}>
          <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', backgroundColor: lineColor }}></span>
          <span>Close Price (INR ₹)</span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: '100%', height: 'auto', display: 'block', cursor: 'crosshair' }}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const mouseX = e.clientX - rect.left;
          const ratio = (mouseX - (padding.left / width) * rect.width) / ((chartWidth / width) * rect.width);
          const rawIndex = Math.round(ratio * (data.length - 1));
          const boundedIndex = Math.max(0, Math.min(data.length - 1, rawIndex));
          setHoverIndex(boundedIndex);
        }}
        onMouseLeave={() => setHoverIndex(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity="0.20" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Horizontal grid lines & Y labels */}
        {tickPrices.map((price, i) => {
          const y = getY(price);
          return (
            <g key={i}>
              <line
                x1={padding.left}
                y1={y}
                x2={padding.left + chartWidth}
                y2={y}
                stroke="#EAE3D7"
                strokeDasharray="3,3"
              />
              <text
                x={padding.left - 8}
                y={y + 4}
                textAnchor="end"
                fontSize="10"
                fill="#736B63"
                fontFamily="var(--font-mono)"
                fontWeight="600"
              >
                ₹{price.toFixed(1)}
              </text>
            </g>
          );
        })}

        {/* Area fill */}
        <polygon points={areaPoints} fill={`url(#${gradientId})`} />

        {/* Main Line */}
        <polyline
          fill="none"
          stroke={lineColor}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={linePoints}
        />

        {/* Catalyst Pin at the latest or target point */}
        <g transform={`translate(${getX(data.length - 1)}, ${getY(data.length - 1)})`}>
          <circle r="6" fill="#A71919" stroke="#ffffff" strokeWidth="2" />
          <circle r="12" fill="none" stroke="#A71919" strokeWidth="1.5" opacity="0.6" className="pulse-dot" />
        </g>

        {/* Crosshair indicator on hover */}
        {hoverIndex !== null && (
          <g>
            <line
              x1={activeX}
              y1={padding.top}
              x2={activeX}
              y2={padding.top + chartHeight}
              stroke="#A71919"
              strokeDasharray="2,2"
              strokeWidth="1.5"
            />
            <circle cx={activeX} cy={activeY} r="5" fill="#ffffff" stroke="#A71919" strokeWidth="2" />
          </g>
        )}

        {/* X-axis date labels */}
        {data.filter((_, i) => i % Math.ceil(data.length / 5) === 0 || i === data.length - 1).map((d, idx) => {
          const origIndex = data.findIndex((item) => item.date === d.date);
          const x = getX(origIndex);
          return (
            <text
              key={idx}
              x={x}
              y={padding.top + chartHeight + 18}
              textAnchor="middle"
              fontSize="10"
              fill="#736B63"
              fontFamily="var(--font-mono)"
              fontWeight="600"
            >
              {d.date.slice(5)}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
