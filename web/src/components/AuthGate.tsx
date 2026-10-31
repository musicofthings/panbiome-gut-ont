import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { accessToken, CALLBACK_PATH, completeSignIn, loadAuthConfig } from '../auth'

type State = { kind: 'loading' } | { kind: 'ready' } | { kind: 'error'; message: string }

/** Renders the app once the user is signed in, or straight away when sign-in is off (local development). */
export function AuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const config = await loadAuthConfig()
      if (config && location.pathname === CALLBACK_PATH) {
        history.replaceState(null, '', await completeSignIn())
      } else if (config) {
        await accessToken()
      }
      if (!cancelled) setState({ kind: 'ready' })
    })().catch((e: unknown) => {
      if (!cancelled) setState({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    })
    return () => {
      cancelled = true
    }
  }, [])

  if (state.kind === 'ready') return children
  return (
    <main className="page">
      {state.kind === 'loading' ? (
        <p className="muted">Signing in…</p>
      ) : (
        <>
          <p className="error">{state.message}</p>
          <button onClick={() => location.assign('/')}>Try again</button>
        </>
      )}
    </main>
  )
}
