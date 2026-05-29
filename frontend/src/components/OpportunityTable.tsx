import { useState } from 'react'
import type { Opportunity, SortKey, SortDir } from '../types'
import {
  formatBudget, parseDeadline, formatScore, formatConfidence,
  opportunityTypeLabel, scoreColor
} from '../utils/format'
import styles from './OpportunityTable.module.css'

interface Props {
  items: Opportunity[]
  total: number
  page: number
  pageSize: number
  sortBy: SortKey
  sortDir: SortDir
  selectedId: string | null
  onSelect: (opp: Opportunity) => void
  onSort: (key: SortKey) => void
  onPage: (page: number) => void
}

const COLS: { key: SortKey | null; label: string; width: string }[] = [
  { key: 'final_score', label: 'Score', width: '52px' },
  { key: null,          label: 'Title',  width: '1fr' },
  { key: null,          label: 'Entity', width: '140px' },
  { key: null,          label: 'Type',   width: '110px' },
  { key: 'deadline',    label: 'Deadline', width: '100px' },
  { key: 'budget_amount', label: 'Budget', width: '90px' },
  { key: null,          label: 'Conf',   width: '52px' },
]

export default function OpportunityTable({
  items, total, page, pageSize,
  sortBy, sortDir, selectedId,
  onSelect, onSort, onPage,
}: Props) {
  const totalPages = Math.ceil(total / pageSize)

  const gridTemplate = COLS.map(c => c.width).join(' ')

  return (
    <div className={styles.container}>
      <div className={styles.tableHead} style={{ gridTemplateColumns: gridTemplate }}>
        {COLS.map((col) => (
          <div
            key={col.label}
            className={`${styles.th} ${col.key ? styles.sortable : ''} ${sortBy === col.key ? styles.sorted : ''}`}
            onClick={() => col.key && onSort(col.key)}
          >
            {col.label}
            {col.key && sortBy === col.key && (
              <span className={styles.sortArrow}>{sortDir === 'desc' ? '↓' : '↑'}</span>
            )}
          </div>
        ))}
      </div>

      <div className={styles.body}>
        {items.length === 0 && (
          <div className={styles.empty}>
            No opportunities found. Run a search to populate the pipeline.
          </div>
        )}

        {items.map((opp, i) => {
          const dl = parseDeadline(opp.deadline)
          const score = Math.round(opp.scores.final)
          const isSelected = opp.id === selectedId

          return (
            <div
              key={opp.id}
              className={`${styles.row} ${isSelected ? styles.selected : ''}`}
              style={{ gridTemplateColumns: gridTemplate, animationDelay: `${i * 30}ms` }}
              onClick={() => onSelect(opp)}
            >
              {/* Score */}
              <div className={styles.scoreCell}>
                <span
                  className={styles.scoreVal}
                  style={{ color: scoreColor(score) }}
                >
                  {formatScore(score)}
                </span>
              </div>

              {/* Title */}
              <div className={styles.titleCell}>
                <div className={styles.title} title={opp.title || undefined}>
                  {opp.title || opp.source_url}
                </div>
                <div className={styles.titleSub}>{opp.organization || '—'}</div>
              </div>

              {/* Entity */}
              <div className={styles.cell}>
                <div className={styles.cellMain}>{opp.country || '—'}</div>
                <div className={styles.cellSub}>{opp.city || ''}</div>
              </div>

              {/* Type */}
              <div className={styles.cell}>
                <span className={`${styles.typeBadge} ${styles[`type_${opp.opportunity_type || 'unknown'}`]}`}>
                  {opportunityTypeLabel(opp.opportunity_type)}
                </span>
              </div>

              {/* Deadline */}
              <div className={styles.cell}>
                <div className={`${styles.deadline} ${styles[`dl_${dl.tier}`]}`}>
                  {dl.daysLeft >= 0 && dl.tier !== 'unknown' ? `${dl.daysLeft}d` : dl.label}
                </div>
                {dl.tier !== 'unknown' && dl.tier !== 'closed' && dl.daysLeft >= 0 && (
                  <div className={styles.cellSub}>{opp.deadline}</div>
                )}
              </div>

              {/* Budget */}
              <div className={styles.cell}>
                <span className={styles.budget}>
                  {formatBudget(opp.budget_amount, opp.budget_currency)}
                </span>
              </div>

              {/* Confidence */}
              <div className={styles.cell}>
                <span className={styles.conf}>
                  {formatConfidence(opp.extraction_confidence)}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {totalPages > 1 && (
        <div className={styles.pagination}>
          <span className={styles.pageInfo}>
            {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
          </span>
          <div className={styles.pageButtons}>
            <button
              className={styles.pageBtn}
              onClick={() => onPage(page - 1)}
              disabled={page <= 1}
            >
              Prev
            </button>
            <button
              className={styles.pageBtn}
              onClick={() => onPage(page + 1)}
              disabled={page >= totalPages}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
