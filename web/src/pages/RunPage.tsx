import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ACTIVE, formatDuration, formatTime, runDuration, useJson, useMediaQuery } from '../api'
import type { HeadLog, PipelineGraph, Report, RunDetail, TaskStatus } from '../api'
import { StatusBadge } from '../components/Status'
import { StepGraph } from '../components/StepGraph'
import { StepList } from '../components/StepList'
import { TaskTable } from '../components/Tasks'

type Tab = 'tasks' | 'log' | 'reports' | 'params'

const SOURCE: Record<RunDetail['source'], string> = {
  batch: 'Live from AWS Batch',
  trace: 'From the run’s trace.txt',
  none: 'No tasks yet',
}

export function RunPage() {
  const run = useParams().run!
  const base = `/api/runs/${encodeURIComponent(run)}`
  const [pollActive, setPollActive] = useState(true)
  const detail = useJson<RunDetail>(base, pollActive)
  const graph = useJson<PipelineGraph>('/api/pipeline')
  const [selected, setSelected] = useState<string | null>(null)
  const [showSkipped, setShowSkipped] = useState(false)
  const [tab, setTab] = useState<Tab>('tasks')
  const narrow = useMediaQuery('(max-width: 640px)')

  const d = detail.data
  const isActive = d ? ACTIVE.includes(d.status) : true
  if (d && pollActive !== isActive) setPollActive(isActive)

  const counts = useMemo(() => {
    const c: Record<TaskStatus, number> = { queued: 0, running: 0, completed: 0, failed: 0 }
    for (const t of d?.tasks ?? []) c[t.status] = (c[t.status] ?? 0) + 1
    return c
  }, [d])

  const selectedTasks = d?.tasks.filter((t) => t.process === selected) ?? []
  const selectedInfo = graph.data?.processes.find((p) => p.id === selected)

  return (
    <main className="page">
      <Link to="/" className="back">
        ← All runs
      </Link>
      <div className="page-head">
        <div>
          <h1 className="run-title">
            {run} {d && <StatusBadge status={d.status} />}
          </h1>
          {d && (
            <p className="muted">
              {d.script ?? 'script unknown'} · created {formatTime(d.created)}
              {d.started && ` · started ${formatTime(d.started)}`}
              {d.started && ` · ${formatDuration(runDuration(d))}`}
            </p>
          )}
          {d?.reason && d.status === 'failed' && <p className="error small">{d.reason}</p>}
        </div>
        <div className="head-actions">
          {d?.kind === 'pipeline' && (
            <Link to={`/runs/${encodeURIComponent(run)}/report`} className="button primary">
              View report
            </Link>
          )}
          {detail.updated && (
            <span className="muted small">
              {d && SOURCE[d.source]} · updated {detail.updated.toLocaleTimeString()}
              {isActive && ' · refreshes every 15 s'}
            </span>
          )}
          <button onClick={detail.reload} disabled={detail.loading}>
            {detail.loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      {detail.error && <p className="error">{detail.error}</p>}
      {!d && !detail.error && <p className="muted">Loading run…</p>}

      {d && (
        <>
          <div className="stats">
            <Stat label="Done" value={counts.completed} cls="s-completed" />
            <Stat label="Running" value={counts.running} cls="s-running" />
            <Stat label="Queued" value={counts.queued} cls="s-queued" />
            <Stat label="Failed" value={counts.failed} cls="s-failed" />
          </div>

          {d.status === 'waiting' && (
            <p className="notice">
              The head job is waiting in AWS Batch, usually for jobs it depends on to finish. Steps start once it runs.
            </p>
          )}

          {d.kind === 'pipeline' && d.processes && graph.data && (
            <section className="card graph-card">
              <div className="card-head">
                <h2>Pipeline steps</h2>
                <label className="toggle">
                  <input type="checkbox" checked={showSkipped} onChange={(e) => setShowSkipped(e.target.checked)} />
                  Show steps not in this run
                </label>
              </div>
              <div className="graph-layout">
                {narrow ? (
                  <StepList
                    graph={graph.data}
                    processes={d.processes}
                    tasks={d.tasks}
                    showSkipped={showSkipped}
                    selected={selected}
                    onSelect={setSelected}
                  />
                ) : (
                  <div className="graph">
                    <StepGraph
                      graph={graph.data}
                      processes={d.processes}
                      tasks={d.tasks}
                      showSkipped={showSkipped}
                      selected={selected}
                      onSelect={setSelected}
                    />
                  </div>
                )}
                {selected && (
                  <aside className="drawer">
                    <div className="drawer-head">
                      <div>
                        <h3>{selectedInfo?.label ?? selected}</h3>
                        <p className="muted small">
                          {selectedInfo?.description} · <span className="mono">{selected}</span>
                        </p>
                      </div>
                      <button className="link" onClick={() => setSelected(null)} aria-label="Close">
                        ✕
                      </button>
                    </div>
                    <StatusBadge status={d.processes[selected]?.status ?? 'pending'} />
                    <TaskTable tasks={selectedTasks} run={run} compact />
                  </aside>
                )}
              </div>
              <Legend />
            </section>
          )}

          <section className="card">
            <nav className="tabs">
              {(['tasks', 'log', 'reports', 'params'] as Tab[]).map((t) => (
                <button key={t} className={tab === t ? 'tab on' : 'tab'} onClick={() => setTab(t)}>
                  {{ tasks: `All tasks (${d.tasks.length})`, log: 'Nextflow log', reports: 'Reports', params: 'Parameters' }[t]}
                </button>
              ))}
            </nav>
            {tab === 'tasks' && <TaskTable tasks={d.tasks} run={run} />}
            {tab === 'log' && <HeadLogView base={base} active={isActive} />}
            {tab === 'reports' && <ReportsView base={base} />}
            {tab === 'params' &&
              (d.params ? (
                <pre className="params">{JSON.stringify(d.params, null, 2)}</pre>
              ) : (
                <p className="muted">The run has not written params.json yet.</p>
              ))}
          </section>
        </>
      )}
    </main>
  )
}

function Stat({ label, value, cls }: { label: string; value: number; cls: string }) {
  return (
    <div className={`stat ${cls}`}>
      <span className="stat-value">{value}</span>
      <span className="stat-label">
        <span className="dot" />
        {label}
      </span>
    </div>
  )
}

function Legend() {
  const items: [string, string][] = [
    ['completed', 'Done'],
    ['running', 'Running'],
    ['queued', 'Queued'],
    ['failed', 'Failed'],
    ['pending', 'Not started'],
  ]
  return (
    <div className="legend">
      {items.map(([s, l]) => (
        <span key={s} className={`s-${s}`}>
          <span className="dot" />
          {l}
        </span>
      ))}
      <span className="muted">Chips are samples. Click a step for its tasks and logs.</span>
    </div>
  )
}

function HeadLogView({ base, active }: { base: string; active: boolean }) {
  const { data, error } = useJson<HeadLog>(`${base}/log?lines=400`, active)
  if (error) return <p className="error">{error}</p>
  if (!data) return <p className="muted">Loading…</p>
  if (!data.lines) return <p className="muted">{data.note}</p>
  return <pre className="log">{data.lines.join('\n')}</pre>
}

function ReportsView({ base }: { base: string }) {
  const { data, error, reload } = useJson<Report[]>(`${base}/reports`)
  if (error) return <p className="error">{error}</p>
  if (!data) return <p className="muted">Loading…</p>
  if (!data.length) return <p className="muted">No reports yet. They are written when the run finishes.</p>
  return (
    <>
      <p className="muted small">
        Links expire after 15 minutes. <button className="link" onClick={reload}>Renew links</button>
      </p>
      <ul className="reports">
        {data.map((r) => (
          <li key={r.path}>
            <a href={r.url} target="_blank" rel="noreferrer">
              {r.path}
            </a>
            <span className="muted small"> {(r.size / 1024).toFixed(r.size < 10240 ? 1 : 0)} KB</span>
          </li>
        ))}
      </ul>
    </>
  )
}
