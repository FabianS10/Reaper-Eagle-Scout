import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { startSearch, getJobStatus } from '../api/client'
import type { SearchJob } from '../types'
import styles from './Search.module.css'

const PRESET_QUERIES = [
  'AI software procurement tenders worldwide 2025',
  'data analytics RFP government contract global',
  'healthcare AI tender procurement international',
  'traffic management smart city tender worldwide',
  'cybersecurity public sector RFP 2025',
  'World Bank digital platform procurement data analytics',
  'EU TED artificial intelligence software tender',
  'UNGM cloud software procurement opportunity',
]

const PIPELINE_STAGES = [
  { key: 'discovery',  label: 'SERP Discovery — Bright Data' },
  { key: 'fetching',   label: 'Page fetch — Web Unlocker' },
  { key: 'parsing',    label: 'HTML / PDF parsing' },
  { key: 'extracting', label: 'AI structured extraction' },
  { key: 'scoring',    label: 'Scoring + ranking' },
] as const

const STAGE_ORDER = ['pending','running','discovery','fetching','parsing','extracting','scoring','complete','failed']

function stageStatus(currentStage: string, stageKey: string): 'done' | 'running' | 'pending' {
  const ci = STAGE_ORDER.indexOf(currentStage)
  const si = STAGE_ORDER.indexOf(stageKey)
  if (ci > si) return 'done'
  if (ci === si) return 'running'
  return 'pending'
}

export default function SearchPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [country, setCountry] = useState('')
  const [sector, setSector] = useState('')
  const [maxResults, setMaxResults] = useState(20)
  const [job, setJob] = useState<SearchJob | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const stopPolling = () => {
    if (pollRef.current) clearTimeout(pollRef.current)
  }

  const pollJob = useCallback(async (jobId: string) => {
    try {
      const updated = await getJobStatus(jobId)
      setJob(updated)
      if (updated.status === 'complete') {
        setLoading(false)
        // Navigate to opportunities filtered by this job
        navigate(`/opportunities?job_id=${jobId}`)
      } else if (updated.status === 'failed') {
        setLoading(false)
        setError(updated.error_message || 'Pipeline failed')
      } else {
        pollRef.current = setTimeout(() => pollJob(jobId), 1500)
      }
    } catch (e: any) {
      setError(e.message)
      setLoading(false)
    }
  }, [navigate])

  useEffect(() => () => stopPolling(), [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setError(null)
    setLoading(true)
    setJob(null)
    stopPolling()

    try {
      const newJob = await startSearch({
        query: query.trim(),
        country: country || undefined,
        sector: sector || undefined,
        max_results: maxResults,
      })
      setJob(newJob)
      pollRef.current = setTimeout(() => pollJob(newJob.job_id), 1000)
    } catch (e: any) {
      setError(e.message)
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.inner}>
        <div className={styles.heading}>
          <h1 className={styles.h1}>Search</h1>
          <p className={styles.subtitle}>
            Describe what you are looking for. Eagle Scout runs discovery, fetching,
            parsing, and AI extraction automatically.
          </p>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.queryRow}>
            <input
              className={styles.queryInput}
              type="text"
              placeholder="e.g. AI and software tenders Colombia, healthcare analytics LATAM..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              disabled={loading}
              autoFocus
            />
            <button
              type="submit"
              className={styles.submitBtn}
              disabled={loading || !query.trim()}
            >
              {loading ? 'Running...' : 'Deploy'}
            </button>
          </div>

          <div className={styles.filters}>
            <select
              className={styles.select}
              value={country}
              onChange={e => setCountry(e.target.value)}
              disabled={loading}
            >
              <option value="">Worldwide</option>
              <option value="Worldwide">Worldwide</option>
              <option value="United States">United States</option>
              <option value="United Kingdom">United Kingdom</option>
              <option value="European Union">European Union</option>
              <option value="Canada">Canada</option>
              <option value="Australia">Australia</option>
              <option value="Colombia">Colombia</option>
              <option value="Mexico">Mexico</option>
              <option value="Peru">Peru</option>
              <option value="Chile">Chile</option>
              <option value="Brazil">Brazil</option>
              <option value="Argentina">Argentina</option>
            </select>

            <select
              className={styles.select}
              value={sector}
              onChange={e => setSector(e.target.value)}
              disabled={loading}
            >
              <option value="">All sectors</option>
              <option value="AI">AI / ML</option>
              <option value="Software">Software</option>
              <option value="Data Analytics">Data Analytics</option>
              <option value="Healthcare">Healthcare</option>
              <option value="Traffic">Traffic</option>
              <option value="Cybersecurity">Cybersecurity</option>
              <option value="Cloud">Cloud</option>
            </select>

            <select
              className={styles.select}
              value={maxResults}
              onChange={e => setMaxResults(Number(e.target.value))}
              disabled={loading}
            >
              <option value={10}>10 results</option>
              <option value={20}>20 results</option>
              <option value={30}>30 results</option>
              <option value={50}>50 results</option>
            </select>
          </div>

          <div className={styles.presets}>
            {PRESET_QUERIES.map(q => (
              <button
                key={q}
                type="button"
                className={styles.preset}
                onClick={() => setQuery(q)}
                disabled={loading}
              >
                {q}
              </button>
            ))}
          </div>
        </form>

        {error && (
          <div className={styles.error}>{error}</div>
        )}

        {job && (
          <div className={styles.pipeline}>
            <div className={styles.pipelineHeader}>
              <span className={styles.pipelineLabel}>
                {job.status === 'complete' ? 'Complete' : job.status === 'failed' ? 'Failed' : 'Pipeline running'}
              </span>
              <span className={styles.pipelineProgress}>{job.progress_pct}%</span>
            </div>

            <div className={styles.progressBar}>
              <div className={styles.progressFill} style={{ width: `${job.progress_pct}%` }} />
            </div>

            <div className={styles.stages}>
              {PIPELINE_STAGES.map(stage => {
                const s = stageStatus(job.status, stage.key)
                return (
                  <div key={stage.key} className={`${styles.stage} ${styles[`stage_${s}`]}`}>
                    <span className={styles.stageDot} />
                    <span className={styles.stageLabel}>{stage.label}</span>
                    <span className={styles.stageStatus}>
                      {s === 'done' ? 'done' : s === 'running' ? 'running' : '—'}
                    </span>
                  </div>
                )
              })}
            </div>

            <div className={styles.counters}>
              <div className={styles.counter}>
                <span className={styles.counterVal}>{job.urls_discovered}</span>
                <span className={styles.counterLabel}>discovered</span>
              </div>
              <div className={styles.counter}>
                <span className={styles.counterVal}>{job.urls_fetched}</span>
                <span className={styles.counterLabel}>fetched</span>
              </div>
              <div className={styles.counter}>
                <span className={styles.counterVal}>{job.urls_parsed}</span>
                <span className={styles.counterLabel}>parsed</span>
              </div>
              <div className={styles.counter}>
                <span className={styles.counterVal}>{job.opportunities_extracted}</span>
                <span className={styles.counterLabel}>extracted</span>
              </div>
              <div className={styles.counter}>
                <span className={styles.counterVal}>{job.opportunities_scored}</span>
                <span className={styles.counterLabel}>scored</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
