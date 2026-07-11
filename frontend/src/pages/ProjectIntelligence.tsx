import { useState } from 'react'
import { api, ApiError } from '../api/client'
import type { ProjectAnalysis, ProjectIssue, ProjectTreeNode } from '../api/types'
import {
  ErrorBox,
  EmptyState,
  Button,
} from '../components/ui'
import { Stat } from '../components/ui/Stat'
import { StatusBadge } from '../components/ui/StatusBadge'
import { fmtBytes } from '../lib/format'

const SEVERITY_TONE: Record<string, 'ok' | 'warn' | 'fail' | 'idle'> = {
  low: 'idle',
  info: 'idle',
  medium: 'warn',
  high: 'fail',
}

const SEVERITY_GLYPH: Record<string, string> = {
  low: '·',
  info: 'i',
  medium: '!',
  high: '✕',
}

const MAX_DEPTH_DEFAULT = 5

export function ProjectIntelligencePage() {
  const [path, setPath] = useState('')
  const [maxDepth, setMaxDepth] = useState(MAX_DEPTH_DEFAULT)
  const [includeHidden, setIncludeHidden] = useState(false)
  const [analysis, setAnalysis] = useState<ProjectAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scanProgress, setScanProgress] = useState(0)

  async function analyze() {
    const trimmed = path.trim()
    if (!trimmed) return
    setLoading(true)
    setError(null)
    setAnalysis(null)
    setScanProgress(0)

    // Simulated scan progress — the endpoint is synchronous, but we animate
    // the scan bar so the user sees motion while the request is in flight.
    const progTimer = window.setInterval(() => {
      setScanProgress((p) => (p >= 92 ? p : p + Math.random() * 14))
    }, 250)

    try {
      const result = await api.analyzeProject({
        path: trimmed,
        max_depth: maxDepth,
        include_hidden: includeHidden,
      })
      setScanProgress(100)
      setAnalysis(result)
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)
      setError(msg)
    } finally {
      window.clearInterval(progTimer)
      setLoading(false)
    }
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      analyze()
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-100">Project Intelligence</h1>
          <p className="mt-0.5 text-xs text-ink-400">
            Scan a project directory — detect stack, dependencies, structure, issues, and recommendations.
          </p>
        </div>
      </header>

      {/* Scan form */}
      <section className="panel mt-4 p-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="hud-label">Project Path</span>
          <span className="font-mono text-[10px] text-ink-500">
            sandbox-validated · ⌘↵ to scan
          </span>
        </div>
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="/path/to/project (within sandbox roots)"
            className="focus-ring h-10 flex-1 rounded-md border border-ink-700/70 bg-ink-900/70 px-3 font-mono text-sm text-gray-100 placeholder:text-ink-600"
          />
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 font-mono text-[11px] text-ink-400">
              depth
              <input
                type="number"
                min={1}
                max={20}
                value={maxDepth}
                onChange={(e) => setMaxDepth(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
                className="focus-ring w-14 rounded border border-ink-700/70 bg-ink-900/70 px-2 py-1 text-center text-xs text-gray-100"
              />
            </label>
            <label className="flex items-center gap-1.5 font-mono text-[11px] text-ink-400">
              <input
                type="checkbox"
                checked={includeHidden}
                onChange={(e) => setIncludeHidden(e.target.checked)}
                className="accent-sig-400"
              />
              hidden
            </label>
            <Button
              variant="primary"
              onClick={analyze}
              disabled={loading || !path.trim()}
            >
              {loading ? 'Scanning…' : 'Scan →'}
            </Button>
          </div>
        </div>

        {/* Scan progress bar */}
        {loading ? (
          <div className="mt-3">
            <div className="scanbar h-1.5 w-full overflow-hidden rounded-full bg-ink-800/80">
              <div
                className="h-full bg-sig-400/70 transition-all duration-300"
                style={{ width: `${scanProgress}%` }}
              />
            </div>
            <div className="mt-1 flex justify-between font-mono text-[10px] text-ink-500">
              <span>analyzing structure · detecting stack · parsing dependencies</span>
              <span>{Math.round(scanProgress)}%</span>
            </div>
          </div>
        ) : null}
      </section>

      {error ? (
        <div className="mt-4">
          <ErrorBox message={error} />
        </div>
      ) : null}

      {!loading && !analysis && !error ? (
        <div className="panel mt-4">
          <EmptyState
            icon="◎"
            title="No project scanned yet"
            hint="Enter a project path above to analyze its structure, technologies, and issues."
          />
        </div>
      ) : null}

      {analysis ? <AnalysisResult analysis={analysis} /> : null}
    </div>
  )
}

