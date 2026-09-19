import { useEffect, useState } from 'react'
import { api, type Policy } from '../api/client'

const MERCHANT_ID = import.meta.env.VITE_MERCHANT_ID || ''

const POLICY_META: Record<string, { label: string; desc: string; type: 'number' | 'boolean' | 'json' }> = {
  max_actions_per_case:    { label: 'Max Actions per Case', desc: 'Maximum automated interventions before escalation', type: 'number' },
  cooldown_hours:          { label: 'Cooldown Hours', desc: 'Minimum hours between touches on same customer', type: 'number' },
  contact_hours_start:     { label: 'Contact Window Start', desc: '24h hour (UTC) before which no SMS/email', type: 'number' },
  contact_hours_end:       { label: 'Contact Window End', desc: '24h hour (UTC) after which no SMS/email', type: 'number' },
  max_discount_pct:        { label: 'Max Discount %', desc: 'Maximum discount the agent can offer', type: 'number' },
  max_agent_spend_per_day: { label: 'Daily Spend Ceiling ($)', desc: 'Max agent cost in USD before pausing automation', type: 'number' },
  dnc_respect:             { label: 'Respect DNC List', desc: 'Always skip do-not-contact customers', type: 'boolean' },
  diagnosis_playbook:      { label: 'Diagnosis Playbook', desc: 'Maps diagnosis codes to allowed tool names', type: 'json' },
}

export default function Policies() {
  const [policies, setPolicies] = useState<Policy[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    if (!MERCHANT_ID) return
    api.policies.list(MERCHANT_ID).then(setPolicies).finally(() => setLoading(false))
  }, [])

  const getValue = (policy: Policy): string => {
    const meta = POLICY_META[policy.key]
    const raw = policy.value
    if (meta?.type === 'json') return JSON.stringify(raw, null, 2)
    if (typeof raw === 'object' && 'v' in raw) return String(raw.v)
    return JSON.stringify(raw)
  }

  const handleSave = async (key: string) => {
    const raw = editing[key]
    if (!raw) return
    setSaving(key)
    try {
      const meta = POLICY_META[key]
      let value: Record<string, unknown>
      if (meta?.type === 'json') {
        value = JSON.parse(raw)
      } else if (meta?.type === 'boolean') {
        value = { v: raw === 'true' }
      } else {
        value = { v: Number(raw) }
      }
      const updated = await api.policies.upsert(MERCHANT_ID, key, value)
      setPolicies((prev) => prev.map((p) => (p.key === key ? updated : p)))
      setEditing((prev) => { const n = { ...prev }; delete n[key]; return n })
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Policies</h1>
        <p className="page-subtitle">Merchant guardrails — edit values and save to take effect immediately</p>
      </div>

      <div className="card card-body">
        {loading && <div className="spinner" style={{ margin: '40px auto' }} />}
        {!loading && policies.map((policy) => {
          const meta = POLICY_META[policy.key]
          const isEditing = policy.key in editing
          const isJson = meta?.type === 'json'

          return (
            <div key={policy.key} className="policy-row">
              <div>
                <div className="policy-key">{meta?.label ?? policy.key}</div>
                <div className="policy-key-desc">{meta?.desc ?? ''}</div>
              </div>
              <div>
                {isEditing ? (
                  isJson ? (
                    <textarea
                      className="input"
                      rows={8}
                      style={{ fontFamily: 'monospace', fontSize: 11 }}
                      value={editing[policy.key]}
                      onChange={(e) => setEditing((p) => ({ ...p, [policy.key]: e.target.value }))}
                    />
                  ) : (
                    <input
                      className="input"
                      value={editing[policy.key]}
                      onChange={(e) => setEditing((p) => ({ ...p, [policy.key]: e.target.value }))}
                    />
                  )
                ) : (
                  <div style={{
                    fontSize: isJson ? 11 : 14,
                    fontFamily: isJson ? 'monospace' : 'inherit',
                    color: 'var(--text-primary)',
                    background: 'var(--bg-elevated)',
                    padding: isJson ? '8px 12px' : '6px 12px',
                    borderRadius: 'var(--radius-sm)',
                    maxHeight: isJson ? 120 : 'none',
                    overflow: 'auto',
                    whiteSpace: isJson ? 'pre' : 'normal',
                  }}>
                    {getValue(policy)}
                  </div>
                )}
              </div>
              <div className="flex-center gap-2">
                {isEditing ? (
                  <>
                    <button className="btn btn-primary" onClick={() => handleSave(policy.key)} disabled={saving === policy.key}>
                      {saving === policy.key ? 'Saving…' : 'Save'}
                    </button>
                    <button className="btn btn-ghost" onClick={() => setEditing((p) => { const n = { ...p }; delete n[policy.key]; return n })}>
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    className="btn btn-ghost"
                    onClick={() => setEditing((p) => ({ ...p, [policy.key]: getValue(policy) }))}
                  >
                    Edit
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
