import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { formatBytes, formatTime, query, sendJson, useJson } from '../api'
import type { FileRoot, Listing } from '../api'
import { UploadPanel } from '../components/UploadPanel'
import { addUploads, filesFromDrop, onUploaded } from '../uploads'

export function FilesPage() {
  const [params, setParams] = useSearchParams()
  const root = params.get('root') || 'uploads'
  const path = params.get('path') || ''
  const roots = useJson<FileRoot[]>('/api/files/roots')
  const listing = useJson<Listing>(`/api/files?${query({ root, path })}`)
  const [busy, setBusy] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)
  const { reload } = listing

  useEffect(() => onUploaded((u) => u.root === root && u.path.startsWith(path) && reload()), [root, path, reload])

  const go = (r: string, p: string) => setParams(p ? { root: r, path: p } : { root: r })
  const crumbs = path.split('/').filter(Boolean)
  const l = listing.data
  const writable = l?.writable ?? false

  const enqueue = (items: { path: string; file: File }[]) => {
    if (items.length) addUploads(root, items.map((i) => ({ path: path + i.path, file: i.file })))
  }

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label)
    setActionError(null)
    try {
      await fn()
      reload()
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const download = (name: string, view = false) =>
    act(`open ${name}`, async () => {
      const { url } = await sendJson<{ url: string }>('GET', `/api/files/${view ? 'view' : 'download'}?${query({ root, path: path + name })}`)
      if (view) window.open(url, '_blank', 'noopener')
      else window.location.assign(url)
    })

  const newFolder = () => {
    const name = window.prompt('New folder name')?.trim()
    if (name) act('folder', () => sendJson('POST', '/api/files/folders', { root, path: path + name }))
  }

  const remove = (name: string, folder: boolean) => {
    if (!window.confirm(`Delete ${folder ? 'the empty folder' : ''} ${name}? This cannot be undone.`)) return
    act(`delete ${name}`, () => sendJson('DELETE', `/api/files?${query({ root, path: path + name, folder })}`))
  }

  return (
    <main
      className={`page files-page${dragging ? ' dragging' : ''}`}
      onDragOver={(e) => {
        if (!writable) return
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragging(false)
      }}
      onDrop={async (e) => {
        if (!writable) return
        e.preventDefault()
        setDragging(false)
        enqueue(await filesFromDrop(e.dataTransfer.items))
      }}
    >
      <div className="page-head">
        <div>
          <h1>Files</h1>
          <p className="muted">
            Upload raw reads and sample sheets, and download results. Files go straight to the private S3 bucket in
            ap-south-1.
          </p>
        </div>
      </div>

      <nav className="tabs root-tabs">
        {(roots.data ?? []).map((r) => (
          <button key={r.name} className={r.name === root ? 'tab on' : 'tab'} onClick={() => go(r.name, '')}>
            {r.label}
            {!r.writable && <span className="muted small"> · read-only</span>}
          </button>
        ))}
      </nav>

      <section className="card">
        <div className="files-bar">
          <nav className="crumbs" aria-label="Folder">
            <button className="link" onClick={() => go(root, '')}>
              {roots.data?.find((r) => r.name === root)?.label ?? root}
            </button>
            {crumbs.map((c, i) => (
              <span key={i}>
                <span className="muted"> / </span>
                <button className="link" onClick={() => go(root, crumbs.slice(0, i + 1).join('/') + '/')}>
                  {c}
                </button>
              </span>
            ))}
          </nav>
          <div className="head-actions">
            {writable && (
              <>
                <button onClick={() => fileInput.current?.click()}>Upload files</button>
                <button onClick={() => folderInput.current?.click()}>Upload folder</button>
                <button onClick={newFolder} disabled={busy !== null}>
                  New folder
                </button>
              </>
            )}
            <button onClick={reload} disabled={listing.loading}>
              {listing.loading ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
        </div>
        <input
          ref={fileInput}
          type="file"
          multiple
          hidden
          onChange={(e) => {
            enqueue(Array.from(e.target.files ?? []).map((file) => ({ path: file.name, file })))
            e.target.value = ''
          }}
        />
        <input
          ref={folderInput}
          type="file"
          hidden
          {...{ webkitdirectory: '' }}
          onChange={(e) => {
            enqueue(Array.from(e.target.files ?? []).map((file) => ({ path: file.webkitRelativePath || file.name, file })))
            e.target.value = ''
          }}
        />

        {actionError && <p className="error">{actionError}</p>}
        {listing.error && <p className="error">{listing.error}</p>}
        {!l && !listing.error && <p className="muted">Loading…</p>}
        {l && (
          <div className="table-wrap">
            <table className="files">
              <thead>
                <tr>
                  <th>Name</th>
                  <th className="num">Size</th>
                  <th>Modified</th>
                  <th className="num">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {path && (
                  <tr>
                    <td colSpan={4}>
                      <button className="link" onClick={() => go(root, crumbs.slice(0, -1).join('/') + (crumbs.length > 1 ? '/' : ''))}>
                        ↑ Up one folder
                      </button>
                    </td>
                  </tr>
                )}
                {l.folders.map((f) => (
                  <tr key={`d-${f}`}>
                    <td>
                      <button className="link file-name" onClick={() => go(root, `${path}${f}/`)}>
                        <FolderIcon /> {f}
                      </button>
                    </td>
                    <td className="num muted">–</td>
                    <td className="muted">–</td>
                    <td className="num row-actions">
                      {root === 'results' && !path && (
                        <Link to={`/runs/${encodeURIComponent(f)}/report`}>Report</Link>
                      )}
                      {writable && (
                        <button className="link danger" onClick={() => remove(f, true)} disabled={busy !== null}>
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {l.files.map((f) => (
                  <tr key={`f-${f.name}`}>
                    <td className="file-name">
                      <FileIcon /> {f.name}
                    </td>
                    <td className="num">{formatBytes(f.size)}</td>
                    <td>{formatTime(f.modified)}</td>
                    <td className="num row-actions">
                      {f.name.endsWith('.html') && (
                        <button className="link" onClick={() => download(f.name, true)} disabled={busy !== null}>
                          View
                        </button>
                      )}
                      <button className="link" onClick={() => download(f.name)} disabled={busy !== null}>
                        Download
                      </button>
                      {writable && (
                        <button className="link danger" onClick={() => remove(f.name, false)} disabled={busy !== null}>
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {!l.folders.length && !l.files.length && (
                  <tr>
                    <td colSpan={4} className="muted empty">
                      {writable ? 'This folder is empty. Drop files or folders here, or use Upload.' : 'This folder is empty.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            {l.next_token && <p className="muted small">Showing the first 1,000 items.</p>}
          </div>
        )}
        {writable && <p className="drop-hint muted small">Drag files or whole run folders anywhere on this page to upload them here.</p>}
      </section>

      <UploadPanel />
      {dragging && <div className="drop-overlay">Drop to upload to {root}/{path}</div>}
    </main>
  )
}

function FolderIcon() {
  return (
    <svg className="icon" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M1.5 3.5h4l1.5 1.5h7.5v8h-13z" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  )
}

function FileIcon() {
  return (
    <svg className="icon muted" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3.5 1.5h6l3 3v10h-9z M9.5 1.5v3h3" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  )
}
