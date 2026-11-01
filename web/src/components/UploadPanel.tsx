import { formatBytes } from '../api'
import { cancelUpload, clearFinished, retryUpload, useUploads } from '../uploads'
import type { Upload } from '../uploads'

const LABEL: Record<Upload['state'], string> = {
  queued: 'Waiting',
  uploading: 'Uploading',
  done: 'Uploaded',
  failed: 'Failed',
  cancelled: 'Cancelled',
  exists: 'Already exists',
}

const CLS: Record<Upload['state'], string> = {
  queued: 's-queued',
  uploading: 's-running',
  done: 's-completed',
  failed: 's-failed',
  cancelled: 's-pending',
  exists: 's-queued',
}

function rate(u: Upload): string {
  if (!u.started || u.sent === 0) return ''
  const secs = ((u.finished ?? Date.now()) - u.started) / 1000
  return secs > 0 ? `${formatBytes(u.sent / secs)}/s` : ''
}

export function UploadPanel() {
  const list = useUploads()
  if (!list.length) return null
  const active = list.filter((u) => u.state === 'queued' || u.state === 'uploading')
  const total = active.reduce((s, u) => s + u.file.size, 0)
  const sent = active.reduce((s, u) => s + u.sent, 0)

  return (
    <section className="card uploads">
      <div className="card-head">
        <h2>
          Uploads{' '}
          {active.length > 0 && (
            <span className="muted small">
              {active.length} in progress · {formatBytes(sent)} of {formatBytes(total)}
            </span>
          )}
        </h2>
        {active.length < list.length && (
          <button className="link" onClick={clearFinished}>
            Clear finished
          </button>
        )}
      </div>
      {active.length > 0 && <p className="muted small">Keep this tab open until uploads finish. You can browse other pages meanwhile.</p>}
      <ul className="upload-list">
        {list.map((u) => {
          const pct = u.file.size ? Math.round((100 * u.sent) / u.file.size) : 100
          return (
            <li key={u.id}>
              <div className="upload-row">
                <span className="mono upload-path" title={`${u.root}/${u.path}`}>
                  {u.path}
                </span>
                <span className={`badge ${CLS[u.state]}`}>
                  <span className="dot" />
                  {LABEL[u.state]}
                </span>
                <span className="muted small num">
                  {formatBytes(u.sent)} / {formatBytes(u.file.size)} {u.state === 'uploading' && rate(u)}
                </span>
                <span className="row-actions">
                  {(u.state === 'queued' || u.state === 'uploading') && (
                    <button className="link" onClick={() => cancelUpload(u.id)}>
                      Cancel
                    </button>
                  )}
                  {(u.state === 'failed' || u.state === 'cancelled') && (
                    <button className="link" onClick={() => retryUpload(u.id)}>
                      Retry
                    </button>
                  )}
                  {u.state === 'exists' && (
                    <button className="link danger" onClick={() => retryUpload(u.id, true)}>
                      Overwrite
                    </button>
                  )}
                </span>
              </div>
              {u.state === 'uploading' && (
                <div className="bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
                  <span style={{ width: `${pct}%` }} />
                </div>
              )}
              {u.error && u.state !== 'exists' && <p className="error small">{u.error}</p>}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
