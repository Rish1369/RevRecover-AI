import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from 'recharts'
import { api, type RecoveryMetrics } from '../api/client'

const MERCHANT_ID = import.meta.env.VITE_MERCHANT_ID || ''

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#f43f5e', '#06b6d4', '#a78bfa', '#fb923c']

function paise(v: number) {
  return `â‚¹${(v / 100).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

function MetricTile({
  label, value, sub, color, icon,
}: { label: string; value: string | number; sub: string; color: string; icon: string }) {
  return (
    <div className="metric-tile" style={{ '--accent-color': color } as React.CSSProperties}>
      <div style={{ fontSize: 22, marginBottom: 10 }}>{icon}</div>
      <div className="metric-tile-label">{label}</div>
      <div className="metric-tile-value" style={{ color }}>{value}</div>
      <div className="metric-tile-sub">{sub}</div>
    </div>
  )
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState<RecoveryMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    if (!MERCHANT_ID) return
    setLoading(true)
    api.metrics.recovery(MERCHANT_ID, days)
      .then(setMetrics)
      .finally(() => setLoading(false))
  }, [days])

  if (!MERCHANT_ID) {
    return (
      <div className="page">
        <div className="hero-banner">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <span style={{ fontSize: 28 }}>âš¡</span>
            <div>
              <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)' }}>RevRecover AI</div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Autonomous Revenue Recovery Agent</div>
            </div>
          </div>
          <p style={{ color: 'var(--accent-amber)', fontSize: 13, fontWeight: 500 }}>
            âš  Set <code style={{ background: 'rgba(245,158,11,0.1)', padding: '1px 6px', borderRadius: 4, fontFamily: 'monospace' }}>VITE_MERCHANT_ID</code> in your <code style={{ fontFamily: 'monospace' }}>.env</code> to load live data.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header flex-between mb-8">
        <div>
          <h1 className="page-title">Recovery Dashboard</h1>
          <p className="page-subtitle">AI-powered revenue attribution &amp; intervention analytics</p>
        </div>
        <div className="flex-center gap-3">
          <div className="flex-center gap-2" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-emerald)', boxShadow: '0 0 6px var(--accent-emerald)', animation: 'pulse-dot 2s infinite' }} />
            Groq Â· Llama 3.3 live
          </div>
          <select
            className="input"
            style={{ width: 150 }}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>

      {loading && <div className="spinner" style={{ margin: '80px auto' }} />}

      {metrics && (
        <>
          {/* â”€â”€ Headline metrics â”€â”€ */}
          <div className="metrics-grid">
            <MetricTile
              label="Revenue Recovered"
              value={paise(metrics.total_recovered_paise)}
              sub={`${metrics.recovered_cases} cases closed`}
              color="var(--accent-emerald)"
              icon="ðŸ’°"
            />
            <MetricTile
              label="Recovery Rate"
              value={`${metrics.recovery_rate_pct}%`}
              sub={`${metrics.total_cases} total cases`}
              color="var(--accent-indigo-light)"
              icon="ðŸ“ˆ"
            />
            <MetricTile
              label="Avg Recovery Time"
              value={metrics.avg_recovery_days != null ? `${metrics.avg_recovery_days}d` : 'â€”'}
              sub="attribution window 7d"
              color="var(--accent-violet)"
              icon="â±"
            />
            <MetricTile
              label="Monitoring"
              value={metrics.monitoring_cases}
              sub="awaiting attribution"
              color="var(--accent-amber)"
              icon="ðŸ‘"
            />
            <MetricTile
              label="Escalated"
              value={metrics.escalated_cases}
              sub="needs human review"
              color="var(--accent-rose)"
              icon="ðŸš¨"
            />
          </div>

          {/* â”€â”€ Charts â”€â”€ */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
            {/* Recovery by diagnosis */}
            <div className="card">
              <div className="card-header">
                <div>
                  <div className="card-title">Recovery by Diagnosis</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Cases recovered vs total</div>
                </div>
              </div>
              <div className="card-body">
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={metrics.by_diagnosis} layout="vertical" margin={{ left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.08)" horizontal={false} />
                      <XAxis type="number" tick={{ fontSize: 10, fill: '#475569' }} tickLine={false} axisLine={false} />
                      <YAxis type="category" dataKey="diagnosis_code" tick={{ fontSize: 9.5, fill: '#475569' }} width={150} tickLine={false} axisLine={false} />
                      <Tooltip
                        contentStyle={{ background: '#0b0f1c', border: '1px solid rgba(99,102,241,0.25)', borderRadius: 10, fontSize: 12 }}
                        formatter={(val, name) => [val, name === 'recovered' ? 'Recovered' : 'Total']}
                      />
                      <Bar dataKey="total" fill="rgba(99,102,241,0.2)" radius={[0, 4, 4, 0]} />
                      <Bar dataKey="recovered" fill="#10b981" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Interventions by tool */}
            <div className="card">
              <div className="card-header">
                <div>
                  <div className="card-title">Interventions by Tool</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Agent action distribution</div>
                </div>
              </div>
              <div className="card-body">
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={metrics.by_tool}
                        dataKey="count"
                        nameKey="tool"
                        cx="50%"
                        cy="50%"
                        outerRadius={95}
                        innerRadius={52}
                        paddingAngle={3}
                        label={({ tool, percent }) =>
                          percent > 0.05 ? `${tool.replace(/_/g, ' ')} ${(percent * 100).toFixed(0)}%` : ''
                        }
                        labelLine={false}
                      >
                        {metrics.by_tool.map((_, i) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: '#0b0f1c', border: '1px solid rgba(99,102,241,0.25)', borderRadius: 10, fontSize: 12 }}
                        formatter={(val: number, name: string) => [val, name.replace(/_/g, ' ')]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>

          {/* â”€â”€ Diagnosis breakdown table â”€â”€ */}
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Diagnosis Breakdown</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Performance by failure reason</div>
              </div>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{metrics.by_diagnosis.length} categories</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Diagnosis Code</th>
                    <th>Total Cases</th>
                    <th>Recovered</th>
                    <th>Recovery Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.by_diagnosis.map((row) => (
                    <tr key={row.diagnosis_code} style={{ cursor: 'default' }}>
                      <td>
                        <span className="font-mono" style={{ color: 'var(--accent-cyan)' }}>
                          {row.diagnosis_code}
                        </span>
                      </td>
                      <td>{row.total}</td>
                      <td className="text-emerald" style={{ fontWeight: 600 }}>{row.recovered}</td>
                      <td>
                        <div className="flex-center gap-3">
                          <div className="progress-bar-bg">
                            <div className="progress-bar-fill" style={{
                              width: `${row.recovery_rate_pct}%`,
                              background: row.recovery_rate_pct > 50
                                ? 'linear-gradient(90deg,#10b981,#34d399)'
                                : 'linear-gradient(90deg,#6366f1,#818cf8)',
                            }} />
                          </div>
                          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', minWidth: 32 }}>
                            {row.recovery_rate_pct}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
