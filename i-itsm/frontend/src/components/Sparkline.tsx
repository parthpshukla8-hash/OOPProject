interface SparklineProps { values: number[]; width?: number; height?: number; label: string }

/** Tufte-style word-sized chart: just the line and the last point. */
export function Sparkline({ values, width = 140, height = 28, label }: SparklineProps) {
  if (values.length < 2) return null
  const max = Math.max(...values, 1)
  const step = (width - 6) / (values.length - 1)
  const points = values.map((value, index) => [3 + index * step, height - 3 - (value / max) * (height - 6)])
  const last = points[points.length - 1]
  return (
    <svg width={width} height={height} role="img" aria-label={label} style={{ color: 'var(--colorBrandForeground1)' }}>
      <polyline points={points.map(([x, y]) => `${x},${y}`).join(' ')} fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx={last[0]} cy={last[1]} r="2.5" fill="currentColor" />
    </svg>
  )
}
