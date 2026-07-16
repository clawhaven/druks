import { LoginSteps, useHarnessLogin } from './HarnessLogin'
import type { Account } from '../api/types'

// The unauthenticated door: connect a harness, get a session.
export function Landing({ onSignedIn }: { onSignedIn: (account: Account) => void }) {
  return (
    <div className="landing">
      <div className="landing-card">
        <h1>druks</h1>
        <p className="landing-hint">
          Sign in with the coding subscription your runs will use — connecting it is the login.
        </p>
        <LandingConnect name="codex" label="Connect Codex" onSignedIn={onSignedIn} />
        <LandingConnect name="claude" label="Connect Claude" onSignedIn={onSignedIn} />
      </div>
    </div>
  )
}

function LandingConnect({
  name,
  label,
  onSignedIn,
}: {
  name: string
  label: string
  onSignedIn: (account: Account) => void
}) {
  const flow = useHarnessLogin(name, onSignedIn)
  return (
    <div className="landing-connect">
      {!flow.challenge && (
        <button className="hr-conn-btn" onClick={() => void flow.start()} disabled={flow.busy}>
          {label}
        </button>
      )}
      <LoginSteps flow={flow} />
      {flow.error && <div className="hr-conn-error">{flow.error}</div>}
    </div>
  )
}
