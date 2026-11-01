import { useSyncExternalStore } from 'react'
import { ApiError, sendJson } from './api'

// Uploads go from the browser straight to S3: the API starts a multipart upload and signs each part,
// so files of any size never pass through the API. They keep running while you browse other pages.

const PARALLEL_PARTS = 4
const PARALLEL_FILES = 2
const URL_BATCH = 50
const RETRIES = 4

export type UploadState = 'queued' | 'uploading' | 'done' | 'failed' | 'cancelled' | 'exists'

export interface Upload {
  id: number
  root: string
  path: string
  file: File
  state: UploadState
  sent: number
  error: string | null
  started: number | null
  finished: number | null
}

interface Started {
  key: string
  upload_id: string | null
  part_size: number
  parts: number
}

let nextId = 1
let uploads: Upload[] = []
const controllers = new Map<number, AbortController>()
const listeners = new Set<() => void>()
const doneListeners = new Set<(u: Upload) => void>()

function emit() {
  uploads = [...uploads]
  for (const l of listeners) l()
}

function update(id: number, patch: Partial<Upload>) {
  const u = uploads.find((x) => x.id === id)
  if (!u) return
  Object.assign(u, patch)
  emit()
}

export function useUploads(): Upload[] {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => uploads,
  )
}

/** Called whenever a file finishes uploading, so the open folder can refresh. */
export function onUploaded(fn: (u: Upload) => void): () => void {
  doneListeners.add(fn)
  return () => doneListeners.delete(fn)
}

export function addUploads(root: string, items: { path: string; file: File }[]) {
  for (const { path, file } of items) {
    uploads.push({ id: nextId++, root, path, file, state: 'queued', sent: 0, error: null, started: null, finished: null })
  }
  emit()
  pump()
}

export function cancelUpload(id: number) {
  const c = controllers.get(id)
  if (c) c.abort()
  else update(id, { state: 'cancelled' })
}

export function retryUpload(id: number, overwrite = false) {
  update(id, { state: 'queued', sent: 0, error: null, started: null, finished: null })
  pump(overwrite ? id : undefined)
}

export function clearFinished() {
  uploads = uploads.filter((u) => u.state === 'queued' || u.state === 'uploading')
  emit()
}

export function uploading(): boolean {
  return uploads.some((u) => u.state === 'queued' || u.state === 'uploading')
}

window.addEventListener('beforeunload', (e) => {
  if (uploading()) e.preventDefault()
})

const overwriteIds = new Set<number>()

function pump(overwriteId?: number) {
  if (overwriteId !== undefined) overwriteIds.add(overwriteId)
  const running = uploads.filter((u) => u.state === 'uploading').length
  const queued = uploads.filter((u) => u.state === 'queued')
  for (const u of queued.slice(0, Math.max(0, PARALLEL_FILES - running))) {
    run(u).finally(pump)
  }
}

async function run(u: Upload) {
  const controller = new AbortController()
  controllers.set(u.id, controller)
  update(u.id, { state: 'uploading', started: Date.now() })
  let started: Started | null = null
  try {
    started = await sendJson<Started>('POST', '/api/uploads', {
      root: u.root,
      path: u.path,
      size: u.file.size,
      overwrite: overwriteIds.has(u.id),
    })
    if (started.upload_id) await sendParts(u, started, controller.signal)
    update(u.id, { state: 'done', sent: u.file.size, finished: Date.now() })
    for (const fn of doneListeners) fn(u)
  } catch (e) {
    const cancelled = controller.signal.aborted
    if (started?.upload_id) {
      sendJson('POST', '/api/uploads/abort', { key: started.key, upload_id: started.upload_id }).catch(() => {})
    }
    if (e instanceof ApiError && e.status === 409) update(u.id, { state: 'exists', error: e.message })
    else update(u.id, { state: cancelled ? 'cancelled' : 'failed', error: cancelled ? null : (e as Error).message })
  } finally {
    controllers.delete(u.id)
    overwriteIds.delete(u.id)
  }
}

