// Cognito managed login with the authorization code grant and PKCE. The deployed site serves /config.json
// (written by infra/aws/deploy_web.sh); without it, as under `npm run dev`, sign-in is off.
// Tokens live in sessionStorage, so they end with the tab. API Gateway checks the access token.

export interface AuthConfig {
  authDomain: string
  clientId: string
}

interface Tokens {
  access: string
  id: string
  refresh: string | null
  expiresAt: number
}

const TOKENS = 'panbiome.tokens'
const PENDING = 'panbiome.pkce'
export const CALLBACK_PATH = '/auth/callback'

let config: AuthConfig | null = null

export async function loadAuthConfig(): Promise<AuthConfig | null> {
  const res = await fetch('/config.json', { cache: 'no-store' })
  if (!res.ok || !res.headers.get('content-type')?.includes('application/json')) return null
  config = (await res.json()) as AuthConfig
  return config
}

function redirectUri() {
  return `${location.origin}${CALLBACK_PATH}`
}

function base64url(bytes: Uint8Array) {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function randomString() {
  return base64url(crypto.getRandomValues(new Uint8Array(32)))
}

function readTokens(): Tokens | null {
  try {
    const raw = sessionStorage.getItem(TOKENS)
    return raw ? (JSON.parse(raw) as Tokens) : null
  } catch {
    return null
  }
}

function saveTokens(body: { access_token: string; id_token: string; refresh_token?: string; expires_in: number }) {
  const previous = readTokens()
  const tokens: Tokens = {
    access: body.access_token,
    id: body.id_token,
    refresh: body.refresh_token ?? previous?.refresh ?? null,
    expiresAt: Date.now() + body.expires_in * 1000,
  }
  sessionStorage.setItem(TOKENS, JSON.stringify(tokens))
}

async function tokenRequest(params: Record<string, string>) {
  const res = await fetch(`https://${config!.authDomain}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_id: config!.clientId, ...params }),
  })
  if (!res.ok) throw new Error(`Sign-in failed (${res.status})`)
  saveTokens(await res.json())
}

export async function signIn(): Promise<never> {
  const verifier = randomString()
  const state = randomString()
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)))
  sessionStorage.setItem(PENDING, JSON.stringify({ verifier, state, returnTo: location.pathname + location.search }))
  const query = new URLSearchParams({
    response_type: 'code',
    client_id: config!.clientId,
    redirect_uri: redirectUri(),
    scope: 'openid email',
    code_challenge: base64url(digest),
    code_challenge_method: 'S256',
    state,
  })
  location.assign(`https://${config!.authDomain}/oauth2/authorize?${query}`)
  return new Promise<never>(() => {})
}

/** Exchanges the code on /auth/callback for tokens and returns the path to go back to. */
export async function completeSignIn(): Promise<string> {
  const query = new URLSearchParams(location.search)
  const pending = JSON.parse(sessionStorage.getItem(PENDING) ?? 'null') as {
    verifier: string
    state: string
    returnTo: string
  } | null
  sessionStorage.removeItem(PENDING)
  if (query.get('error')) throw new Error(query.get('error_description') ?? query.get('error')!)
  if (!pending || query.get('state') !== pending.state || !query.get('code')) throw new Error('Sign-in response did not match')
  await tokenRequest({
    grant_type: 'authorization_code',
    code: query.get('code')!,
    redirect_uri: redirectUri(),
    code_verifier: pending.verifier,
  })
  return pending.returnTo.startsWith('/') && !pending.returnTo.startsWith(CALLBACK_PATH) ? pending.returnTo : '/'
}

/** A valid access token, refreshed if it is about to expire; null when auth is off; signs in when needed. */
export async function accessToken(): Promise<string | null> {
  if (!config) return null
  let tokens = readTokens()
  if (tokens && tokens.expiresAt - Date.now() < 60_000 && tokens.refresh) {
    try {
      await tokenRequest({ grant_type: 'refresh_token', refresh_token: tokens.refresh })
      tokens = readTokens()
    } catch {
      tokens = null
    }
  }
  if (!tokens || tokens.expiresAt - Date.now() < 60_000) return signIn()
  return tokens.access
}

export function signedInEmail(): string | null {
  const id = readTokens()?.id
  if (!id) return null
  try {
    const payload = JSON.parse(atob(id.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.email === 'string' ? payload.email : null
  } catch {
    return null
  }
}

export function authEnabled() {
  return config !== null
}

export async function signOut() {
  const refresh = readTokens()?.refresh
  sessionStorage.removeItem(TOKENS)
  if (refresh) {
    await fetch(`https://${config!.authDomain}/oauth2/revoke`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ client_id: config!.clientId, token: refresh }),
    }).catch(() => undefined)
  }
  const query = new URLSearchParams({ client_id: config!.clientId, logout_uri: `${location.origin}/` })
  location.assign(`https://${config!.authDomain}/logout?${query}`)
}
