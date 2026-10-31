import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { accessToken, signIn } from './auth'

export type RunStatus = 'waiting' | 'starting' | 'running' | 'succeeded' | 'failed' | 'unknown'
export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed'
export type StepStatus = TaskStatus | 'pending' | 'skipped'

export interface RunSummary {
  name: string
  script: string | null
  status: RunStatus
  reason: string | null
  created: string | null
  started: string | null
  stopped: string | null
  head_job_id: string | null
}

export interface Task {
  process: string
  tag: string | null
  status: TaskStatus
  submitted: string | null
  duration_s: number | null
  peak_rss: string | null
  exit: string | null
  hash: string | null
  job_id: string | null
  reason?: string | null
}

export interface ProcessState {
  status: StepStatus
  counts: Partial<Record<TaskStatus, number>>
}

export interface RunDetail extends RunSummary {
  kind: 'pipeline' | 'utility'
  source: 'trace' | 'batch' | 'none'
  params: Record<string, unknown> | null
  processes: Record<string, ProcessState> | null
  tasks: Task[]
}

export interface PipelineGraph {
  stages: { id: string; label: string }[]
  processes: { id: string; stage: string; label: string; description: string }[]
  edges: { source: string; target: string }[]
}

export interface Report {
  path: string
  size: number
  url: string
}

export interface TaskLog {
  found: boolean
  workdir?: string
  command_sh?: string | null
  command_log?: string | null
  command_err?: string | null
}

export interface HeadLog {
  lines: string[] | null
  note: string | null
}

export async function getJson<T>(path: string): Promise<T> {
  const token = await accessToken()
  const res = await fetch(path, token ? { headers: { Authorization: `Bearer ${token}` } } : undefined)
  if (res.status === 401 && token) return signIn()
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ? String(body.detail) : `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export const ACTIVE: RunStatus[] = ['waiting', 'starting', 'running']

/** Fetch `path`, and again every `intervalMs` while `poll` is true. Results for an older path are dropped. */
export function useJson<T>(path: string | null, poll = false, intervalMs = 15000) {
  const [state, setState] = useState<{ path: string | null; data: T | null; error: string | null; updated: Date | null }>(
    { path: null, data: null, error: null, updated: null },
  )
  const [loading, setLoading] = useState(false)
  const current = useRef(path)
  useEffect(() => {
    current.current = path
  }, [path])

  const load = useCallback(async () => {
    if (!path) return
    setLoading(true)
    try {
      const data = await getJson<T>(path)
      if (current.current === path) setState({ path, data, error: null, updated: new Date() })
    } catch (e) {
      if (current.current === path) setState((s) => ({ ...s, path, error: (e as Error).message }))
    } finally {
      setLoading(false)
    }
  }, [path])

  useEffect(() => {
    load()
    if (!poll) return
    const id = setInterval(load, intervalMs)
    return () => clearInterval(id)
  }, [poll, load, intervalMs])

  const mine = state.path === path
  return {
    data: mine ? state.data : null,
    error: mine ? state.error : null,
    updated: mine ? state.updated : null,
    loading,
    reload: load,
  }
}

export function formatDuration(s: number | null | undefined): string {
  if (s == null) return '–'
  if (s < 1) return '<1s'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  if (h) return `${h}h ${String(m).padStart(2, '0')}m`
  if (m) return `${m}m ${String(sec).padStart(2, '0')}s`
  return `${sec}s`
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '–'
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function runDuration(run: RunSummary): number | null {
  if (!run.started) return null
  const end = run.stopped ? new Date(run.stopped) : new Date()
  return (end.getTime() - new Date(run.started).getTime()) / 1000
}

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      const m = window.matchMedia(query)
      m.addEventListener('change', notify)
      return () => m.removeEventListener('change', notify)
    },
    () => window.matchMedia(query).matches,
  )
}