async function sendParts(u: Upload, s: Started, signal: AbortSignal) {
  const sentByPart = new Map<number, number>()
  const etags: { part_number: number; etag: string }[] = []
  const urls = new Map<number, string>()
  let next = 1

  const report = () => {
    let sent = 0
    for (const v of sentByPart.values()) sent += v
    update(u.id, { sent })
  }

  const urlFor = async (n: number) => {
    if (!urls.has(n)) {
      const want = []
      for (let i = n; i < n + URL_BATCH && i <= s.parts; i++) want.push(i)
      const got = await sendJson<{ urls: Record<string, string> }>('POST', '/api/uploads/parts', {
        key: s.key,
        upload_id: s.upload_id,
        part_numbers: want,
      })
      for (const [k, v] of Object.entries(got.urls)) urls.set(Number(k), v)
    }
    return urls.get(n)!
  }

  const worker = async () => {
    while (next <= s.parts) {
      const n = next++
      const blob = u.file.slice((n - 1) * s.part_size, Math.min(n * s.part_size, u.file.size))
      for (let attempt = 1; ; attempt++) {
        try {
          const etag = await putPart(await urlFor(n), blob, signal, (loaded) => {
            sentByPart.set(n, loaded)
            report()
          })
          etags.push({ part_number: n, etag })
          break
        } catch (e) {
          if (signal.aborted || attempt >= RETRIES) throw e
          // A presigned URL may have expired during a long upload; sign it again
          urls.delete(n)
          await new Promise((r) => setTimeout(r, 1000 * 2 ** attempt))
        }
      }
    }
  }

  await Promise.all(Array.from({ length: Math.min(PARALLEL_PARTS, s.parts) }, worker))
  await sendJson('POST', '/api/uploads/complete', { key: s.key, upload_id: s.upload_id, parts: etags })
}

/** XMLHttpRequest rather than fetch, for upload progress. */
function putPart(url: string, blob: Blob, signal: AbortSignal, progress: (loaded: number) => void): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', url)
    xhr.upload.onprogress = (e) => progress(e.loaded)
    xhr.onload = () => {
      const etag = xhr.getResponseHeader('ETag')
      if (xhr.status >= 200 && xhr.status < 300 && etag) {
        progress(blob.size)
        resolve(etag)
      } else if (xhr.status >= 200 && xhr.status < 300) {
        reject(new Error('S3 did not expose the ETag header; check the bucket CORS rule'))
      } else {
        reject(new Error(`S3 returned ${xhr.status}`))
      }
    }
    xhr.onerror = () => reject(new Error('Network error while uploading (or blocked by the bucket CORS rule)'))
    xhr.onabort = () => reject(new DOMException('Cancelled', 'AbortError'))
    signal.addEventListener('abort', () => xhr.abort(), { once: true })
    xhr.send(blob)
  })
}

/** Files from a drop, including the contents of dropped folders, with their relative paths. */
export async function filesFromDrop(items: DataTransferItemList): Promise<{ path: string; file: File }[]> {
  const entries = Array.from(items)
    .map((i) => i.webkitGetAsEntry())
    .filter((e): e is FileSystemEntry => e !== null)
  const out: { path: string; file: File }[] = []
  const walk = async (entry: FileSystemEntry, prefix: string): Promise<void> => {
    if (entry.isFile) {
      const file = await new Promise<File>((res, rej) => (entry as FileSystemFileEntry).file(res, rej))
      out.push({ path: prefix + entry.name, file })
    } else if (entry.isDirectory) {
      const reader = (entry as FileSystemDirectoryEntry).createReader()
      // readEntries returns at most 100 entries per call
      for (;;) {
        const batch = await new Promise<FileSystemEntry[]>((res, rej) => reader.readEntries(res, rej))
        if (!batch.length) break
        for (const child of batch) await walk(child, `${prefix}${entry.name}/`)
      }
    }
  }
  for (const e of entries) await walk(e, '')
  return out
}
