export interface OpportunityScores {
  relevance: number
  urgency: number
  strategic_fit: number
  evidence_confidence: number
  value: number
  final: number
}

export interface Opportunity {
  id: string
  title: string | null
  source_url: string
  organization: string | null
  country: string | null
  city: string | null
  sector: string | null
  opportunity_type: string | null
  budget_amount: number | null
  budget_currency: string | null
  deadline: string | null
  publication_date: string | null
  summary: string | null
  requirements: string[]
  eligibility: string[]
  evidence_snippets: string[]
  contact_email: string | null
  scores: OpportunityScores
  source_reliability: number | null
  extraction_confidence: number | null
  why_score: string
  is_bookmarked: boolean
  response_initiated: boolean
  created_at: string
}

export interface OpportunityListOut {
  items: Opportunity[]
  total: number
  page: number
  page_size: number
}

export interface SearchJob {
  job_id: string
  status: string
  progress_pct: number
  query: string
  urls_discovered: number
  urls_fetched: number
  urls_parsed: number
  opportunities_extracted: number
  opportunities_scored: number
  error_message: string | null
  duration_seconds: number | null
}

export interface DashboardSummary {
  total_opportunities: number
  high_priority_count: number
  closing_soon_count: number
  avg_confidence: number
  total_pipeline_value_usd: number
  sources_scanned: number
  by_sector: Record<string, number>
  by_country: Record<string, number>
  by_type: Record<string, number>
  urgency_map: Record<string, number>
}

export interface SearchRequest {
  query: string
  country?: string
  sector?: string
  max_results?: number
  min_score?: number
}

export type SortKey = 'final_score' | 'deadline' | 'budget_amount' | 'created_at'
export type SortDir = 'asc' | 'desc'

export interface ListParams {
  page?: number
  page_size?: number
  sort_by?: SortKey
  sort_dir?: SortDir
  sector?: string
  country?: string
  opportunity_type?: string
  min_score?: number
  search?: string
  job_id?: string
}
