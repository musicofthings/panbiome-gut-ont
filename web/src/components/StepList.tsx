import type { PipelineGraph, ProcessState, Task } from '../api'
import { StatusBadge } from './Status'

interface Props {
  graph: PipelineGraph
  processes: Record<string, ProcessState>
  tasks: Task[]
  showSkipped: boolean
  selected: string | null
  onSelect: (process: string | null) => void
}

/** The step graph as a vertical list of stages, for narrow screens. */
export function StepList({ graph, processes, tasks, showSkipped, selected, onSelect }: Props) {
  const visible = graph.processes.filter((p) => showSkipped || processes[p.id]?.status !== 'skipped')
  return (
    <div className="step-list">
      {graph.stages.map((stage) => {
        const steps = visible.filter((p) => p.stage === stage.id)
        if (!steps.length) return null
        return (
          <div key={stage.id}>
            <div className="stage-label">{stage.label}</div>
            {steps.map((p) => {
              const state = processes[p.id] ?? { status: 'pending', counts: {} }
              const mine = tasks.filter((t) => t.process === p.id)
              return (
                <button
                  key={p.id}
                  className={`step-row s-${state.status}${selected === p.id ? ' selected' : ''}`}
                  onClick={() => onSelect(selected === p.id ? null : p.id)}
                >
                  <span className="step-row-head">
                    <span className="step-label">{p.label}</span>
                    <StatusBadge status={state.status} />
                  </span>
                  {mine.length > 0 && (
                    <span className="chips">
                      {mine.map((t) => (
                        <span key={`${t.tag}-${t.job_id}`} className={`chip s-${t.status}`}>
                          {t.tag ?? 'run'}
                        </span>
                      ))}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
