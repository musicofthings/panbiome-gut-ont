import type { RunStatus, StepStatus } from '../api'

const LABEL: Record<RunStatus | StepStatus, string> = {
  waiting: 'Waiting',
  starting: 'Starting',
  running: 'Running',
  succeeded: 'Succeeded',
  failed: 'Failed',
  unknown: 'Unknown',
  queued: 'Queued',
  completed: 'Done',
  pending: 'Not started',
  skipped: 'Not in this run',
}

export function StatusBadge({ status }: { status: RunStatus | StepStatus }) {
  return (
    <span className={`badge s-${status}`}>
      <span className="dot" />
      {LABEL[status] ?? status}
    </span>
  )
}
