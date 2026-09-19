import { useEffect, useState } from 'react'
import { api, type AuditEntry } from '../api/client'
import AuditTimeline from '../components/AuditTimeline'

const MERCHANT_ID = import.meta.env.VITE_MERCHANT_ID || ''

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [chainValidity, setChainValidity] = useState<{ chain_valid: boolean; message: string } | null>(null)
  const [verifying, setVerifying] = useState(false)

  useEffect(() => {
    if (!MERCHANT_ID) return
    api.audit.list(MERCHANT_ID).then(setEntries).finally(() => setLoading(false))
  }, [])

  const handleVerify = async () => {
    setVerifying(true)
    try {
      const result = await api.audit.verifyChain(MERCHANT_ID)
      setChainValidity(result)
    } finally {
      setVerifying(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header flex-center" style={{ justifyContent: 'space-between' }}>
        <div>
          <h1 className="page-title">Audit Log</h1>
          <p className="page-subtitle">Tamper-evident hash-chained record of every agent decision</p>
        </div>
        <button className="btn btn-ghost" onClick={handleVerify} disabled={verifying}>
          {verifying ? '⟳ Verifying…' : '🔒 Verify Chain'}
        </button>
      </div>

      {chainValidity && (
        <div style={{
          padding: '12px 20px',
          borderRadius: 'var(--radius-sm)',
          marginBottom: 20,
          background: chainValidity.chain_valid ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)',
          border: `1px solid ${chainValidity.chain_valid ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.3)'}`,
          color: chainValidity.chain_valid ? 'var(--accent-emerald)' : 'var(--accent-rose)',
          fontSize: 13,
        }}>
          {chainValidity.chain_valid ? '✓' : '✗'} {chainValidity.message}
        </div>
      )}

      <div className="card card-body">
        {loading && <div className="spinner" style={{ margin: '40px auto' }} />}
        {!loading && <AuditTimeline entries={entries} />}
      </div>
    </div>
  )
}