function AnalysisResult({ analysis }: { analysis: ProjectAnalysis }) {
  return (
    <div className="mt-4 flex flex-col gap-4">
      {/* Summary stats */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="Files"
          value={analysis.file_count.toLocaleString()}
          tone="default"
          sub={fmtBytes(analysis.total_size_bytes)}
        />
        <Stat
          label="Technologies"
          value={analysis.technologies.length}
          tone="active"
          sub="detected"
        />
        <Stat
          label="Issues"
          value={analysis.issues.length}
          tone={analysis.issues.length > 0 ? 'warn' : 'ok'}
          sub={`${analysis.issues.filter((i) => i.severity === 'high').length} high`}
        />
        <Stat
          label="Recommendations"
          value={analysis.recommendations.length}
          tone="default"
        />
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Technologies */}
        <div className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="hud-label">Detected Stack</span>
            <span className="data-mono text-[10px] text-ink-500">
              {analysis.technologies.length} tech
            </span>
          </div>
          {analysis.technologies.length === 0 ? (
            <p className="font-mono text-[11px] text-ink-500">
              No technologies detected.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {analysis.technologies.map((tech) => (
                <div
                  key={tech.name}
                  className="rounded-md border border-ink-800/60 bg-ink-900/40 p-2.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-medium text-sig-300">
                      {tech.name}
                    </span>
                    <span className="data-mono text-[10px] text-ink-400">
                      {(tech.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-ink-800/80">
                    <div
                      className="h-full bg-gradient-to-r from-sig-500/70 to-sig-300"
                      style={{ width: `${Math.max(4, tech.confidence * 100)}%` }}
                    />
                  </div>
                  {tech.evidence.length > 0 ? (
                    <p className="mt-1.5 truncate font-mono text-[10px] text-ink-500">
                      {tech.evidence.join(' · ')}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Dependencies */}
        <div className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="hud-label">Dependencies</span>
            <span className="data-mono text-[10px] text-ink-500">
              {Object.keys(analysis.dependencies).length} manager(s)
            </span>
          </div>
          {Object.keys(analysis.dependencies).length === 0 ? (
            <p className="font-mono text-[11px] text-ink-500">
              No dependency files detected.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {Object.entries(analysis.dependencies).map(([mgr, deps]) => (
                <DependencyGroup key={mgr} manager={mgr} deps={deps} />
              ))}
            </div>
          )}
        </div>

        {/* Issues */}
        <div className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="hud-label">Issues Detected</span>
            <span className="data-mono text-[10px] text-ink-500">
              {analysis.issues.length} total
            </span>
          </div>
          {analysis.issues.length === 0 ? (
            <EmptyState icon="✓" title="No issues found" hint="Project looks clean." />
          ) : (
            <div className="flex flex-col gap-1.5">
              {analysis.issues.map((issue, i) => (
                <IssueRow key={i} issue={issue} />
              ))}
            </div>
          )}
        </div>

        {/* Recommendations */}
        <div className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="hud-label">Recommendations</span>
            <span className="data-mono text-[10px] text-ink-500">
              {analysis.recommendations.length} suggestion(s)
            </span>
          </div>
          {analysis.recommendations.length === 0 ? (
            <EmptyState icon="✓" title="No recommendations" hint="Nothing to flag." />
          ) : (
            <ul className="flex flex-col gap-2">
              {analysis.recommendations.map((rec, i) => (
                <li
                  key={i}
                  className="flex gap-2 rounded-md border border-ink-800/60 bg-ink-900/40 p-2.5 text-xs text-ink-200"
                >
                  <span className="text-sig-400">→</span>
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Structure tree */}
      <div className="panel p-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="hud-label">Project Structure</span>
          <span className="data-mono text-[10px] text-ink-500">
            root: {analysis.root}
          </span>
        </div>
        <div className="overflow-x-auto">
          <TreeView node={analysis.structure} depth={0} />
        </div>
      </div>
    </div>
  )
}

function DependencyGroup({ manager, deps }: { manager: string; deps: string[] }) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? deps : deps.slice(0, 8)
  return (
    <div className="rounded-md border border-ink-800/60 bg-ink-900/40 p-2.5">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between"
      >
        <span className="font-mono text-[11px] uppercase tracking-wide text-violet-400">
          {manager}
        </span>
        <span className="data-mono text-[10px] text-ink-500">
          {deps.length} pkg{deps.length === 1 ? '' : 's'} {expanded ? '▾' : '▸'}
        </span>
      </button>
      <div className="mt-2 flex flex-wrap gap-1">
        {visible.map((d) => (
          <span
            key={d}
            className="rounded border border-ink-700/60 bg-ink-850/60 px-1.5 py-0.5 font-mono text-[10px] text-ink-300"
          >
            {d}
          </span>
        ))}
        {deps.length > 8 && !expanded ? (
          <button
            onClick={() => setExpanded(true)}
            className="font-mono text-[10px] text-sig-400 hover:underline"
          >
            +{deps.length - 8} more
          </button>
        ) : null}
      </div>
    </div>
  )
}

function IssueRow({ issue }: { issue: ProjectIssue }) {
  const tone = SEVERITY_TONE[issue.severity] ?? 'idle'
  const glyph = SEVERITY_GLYPH[issue.severity] ?? '·'
  return (
    <div className="flex items-start gap-2 rounded-md border border-ink-800/60 bg-ink-900/40 p-2.5">
      <span
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded font-mono text-[11px] ${
          tone === 'fail'
            ? 'bg-bad-500/15 text-bad-400'
            : tone === 'warn'
            ? 'bg-warn-500/15 text-warn-400'
            : 'bg-ink-800/60 text-ink-400'
        }`}
      >
        {glyph}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-wide text-ink-400">
            {issue.category}
          </span>
          <StatusBadge tone={tone} label={issue.severity} />
        </div>
        <p className="mt-0.5 text-xs text-ink-200">{issue.message}</p>
      </div>
    </div>
  )
}

function TreeView({ node, depth }: { node: ProjectTreeNode; depth: number }) {
  const [expanded, setExpanded] = useState(depth < 2)
  const isDir = node.type === 'dir'
  return (
    <div>
      <button
        onClick={isDir ? () => setExpanded((v) => !v) : undefined}
        className={`flex items-center gap-1.5 py-0.5 font-mono text-[11px] ${
          isDir ? 'cursor-pointer hover:text-gray-100' : 'cursor-default'
        }`}
        style={{ paddingLeft: `${depth * 16}px` }}
      >
        {isDir ? (
          <span className="text-ink-500">{expanded ? '▾' : '▸'}</span>
        ) : (
          <span className="text-ink-600">·</span>
        )}
        <span className={isDir ? 'text-sig-300' : 'text-ink-300'}>{node.name}</span>
        {!isDir && typeof node.size === 'number' ? (
          <span className="text-[10px] text-ink-600">{fmtBytes(node.size)}</span>
        ) : null}
      </button>
      {isDir && expanded && node.children ? (
        <div>
          {node.children.map((child, i) => (
            <TreeView key={`${child.name}-${i}`} node={child} depth={depth + 1} />
          ))}
        </div>
      ) : null}
    </div>
  )
}
