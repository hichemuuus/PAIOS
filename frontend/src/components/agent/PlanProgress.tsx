import { useMemo } from 'react'
import type { WsEvent } from '../../api/types'
import {
  extractPlan,
  planPercent,
  STEP_STATUS_TONE,
  STEP_STATUS_GLYPH,
} from '../../lib/execution'
import { TONE_RING, TONE_DOT } from '../../lib/format'

const TONE_NODE: Record<string, string> = {
  ok: 'border-ok-500/60 bg-ok-500/15 text-ok-400',
  active: 'border-sig-400/60 bg-sig-500/15 text-sig-300',
  warn: 'border-warn-500/60 bg-warn-500/15 text-warn-400',
  fail: 'border-bad-500/60 bg-bad-500/15 text-bad-400',
  idle: 'border-ink-600/60 bg-ink-700/40 text-ink-400',
}

/**
 * Plan execution panel — shows the DAG-decomposed steps with verifier
 * status (completed / failed / error), retry count, and per-step tool calls.
 * Only renders when plan.* events have been emitted for this task.
 */
export function PlanProgress({ events }: { events: WsEvent[] }) {
  const plan = useMemo(() => extractPlan(events), [events])

  if (!plan.started) return null

  const pct = planPercent(plan)
  const activeStep = plan.steps.find((s) => s.status === 'running')

  return (
    <div className="rounded-lg border border-ink-800/70 bg-ink-900/40 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="hud-label text-violet-300">Plan Execution</span>
          {plan.replanned > 0 ? (
            <span className="rounded border border-warn-500/40 px-1 py-px font-mono text-[9px] uppercase text-warn-400">
              ↻ replanned ×{plan.replanned}
            </span>
          ) : null}
          {plan.synthesized ? (
            <span className="rounded border border-ok-500/40 px-1 py-px font-mono text-[9px] uppercase text-ok-400">
              ✓ synthesized
            </span>
          ) : null}
        </div>
        <span className="data-mono text-[10px] text-ink-500">
          {plan.completed + plan.failed}/{plan.stepCount} steps
        </span>
      </div>

      {/* Plan progress bar */}
      <div className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-ink-800/80">
        <div
          className="h-full bg-gradient-to-r from-violet-500/70 to-sig-300 transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Active step indicator */}
      {activeStep ? (
        <div className="mb-2 flex items-center gap-2 rounded border border-sig-400/30 bg-sig-500/5 px-2 py-1">
          <span className="h-1.5 w-1.5 rounded-full bg-sig-400 animate-pulseDot" />
          <span className="hud-label">Executing</span>
          <span className="truncate font-mono text-[11px] text-sig-200">{activeStep.goal}</span>
        </div>
      ) : null}

      {/* Step list */}
      <ol className="relative">
        <div className="absolute bottom-2 left-[11px] top-2 w-px bg-gradient-to-b from-violet-700/60 via-ink-700/40 to-transparent" />
        {plan.steps.map((step, i) => {
          const tone = STEP_STATUS_TONE[step.status]
          return (
            <li key={step.key} className={`relative pl-8 ${i === plan.steps.length - 1 ? 'pb-1' : 'pb-3'}`}>
              <div
                className={`absolute left-0 top-0.5 flex h-6 w-6 items-center justify-center rounded-md border font-mono text-[11px] ${TONE_NODE[tone]}`}
              >
                {STEP_STATUS_GLYPH[step.status]}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-xs font-medium text-gray-200">{step.goal}</span>
                  {step.retry > 0 ? (
                    <span className="rounded border border-warn-500/30 px-1 py-px font-mono text-[9px] text-warn-400">
                      retry {step.retry}
                    </span>
                  ) : null}
                  <span
                    className={`rounded-full border px-1.5 py-px font-mono text-[9px] uppercase ${TONE_RING[tone]}`}
                  >
                    <span className={`mr-1 inline-block h-1 w-1 rounded-full ${TONE_DOT[tone]}`} />
                    {step.status}
                  </span>
                </div>
                {step.error ? (
                  <p className="mt-0.5 truncate font-mono text-[10px] text-bad-400/80" title={step.error}>
                    {step.error}
                  </p>
                ) : null}
                {step.toolCalls.length > 0 ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {step.toolCalls.map((tc, j) => (
                      <span
                        key={j}
                        className={`inline-flex items-center gap-1 rounded border px-1.5 py-px font-mono text-[10px] ${
                          tc.ok
                            ? 'border-ok-500/30 text-ok-400'
                            : 'border-bad-500/30 text-bad-400'
                        }`}
                      >
                        ⚙ {tc.tool}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>

      {plan.steps.length === 0 && plan.created ? (
        <p className="font-mono text-[11px] text-ink-500">
          {plan.stepCount} step(s) planned — waiting for execution to begin.
        </p>
      ) : null}
    </div>
  )
}
