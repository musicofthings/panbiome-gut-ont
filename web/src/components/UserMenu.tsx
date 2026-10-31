import { authEnabled, signedInEmail, signOut } from '../auth'

export function UserMenu() {
  if (!authEnabled()) return <span className="muted small topbar-sub">panbiome-gut-ont · AWS ap-south-1</span>
  return (
    <span className="user-menu small">
      <span className="muted topbar-sub">{signedInEmail()}</span>
      <button className="link" onClick={() => void signOut()}>
        Sign out
      </button>
    </span>
  )
}
