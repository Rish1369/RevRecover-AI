import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { formatDistanceToNow, format } from 'date-fns'
import { api, type RiskCase, type AgentAction, type AuditEntry } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import AuditTimeline from '../components/AuditTimeline'

const MERCHANT_ID = import.meta.env.VITE_MERCHANT_ID || ''

export default function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const [riskCase, setRiskCase] = useState<RiskCase | null>(null)
  const [actions, setActions] = useState<AgentAction[]>([])
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [escalating, setEscalating] = useState(false)

  useEffect(() => {
    if (!MERCHANT_ID || !caseId) return
    Promise.all([
      api.cases.get(MERCHANT_ID, caseId),
      api.actions.listForCase(MERCHANT_ID, caseId),
      api.audit.list(MERCHANT_ID),
    ]).then(([c, a, au]) => {
      setRiskCase(c)
      setActions(a)
      // filter audit entries to this case
      setAudit(au.filter((e) => e.target_id === caseId))
    }).finally(() => setLoading(false))
  }, [caseId])

  const handleEscalate = async () => {
    if (!riskCase || !MERCHANT_ID) return
    setEscalating(true)
    try {
      await api.cases.escalate(MERCHANT_ID, riskCase.id)
      setRiskCase({ ...riskCase, status: 'escalated' })
    } finally {
      setEscalating(false)
    }
  }

  if (loading) return <div className="page"><div className="spinner" style={{ margin: '60px auto' }} /></div>
  if (!riskCase) return <div className="page"><p className="text-muted">Case not found</p></div>

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header flex-center" style={{ justifyContent: 'space-between' }}>
        <div>
          <button className="btn btn-ghost mb-4" style={{ fontSize: 12 }} onClick={() => navigate('/cases')}>
            ← Back to Cases
          </button>
          <h1 className="page-title">
            Case: <span className="font-mono" style={{ fontSize: 18 }}>{riskCase.id.slice(0, 8)}…</span>
          </h1>
          <p className="page-subtitle">
            {riskCase.source_type.replace(/_/g, ' ')} · created {formatDistanceToNow(new Date(riskCase.created_at), { addSuffix: true })}
          </p>
        </div>
        <div className="flex-center gap-2">
          <StatusBadge status={riskCase.status} />
          {!['recovered', 'closed_unrecovered', 'escalated'].includes(riskCase.status) && (
            <button className="btn btn-danger" onClick={handleEscalate} disabled={escalating}>
              {escalating ? 'Escalating…' : 'Escalate to Human'}
            </button>
          )}
        </div>
      </div>

      {/* Case summary */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        <div className="card card-body">
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 16, color: 'var(--text-muted)' }}>CASE INFO</h3>
          <dl style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '10px 16px', fontSize: 13 }}>
            <dt style={{ color: 'var(--text-muted)' }}>Source Type</dt>
            <dd>{riskCase.source_type}</dd>
            <dt style={{ color: 'var(--text-muted)' }}>Source ID</dt>
            <dd className="font-mono">{riskCase.source_id ?? '—'}</dd>
            <dt style={{ color: 'var(--text-muted)' }}>Diagnosis</dt>
            <dd style={{ color: 'var(--accent-cyan)' }}>{riskCase.diagnosis_code ?? '—'}</dd>
            <dt style={{ color: 'var(--text-muted)' }}>Confidence</dt>
            <dd>{riskCase.diagnosis_confidence != null ? `${(riskCase.diagnosis_confidence * 100).toFixed(0)}%` : '—'}</dd>
            <dt style={{ color: 'var(--text-muted)' }}>Attempts</dt>
            <dd>{riskCase.attempts_count}</dd>
            <dt style={{ color: 'var(--text-muted)' }}>Resolved</dt>
            <dd>{riskCase.resolved_at ? format(new Date(riskCase.resolved_at), 'PPpp') : '—'}</dd>
          </dl>
        </div>

        <div className="card card-body">
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 16, color: 'var(--text-muted)' }}>CUSTOMER</h3>
          <dl style={{ display: 'grid', gridTemplateColumns: '100px 1fr', gap: '10px 16px', fontSize: 13 }}>
            <dt style={{ color: 'var(--text-muted)' }}>Name</dt>
            <dd>{riskCase.customer_name ?? '—'}</dd>
            <dt style={{ color: 'var(--text-muted)' }}>Email</dt>
            <dd>{riskCase.customer_email ?? '—'}</dd>
          </dl>
        </div>
      </div>

      {/* Agent actions */}
      <div className="card mb-6">
        <div className="card-header" style={{ paddingBottom: 16 }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>Agent Actions</span>
          <span className="td-muted">{actions.length} total</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tool</th>
                <th>Reasoning</th>
                <th>Policy Check</th>
                <th>Status</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {actions.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>No actions yet</td></tr>
              )}
              {actions.map((a) => (
                <tr key={a.id}>
                  <td>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-indigo-light)' }}>
                      {a.tool_name.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td style={{ maxWidth: 300 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      {a.reasoning_summary ?? '—'}
                    </div>
                  </td>
                  <td>
                    <StatusBadge status={a.policy_check_result ?? 'pending'} />
                    {a.policy_check_reason && (
                      <div className="td-muted" style={{ marginTop: 4, maxWidth: 200 }}>
                        {a.policy_check_reason.slice(0, 80)}
                      </div>
                    )}
                  </td>
                  <td><StatusBadge status={a.status} /></td>
                  <td className="td-muted">
                    {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Audit trail */}
      <div className="card card-body">
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 20 }}>
          Audit Trail
          <span className="td-muted" style={{ fontWeight: 400, marginLeft: 8 }}>{audit.length} entries</span>
        </h3>
        <AuditTimeline entries={audit} />
      </div>
    </div>
  )
}
