import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { api, type RiskCase } from '../api/client'
import StatusBadge from '../components/StatusBadge'

const MERCHANT_ID = import.meta.env.VITE_MERCHANT_ID || ''

const STATUS_FILTERS = ['all', 'detected', 'diagnosed', 'monitoring', 'recovered', 'escalated', 'closed_unrecovered']

export default function Cases() {
  const navigate = useNavigate()
  const [cases, setCases] = useState<RiskCase[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (!MERCHANT_ID) return
    setLoading(true)
    api.cases.list(MERCHANT_ID, statusFilter !== 'all' ? { status: statusFilter } : {})
      .then(setCases)
      .finally(() => setLoading(false))
  }, [statusFilter])

  const filtered = cases.filter((c) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      c.source_id?.toLowerCase().includes(q) ||
      c.customer_email?.toLowerCase().includes(q) ||
      c.customer_name?.toLowerCase().includes(q) ||
      c.diagnosis_code?.toLowerCase().includes(q)
    )
  })

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Risk Cases</h1>
        <p className="page-subtitle">All active and historical revenue recovery cases</p>
      </div>

      {/* Filters */}
      <div className="flex-center gap-2 mb-6" style={{ flexWrap: 'wrap' }}>
        <input
          className="input"
          placeholder="Search by customer, source ID, diagnosis…"
          style={{ maxWidth: 320 }}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="flex-center gap-2">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              className={`btn ${statusFilter === s ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: 12, padding: '6px 12px' }}
              onClick={() => setStatusFilter(s)}
            >
              {s === 'all' ? 'All' : s.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        {loading && <div className="spinner" style={{ margin: '40px auto' }} />}
        {!loading && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Customer</th>
                  <th>Diagnosis</th>
                  <th>Status</th>
                  <th>Attempts</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>
                      No cases found
                    </td>
                  </tr>
                )}
                {filtered.map((c) => (
                  <tr key={c.id} onClick={() => navigate(`/cases/${c.id}`)}>
                    <td>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 2 }}>
                        {c.source_type.replace(/_/g, ' ')}
                      </div>
                      <div className="td-mono truncate" style={{ maxWidth: 140 }}>
                        {c.source_id ?? '—'}
                      </div>
                    </td>
                    <td>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{c.customer_name ?? '—'}</div>
                      <div className="td-muted">{c.customer_email ?? ''}</div>
                    </td>
                    <td>
                      {c.diagnosis_code ? (
                        <div>
                          <div className="font-mono" style={{ color: 'var(--accent-cyan)', fontSize: 11 }}>
                            {c.diagnosis_code}
                          </div>
                          {c.diagnosis_confidence != null && (
                            <div className="td-muted">
                              {(c.diagnosis_confidence * 100).toFixed(0)}% conf.
                            </div>
                          )}
                        </div>
                      ) : '—'}
                    </td>
                    <td><StatusBadge status={c.status} /></td>
                    <td style={{ textAlign: 'center' }}>
                      <span style={{
                        display: 'inline-block',
                        width: 24, height: 24,
                        borderRadius: '50%',
                        background: 'rgba(99,102,241,0.15)',
                        lineHeight: '24px',
                        textAlign: 'center',
                        fontSize: 12,
                        fontWeight: 700,
                        color: 'var(--accent-indigo-light)',
                      }}>
                        {c.attempts_count}
                      </span>
                    </td>
                    <td className="td-muted">
                      {formatDistanceToNow(new Date(c.created_at), { addSuffix: true })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
