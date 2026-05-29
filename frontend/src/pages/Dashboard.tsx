import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getDashboardSummary, listOpportunities, listJobs, getReportUrl } from '../api/client'
import type { DashboardSummary, Opportunity, SearchJob } from '../types'
import { formatPipelineValue, formatBudget, parseDeadline, scoreColor } from '../utils/format'
import styles from './Dashboard.module.css'

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [topOpps, setTopOpps] = useState<Opportunity[]>([])
  const [recentJobs, setRecentJobs] = useState<SearchJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      getDashboardSummary(),
      listOpportunities({ sort_by: 'final_score', sort_dir: 'desc', page_size: 6 }),
      listJobs(),
    ])
      .then(([s, opps, jobs]) => {
        setSummary(s)
        setTopOpps(opps.items)
        setRecentJobs(jobs.slice(0, 5))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className={styles.loading}>Loading...</div>
  }

  if (error) {
    return <div className={styles.errorPage}>{error}</div>
  }

  return (
    <div className={styles.page}>
      {/* Top stat cards */}
      <div className={styles.statsGrid}>
        <div className={styles.stat}>
          <div className={styles.statNum}>{summary?.total_opportunities ?? 0}</div>
          <div className={styles.statLabel}>Total opportunities</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statNum} style={{ color: 'var(--green)' }}>
            {summary?.high_priority_count ?? 0}
          </div>
          <div className={styles.statLabel}>High priority (80+)</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statNum} style={{ color: '#a04040' }}>
            {summary?.closing_soon_count ?? 0}
          </div>
          <div className={styles.statLabel}>Closing within 14 days</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statNum}>
            {formatPipelineValue(summary?.total_pipeline_value_usd ?? 0)}
          </div>
          <div className={styles.statLabel}>Total pipeline value</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statNum}>
            {summary ? `${Math.round(summary.avg_confidence * 100)}%` : '—'}
          </div>
          <div className={styles.statLabel}>Avg AI confidence</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statNum}>{summary?.sources_scanned ?? 0}</div>
          <div className={styles.statLabel}>Sources indexed</div>
        </div>
      </div>

      <div className={styles.bodyGrid}>
        {/* Top opportunities */}
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <span className={styles.cardTitle}>Top opportunities</span>
            <Link to="/opportunities" className={styles.cardLink}>View all</Link>
          </div>
          <div className={styles.oppList}>
            {topOpps.length === 0 && (
              <div className={styles.empty}>
                No opportunities yet.{' '}
                <Link to="/search" className={styles.emptyLink}>Run a search</Link> to populate.
              </div>
            )}
            {topOpps.map(opp => {
              const dl = parseDeadline(opp.deadline)
              const score = Math.round(opp.scores.final)
              return (
                <Link
                  key={opp.id}
                  to={`/opportunities`}
                  state={{ selectId: opp.id }}
                  className={styles.oppRow}
                >
                  <span className={styles.oppScore} style={{ color: scoreColor(score) }}>
                    {score}
                  </span>
                  <div className={styles.oppMain}>
                    <div className={styles.oppTitle}>{opp.title || opp.source_url}</div>
                    <div className={styles.oppSub}>
                      {opp.organization || '—'} · {opp.country || '—'}
                    </div>
                  </div>
                  <div className={styles.oppRight}>
                    <div className={`${styles.oppDl} ${styles[`dl_${dl.tier}`]}`}>
                      {dl.tier === 'unknown' ? '—' : `${dl.daysLeft}d`}
                    </div>
                    <div className={styles.oppBudget}>
                      {formatBudget(opp.budget_amount, opp.budget_currency)}
                    </div>
                  </div>
                </Link>
              )
            })}
          </div>
        </div>

        {/* Right column */}
        <div className={styles.rightCol}>
          {/* Sector breakdown */}
          <div className={styles.card}>
            <div className={styles.cardHead}>
              <span className={styles.cardTitle}>By sector</span>
            </div>
            <div className={styles.barChart}>
              {summary && Object.entries(summary.by_sector)
                .sort((a, b) => b[1] - a[1])
                .map(([sec, count]) => {
                  const max = Math.max(...Object.values(summary.by_sector))
                  return (
                    <div key={sec} className={styles.barRow}>
                      <span className={styles.barLabel}>{sec}</span>
                      <div className={styles.barTrack}>
                        <div
                          className={styles.barFill}
                          style={{ width: `${(count / max) * 100}%` }}
                        />
                      </div>
                      <span className={styles.barCount}>{count}</span>
                    </div>
                  )
                })}
              {!summary?.by_sector || Object.keys(summary.by_sector).length === 0 && (
                <div className={styles.empty}>No data</div>
              )}
            </div>
          </div>

          {/* Urgency */}
          <div className={styles.card}>
            <div className={styles.cardHead}>
              <span className={styles.cardTitle}>Urgency</span>
            </div>
            <div className={styles.urgencyGrid}>
              <div className={styles.urgItem}>
                <span className={styles.urgNum} style={{ color: '#a04040' }}>
                  {summary?.urgency_map.critical ?? 0}
                </span>
                <span className={styles.urgLabel}>Critical ≤7d</span>
              </div>
              <div className={styles.urgItem}>
                <span className={styles.urgNum} style={{ color: '#9a8030' }}>
                  {summary?.urgency_map.hot ?? 0}
                </span>
                <span className={styles.urgLabel}>Hot 8–21d</span>
              </div>
              <div className={styles.urgItem}>
                <span className={styles.urgNum} style={{ color: 'var(--text2)' }}>
                  {summary?.urgency_map.open ?? 0}
                </span>
                <span className={styles.urgLabel}>Open &gt;21d</span>
              </div>
            </div>
          </div>

          {/* Recent jobs */}
          <div className={styles.card}>
            <div className={styles.cardHead}>
              <span className={styles.cardTitle}>Recent scans</span>
              <Link to="/search" className={styles.cardLink}>New search</Link>
            </div>
            <div className={styles.jobList}>
              {recentJobs.length === 0 && (
                <div className={styles.empty}>No scans yet.</div>
              )}
              {recentJobs.map(job => (
                <div key={job.job_id} className={styles.jobRow}>
                  <div className={styles.jobQuery}>{job.query}</div>
                  <div className={styles.jobMeta}>
                    <span className={`${styles.jobStatus} ${styles[`js_${job.status}`]}`}>
                      {job.status}
                    </span>
                    <span className={styles.jobCount}>
                      {job.opportunities_scored} results
                    </span>
                    {job.duration_seconds != null && (
                      <span className={styles.jobDuration}>
                        {job.duration_seconds.toFixed(1)}s
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Report */}
          <a
            href={getReportUrl()}
            target="_blank"
            rel="noreferrer"
            className={styles.reportBtn}
          >
            Export intelligence report
          </a>
        </div>
      </div>
    </div>
  )
}
