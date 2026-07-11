/**
 * Helpers for parsing execution events into structured views for the
 * AgentWorkspace: tool-call cards, plan-step progress, and verifier status.
 *
 * All data here is derived from the WebSocket event stream — no mock data.
 * Chain-of-thought (`agent.thinking`, `agent.iteration`) is deliberately
 * ignored; only actions, tools, results, and verifier outcomes are surfaced.
 */

import type { WsEvent } from '../api/types'

export interface ToolCall {
  /** Stable key for React rendering. */
  key: string
  tool: string
  iteration: number
  arguments: Record<string, unknown>
  /** Present once the matching tool.result event arrives. */
  result?: {
    ok: boolean
    output_preview: string
    duration_ms: number
  }
  /** Wall-clock when the request was emitted (ms). */
  startedAt: number
}

export interface PlanStepInfo {
  key: string
  stepId: string | null
  goal: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'error'
  retry: number
  error?: string
  /** Tool calls inside this step (from plan.step.tool events). */
  toolCalls: Array<{ tool: string; ok: boolean; output_preview?: string }>
}

export interface PlanSummary {
  started: boolean
  created: boolean
  stepCount: number
  stepGoals: string[]
  completed: number
  failed: number
  errors: number
  replanned: number
  synthesized: boolean
  steps: PlanStepInfo[]
}

/**
 * Pair tool.request and tool.result events into a list of tool calls.
 * Results are matched by tool name + iteration (the agent emits one pair
 * per iteration in ReAct mode). Falls back to "open" if no result yet.
 */
export function extractToolCalls(events: WsEvent[]): ToolCall[] {
  const calls: ToolCall[] = []
  for (const ev of events) {
    if (ev.type === 'tool.request') {
      const p = ev.payload as Record<string, unknown>
      calls.push({
        key: `${ev.ts}-${p.tool}-${calls.length}`,
        tool: String(p.tool ?? 'unknown'),
        iteration: Number(p.iteration ?? 0),
        arguments: (p.arguments as Record<string, unknown>) ?? {},
        startedAt: ev.ts * 1000,
      })
    } else if (ev.type === 'tool.result') {
      const p = ev.payload as Record<string, unknown>
      const tool = String(p.tool ?? '')
      const iteration = Number(p.iteration ?? 0)
      // Match the most recent open call for this tool + iteration.
      for (let i = calls.length - 1; i >= 0; i--) {
        const c = calls[i]
        if (c.tool === tool && c.iteration === iteration && !c.result) {
          c.result = {
            ok: Boolean(p.ok),
            output_preview: String(p.output_preview ?? ''),
            duration_ms: Number(p.duration_ms ?? 0),
          }
          break
        }
      }
    }
  }
  return calls
}

/**
 * Build a plan progress view from plan.* events. Steps are keyed by step_id
 * when present (planner emits it), otherwise by goal string.
 */
export function extractPlan(events: WsEvent[]): PlanSummary {
  const summary: PlanSummary = {
    started: false,
    created: false,
    stepCount: 0,
    stepGoals: [],
    completed: 0,
    failed: 0,
    errors: 0,
    replanned: 0,
    synthesized: false,
    steps: [],
  }

  const stepsByKey = new Map<string, PlanStepInfo>()
  const stepsByGoal = new Map<string, PlanStepInfo>()

  for (const ev of events) {
    const p = (ev.payload as Record<string, unknown>) ?? {}
    if (ev.type === 'plan.start') {
      summary.started = true
    } else if (ev.type === 'plan.created' || ev.type === 'plan.replanned') {
      if (ev.type === 'plan.replanned') summary.replanned += 1
      summary.created = true
      summary.stepCount = Number(p.step_count ?? 0)
      const goals = Array.isArray(p.steps) ? (p.steps as string[]) : []
      summary.stepGoals = goals
      // Reset step tracking on (re)plan — but preserve status for goals that
      // already exist so completed steps don't get demoted.
      for (const goal of goals) {
        const existing = stepsByGoal.get(goal)
        if (!existing) {
          const step: PlanStepInfo = {
            key: `${goal}-${stepsByKey.size}`,
            stepId: null,
            goal,
            status: 'pending',
            retry: 0,
            toolCalls: [],
          }
          stepsByGoal.set(goal, step)
          stepsByKey.set(step.key, step)
          summary.steps.push(step)
        }
      }
    } else if (ev.type === 'plan.step.start') {
      const goal = String(p.goal ?? '')
      const stepId = p.step_id != null ? String(p.step_id) : null
      const step = findStep(stepsByGoal, goal, stepId)
      step.status = 'running'
      step.retry = Number(p.retry ?? step.retry)
    } else if (ev.type === 'plan.step.tool') {
      const goal = String(p.goal ?? '')
      const step = findStep(stepsByGoal, goal, null)
      step.toolCalls.push({
        tool: String(p.tool ?? ''),
        ok: Boolean(p.ok),
        output_preview: p.output_preview != null ? String(p.output_preview) : undefined,
      })
    } else if (ev.type === 'plan.step.complete') {
      const goal = String(p.goal ?? '')
      const step = findStep(stepsByGoal, goal, null)
      if (step.status !== 'failed') step.status = 'completed'
      summary.completed += 1
    } else if (ev.type === 'plan.step.error') {
      const goal = String(p.goal ?? '')
      const step = findStep(stepsByGoal, goal, null)
      step.status = 'error'
      step.error = String(p.error ?? step.error)
      step.retry = Number(p.attempt ?? step.retry)
      summary.errors += 1
    } else if (ev.type === 'plan.step.failed') {
      const goal = String(p.goal ?? '')
      const step = findStep(stepsByGoal, goal, null)
      step.status = 'failed'
      step.error = String(p.error ?? step.error)
      summary.failed += 1
    } else if (ev.type === 'plan.synthesized') {
      summary.synthesized = true
    }
  }

  return summary
}

function findStep(
  byGoal: Map<string, PlanStepInfo>,
  goal: string,
  stepId: string | null,
): PlanStepInfo {
  let step = byGoal.get(goal)
  if (!step) {
    step = {
      key: `${goal}-${byGoal.size}`,
      stepId,
      goal,
      status: 'pending',
      retry: 0,
      toolCalls: [],
    }
    byGoal.set(goal, step)
  }
  if (stepId && !step.stepId) step.stepId = stepId
  return step
}

export function planPercent(plan: PlanSummary): number {
  if (plan.stepCount === 0) return 0
  const done = plan.completed + plan.failed
  return Math.min(100, (done / plan.stepCount) * 100)
}

export const STEP_STATUS_TONE: Record<PlanStepInfo['status'], 'ok' | 'active' | 'warn' | 'fail' | 'idle'> = {
  completed: 'ok',
  running: 'active',
  error: 'warn',
  failed: 'fail',
  pending: 'idle',
}

export const STEP_STATUS_GLYPH: Record<PlanStepInfo['status'], string> = {
  completed: '✓',
  running: '▸',
  error: '!',
  failed: '✕',
  pending: '·',
}
