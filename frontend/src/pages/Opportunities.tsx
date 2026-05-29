import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listOpportunities, getReportUrl } from '../api/client'
import type { Opportunity, SortKey, SortDir, ListParams } from '../types'
import OpportunityTable from '../components/OpportunityTable'
import OpportunityDetail from '../components/OpportunityDetail'
import styles from './Opportunities.module.css'

export default function OpportunitiesPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const [items, setItems] = useState<Opportunity[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [selectedOpp, setSelectedOpp] = useState<Opportunity | null>(null)

  // Filter/sort state — read initial values from URL
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState<SortKey>('final_score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [sector, setSector] = useState(searchParams.get('sector') || '')
  const [country, setCountry] = useState(searchParams.get('country') || '')
  const [oppType, setOppType] = useState(searchParams.get('type') || '')
  const [minScore, setMinScore] = useState(Number(searchParams.get('min_score') || 0))
  const [search, setSearch] = useState('')
  const jobId = searchParams.get('job_id') || undefined

  const PAGE_SIZE = 25

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: ListParams = {
        page,
        page_size: PAGE_SIZE,
        sort_by: sortBy,
        sort_dir: sortDir,
        sector: sector || undefined,
        country: country || undefined,
        opportunity_type: oppType || undefined,
        min_score: minScore || undefined,
        search: search || undefined,
        job_id: jobId,
      }
      const res = await listOpportunities(params)
      setItems(res.items)
      setTotal(res.total)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [page, sortBy, sortDir, sector, country, oppType, minScore, search, jobId])

  useEffect(() => { load() }, [load])

  const handleSort = (key: SortKey) => {
    if (sortBy === key) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    } else {
      setSortBy(key)
      setSortDir('desc')
    }
    setPage(1)
  }

  const handleSelect = (opp: Opportunity) => {
    setSelectedOpp(opp)
  }

  const handleUpdate = (id: string, patch: Partial<Opportunity>) => {
    setItems(prev => prev.map(o => o.id === id ? { ...o, ...patch } : o))
    if (selectedOpp?.id === id) {
      setSelectedOpp(prev => prev ? { ...prev, ...patch } : null)
    }
  }

  const clearJobFilter = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('job_id')
    setSearchParams(next)
  }

  return (
    <div className={styles.page}>
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          <span className={styles.total}>
            {loading ? '...' : `${total} opportunities`}
          </span>
          {jobId && (
            <span className={styles.jobFilter}>
              job: {jobId.slice(0, 8)}
              <button className={styles.clearJob} onClick={clearJobFilter}>×</button>
            </span>
          )}
        </div>

        <div className={styles.filters}>
          <input
            className={styles.searchInput}
            type="text"
            placeholder="Filter by title, org..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
          />
          <select className={styles.select} value={sector} onChange={e => { setSector(e.target.value); setPage(1) }}>
            <option value="">All sectors</option>
            <option value="AI">AI</option>
            <option value="Software">Software</option>
            <option value="Data Analytics">Data Analytics</option>
            <option value="Healthcare">Healthcare</option>
            <option value="Traffic">Traffic</option>
            <option value="Cybersecurity">Cybersecurity</option>
          </select>
          <select className={styles.select} value={country} onChange={e => { setCountry(e.target.value); setPage(1) }}>
            <option value="">All countries</option>
            <option value="Colombia">Colombia</option>
            <option value="Mexico">Mexico</option>
            <option value="Peru">Peru</option>
            <option value="Chile">Chile</option>
            <option value="Brazil">Brazil</option>
            <option value="Argentina">Argentina</option>
          </select>
          <select className={styles.select} value={oppType} onChange={e => { setOppType(e.target.value); setPage(1) }}>
            <option value="">All types</option>
            <option value="public_tender">Public Tender</option>
            <option value="private_rfp">Private RFP</option>
            <option value="grant">Grant</option>
          </select>
          <select className={styles.select} value={minScore} onChange={e => { setMinScore(Number(e.target.value)); setPage(1) }}>
            <option value={0}>Any score</option>
            <option value={60}>60+</option>
            <option value={70}>70+</option>
            <option value={80}>80+</option>
            <option value={90}>90+</option>
          </select>
          <a
            href={getReportUrl()}
            target="_blank"
            rel="noreferrer"
            className={styles.reportBtn}
          >
            Export report
          </a>
        </div>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {/* Split view */}
      <div className={styles.split}>
        <div className={styles.tablePane}>
          <OpportunityTable
            items={items}
            total={total}
            page={page}
            pageSize={PAGE_SIZE}
            sortBy={sortBy}
            sortDir={sortDir}
            selectedId={selectedOpp?.id ?? null}
            onSelect={handleSelect}
            onSort={handleSort}
            onPage={setPage}
          />
        </div>

        {selectedOpp && (
          <div className={styles.detailPane}>
            <OpportunityDetail
              opportunity={selectedOpp}
              onUpdate={handleUpdate}
            />
          </div>
        )}
      </div>
    </div>
  )
}
