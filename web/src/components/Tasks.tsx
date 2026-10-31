import { useState } from 'react'
import { formatDuration, formatTime, useJson } from '../api'
import type { Task, TaskLog } from '../api'
import { StatusBadge } from './Status'

export function TaskTable({ tasks, run, compact = false }: { tasks: Task[]; run: string; compact?: boolean }) {
  const [openKey, setOpenKey] = useState<string | null>(null)
  const keyOf = (t: Task) => `${t.process}|${t.tag}|${t.job_id}`
  const open = tasks.find((t) => keyOf(t) === openKey) ?? null
  if (!tasks.length) return <p className="muted">No tasks have been submitted yet.</p>
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {!compact && <th>Step</th>}
              <th>Sample</th>
              <th>Status</th>
              {!compact && <th>Submitted</th>}
              <th className="num">Duration</th>
              <th className="num">{compact ? 'Memory' : 'Peak memory'}</th>
              <th className="num">Exit</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={keyOf(t)} className={open === t ? 'active' : ''}>
                {!compact && <td className="mono">{t.process}</td>}
                <td>{t.tag ?? '–'}</td>
                <td>
                  <StatusBadge status={t.status} />
                </td>
                {!compact && <td>{formatTime(t.submitted)}</td>}
                <td className="num">{formatDuration(t.duration_s)}</td>
                <td className="num">{t.peak_rss && t.peak_rss !== '-' ? t.peak_rss : '–'}</td>
                <td className="num">{t.exit ?? '–'}</td>
                <td className="num">
                  {t.hash && (
                    <button className="link" onClick={() => setOpenKey(open === t ? null : keyOf(t))}>
                      {open === t ? 'Hide log' : 'Log'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open?.hash && <TaskLogView run={run} task={open} />}
    </>
  )
}

function TaskLogView({ run, task }: { run: string; task: Task }) {
  const active = task.status === 'running' || task.status === 'queued'
  const { data, error, loading } = useJson<TaskLog>(
    `/api/runs/${encodeURIComponent(run)}/tasks/log?hash=${encodeURIComponent(task.hash!)}`,
    active,
  )
  return (
    <div className="log-box">
      <div className="log-title">
        {task.process}
        {task.tag ? ` (${task.tag})` : ''}
        {data?.workdir && <span className="mono muted"> {data.workdir}</span>}
      </div>
      {error && <p className="error">{error}</p>}
      {loading && !data && <p className="muted">Loading…</p>}
      {data && !data.found && <p className="muted">The work directory for this task is not in S3.</p>}
      {data?.found && (
        <>
          <h4>Command</h4>
          <pre>{data.command_sh ?? '–'}</pre>
          <h4>Error output (last lines)</h4>
          <pre>{data.command_err || (active ? 'Written to S3 when the task ends.' : '(empty)')}</pre>
          <h4>Log (last lines)</h4>
          <pre>{data.command_log || (active ? 'Written to S3 when the task ends.' : '(empty)')}</pre>
        </>
      )}
    </div>
  )
}
