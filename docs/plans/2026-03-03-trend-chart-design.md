# Trend Chart Design — fund-watch

Date: 2026-03-03

## Goal

Replace the placeholder blue-dot trend visualization with a proper Recharts line chart, showing both estimated NAV (gsz) and change percentage (gszzl) on dual Y-axes.

## Decision: Recharts

Chose Recharts over ECharts (too heavy) and hand-drawn SVG (too much effort). Recharts is lightweight (~200KB gzip), React-native, has good TypeScript support, and dual Y-axis / Tooltip out of the box.

## Scope

- **Backend**: No changes needed. `GET /api/snapshots/{code}?limit=30` already returns the required data.
- **Frontend**: Replace blue-dot section in App.tsx with Recharts `LineChart`.

## Chart Spec

- **X-axis**: `gztime` (估值时间)
- **Left Y-axis**: `gsz` (估算净值), blue line
- **Right Y-axis**: `gszzl` (涨跌幅%), green/red contextual line
- **Tooltip**: hover shows gztime + gsz + gszzl%
- **Legend**: clickable toggle for each line
- **Responsive**: `<ResponsiveContainer>` wrapping
- **Risk disclaimer**: static text below chart: "以上为盘中估算数据，非最终成交净值"

## Interaction

1. User clicks "查看趋势" on a fund row
2. Chart area expands below the table (same as current behavior)
3. Fetches snapshots from existing API
4. Recharts renders the line chart
5. Clicking another fund switches; clicking same fund collapses

## Files to Change

1. `frontend/package.json` — add `recharts` dependency
2. `frontend/src/App.tsx` — replace blue-dot section with Recharts component
3. `frontend/src/styles.css` — minor styling for chart container and disclaimer
