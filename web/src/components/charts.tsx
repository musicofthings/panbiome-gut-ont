import { useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

// Small SVG charts for the report viewer. Colours come from CSS variables (--series-*), marks are thin with
// 4px rounded data ends on the baseline, grid and axes stay quiet, and every mark has a hover tooltip.

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}

function niceMax(v: number): number {
  if (v <= 0) return 1
  const p = 10 ** Math.floor(Math.log10(v))
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p
  return 10 * p
}

const compact = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })

interface Tip {
  x: number
  y: number
  content: ReactNode
}

function Tooltip({ tip }: { tip: Tip | null }) {
  if (!tip) return null
  return (
    <div className="chart-tip" style={{ left: tip.x, top: tip.y }} role="status">
      {tip.content}
    </div>
  )
}

/** Rect with the two corners at the data end rounded and the baseline end square. */
function barPath(x: number, y: number, w: number, h: number, r: number, horizontal = false): string {
  r = Math.min(r, w / 2, h / 2)
  if (horizontal) {
    return `M${x},${y}h${w - r}a${r},${r} 0 0 1 ${r},${r}v${h - 2 * r}a${r},${r} 0 0 1 ${-r},${r}h${-(w - r)}z`
  }
  return `M${x},${y + h}v${-(h - r)}a${r},${r} 0 0 1 ${r},${-r}h${w - 2 * r}a${r},${r} 0 0 1 ${r},${r}v${h - r}z`
}

export interface HistBin {
  label: string
  value: number
}

export function Histogram({
  bins,
  xLabel,
  yLabel,
  height = 220,
  describe,
}: {
  bins: HistBin[]
  xLabel: string
  yLabel: string
  height?: number
  describe: (b: HistBin) => ReactNode
}) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [tip, setTip] = useState<Tip | null>(null)
  const [hover, setHover] = useState<number | null>(null)
  const m = { top: 12, right: 8, bottom: 40, left: 48 }
  const w = Math.max(0, width - m.left - m.right)
  const h = height - m.top - m.bottom
  const max = niceMax(Math.max(...bins.map((b) => b.value), 0))
  const step = bins.length ? w / bins.length : 0
  const gap = step > 6 ? 2 : 0
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max)
  const labelEvery = Math.max(1, Math.ceil(bins.length / Math.max(1, Math.floor(w / 46))))

  return (
    <div className="chart" ref={ref}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={`${yLabel} by ${xLabel}`}>
          <g transform={`translate(${m.left},${m.top})`}>
            {ticks.map((t) => (
              <g key={t} transform={`translate(0,${h - (t / max) * h})`}>
                <line x2={w} className="grid" />
                <text x={-6} dy="0.32em" textAnchor="end" className="tick">
                  {compact.format(t)}
                </text>
              </g>
            ))}
            {bins.map((b, i) => {
              const bh = (b.value / max) * h
              return (
                <g key={b.label}>
                  {bh > 0 && (
                    <path
                      d={barPath(i * step + gap / 2, h - bh, Math.max(1, step - gap), bh, 4)}
                      className={hover === i ? 'mark on' : 'mark'}
                    />
                  )}
                  <rect
                    x={i * step}
                    y={0}
                    width={step}
                    height={h}
                    fill="transparent"
                    onMouseMove={(e) => {
                      setHover(i)
                      const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                      setTip({ x: e.clientX - box.left, y: e.clientY - box.top, content: describe(b) })
                    }}
                    onMouseLeave={() => {
                      setHover(null)
                      setTip(null)
                    }}
                  />
                  {/* The last bin is often an open-ended "≥" bin, so it always keeps its label */}
                  {(i === bins.length - 1 || (i % labelEvery === 0 && bins.length - 1 - i >= labelEvery)) && (
                    <text x={i * step + step / 2} y={h + 16} textAnchor="middle" className="tick">
                      {b.label}
                    </text>
                  )}
                </g>
              )
            })}
            <line y1={h} y2={h} x2={w} className="axis" />
            <text x={w / 2} y={h + 34} textAnchor="middle" className="axis-label">
              {xLabel}
            </text>
            <text transform={`translate(${-38},${h / 2}) rotate(-90)`} textAnchor="middle" className="axis-label">
              {yLabel}
            </text>
          </g>
        </svg>
      )}
      <Tooltip tip={tip} />
    </div>
  )
}

export interface BarRow {
  label: string
  value: number
  detail: ReactNode
}

