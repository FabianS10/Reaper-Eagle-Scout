import axios from 'axios'
import type {
  Opportunity,
  OpportunityListOut,
  SearchJob,
  SearchRequest,
  DashboardSummary,
  ListParams,
} from '../types'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: BASE,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Unknown error'
    return Promise.reject(new Error(msg))
  }
)

// ── Search ──────────────────────────────────────────────────────────────────

export const startSearch = async (req: SearchRequest): Promise<SearchJob> => {
  const { data } = await client.post('/api/search', req)
  return data
}

export const getJobStatus = async (jobId: string): Promise<SearchJob> => {
  const { data } = await client.get(`/api/search/${jobId}`)
  return data
}

export const listJobs = async (): Promise<SearchJob[]> => {
  const { data } = await client.get('/api/search')
  return data
}

// ── Opportunities ───────────────────────────────────────────────────────────

export const listOpportunities = async (params: ListParams = {}): Promise<OpportunityListOut> => {
  const { data } = await client.get('/api/opportunities', { params })
  return data
}

export const getOpportunity = async (id: string): Promise<Opportunity> => {
  const { data } = await client.get(`/api/opportunities/${id}`)
  return data
}

export const bookmarkOpportunity = async (id: string): Promise<{ is_bookmarked: boolean }> => {
  const { data } = await client.post(`/api/opportunities/${id}/bookmark`)
  return data
}

export const initiateResponse = async (id: string): Promise<void> => {
  await client.post(`/api/opportunities/${id}/initiate`)
}

export const deleteOpportunity = async (id: string): Promise<void> => {
  await client.delete(`/api/opportunities/${id}`)
}

// ── Dashboard ───────────────────────────────────────────────────────────────

export const getDashboardSummary = async (): Promise<DashboardSummary> => {
  const { data } = await client.get('/api/dashboard/summary')
  return data
}

export const getReportUrl = (): string => `${BASE}/api/dashboard/report`

// ── Health ──────────────────────────────────────────────────────────────────

export const checkHealth = async (): Promise<boolean> => {
  try {
    await client.get('/health')
    return true
  } catch {
    return false
  }
}
