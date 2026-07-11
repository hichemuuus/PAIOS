import { useState } from 'react'
import type { ToolCall } from '../../lib/execution'
import { fmtMs } from '../../lib/format'

/**
 * Card showing one tool invocation: name, arguments (expandable), and result
 * status with output preview. Pairs tool.request + tool.result events.
 */
export function ToolCallCard({ call }: { call: ToolCall }) {
  const [expanded, setExpanded] = useState(false)
  const hasResult = !!call.result
  const argKeys = Object.keys(call.arguments)

  return (
    <div className="rounded-md border border-ink-800/60 bg-ink-900/40 p-2.5">
      <div className="flex items-center gap-2">
        <span
          className={`flex h-6 w-6 items-center justify-center rounded font-mono text-[11px] ${
            !hasResult
              ? 'bg-sig-500/15 text-sig-300 animate-pulseDot'
              : call.result?.ok
              ? 'bg-ok-500/15 text-ok-400'
              : 'bg-bad-500/15 text-bad-400'
          }`}
        >
          ⚙
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-medium text-gray-200">{call.tool}</span>
            <span className="font-mono text-[10px] text-ink-500">
              iter {call.iteration || '—'}
            </span>
          </div>
        </div>
        {hasResult ? (
          <div className="flex items-center gap-2">
            <span
              className={`font-mono text-[10px] ${
                call.result?.ok ? 'text-ok-400' : 'text-bad-400'
              }`}
            >
              {call.result?.ok ? '✓ ok' : '✕ fail'}
            </span>
            <span className="data-mono text-[10px] text-ink-500">
              {fmtMs(call.result?.duration_ms ?? 0)}
            </span>
          </div>
        ) : (
          <span className="font-mono text-[10px] text-sig-300 animate-pulseDot">running…</span>
        )}
      </div>

      {/* Arguments */}
      {argKeys.length > 0 ? (
        <div className="mt-2">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 font-mono text-[10px] text-ink-400 hover:text-ink-200"
          >
            <span>{expanded ? '▾' : '▸'}</span>
            <span className="hud-label">arguments</span>
            <span className="text-ink-600">({argKeys.length})</span>
          </button>
          {expanded ? (
            <pre className="mt-1 max-h-40 overflow-auto rounded bg-ink-950/60 p-2 font-mono text-[10px] text-ink-300">
              {JSON.stringify(call.arguments, null, 2)}
            </pre>
          ) : (
            <div className="mt-1 flex flex-wrap gap-1">
              {argKeys.slice(0, 4).map((k) => (
                <span
                  key={k}
                  className="rounded border border-ink-700/60 bg-ink-850/60 px-1.5 py-0.5 font-mono text-[10px] text-ink-400"
                >
                  {k}
                </span>
              ))}
              {argKeys.length > 4 ? (
                <span className="font-mono text-[10px] text-ink-500">
                  +{argKeys.length - 4}
                </span>
              ) : null}
            </div>
          )}
        </div>
      ) : null}

      {/* Result preview */}
      {hasResult && call.result?.output_preview ? (
        <div className="mt-2">
          <div className="hud-label mb-1">output</div>
          <pre className="max-h-32 overflow-auto whitespace-pre-wrap break-words rounded bg-ink-950/60 p-2 font-mono text-[10px] text-ink-300">
            {call.result.output_preview}
          </pre>
        </div>
      ) : null}

      {hasResult && !call.result?.ok && call.result?.output_preview ? (
        <div className="mt-1 text-[10px] text-bad-400">tool failed — see output above</div>
      ) : null}
    </div>
  )
}
