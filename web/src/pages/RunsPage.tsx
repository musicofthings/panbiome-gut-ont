import { Link } from 'react-router-dom'
import { ACTIVE, formatDuration, formatTime, runDuration, useJson } from '../api'
import type { RunSummary } from '../api'
import { StatusBadge } from '../components/Status'

function scriptLabel(script: string | null) {
  if (script === 'main.nf') return 'Pipeline'
  if (!script) return '–'
  return script.replace(/^infra\/aws\//, '').replace(/\.nf$/, '')
}

export function RunsPage() {
  const { data, error, loading, updated, reload } = useJson<RunSummary[]>('/api/runs', true, 30000)
  const active = data?.filter((r) => ACTIVE.includes(r.status)).length ?? 0

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Runs</h1>
          <p className="muted">
            Workflow runs on AWS Batch (ap-south-1).{' '}
            {data && `${data.length} runs, ${active} active.`}
          </p>
        </div>
        <button onClick={reload} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="muted">Loading runs…</p>}
      {data && (
        <div className="table-wrap card">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Type</th>
                <th>Status</th>
                <th>Created</th>
                <th className="num">Duration</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.name}>
                  <td>
                    <Link to={`/runs/${encodeURIComponent(r.name)}`} className="run-link">
                      {r.name}
                    </Link>
                  </td>
                  <td className={r.script === 'main.nf' ? '' : 'muted'}>{scriptLabel(r.script)}</td>
                  <td>
                    <StatusBadge status={r.status} />
                  </td>
                  <td>{formatTime(r.created ?? r.stopped)}</td>
                  <td className="num">{formatDuration(runDuration(r))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {updated && <p className="muted small">Updated {updated.toLocaleTimeString()}</p>}
    </main>
  )
}
