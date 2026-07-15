/**
 * Typed REST client for the Veyron backend.
 *
 * All paths are relative to `/api` and rely on the Vite dev proxy
 * (vite.config.ts) in dev and FastAPI StaticFiles in prod.
 */

import type {
  AgentResponse,
  DashboardData,
  Memory,
  MemoryListResponse,
  MemorySearchResponse,
  MemoryStats,
  MemoryUpdate,
  ProjectAnalysis,
  SystemCpu,
  SystemDisk,
  SystemHealth,
  SystemMemory,
  SystemOverview,
  SystemProcesses,
  TaskDetail,
  TaskListResponse,
  TimelineResponse,
  ToolListResponse,
  ToolRecentResponse,
  ToolSchema,
} from './types'

const BASE = '/api'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE}${path}`
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })
  if (!res.ok) {
    let body = ''
    try {
      body = await res.text()
    } catch {
      // ignore
    }
    throw new ApiError(res.status, `API ${res.status}: ${body.slice(0, 200)}`)
  }
  // Some DELETE / control endpoints may return empty bodies; guard that.
  const text = await res.text()
  if (!text) return {} as T
  try {
    return JSON.parse(text) as T
  } catch {
    return {} as T
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export interface ListParams {
  limit?: number
  offset?: number
  status?: string
  mode?: string
}

export interface SystemResponse<T> {
  ok: boolean
  output?: string
  data?: T
  error?: string
}

export const api = {
  // ── Dashboard / system ────────────────────────────────────────────────
  dashboard(): Promise<DashboardData> {
    return request<DashboardData>('/dashboard')
  },

  systemOverview(): Promise<SystemResponse<SystemOverview>> {
    return request('/system/overview')
  },

  systemCpu(): Promise<SystemResponse<SystemCpu>> {
    return request('/system/cpu')
  },

  systemMemory(): Promise<SystemResponse<SystemMemory>> {
    return request('/system/memory')
  },

  systemDisk(): Promise<SystemResponse<SystemDisk>> {
    return request('/system/disk')
  },

  systemHealth(): Promise<SystemResponse<SystemHealth>> {
    return request('/system/health')
  },

  systemProcesses(
    count: number = 12,
    sortBy: 'cpu' | 'memory' = 'cpu',
  ): Promise<SystemResponse<SystemProcesses>> {
    return request(`/system/processes?count=${count}&sort_by=${sortBy}`)
  },

  info(): Promise<{
    version: string
    tools: string[]
    sandbox_roots: string[]
    model: { base_model: string; ollama_url: string }
  }> {
    return request('/info')
  },

  // ── Agent / tasks ─────────────────────────────────────────────────────
  createTask(request_text: string): Promise<AgentResponse> {
    return request<AgentResponse>('/agent', {
      method: 'POST',
      body: JSON.stringify({ request: request_text }),
    })
  },

  getTask(publicId: string): Promise<TaskDetail> {
    return request<TaskDetail>(`/agent/${publicId}`)
  },

  listTasks(params?: ListParams): Promise<TaskListResponse> {
    const q = new URLSearchParams()
    if (params?.limit != null) q.set('limit', String(params.limit))
    if (params?.offset != null) q.set('offset', String(params.offset))
    if (params?.status) q.set('status', params.status)
    if (params?.mode) q.set('mode', params.mode)
    const qs = q.toString()
    return request<TaskListResponse>(`/agent${qs ? `?${qs}` : ''}`)
  },

  getTimeline(publicId: string): Promise<TimelineResponse> {
    return request<TimelineResponse>(`/agent/${publicId}/timeline`)
  },

  cancelTask(publicId: string): Promise<{ status: string; public_id: string }> {
    return request(`/agent/${publicId}/cancel`, { method: 'POST' })
  },

  pauseTask(publicId: string): Promise<{ status: string; public_id: string }> {
    return request(`/agent/${publicId}/pause`, { method: 'POST' })
  },

  resumeTask(publicId: string): Promise<{ status: string; public_id: string }> {
    return request(`/agent/${publicId}/resume`, { method: 'POST' })
  },

  deleteTask(publicId: string): Promise<{ status: string; public_id: string }> {
    return request(`/agent/${publicId}`, { method: 'DELETE' })
  },

  // ── Tools ─────────────────────────────────────────────────────────────
  listTools(): Promise<ToolListResponse> {
    return request<ToolListResponse>('/tools')
  },

  getTool(name: string): Promise<ToolSchema> {
    return request<ToolSchema>(`/tools/${encodeURIComponent(name)}`)
  },

  recentToolInvocations(name: string, limit: number = 20): Promise<ToolRecentResponse> {
    return request<ToolRecentResponse>(
      `/tools/${encodeURIComponent(name)}/recent?limit=${limit}`,
    )
  },

  // ── Memory ────────────────────────────────────────────────────────────
  listMemories(params?: {
    limit?: number
    offset?: number
    category?: string
    tags?: string
    min_importance?: number
    include_decayed?: boolean
  }): Promise<MemoryListResponse> {
    const q = new URLSearchParams()
    if (params?.limit != null) q.set('limit', String(params.limit))
    if (params?.offset != null) q.set('offset', String(params.offset))
    if (params?.category) q.set('category', params.category)
    if (params?.tags) q.set('tags', params.tags)
    if (params?.min_importance != null)
      q.set('min_importance', String(params.min_importance))
    if (params?.include_decayed) q.set('include_decayed', 'true')
    const qs = q.toString()
    return request<MemoryListResponse>(`/memory${qs ? `?${qs}` : ''}`)
  },

  searchMemories(query: string, params?: {
    category?: string
    tags?: string
    limit?: number
  }): Promise<MemorySearchResponse> {
    const q = new URLSearchParams()
    q.set('q', query)
    if (params?.category) q.set('category', params.category)
    if (params?.tags) q.set('tags', params.tags)
    if (params?.limit != null) q.set('limit', String(params.limit))
    return request<MemorySearchResponse>(`/memory/search?${q.toString()}`)
  },

  memoryStats(): Promise<MemoryStats> {
    return request<MemoryStats>('/memory/stats')
  },

  getMemory(publicId: string): Promise<Memory> {
    return request<Memory>(`/memory/${publicId}`)
  },

  updateMemory(publicId: string, patch: MemoryUpdate): Promise<Memory> {
    return request<Memory>(`/memory/${publicId}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
  },

  deleteMemory(publicId: string): Promise<{ status: string; public_id: string }> {
    return request(`/memory/${publicId}`, { method: 'DELETE' })
  },

  // ── Projects ──────────────────────────────────────────────────────────
  analyzeProject(req: {
    path: string
    max_depth?: number
    include_hidden?: boolean
  }): Promise<ProjectAnalysis> {
    return request<ProjectAnalysis>('/projects/analyze', {
      method: 'POST',
      body: JSON.stringify({
        path: req.path,
        max_depth: req.max_depth ?? 5,
        include_hidden: req.include_hidden ?? false,
      }),
    })
  },
}