/** Ranked horizontal bars, one series. Names on the left; values in the tooltip and the table below. */
export function BarList({ rows, format }: { rows: BarRow[]; format: (v: number) => string }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [tip, setTip] = useState<Tip | null>(null)
  const [hover, setHover] = useState<number | null>(null)
  const rowH = 22
  const labelW = Math.min(240, Math.max(120, width * 0.38))
  const m = { top: 4, right: 56, bottom: 4, left: labelW }
  const w = Math.max(0, width - m.left - m.right)
  const max = Math.max(...rows.map((r) => r.value), 0) || 1
  const height = m.top + m.bottom + rows.length * rowH

  return (
    <div className="chart" ref={ref}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label="Ranked bars">
          <g transform={`translate(${m.left},${m.top})`}>
            {rows.map((r, i) => {
              const bw = (r.value / max) * w
              return (
                <g
                  key={r.label}
                  transform={`translate(0,${i * rowH})`}
                  onMouseMove={(e) => {
                    setHover(i)
                    const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                    setTip({ x: e.clientX - box.left, y: e.clientY - box.top, content: r.detail })
                  }}
                  onMouseLeave={() => {
                    setHover(null)
                    setTip(null)
                  }}
                >
                  <rect x={-labelW} width={labelW + w + m.right} height={rowH} fill="transparent" />
                  <text x={-8} y={rowH / 2} dy="0.32em" textAnchor="end" className="bar-label">
                    {r.label.length > 34 ? `${r.label.slice(0, 33)}…` : r.label}
                  </text>
                  {bw > 0 && (
                    <path d={barPath(0, 4, Math.max(2, bw), rowH - 8, 4, true)} className={hover === i ? 'mark on' : 'mark'} />
                  )}
                  {/* Values only on the first bars; the rest are in the tooltip and table */}
                  {i < 3 && (
                    <text x={bw + 6} y={rowH / 2} dy="0.32em" className="tick">
                      {format(r.value)}
                    </text>
                  )}
                </g>
              )
            })}
            <line y2={rows.length * rowH} className="axis" />
          </g>
        </svg>
      )}
      <Tooltip tip={tip} />
    </div>
  )
}

export interface ScatterGroup {
  key: string
  label: string
  color: string
}

export interface ScatterPoint {
  x: number
  y: number
  group: string
  detail: ReactNode
}

export function Scatter({
  points,
  groups,
  xLabel,
  yLabel,
  xMax,
  yMax,
  height = 260,
}: {
  points: ScatterPoint[]
  groups: ScatterGroup[]
  xLabel: string
  yLabel: string
  xMax: number
  yMax: number
  height?: number
}) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [tip, setTip] = useState<Tip | null>(null)
  const m = { top: 12, right: 12, bottom: 40, left: 48 }
  const w = Math.max(0, width - m.left - m.right)
  const h = height - m.top - m.bottom
  const sx = (v: number) => (Math.min(v, xMax) / xMax) * w
  const sy = (v: number) => h - (Math.min(v, yMax) / yMax) * h
  const color = Object.fromEntries(groups.map((g) => [g.key, g.color]))
  const xt = [0, 0.25, 0.5, 0.75, 1].map((t) => t * xMax)
  const yt = [0, 0.25, 0.5, 0.75, 1].map((t) => t * yMax)

  return (
    <div className="chart" ref={ref}>
      <div className="chart-legend">
        {groups.map((g) => (
          <span key={g.key}>
            <span className="swatch" style={{ background: g.color }} />
            {g.label}
          </span>
        ))}
      </div>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={`${yLabel} against ${xLabel}`}>
          <g transform={`translate(${m.left},${m.top})`}>
            {yt.map((t) => (
              <g key={`y${t}`} transform={`translate(0,${sy(t)})`}>
                <line x2={w} className="grid" />
                <text x={-6} dy="0.32em" textAnchor="end" className="tick">
                  {compact.format(t)}
                </text>
              </g>
            ))}
            {xt.map((t) => (
              <text key={`x${t}`} x={sx(t)} y={h + 16} textAnchor="middle" className="tick">
                {compact.format(t)}
              </text>
            ))}
            <line y1={h} y2={h} x2={w} className="axis" />
            {/* Later groups first, so the first group (the one that matters most) is drawn on top */}
            {[...points]
              .sort((a, b) => groups.findIndex((g) => g.key === b.group) - groups.findIndex((g) => g.key === a.group))
              .map((p, i) => (
              <circle
                key={i}
                cx={sx(p.x)}
                cy={sy(p.y)}
                r={4.5}
                fill={color[p.group] ?? 'var(--pending)'}
                className="dot-mark"
                onMouseMove={(e) => {
                  const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                  setTip({ x: e.clientX - box.left, y: e.clientY - box.top, content: p.detail })
                }}
                onMouseLeave={() => setTip(null)}
              />
            ))}
            <text x={w / 2} y={h + 34} textAnchor="middle" className="axis-label">
              {xLabel}
            </text>
            <text transform={`translate(${-38},${h / 2}) rotate(-90)`} textAnchor="middle" className="axis-label">
              {yLabel}
            </text>
          </g>
        </svg>
      )}
      <Tooltip tip={tip} />
    </div>
  )
}
