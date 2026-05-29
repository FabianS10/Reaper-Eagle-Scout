import { useState } from 'react'
import type { Opportunity } from '../types'
import { formatBudget, parseDeadline, opportunityTypeLabel, scoreColor, formatConfidence } from '../utils/format'
import { bookmarkOpportunity, initiateResponse } from '../api/client'
import styles from './OpportunityDetail.module.css'

interface Props {
  opportunity: Opportunity | null
  onUpdate: (id: string, patch: Partial<Opportunity>) => void
}

const SCORE_ROWS = [
  { key: 'relevance',          label: 'Relevance',   weight: '30%' },
  { key: 'urgency',            label: 'Urgency',     weight: '25%' },
  { key: 'strategic_fit',      label: 'Strat. Fit',  weight: '20%' },
  { key: 'evidence_confidence', label: 'Evidence',   weight: '15%' },
  { key: 'value',              label: 'Value',       weight: '10%' },
] as const

export default function OpportunityDetail({ opportunity: opp, onUpdate }: Props) {
  const [actionLoading, setActionLoading] = useState(false)

  if (!opp) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyText}>Select an opportunity to view details</div>
      </div>
    )
  }

  const dl = parseDeadline(opp.deadline)
  const score = Math.round(opp.scores.final)

  const handleBookmark = async () => {
    setActionLoading(true)
    try {
      const res = await bookmarkOpportunity(opp.id)
      onUpdate(opp.id, { is_bookmarked: res.is_bookmarked })
    } finally {
      setActionLoading(false)
    }
  }

  const handleInitiate = async () => {
    setActionLoading(true)
    try {
      await initiateResponse(opp.id)
      onUpdate(opp.id, { response_initiated: true })
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.head}>
        <div className={styles.headTop}>
          <div className={styles.score} style={{ color: scoreColor(score) }}>
            {score}
          </div>
          <div className={styles.headMeta}>
            <div className={styles.title}>{opp.title || opp.source_url}</div>
            <div className={styles.org}>{opp.organization || '—'}</div>
            <div className={styles.location}>
              {[opp.country, opp.city].filter(Boolean).join(', ') || '—'}
            </div>
          </div>
        </div>

        {/* Score breakdown */}
        <div className={styles.breakdown}>
          {SCORE_ROWS.map(({ key, label, weight }) => {
            const val = opp.scores[key]
            return (
              <div key={key} className={styles.bRow}>
                <span className={styles.bLabel}>{label}</span>
                <div className={styles.bTrack}>
                  <div
                    className={styles.bFill}
                    style={{ width: `${val}%`, background: scoreColor(val) }}
                  />
                </div>
                <span className={styles.bVal}>{Math.round(val)}</span>
                <span className={styles.bWeight}>{weight}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Body */}
      <div className={styles.body}>
        {/* Vitals */}
        <section className={styles.section}>
          <div className={styles.sectionTitle}>Vitals</div>
          <div className={styles.vitals}>
            <div className={styles.vitalItem}>
              <span className={styles.vitalLabel}>Deadline</span>
              <span className={`${styles.vitalVal} ${styles[`dl_${dl.tier}`]}`}>
                {dl.tier === 'unknown' ? '—' : `${opp.deadline} (${dl.daysLeft}d)`}
              </span>
            </div>
            <div className={styles.vitalItem}>
              <span className={styles.vitalLabel}>Budget</span>
              <span className={styles.vitalVal}>
                {formatBudget(opp.budget_amount, opp.budget_currency)}
              </span>
            </div>
            <div className={styles.vitalItem}>
              <span className={styles.vitalLabel}>Type</span>
              <span className={styles.vitalVal}>{opportunityTypeLabel(opp.opportunity_type)}</span>
            </div>
            <div className={styles.vitalItem}>
              <span className={styles.vitalLabel}>Sector</span>
              <span className={styles.vitalVal}>{opp.sector || '—'}</span>
            </div>
            <div className={styles.vitalItem}>
              <span className={styles.vitalLabel}>Source</span>
              <a
                href={opp.source_url}
                target="_blank"
                rel="noreferrer"
                className={styles.sourceLink}
              >
                {opp.source_url.replace(/^https?:\/\//, '').slice(0, 48)}
              </a>
            </div>
            <div className={styles.vitalItem}>
              <span className={styles.vitalLabel}>Trust</span>
              <span className={styles.vitalVal}>
                {opp.source_reliability ? `${opp.source_reliability}%` : '—'}
              </span>
            </div>
            <div className={styles.vitalItem}>
              <span className={styles.vitalLabel}>AI Confidence</span>
              <span className={styles.vitalVal}>{formatConfidence(opp.extraction_confidence)}</span>
            </div>
            {opp.contact_email && (
              <div className={styles.vitalItem}>
                <span className={styles.vitalLabel}>Contact</span>
                <a href={`mailto:${opp.contact_email}`} className={styles.sourceLink}>
                  {opp.contact_email}
                </a>
              </div>
            )}
          </div>
        </section>

        {/* Why this score */}
        <section className={styles.section}>
          <div className={styles.sectionTitle}>Score Rationale</div>
          <p className={styles.why}>{opp.why_score}</p>
        </section>

        {/* Summary */}
        {opp.summary && (
          <section className={styles.section}>
            <div className={styles.sectionTitle}>Summary</div>
            <p className={styles.summary}>{opp.summary}</p>
          </section>
        )}

        {/* Evidence */}
        {opp.evidence_snippets?.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionTitle}>Evidence Snippets</div>
            <div className={styles.evidenceList}>
              {opp.evidence_snippets.map((ev, i) => (
                <div key={i} className={styles.evidence}>
                  <span className={styles.evidenceQuote}>&ldquo;</span>
                  {ev}
                  <span className={styles.evidenceQuote}>&rdquo;</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Requirements */}
        {opp.requirements?.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionTitle}>Requirements</div>
            <ul className={styles.reqList}>
              {opp.requirements.map((r, i) => (
                <li key={i} className={styles.reqItem}>{r}</li>
              ))}
            </ul>
          </section>
        )}

        {/* Eligibility */}
        {opp.eligibility?.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionTitle}>Eligibility</div>
            <ul className={styles.reqList}>
              {opp.eligibility.map((e, i) => (
                <li key={i} className={styles.reqItem}>{e}</li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {/* Footer actions */}
      <div className={styles.foot}>
        <button
          className={`${styles.actionBtn} ${styles.primary}`}
          onClick={handleInitiate}
          disabled={actionLoading || opp.response_initiated}
        >
          {opp.response_initiated ? 'Response initiated' : 'Initiate response'}
        </button>
        <button
          className={`${styles.actionBtn} ${opp.is_bookmarked ? styles.bookmarked : ''}`}
          onClick={handleBookmark}
          disabled={actionLoading}
        >
          {opp.is_bookmarked ? 'Bookmarked' : 'Bookmark'}
        </button>
        <a
          href={opp.source_url}
          target="_blank"
          rel="noreferrer"
          className={styles.actionBtn}
        >
          View source
        </a>
      </div>
    </div>
  )
}
