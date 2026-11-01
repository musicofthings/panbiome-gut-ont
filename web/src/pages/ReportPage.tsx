import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { formatCount, query, sendJson, useJson } from '../api'
import type { ReadStats, Row, RunSummaryReport, SampleReport, Table } from '../api'
import { BarList, Histogram, Scatter } from '../components/charts'

const SECTIONS = [
  ['reads', 'Reads'],
  ['taxonomy', 'Species'],
  ['diversity', 'Diversity'],
  ['mags', 'MAGs'],
  ['amr', 'Resistance'],
  ['function', 'Function'],
] as const

const pct = (v: number | null | undefined, digits = 1) => (v == null ? '–' : `${(v * 100).toFixed(digits)}%`)
const num = (v: unknown, digits = 1) => (typeof v === 'number' ? v.toFixed(digits) : '–')

export function ReportPage() {
  const run = useParams().run!
  const [params, setParams] = useSearchParams()
  const base = `/api/runs/${encodeURIComponent(run)}/samples`
  const summary = useJson<RunSummaryReport>(base)
  const samples = summary.data?.samples ?? []
  const sample = params.get('sample') || samples[0] || null
  const report = useJson<SampleReport>(sample ? `${base}/${encodeURIComponent(sample)}` : null)

  return (
    <main className="page report">
      <Link to={`/runs/${encodeURIComponent(run)}`} className="back">
        ← Run {run}
      </Link>
      <div className="page-head">
        <div>
          <h1>Report · {run}</h1>
          <p className="muted">QC and results for each sample, read from the run's output files.</p>
        </div>
        <div className="head-actions">
          <Link to={`/files?${query({ root: 'results', path: `${run}/` })}`}>Browse output files</Link>
        </div>
      </div>

      {summary.error && <p className="error">{summary.error}</p>}
      {!summary.data && !summary.error && <p className="muted">Loading report…</p>}
      {summary.data && !samples.length && (
        <p className="notice">This run has no sample results yet. They are written as each step finishes.</p>
      )}
      {summary.data && samples.length > 0 && (
        <>
          <RunOverview data={summary.data} selected={sample} onSelect={(s) => setParams({ sample: s })} />
          <div className="report-layout">
            <aside className="report-nav">
              {samples.length > 1 && (
                <label className="sample-pick">
                  <span className="muted small">Sample</span>
                  <select value={sample ?? ''} onChange={(e) => setParams({ sample: e.target.value })}>
                    {samples.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
              )}
              <nav>
                {SECTIONS.map(([id, label]) => (
                  <a key={id} href={`#${id}`}>
                    {label}
                  </a>
                ))}
              </nav>
              {sample && <SampleLinks run={run} sample={sample} />}
            </aside>
            <div className="report-body">
              {report.error && <p className="error">{report.error}</p>}
              {!report.data && !report.error && <p className="muted">Loading {sample}…</p>}
              {report.data && <Sample r={report.data} />}
            </div>
          </div>
        </>
      )}
    </main>
  )
}

function QcStatus({ status }: { status: unknown }) {
  const s = String(status ?? '').toUpperCase()
  const cls = s === 'PASS' ? 's-completed' : s === 'FAIL' ? 's-failed' : s === 'WARN' ? 's-queued' : 's-pending'
  const icon = s === 'PASS' ? '✓' : s === 'FAIL' ? '✕' : s === 'WARN' ? '!' : '–'
  return (
    <span className={`badge ${cls}`}>
      <span aria-hidden="true">{icon}</span>
      {s || 'Unknown'}
    </span>
  )
}

function RunOverview({ data, selected, onSelect }: { data: RunSummaryReport; selected: string | null; onSelect: (s: string) => void }) {
  const alpha = Object.fromEntries((data.alpha ?? []).map((a) => [String(a.sample), a]))
  return (
    <section className="card">
      <div className="card-head">
        <h2>Run QC</h2>
        {data.control && (
          <span className="muted small">
            Controls: <strong>{data.control.status}</strong>
            {data.control.reason && ` · ${data.control.reason}`}
          </span>
        )}
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Sample</th>
              <th>QC</th>
              <th className="num">Raw reads</th>
              <th className="num">Filtered reads</th>
              <th className="num">Gb</th>
              <th className="num">N50</th>
              <th className="num">Median Q</th>
              <th className="num">Host</th>
              <th className="num">Species</th>
              <th>Flags</th>
            </tr>
          </thead>
          <tbody>
            {(data.qc ?? []).map((q) => {
              const name = String(q.sample)
              return (
                <tr key={name} className={name === selected ? 'active' : ''}>
                  <td>
                    <button className="link run-link" onClick={() => onSelect(name)}>
                      {name}
                    </button>
                  </td>
                  <td>
                    <QcStatus status={q.status} />
                  </td>
                  <td className="num">{formatCount(q.raw_reads as number)}</td>
                  <td className="num">{formatCount(q.filtered_reads as number)}</td>
                  <td className="num">{num(q.filtered_gb, 2)}</td>
                  <td className="num">{formatCount(q.n50 as number)}</td>
                  <td className="num">{num(q.median_read_q)}</td>
                  <td className="num">{num(q.host_pct, 2)}%</td>
                  <td className="num">{formatCount(alpha[name]?.observed_species as number)}</td>
                  <td className="small muted">{q.flags ? String(q.flags) : '–'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function SampleLinks({ run, sample }: { run: string; sample: string }) {
  const [error, setError] = useState<string | null>(null)
  const open = async (path: string) => {
    setError(null)
    try {
      const { url } = await sendJson<{ url: string }>('GET', `/api/files/view?${query({ root: 'results', path: `${run}/${path}` })}`)
      window.open(url, '_blank', 'noopener')
    } catch (e) {
      setError((e as Error).message)
    }
  }
  return (
    <div className="report-links">
      <span className="muted small">Original reports</span>
      <button className="link" onClick={() => open(`samples/${sample}/${sample}.sample_report.html`)}>
        Sample report
      </button>
      <button className="link" onClick={() => open(`samples/${sample}/taxonomy/${sample}.krona.html`)}>
        Krona chart
      </button>
      <button className="link" onClick={() => open('wf-gut-report.html')}>
        Run report
      </button>
      {error && <p className="error small">{error}</p>}
    </div>
  )
}

function Section({ id, title, children, note }: { id: string; title: string; children: ReactNode; note?: ReactNode }) {
  return (
    <section className="card report-section" id={id}>
      <div className="card-head">
        <h2>{title}</h2>
        {note && <span className="muted small">{note}</span>}
      </div>
      {children}
    </section>
  )
}

function Tile({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className="tile-value">{value}</span>
      {sub && <span className="tile-sub muted small">{sub}</span>}
    </div>
  )
}

function Missing({ what }: { what: string }) {
  return <p className="muted">No {what} for this sample. The step may be skipped in this run or not finished yet.</p>
}

function Sample({ r }: { r: SampleReport }) {
  return (
    <>
      <Reads r={r} />
      <Taxonomy r={r} />
      <Diversity r={r} />
      <Mags r={r} />
      <Resistance r={r} />
      <Function r={r} />
    </>
  )
}

function histBins(hist: Record<string, number>, kind: 'length' | 'quality') {
  const keys = Object.keys(hist).sort((a, b) => Number(a) - Number(b))
  const last = keys[keys.length - 1]
  return keys.map((k) => {
    const n = Number(k)
    const label =
      kind === 'length' ? (k === last ? `≥${n / 1000}k` : n >= 1000 ? `${n / 1000}k` : String(n)) : k === last ? `≥${n}` : String(n)
    return { label, value: hist[k], start: n }
  })
}

function Reads({ r }: { r: SampleReport }) {
  const [stage, setStage] = useState<'filtered' | 'raw'>('filtered')
  const s: ReadStats | null = r[stage] ?? r.filtered ?? r.raw
  if (!s) return <Section id="reads" title="Reads"><Missing what="read statistics" /></Section>
  const host = r.host
  const length = histBins(s.length_hist, 'length')
  const qual = histBins(s.qual_hist, 'quality')
  const step = length.length > 1 ? length[1].start - length[0].start : 500
  return (
    <Section
      id="reads"
      title="Reads"
      note={
        <span className="segmented" role="group" aria-label="Read set">
          {(['filtered', 'raw'] as const).map((k) => (
            <button key={k} className={stage === k ? 'on' : ''} onClick={() => setStage(k)} disabled={!r[k]}>
              {k === 'filtered' ? 'After filtering' : 'Raw'}
            </button>
          ))}
        </span>
      }
    >
      <div className="tiles">
        <Tile label="Reads" value={formatCount(s.reads)} sub={stage === 'filtered' && r.raw ? `of ${formatCount(r.raw.reads)} raw` : undefined} />
        <Tile label="Yield" value={`${s.gb.toFixed(2)} Gb`} sub={`${formatCount(s.bases)} bases`} />
        <Tile label="Read N50" value={formatCount(s.n50)} sub={`median ${formatCount(Math.round(s.median_len))} bp`} />
        <Tile label="Median read quality" value={`Q${s.median_read_q.toFixed(1)}`} sub={`${s.pct_q15.toFixed(1)}% ≥ Q15`} />
        <Tile
          label="Human reads"
          value={host ? pct(host.host_fraction, 2) : '–'}
          sub={host ? `${formatCount(host.host_reads)} removed` : 'host depletion skipped'}
        />
        <Tile label="Adapter found" value={`${s.adapter_any_pct.toFixed(2)}%`} sub="of reads checked" />
      </div>
      <div className="chart-grid">
        <figure>
          <figcaption>Read length</figcaption>
          <Histogram
            bins={length}
            xLabel="Read length (bp)"
            yLabel="Reads"
            describe={(b) => {
              const bin = length.find((x) => x.label === b.label)!
              const range = b.label.startsWith('≥') ? `${formatCount(bin.start)} bp and longer` : `${formatCount(bin.start)}–${formatCount(bin.start + step - 1)} bp`
              return (
                <>
                  <strong>{range}</strong>
                  <br />
                  {formatCount(b.value)} reads · {pct(b.value / s.reads)}
                </>
              )
            }}
          />
        </figure>
        <figure>
          <figcaption>Read quality</figcaption>
          <Histogram
            bins={qual}
            xLabel="Mean read quality (Phred)"
            yLabel="Reads"
            describe={(b) => (
              <>
                <strong>Q{b.label}</strong>
                <br />
                {formatCount(b.value)} reads · {pct(b.value / s.reads)}
              </>
            )}
          />
        </figure>
      </div>
    </Section>
  )
}

function Taxonomy({ r }: { r: SampleReport }) {
  const [filter, setFilter] = useState('')
  const sp = r.species
  const rows = useMemo(
    () => (sp?.rows ?? []).filter((x) => String(x.taxon).toLowerCase().includes(filter.toLowerCase())),
    [sp, filter],
  )
  if (!sp) return <Section id="taxonomy" title="Species"><Missing what="species profile" /></Section>
  const ts = r.taxa_summary
  const top = sp.rows.slice(0, 20)
  return (
    <Section
      id="taxonomy"
      title="Species"
      note={ts && `${ts.species_kept} kept of ${ts.species_total_candidates} candidates · rule: ${ts.rule}`}
    >
      <h4>Top 20 by relative abundance</h4>
      <BarList
        format={(v) => pct(v)}
        rows={top.map((x) => ({
          label: String(x.taxon),
          value: Number(x.final_rel_abundance ?? 0),
          detail: (
            <>
              <strong>{String(x.taxon)}</strong>
              <br />
              {pct(Number(x.final_rel_abundance))} · {formatCount(Number(x.final_reads))} reads
              <br />
              <span className="muted">{String(x.evidence)}</span>
            </>
          ),
        }))}
      />
      <Watchlist t={r.watchlist} />
      <div className="table-head">
        <h4>All kept species ({sp.kept})</h4>
        <input type="search" placeholder="Filter species" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </div>
      <div className="table-wrap scroll">
        <table>
          <thead>
            <tr>
              <th>Species</th>
              <th>Evidence</th>
              <th className="num">Abundance</th>
              <th className="num">Reads</th>
              <th className="num">Bracken</th>
              <th className="num">sylph</th>
              <th className="num">sylph ANI</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((x) => (
              <tr key={String(x.taxon)}>
                <td title={String(x.lineage ?? '')}>
                  <em>{String(x.taxon)}</em>
                </td>
                <td className="small">{String(x.evidence ?? '–')}</td>
                <td className="num">{pct(Number(x.final_rel_abundance), 2)}</td>
                <td className="num">{formatCount(Number(x.final_reads))}</td>
                <td className="num">{x.bracken_rel == null ? '–' : pct(Number(x.bracken_rel), 2)}</td>
                <td className="num">{x.sylph_rel == null ? '–' : pct(Number(x.sylph_rel), 2)}</td>
                <td className="num">{num(x.sylph_ani, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sp.kept > sp.rows.length && <p className="muted small">Showing the top {sp.rows.length} of {sp.kept}.</p>}
    </Section>
  )
}

function Watchlist({ t }: { t: Table | null }) {
  if (!t?.rows.length) return null
  const flagged = t.rows.filter((x) => x.flag && x.flag !== 'none')
  return (
    <>
      <h4>Watchlist</h4>
      {flagged.length === 0 ? (
        <p className="small">
          <span className="badge s-completed">✓ None above threshold</span>{' '}
          <span className="muted">{t.rows.map((x) => x.taxon).join(', ')}</span>
        </p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Taxon</th>
                <th>Flag</th>
                <th className="num">Abundance</th>
                <th className="num">Threshold</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {flagged.map((x) => (
                <tr key={String(x.taxon)}>
                  <td>
                    <em>{String(x.taxon)}</em>
                  </td>
                  <td>
                    <span className="badge s-failed">! {String(x.flag)}</span>
                  </td>
                  <td className="num">{pct(Number(x.rel_abundance), 3)}</td>
                  <td className="num">{pct(Number(x.threshold), 3)}</td>
                  <td className="small muted">{String(x.note ?? '')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function Diversity({ r }: { r: SampleReport }) {
  const ts = r.taxa_summary
  return (
    <Section id="diversity" title="Diversity" note="Alpha diversity of the kept species">
      <AlphaTiles sample={r.sample} />
      {ts && (
        <p className="muted small">
          {ts.both_methods_agree} species were found by both Bracken and sylph ({ts.rule} rule).
        </p>
      )}
    </Section>
  )
}

function AlphaTiles({ sample }: { sample: string }) {
  const run = useParams().run!
  const { data } = useJson<RunSummaryReport>(`/api/runs/${encodeURIComponent(run)}/samples`)
  const a = data?.alpha?.find((x) => x.sample === sample)
  if (!a) return <Missing what="diversity values" />
  return (
    <div className="tiles">
      <Tile label="Observed species" value={formatCount(a.observed_species as number)} />
      <Tile label="Shannon" value={num(a.shannon, 2)} />
      <Tile label="Simpson" value={num(a.simpson, 3)} />
      <Tile label="Pielou evenness" value={num(a.pielou_evenness, 3)} />
      <Tile label="Classified reads" value={formatCount(a.classified_reads as number)} />
    </div>
  )
}

const QUALITY = [
  { key: 'high', label: 'High quality (≥90% complete, <5% contamination)', color: 'var(--series-1)' },
  { key: 'medium', label: 'Medium (≥50%, <10%)', color: 'var(--series-2)' },
  { key: 'low', label: 'Low', color: 'var(--series-3)' },
]

function Mags({ r }: { r: SampleReport }) {
  const [only, setOnly] = useState<'all' | 'good'>('good')
  const b = r.bins
  if (!b) return <Section id="mags" title="MAGs"><Missing what="binning results" /></Section>
  const count = (q: string) => b.rows.filter((x) => x.mimag_quality === q).length
  const shown = b.rows
    .filter((x) => only === 'all' || x.mimag_quality === 'high' || x.mimag_quality === 'medium')
    .sort((x, y) => Number(y.completeness) - Number(x.completeness))
  const maxCont = Math.max(10, ...b.rows.map((x) => Number(x.contamination) || 0))
  return (
    <Section id="mags" title="Metagenome-assembled genomes" note="SemiBin2 bins, quality from CheckM2 (MIMAG)">
      <div className="tiles">
        <Tile label="Bins" value={formatCount(b.total)} />
        <Tile label="High quality" value={formatCount(count('high'))} />
        <Tile label="Medium quality" value={formatCount(count('medium'))} />
        <Tile label="Low quality" value={formatCount(count('low'))} />
      </div>
      <figure>
        <figcaption>Completeness and contamination per bin</figcaption>
        <Scatter
          groups={QUALITY}
          xLabel="Completeness (%)"
          yLabel="Contamination (%)"
          xMax={100}
          yMax={Math.min(niceCeil(maxCont), 100)}
          points={b.rows.map((x) => ({
            x: Number(x.completeness) || 0,
            y: Number(x.contamination) || 0,
            group: String(x.mimag_quality),
            detail: (
              <>
                <strong>{String(x.bin)}</strong>
                <br />
                {num(x.completeness)}% complete · {num(x.contamination)}% contamination
                <br />
                {formatCount(Number(x.size_bp))} bp in {formatCount(Number(x.n_contigs))} contigs
              </>
            ),
          }))}
        />
      </figure>
      <div className="table-head">
        <h4>Bins</h4>
        <span className="segmented" role="group" aria-label="Bins shown">
          <button className={only === 'good' ? 'on' : ''} onClick={() => setOnly('good')}>
            High and medium
          </button>
          <button className={only === 'all' ? 'on' : ''} onClick={() => setOnly('all')}>
            All
          </button>
        </span>
      </div>
      <div className="table-wrap scroll">
        <table>
          <thead>
            <tr>
              <th>Bin</th>
              <th>Quality</th>
              <th className="num">Completeness</th>
              <th className="num">Contamination</th>
              <th className="num">Size</th>
              <th className="num">Contigs</th>
              <th className="num">N50</th>
              <th>Taxonomy</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((x) => (
              <tr key={String(x.bin)}>
                <td className="mono small">{String(x.bin)}</td>
                <td>{String(x.mimag_quality)}</td>
                <td className="num">{num(x.completeness)}%</td>
                <td className="num">{num(x.contamination)}%</td>
                <td className="num">{(Number(x.size_bp) / 1e6).toFixed(2)} Mb</td>
                <td className="num">{formatCount(Number(x.n_contigs))}</td>
                <td className="num">{formatCount(Number(x.n50))}</td>
                <td className="small">{x.taxonomy ? String(x.taxonomy) : <span className="muted">not classified</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  )
}

function niceCeil(v: number) {
  return Math.ceil(v / 5) * 5
}

function Resistance({ r }: { r: SampleReport }) {
  const a = r.amr
  const p = r.plasmids
  if (!a) return <Section id="amr" title="Antimicrobial resistance"><Missing what="AMRFinderPlus results" /></Section>
  const rows: Row[] = a.rows
  const classes = new Map<string, number>()
  for (const x of rows) classes.set(String(x.class ?? x.Class), (classes.get(String(x.class ?? x.Class)) ?? 0) + 1)
  const onPlasmid = rows.filter((x) => x.on_plasmid === true).length
  return (
    <Section id="amr" title="Antimicrobial resistance" note="AMRFinderPlus genes on assembled contigs">
      <div className="tiles">
        <Tile label="AMR genes" value={formatCount(a.total)} />
        <Tile label="Drug classes" value={formatCount(classes.size)} />
        <Tile label="On plasmid contigs" value={formatCount(onPlasmid)} />
        <Tile label="Plasmid contigs" value={p ? formatCount(p.total) : '–'} sub="geNomad" />
      </div>
      <div className="table-wrap scroll">
        <table>
          <thead>
            <tr>
              <th>Gene</th>
              <th>Class</th>
              <th className="num">Identity</th>
              <th className="num">Coverage</th>
              <th>Contig</th>
              <th>Plasmid</th>
              <th>Bin</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((x, i) => (
              <tr key={i}>
                <td title={String(x.name ?? x['Element name'] ?? '')}>
                  <strong>{String(x.gene ?? x['Element symbol'])}</strong>
                </td>
                <td className="small">{String(x.class ?? x.Class ?? '–').toLowerCase()}</td>
                <td className="num">{num(x.pct_identity ?? x['% Identity to reference'])}%</td>
                <td className="num">{num(x.pct_coverage ?? x['% Coverage of reference'])}%</td>
                <td className="mono small">{String(x.contig ?? x['Contig id'])}</td>
                <td>{x.on_plasmid === true ? 'yes' : x.on_plasmid === false ? 'no' : '–'}</td>
                <td className="small">{x.bin ? `${String(x.bin)}${x.bin_quality ? ` (${String(x.bin_quality)})` : ''}` : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  )
}

function Function({ r }: { r: SampleReport }) {
  const t = r.function_targets
  const m = r.modules
  if (!t && !m) return <Section id="function" title="Function"><Missing what="eggNOG annotations" /></Section>
  return (
    <Section id="function" title="Function" note="eggNOG-mapper annotations of assembled genes">
      {t && (
        <>
          <h4>Targeted gut functions</h4>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Function</th>
                  <th>Gene</th>
                  <th>KO</th>
                  <th className="num">Genes</th>
                  <th className="num">Depth-weighted</th>
                  <th>Detected</th>
                </tr>
              </thead>
              <tbody>
                {t.rows.map((x, i) => (
                  <tr key={i}>
                    <td>{String(x.function)}</td>
                    <td className="small">{String(x.gene)}</td>
                    <td className="mono small">{String(x.ko)}</td>
                    <td className="num">{formatCount(Number(x.n_genes))}</td>
                    <td className="num">{formatCount(Number(x.depth_weighted))}</td>
                    <td>
                      {x.detected ? <span className="badge s-completed">✓ Yes</span> : <span className="badge s-pending">– No</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {m && (
        <>
          <h4>Top KEGG modules ({formatCount(m.total)} found)</h4>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Module</th>
                  <th className="num">Genes</th>
                  <th className="num">Depth-weighted</th>
                </tr>
              </thead>
              <tbody>
                {m.rows.slice(0, 15).map((x) => (
                  <tr key={String(x.module)}>
                    <td className="mono small">
                      <a href={`https://www.kegg.jp/entry/${String(x.module)}`} target="_blank" rel="noreferrer">
                        {String(x.module)}
                      </a>
                    </td>
                    <td className="num">{formatCount(Number(x.n_genes))}</td>
                    <td className="num">{formatCount(Number(x.depth_weighted))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Section>
  )
}
