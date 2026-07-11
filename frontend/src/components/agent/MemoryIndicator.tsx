import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { MemoryStats } from '../../api/types'

/**
 * Compact chip showing the agent's memory state — total count, high-importance
 * count, and recent recall activity. Polls `/api/memory/stats` periodically.
 *
 * This is an indicator only; it does not expose memory contents in the
 * workspace. The Memory Center page is the place to browse memories.
 */
export function MemoryIndicator({ active }: { active: boolean }) {
  const [stats, setStats] = useState<MemoryStats | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const s = await api.memoryStats()
        if (!cancelled) setStats(s)
      } catch {
        // Memory stats are best-effort.
      }
    }
    load()
    const id = window.setInterval(load, 15000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  if (!stats) {
    return (
      <div className="flex items-center gap-1.5 rounded border border-ink-700/60 bg-ink-900/40 px-2 py-1">
        <span className="h-1.5 w-1.5 rounded-full bg-ink-600" />
        <span className="hud-label">Memory</span>
        <span className="font-mono text-[10px] text-ink-500">—</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 rounded border border-ink-700/60 bg-ink-900/40 px-2 py-1">
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          active ? 'bg-sig-400 animate-pulseDot' : 'bg-violet-400'
        }`}
      />
      <span className="hud-label">Memory</span>
      <span className="data-mono text-[10px] text-violet-300">{stats.total}</span>
      <span className="font-mono text-[10px] text-ink-500">total</span>
      <span className="text-ink-700">·</span>
      <span className="data-mono text-[10px] text-ok-400">{stats.by_importance.high}</span>
      <span className="font-mono text-[10px] text-ink-500">high</span>
      {stats.total_recalls > 0 ? (
        <>
          <span className="text-ink-700">·</span>
          <span className="data-mono text-[10px] text-sig-300">{stats.total_recalls}</span>
          <span className="font-mono text-[10px] text-ink-500">recalls</span>
        </>
      ) : null}
      {stats.decayed > 0 ? (
        <>
          <span className="text-ink-700">·</span>
          <span className="data-mono text-[10px] text-warn-400">{stats.decayed}</span>
          <span className="font-mono text-[10px] text-ink-500">decayed</span>
        </>
      ) : null}
    </div>
  )
}
