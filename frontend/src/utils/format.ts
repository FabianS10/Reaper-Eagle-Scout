import type { Opportunity } from '../types'

export function formatBudget(amount: number | null, currency: string | null): string {
  if (!amount) return '—'
  const c = currency || 'USD'
  if (c === 'COP') {
    if (amount >= 1e9) return `${(amount / 1e9).toFixed(1)}B COP`
    return `${(amount / 1e6).toFixed(0)}M COP`
  }
  if (c === 'USD') {
    if (amount >= 1e6) return `$${(amount / 1e6).toFixed(1)}M`
    if (amount >= 1e3) return `$${(amount / 1e3).toFixed(0)}K`
    return `$${amount.toFixed(0)}`
  }
  if (c === 'MXN') return `${(amount / 1e6).toFixed(1)}M MXN`
  if (c === 'PEN') return `${(amount / 1e6).toFixed(1)}M PEN`
  return `${amount.toLocaleString()} ${c}`
}

export interface DeadlineInfo {
  label: string
  daysLeft: number
  tier: 'critical' | 'hot' | 'open' | 'closed' | 'unknown'
}

export function parseDeadline(deadline: string | null): DeadlineInfo {
  if (!deadline) return { label: '—', daysLeft: 999, tier: 'unknown' }
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const dl = new Date(deadline + 'T00:00:00')
  const diff = Math.ceil((dl.getTime() - today.getTime()) / 86_400_000)

  if (diff < 0) return { label: `Closed`, daysLeft: diff, tier: 'closed' }
  if (diff === 0) return { label: 'Today', daysLeft: 0, tier: 'critical' }
  if (diff <= 7) return { label: deadline, daysLeft: diff, tier: 'critical' }
  if (diff <= 21) return { label: deadline, daysLeft: diff, tier: 'hot' }
  return { label: deadline, daysLeft: diff, tier: 'open' }
}

export function formatScore(score: number): string {
  return Math.round(score).toString()
}

export function formatConfidence(conf: number | null): string {
  if (conf === null || conf === undefined) return '—'
  return `${Math.round(conf * 100)}%`
}

export function formatPipelineValue(usd: number): string {
  if (usd >= 1e9) return `$${(usd / 1e9).toFixed(1)}B`
  if (usd >= 1e6) return `$${(usd / 1e6).toFixed(1)}M`
  if (usd >= 1e3) return `$${(usd / 1e3).toFixed(0)}K`
  return `$${usd.toFixed(0)}`
}

export function opportunityTypeLabel(t: string | null): string {
  const map: Record<string, string> = {
    public_tender: 'Public Tender',
    private_rfp: 'Private RFP',
    grant: 'Grant',
    accelerator: 'Accelerator',
    competitor_signal: 'Competitor Signal',
    market_signal: 'Market Signal',
    unknown: 'Unknown',
  }
  return map[t || 'unknown'] || t || '—'
}

export function scoreColor(score: number): string {
  if (score >= 80) return 'var(--green)'
  if (score >= 65) return 'var(--accent)'
  if (score >= 50) return 'var(--yellow)'
  return 'var(--text3)'
}
