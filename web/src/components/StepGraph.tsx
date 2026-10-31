import { Background, Controls, Handle, MarkerType, Position, ReactFlow } from '@xyflow/react'
import type { Edge, Node, NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useMemo } from 'react'
import type { PipelineGraph, ProcessState, StepStatus, Task } from '../api'

const COL_W = 228
const ROW_H = 100
const TOP = 44

type StepData = {
  label: string
  process: string
  state: ProcessState
  tasks: Task[]
  selected: boolean
}
type StageData = { label: string }

function StepNode({ data }: NodeProps<Node<StepData>>) {
  const { label, process, state, tasks, selected } = data
  const shown = tasks.slice(0, 6)
  return (
    <div className={`step s-${state.status}${selected ? ' selected' : ''}`} title={process}>
      <Handle type="target" id="l" position={Position.Left} />
      <Handle type="target" id="t" position={Position.Top} />
      <div className="step-head">
        <span className="dot" />
        <span className="step-label">{label}</span>
      </div>
      <div className="step-sub">{process}</div>
      {shown.length > 0 && (
        <div className="chips">
          {shown.map((t) => (
            <span key={`${t.tag}-${t.job_id}`} className={`chip s-${t.status}`} title={`${t.tag ?? process}: ${t.status}`}>
              {t.tag ?? 'run'}
            </span>
          ))}
          {tasks.length > shown.length && <span className="chip more">+{tasks.length - shown.length}</span>}
        </div>
      )}
      <Handle type="source" id="r" position={Position.Right} />
      <Handle type="source" id="b" position={Position.Bottom} />
      <Handle type="target" id="rt" position={Position.Right} />
    </div>
  )
}

function StageNode({ data }: NodeProps<Node<StageData>>) {
  return <div className="stage-label">{data.label}</div>
}

const nodeTypes = { step: StepNode, stage: StageNode }

interface Props {
  graph: PipelineGraph
  processes: Record<string, ProcessState>
  tasks: Task[]
  showSkipped: boolean
  selected: string | null
  onSelect: (process: string | null) => void
}

export function StepGraph({ graph, processes, tasks, showSkipped, selected, onSelect }: Props) {
  const { nodes, edges } = useMemo(() => {
    const visible = new Set(
      graph.processes.filter((p) => showSkipped || processes[p.id]?.status !== 'skipped').map((p) => p.id),
    )
    const stages = graph.stages.filter((s) => graph.processes.some((p) => p.stage === s.id && visible.has(p.id)))
    const byProcess = new Map<string, Task[]>()
    for (const t of tasks) byProcess.set(t.process, [...(byProcess.get(t.process) ?? []), t])

    const nodes: Node[] = []
    const column = new Map<string, number>()
    const rowOf = new Map<string, number>()
    stages.forEach((stage, col) => {
      nodes.push({
        id: `stage-${stage.id}`,
        type: 'stage',
        position: { x: col * COL_W, y: 0 },
        data: { label: stage.label },
        selectable: false,
        draggable: false,
      })
      graph.processes
        .filter((p) => p.stage === stage.id && visible.has(p.id))
        .forEach((p, row) => {
          column.set(p.id, col)
          rowOf.set(p.id, row)
          nodes.push({
            id: p.id,
            type: 'step',
            position: { x: col * COL_W, y: TOP + row * ROW_H },
            data: {
              label: p.label,
              process: p.id,
              state: processes[p.id] ?? { status: 'pending', counts: {} },
              tasks: byProcess.get(p.id) ?? [],
              selected: selected === p.id,
            } satisfies StepData,
            draggable: false,
          })
        })
    })

    const statusOf = (id: string): StepStatus => processes[id]?.status ?? 'pending'
    const edges: Edge[] = graph.edges
      .filter((e) => visible.has(e.source) && visible.has(e.target))
      .map((e) => {
        const done = statusOf(e.source) === 'completed'
        const color = done ? '#5b8f7d' : '#c3cad3'
        // Steps in one stage are stacked: link neighbours bottom to top, and others with a bracket on the right,
        // so no link runs behind a card.
        const sameStage = column.get(e.source) === column.get(e.target)
        const adjacent = sameStage && rowOf.get(e.target)! - rowOf.get(e.source)! === 1
        const route = !sameStage
          ? { sourceHandle: 'r', targetHandle: 'l', type: 'default' }
          : adjacent
            ? { sourceHandle: 'b', targetHandle: 't', type: 'straight' }
            : { sourceHandle: 'r', targetHandle: 'rt', type: 'smoothstep' }
        return {
          id: `${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          ...route,
          animated: statusOf(e.target) === 'running',
          style: { stroke: color, strokeWidth: done ? 1.6 : 1.2 },
          markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
        }
      })
    return { nodes, edges }
  }, [graph, processes, tasks, showSkipped, selected])

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.08 }}
      minZoom={0.12}
      maxZoom={1.5}
      nodesConnectable={false}
      elementsSelectable={false}
      onNodeClick={(_, n) => n.type === 'step' && onSelect(n.id === selected ? null : n.id)}
      onPaneClick={() => onSelect(null)}
    >
      <Background gap={24} color="#e4e8ec" />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}
