import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type {
  DiskPartition,
  SystemCpu,
  SystemDisk,
  SystemHealth,
  SystemMemory,
  SystemOverview,
  SystemProcess,
} from '../api/types'
import {
  LoadingSpinner,
  ErrorBox,
  EmptyState,
} from '../components/ui'
import { Stat } from '../components/ui/Stat'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Sparkline } from '../components/ui/Sparkline'
import { ProgressMeter } from '../components/ui/ProgressMeter'
import { useInterval } from '../hooks/useInterval'
import { fmtBytes, fmtPct } from '../lib/format'

const SPARK_SAMPLES = 60
const POLL_MS = 2000
const PROC_POLL_MS = 5000

type SortBy = 'cpu' | 'memory'

export function SystemIntelligencePage() {
  const [overview, setOverview] = useState<SystemOverview | null>(null)
  const [cpu, setCpu] = useState<SystemCpu | null>(null)
  const [mem, setMem] = useState<SystemMemory | null>(null)
  const [disk, setDisk] = useState<SystemDisk | null>(null)
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [procs, setProcs] = useState<SystemProcess[]>([])
  const [sortBy, setSortBy] = useState<SortBy>('cpu')
  const [cpuHistory, setCpuHistory] = useState<number[]>([])
  const [memHistory, setMemHistory] = useState<number[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const pollAll = useCallback(async () => {
    try {
      const [ov, c, m, d, h] = await Promise.all([
        api.systemOverview(),
        api.systemCpu(),
        api.systemMemory(),
        api.systemDisk(),
        api.systemHealth(),
      ])
      setError(null)
      if (ov.data) {
        const d = ov.data
        setOverview(d)
        setCpuHistory((p) => [...p.slice(-(SPARK_SAMPLES - 1)), d.cpu_percent])
        setMemHistory((p) => [...p.slice(-(SPARK_SAMPLES - 1)), d.memory_percent])
      }
      if (c.data) setCpu(c.data)
      if (m.data) setMem(m.data)
      if (d.data) setDisk(d.data)
      if (h.data) setHealth(h.data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const pollProcs = useCallback(async () => {
    try {
      const r = await api.systemProcesses(15, sortBy)
      if (r.data) setProcs(r.data.processes)
    } catch {
      // Processes are best-effort.
    }
  }, [sortBy])

  useEffect(() => {
    pollAll()
  }, [pollAll])

  useEffect(() => {
    pollProcs()
  }, [pollProcs])

  useInterval(pollAll, POLL_MS)
  useInterval(pollProcs, PROC_POLL_MS)

  const healthTone = !health ? 'idle' : health.ok ? 'ok' : 'warn'
  const cpuWarn = (overview?.cpu_percent ?? 0) > 85
  const memWarn = (overview?.memory_percent ?? 0) > 90
  const diskWarn = (overview?.disk_percent ?? 0) > 90

  return (
    <div className="mx-auto max-w-7xl px-6 py-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-100">System Intelligence</h1>
          <p className="mt-0.5 text-xs text-ink-400">
            Live host telemetry — CPU, memory, disk, processes, and health warnings.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge tone={healthTone} pulse={!health?.ok} label={health?.ok ? 'Nominal' : health ? 'Issues Detected' : 'Unknown'} />
        </div>
      </header>

      {error ? (
        <div className="mt-4">
          <ErrorBox message={error} onRetry={pollAll} />
        </div>
      ) : null}

      {/* Top stat strip */}
      <section className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="CPU"
          value={loading && !overview ? '—' : fmtPct(overview?.cpu_percent, 1)}
          tone={cpuWarn ? 'warn' : 'default'}
          sub={`${overview?.cpu_count ?? 0} cores`}
          icon={<span className="h-2 w-2 rounded-full bg-sig-400 animate-pulseDot" />}
        />
        <Stat
          label="Memory"
          value={loading && !overview ? '—' : fmtPct(overview?.memory_percent, 1)}
          tone={memWarn ? 'warn' : 'default'}
          sub={overview ? `${fmtBytes(overview.memory_used)} / ${fmtBytes(overview.memory_total)}` : undefined}
        />
        <Stat
          label="Disk"
          value={loading && !overview ? '—' : fmtPct(overview?.disk_percent, 1)}
          tone={diskWarn ? 'warn' : 'default'}
          sub="avg usage"
        />
        <Stat
          label="Uptime"
          value={loading && !overview ? '—' : uptimeStr(overview?.boot_time)}
          tone="default"
        />
      </section>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* CPU panel */}
        <div className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="hud-label">CPU</span>
            <span className="data-mono text-[10px] text-ink-500">
              {cpu ? `${cpu.cores_physical}p / ${cpu.cores_logical}l` : ''}
              {cpu?.freq_mhz_current ? ` · ${Math.round(cpu.freq_mhz_current)} MHz` : ''}
            </span>
          </div>
          {overview ? (
            <>
              <div className="mb-2 flex items-baseline justify-between">
                <span className={`data-mono text-2xl font-semibold ${cpuWarn ? 'text-warn-400' : 'text-gray-100'}`}>
                  {fmtPct(overview.cpu_percent, 1)}
                </span>
                <span className="font-mono text-[10px] text-ink-500">overall utilization</span>
              </div>
              <Sparkline values={cpuHistory.length ? cpuHistory : [overview.cpu_percent]} color="#52e6ff" />
              {cpu && cpu.per_cpu.length > 0 ? (
                <div className="mt-3 grid grid-cols-4 gap-1 sm:grid-cols-6 md:grid-cols-8">
                  {cpu.per_cpu.map((v, i) => (
                    <div
                      key={i}
                      className="flex flex-col items-center rounded border border-ink-800/60 bg-ink-900/40 px-1 py-1"
                    >
                      <span className="font-mono text-[9px] text-ink-500">c{i}</span>
                      <span className={`data-mono text-[10px] ${v > 85 ? 'text-warn-400' : 'text-ink-300'}`}>
                        {Math.round(v)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
              {cpu?.load_avg && cpu.load_avg.length === 3 ? (
                <div className="mt-3 grid grid-cols-3 gap-2 border-t border-ink-800/60 pt-2">
                  <LoadAvg label="1 min" value={cpu.load_avg[0]} cores={cpu.cores_logical} />
                  <LoadAvg label="5 min" value={cpu.load_avg[1]} cores={cpu.cores_logical} />
                  <LoadAvg label="15 min" value={cpu.load_avg[2]} cores={cpu.cores_logical} />
                </div>
              ) : null}
            </>
          ) : (
            <LoadingSpinner label="Reading CPU" />
          )}
        </div>

        {/* Memory panel */}
        <div className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="hud-label">Memory</span>
            <span className="data-mono text-[10px] text-ink-500">
              {mem ? `swap ${fmtPct(mem.swap_percent, 0)}` : ''}
            </span>
          </div>
          {overview && mem ? (
            <>
              <div className="mb-2 flex items-baseline justify-between">
                <span className={`data-mono text-2xl font-semibold ${memWarn ? 'text-warn-400' : 'text-gray-100'}`}>
                  {fmtPct(overview.memory_percent, 1)}
                </span>
                <span className="font-mono text-[10px] text-ink-500">
                  {fmtBytes(mem.used)} / {fmtBytes(mem.total)}
                </span>
              </div>
              <Sparkline values={memHistory.length ? memHistory : [overview.memory_percent]} color="#a98bff" />
              <div className="mt-3 grid grid-cols-3 gap-2 border-t border-ink-800/60 pt-2">
                <MemStat label="used" value={fmtBytes(mem.used)} />
                <MemStat label="available" value={fmtBytes(mem.available)} />
                <MemStat label="free" value={fmtBytes(mem.free)} />
              </div>
              {mem.swap_total > 0 ? (
                <div className="mt-3">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="hud-label">Swap</span>
                    <span className="data-mono text-[10px] text-ink-500">
                      {fmtBytes(mem.swap_used)} / {fmtBytes(mem.swap_total)}
                    </span>
                  </div>
                  <ProgressMeter percent={mem.swap_percent} compact />
                </div>
              ) : null}
            </>
          ) : (
            <LoadingSpinner label="Reading memory" />
          )}
        </div>

        {/* Disk panel */}
        <div className="panel p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <span className="hud-label">Disk Partitions</span>
            <span className="data-mono text-[10px] text-ink-500">
              {disk?.partitions.length ?? 0} mount(s)
            </span>
          </div>
          {!disk ? (
            <LoadingSpinner label="Reading disk" />
          ) : disk.partitions.length === 0 ? (
            <EmptyState title="No mounts" hint="No accessible disk partitions." />
          ) : (
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {disk.partitions.map((p) => (
                <DiskRow key={p.mountpoint} part={p} />
              ))}
            </div>
          )}
        </div>

        {/* Health / warnings panel */}
        <div className="panel p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <span className="hud-label">Health & Warnings</span>
            <StatusBadge
              tone={healthTone}
              label={health?.ok ? 'No issues' : health ? `${health.issues.length} issue(s)` : 'Unknown'}
            />
          </div>
          {!health ? (
            <LoadingSpinner label="Checking health" />
          ) : health.issues.length === 0 ? (
            <EmptyState icon="✓" title="All systems nominal" hint="No thresholds exceeded." />
          ) : (
            <ul className="flex flex-col gap-2">
              {health.issues.map((issue, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 rounded-md border border-warn-500/30 bg-warn-500/5 p-2.5"
                >
                  <span className="mt-0.5 text-warn-400">!</span>
                  <span className="text-xs text-warn-200">{issue}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Top processes */}
        <div className="panel p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <span className="hud-label">Top Processes</span>
            <div className="flex items-center gap-1 rounded-md border border-ink-700/60 bg-ink-900/40 p-0.5">
              {(['cpu', 'memory'] as SortBy[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setSortBy(s)}
                  className={`focus-ring rounded px-2.5 py-1 font-mono text-[11px] uppercase ${
                    sortBy === s ? 'bg-sig-500/15 text-sig-200' : 'text-ink-400 hover:text-gray-200'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          {procs.length === 0 ? (
            <EmptyState title="No processes" hint="Process list unavailable." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="hud-label border-b border-ink-800/70">
                    <th className="py-2 pr-3 font-medium">PID</th>
                    <th className="py-2 pr-3 font-medium">Name</th>
                    <th className="py-2 pr-3 font-medium">User</th>
                    <th className="py-2 pr-3 text-right font-medium">CPU %</th>
                    <th className="py-2 pr-3 text-right font-medium">MEM %</th>
                  </tr>
                </thead>
                <tbody>
                  {procs.map((p) => (
                    <tr key={p.pid} className="border-b border-ink-800/40 text-xs">
                      <td className="py-2 pr-3 data-mono text-ink-500">{p.pid}</td>
                      <td className="py-2 pr-3 font-mono text-ink-200">{p.name || '?'}</td>
                      <td className="py-2 pr-3 data-mono text-ink-400">{p.username || '—'}</td>
                      <td
                        className={`py-2 pr-3 text-right data-mono ${
                          p.cpu_percent > 50 ? 'text-warn-400' : 'text-ink-300'
                        }`}
                      >
                        {p.cpu_percent.toFixed(1)}
                      </td>
                      <td
                        className={`py-2 pr-3 text-right data-mono ${
                          p.memory_percent > 20 ? 'text-warn-400' : 'text-ink-300'
                        }`}
                      >
                        {p.memory_percent.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function uptimeStr(boot: number | undefined | null): string {
  if (!boot) return '—'
  const secs = Math.max(0, Date.now() / 1000 - boot)
  const d = Math.floor(secs / 86400)
  const h = Math.floor((secs % 86400) / 3600)
  if (d > 0) return `${d}d ${h}h`
  const m = Math.floor((secs % 3600) / 60)
  return `${h}h ${m}m`
}

function LoadAvg({ label, value, cores }: { label: string; value: number; cores: number }) {
  const ratio = cores > 0 ? value / cores : 0
  const tone = ratio > 0.9 ? 'text-warn-400' : ratio > 0.6 ? 'text-sig-300' : 'text-ink-300'
  return (
    <div className="flex flex-col">
      <span className="hud-label">{label}</span>
      <span className={`data-mono text-sm ${tone}`}>{value.toFixed(2)}</span>
    </div>
  )
}

function MemStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="hud-label">{label}</span>
      <span className="data-mono text-sm text-ink-200">{value}</span>
    </div>
  )
}

function DiskRow({ part }: { part: DiskPartition }) {
  const warn = part.percent > 90
  return (
    <div className="rounded-md border border-ink-800/60 bg-ink-900/40 p-2.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-ink-200">{part.mountpoint}</span>
        <span
          className={`rounded border px-1 py-px font-mono text-[9px] uppercase ${
            warn
              ? 'border-warn-500/40 text-warn-400'
              : 'border-ink-600/60 text-ink-400'
          }`}
        >
          {part.fstype}
        </span>
      </div>
      <div className="mt-1.5">
        <ProgressMeter percent={part.percent} compact />
      </div>
      <div className="mt-1.5 flex items-center justify-between font-mono text-[10px] text-ink-500">
        <span>{part.device}</span>
        <span>
          {fmtBytes(part.used)} / {fmtBytes(part.total)} · {fmtBytes(part.free)} free
        </span>
      </div>
    </div>
  )
}
