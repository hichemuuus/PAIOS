import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { Memory, MemoryStats, MemoryUpdate } from '../api/types'
import { useAppStore } from '../stores/appStore'
import {
  LoadingSpinner,
  ErrorBox,
  EmptyState,
  Button,
} from '../components/ui'
import { Stat } from '../components/ui/Stat'
import { fmtRelative, fmtPct } from '../lib/format'

const CATEGORIES = ['all', 'user', 'project', 'history', 'skill'] as const
type CategoryFilter = (typeof CATEGORIES)[number]

const IMPORTANCE_FILTERS = [
  { label: 'all', min: 0.0 },
  { label: 'high', min: 0.67 },
  { label: 'medium', min: 0.34 },
  { label: 'low', min: 0.0 },
] as const
type ImportanceKey = 'all' | 'high' | 'medium' | 'low'

export function MemoryCenterPage() {
  const [memories, setMemories] = useState<Memory[]>([])
  const [stats, setStats] = useState<MemoryStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingStats, setLoadingStats] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState<CategoryFilter>('all')
  const [importance, setImportance] = useState<ImportanceKey>('all')
  const [includeDecayed, setIncludeDecayed] = useState(false)
  const [editing, setEditing] = useState<Memory | null>(null)
  const pushToast = useAppStore((s) => s.pushToast)

  const loadStats = useCallback(async () => {
    setLoadingStats(true)
    try {
      const s = await api.memoryStats()
      setStats(s)
    } catch {
      // Stats are best-effort; ignore failures.
    } finally {
      setLoadingStats(false)
    }
  }, [])

  const loadMemories = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const trimmed = query.trim()
      const categoryParam = category === 'all' ? undefined : category
      const minImportance =
        importance === 'all' ? undefined : IMPORTANCE_FILTERS.find((f) => f.label === importance)?.min
      if (trimmed) {
        const res = await api.searchMemories(trimmed, {
          category: categoryParam,
          limit: 100,
        })
        // Apply local importance + decay filters on top of search results.
        let filtered = res.memories
        if (minImportance != null) filtered = filtered.filter((m) => m.importance >= minImportance)
        if (!includeDecayed) filtered = filtered.filter((m) => !m.decayed)
        setMemories(filtered)
      } else {
        const res = await api.listMemories({
          limit: 100,
          category: categoryParam,
          min_importance: minImportance,
          include_decayed: includeDecayed,
        })
        setMemories(res.memories)
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [query, category, importance, includeDecayed])

  useEffect(() => {
    loadStats()
  }, [loadStats])

  useEffect(() => {
    loadMemories()
  }, [loadMemories])

  async function handleSave(updated: MemoryUpdate, mem: Memory) {
    try {
      await api.updateMemory(mem.public_id, updated)
      pushToast('ok', 'Memory updated')
      setEditing(null)
      await Promise.all([loadMemories(), loadStats()])
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e)
      pushToast('fail', `Update failed: ${msg}`)
    }
  }

  async function handleDelete(mem: Memory) {
    if (!confirm(`Delete this ${mem.category} memory? This cannot be undone.`)) return
    try {
      await api.deleteMemory(mem.public_id)
      pushToast('ok', 'Memory deleted')
      await Promise.all([loadMemories(), loadStats()])
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e)
      pushToast('fail', `Delete failed: ${msg}`)
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-100">Memory Center</h1>
          <p className="mt-0.5 text-xs text-ink-400">
            Long-term agent memory — browse, search, score, edit, and prune by category & importance.
          </p>
        </div>
        <button
          onClick={() => Promise.all([loadMemories(), loadStats()])}
          className="focus-ring rounded-md border border-ink-700/60 px-3 py-1.5 text-xs text-ink-300 hover:bg-ink-800/60"
        >
          ↻ Refresh
        </button>
      </header>

      {/* Stats strip */}
      <section className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-5">
        <Stat
          label="Total"
          value={loadingStats ? '—' : stats?.total ?? 0}
          tone="default"
        />
        <Stat
          label="High importance"
          value={loadingStats ? '—' : stats?.by_importance.high ?? 0}
          tone="ok"
        />
        <Stat
          label="Decayed"
          value={loadingStats ? '—' : stats?.decayed ?? 0}
          tone={stats && stats.decayed > 0 ? 'warn' : 'default'}
        />
        <Stat
          label="Total recalls"
          value={loadingStats ? '—' : stats?.total_recalls ?? 0}
          tone="active"
        />
        <Stat
          label="Categories"
          value={loadingStats ? '—' : Object.keys(stats?.by_category ?? {}).length}
          sub={stats ? Object.entries(stats.by_category).map(([k, v]) => `${k}:${v}`).join(' · ') : undefined}
        />
      </section>

      {/* Filters */}
      <section className="panel mt-4 p-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search memory content…"
            className="focus-ring h-9 flex-1 rounded-md border border-ink-700/70 bg-ink-900/70 px-3 text-sm text-gray-100 placeholder:text-ink-600"
          />
          <div className="flex items-center gap-1 rounded-md border border-ink-700/60 bg-ink-900/40 p-0.5">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                onClick={() => setCategory(c)}
                className={`focus-ring rounded px-2.5 py-1 font-mono text-[11px] uppercase ${
                  category === c ? 'bg-sig-500/15 text-sig-200' : 'text-ink-400 hover:text-gray-200'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 rounded-md border border-ink-700/60 bg-ink-900/40 p-0.5">
            {IMPORTANCE_FILTERS.map((f) => (
              <button
                key={f.label}
                onClick={() => setImportance(f.label as ImportanceKey)}
                className={`focus-ring rounded px-2.5 py-1 font-mono text-[11px] uppercase ${
                  importance === f.label
                    ? 'bg-violet-500/15 text-violet-300'
                    : 'text-ink-400 hover:text-gray-200'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-1.5 font-mono text-[11px] text-ink-400">
            <input
              type="checkbox"
              checked={includeDecayed}
              onChange={(e) => setIncludeDecayed(e.target.checked)}
              className="accent-warn-400"
            />
            show decayed
          </label>
        </div>
      </section>

      {error ? (
        <div className="mt-4">
          <ErrorBox message={error} onRetry={loadMemories} />
        </div>
      ) : null}

      {/* Memory list */}
      <section className="mt-4">
        {loading ? (
          <div className="panel">
            <LoadingSpinner label="Loading memories" />
          </div>
        ) : memories.length === 0 ? (
          <div className="panel">
            <EmptyState
              icon="◎"
              title="No memories match"
              hint="Try a different search, category, or importance filter. Memories are created by the agent during reflection."
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {memories.map((m) => (
              <MemoryCard
                key={m.public_id}
                memory={m}
                onEdit={() => setEditing(m)}
                onDelete={() => handleDelete(m)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Edit modal */}
      {editing ? (
        <EditMemoryModal
          memory={editing}
          onCancel={() => setEditing(null)}
          onSave={(patch) => handleSave(patch, editing)}
        />
      ) : null}
    </div>
  )
}

function MemoryCard({
  memory,
  onEdit,
  onDelete,
}: {
  memory: Memory
  onEdit: () => void
  onDelete: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const tone = memory.importance >= 0.67 ? 'ok' : memory.importance >= 0.34 ? 'warn' : 'idle'
  return (
    <div
      className={`panel flex flex-col p-3 ${
        memory.decayed ? 'opacity-60' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={`rounded border px-1.5 py-px font-mono text-[10px] uppercase ${
              memory.category === 'user'
                ? 'border-sig-400/40 text-sig-300'
                : memory.category === 'project'
                ? 'border-violet-400/40 text-violet-300'
                : memory.category === 'skill'
                ? 'border-ok-500/40 text-ok-400'
                : 'border-ink-600/60 text-ink-300'
            }`}
          >
            {memory.category}
          </span>
          {memory.decayed ? (
            <span className="rounded border border-warn-500/40 px-1 py-px font-mono text-[9px] uppercase text-warn-400">
              decayed
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="data-mono text-[10px] text-ink-500">
            imp {fmtPct(memory.importance * 100, 0)}
          </span>
          <div className="h-1.5 w-12 overflow-hidden rounded-full bg-ink-800/80">
            <div
              className={`h-full ${
                tone === 'ok'
                  ? 'bg-ok-500'
                  : tone === 'warn'
                  ? 'bg-warn-500'
                  : 'bg-ink-500'
              }`}
              style={{ width: `${memory.importance * 100}%` }}
            />
          </div>
        </div>
      </div>

      <p
        className={`mt-2 text-xs text-ink-200 ${
          expanded ? '' : 'line-clamp-3'
        }`}
      >
        {memory.content}
      </p>
      {memory.content.length > 180 ? (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-1 self-start font-mono text-[10px] text-sig-400 hover:underline"
        >
          {expanded ? '▾ less' : '▸ more'}
        </button>
      ) : null}

      {/* Quality + recall row */}
      <div className="mt-2 grid grid-cols-3 gap-2 border-t border-ink-800/60 pt-2">
        <Quality label="useful" value={memory.usefulness_score} />
        <Quality label="reliable" value={memory.reliability_score} />
        <Quality label="success" value={memory.success_frequency} />
      </div>

      {/* Meta row */}
      <div className="mt-2 flex items-center justify-between font-mono text-[10px] text-ink-500">
        <div className="flex items-center gap-2">
          <span title="created">{fmtRelative(memory.created_at)}</span>
          <span>·</span>
          <span title="recall count">↻ {memory.recall_count}</span>
          {memory.last_recalled_at ? (
            <>
              <span>·</span>
              <span title="last recalled">{fmtRelative(memory.last_recalled_at)}</span>
            </>
          ) : null}
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={onEdit}>
            Edit
          </Button>
          <Button variant="ghost" size="sm" onClick={onDelete}>
            Delete
          </Button>
        </div>
      </div>

      {memory.tags ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {memory.tags
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean)
            .map((t) => (
              <span
                key={t}
                className="rounded border border-ink-700/60 bg-ink-850/60 px-1.5 py-0.5 font-mono text-[10px] text-ink-400"
              >
                #{t}
              </span>
            ))}
        </div>
      ) : null}
    </div>
  )
}

function Quality({ label, value }: { label: string; value: number }) {
  const tone = value >= 0.67 ? 'text-ok-400' : value >= 0.34 ? 'text-warn-400' : 'text-ink-400'
  return (
    <div className="flex flex-col">
      <span className="hud-label">{label}</span>
      <span className={`data-mono text-[11px] ${tone}`}>{fmtPct(value * 100, 0)}</span>
    </div>
  )
}

function EditMemoryModal({
  memory,
  onCancel,
  onSave,
}: {
  memory: Memory
  onCancel: () => void
  onSave: (patch: MemoryUpdate) => void
}) {
  const [content, setContent] = useState(memory.content)
  const [importance, setImportance] = useState(memory.importance)
  const [tags, setTags] = useState(memory.tags)
  const dirty =
    content !== memory.content ||
    Math.abs(importance - memory.importance) > 0.001 ||
    tags !== memory.tags

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/70 p-4 backdrop-blur-sm">
      <div className="panel w-full max-w-2xl p-5">
        <div className="flex items-center justify-between">
          <span className="hud-label text-sig-300">Edit Memory</span>
          <span className="font-mono text-[10px] text-ink-500">
            {memory.public_id.slice(0, 12)}…
          </span>
        </div>

        <div className="mt-3">
          <label className="hud-label">Content</label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={8}
            className="focus-ring mt-1 w-full resize-y rounded-md border border-ink-700/70 bg-ink-900/70 p-2.5 text-xs text-gray-100"
          />
        </div>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <div>
            <label className="hud-label">Importance</label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={importance}
                onChange={(e) => setImportance(Number(e.target.value))}
                className="flex-1 accent-sig-400"
              />
              <span className="data-mono w-12 text-right text-xs text-gray-100">
                {fmtPct(importance * 100, 0)}
              </span>
            </div>
          </div>
          <div>
            <label className="hud-label">Tags (comma-separated)</label>
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="tag1, tag2"
              className="focus-ring mt-1 w-full rounded-md border border-ink-700/70 bg-ink-900/70 px-2.5 py-1.5 text-xs text-gray-100 placeholder:text-ink-600"
            />
          </div>
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => onSave({ content, importance, tags })}
            disabled={!dirty || !content.trim()}
          >
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  )
}
