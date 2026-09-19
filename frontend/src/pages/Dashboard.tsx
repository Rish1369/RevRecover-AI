import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from 'recharts'
import { api, type RecoveryMetrics } from '../api/client'

const MERCHANT_ID = import.meta.env.VITE_MERCHANT_ID || ''

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#f43f5e', '#06b6d4', '#a78bfa']

function paise(v: number) {
  return `₹${(v / 100).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
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
        <div className="page-header">
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Set VITE_MERCHANT_ID in your .env to load data.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header flex-center" style={{ justifyContent: 'space-between' }}>
        <div>
          <h1 className="page-title">Recovery Dashboard</h1>
          <p className="page-subtitle">Revenue attribution & intervention metrics</p>
        </div>
        <select
          className="input"
          style={{ width: 140 }}
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {loading && <div className="spinner" style={{ margin: '60px auto' }} />}

      {metrics && (
        <>
          {/* ── Headline metrics ── */}
          <div className="metrics-grid">
            <div className="metric-tile" style={{ '--accent-color': 'var(--accent-emerald)' } as React.CSSProperties}>
              <div className="metric-tile-label">Recovered</div>
              <div className="metric-tile-value glow-emerald">{paise(metrics.total_recovered_paise)}</div>
              <div className="metric-tile-sub">{metrics.recovered_cases} cases closed</div>
            </div>
            <div className="metric-tile" style={{ '--accent-color': 'var(--accent-indigo)' } as React.CSSProperties}>
              <div className="metric-tile-label">Recovery Rate</div>
              <div className="metric-tile-value" style={{ color: 'var(--accent-indigo-light)' }}>
                {metrics.recovery_rate_pct}%
              </div>
              <div className="metric-tile-sub">{metrics.total_cases} total cases</div>
            </div>
            <div className="metric-tile" style={{ '--accent-color': '#a78bfa' } as React.CSSProperties}>
              <div className="metric-tile-label">Avg Recovery Time</div>
              <div className="metric-tile-value" style={{ color: '#a78bfa' }}>
                {metrics.avg_recovery_days != null ? `${metrics.avg_recovery_days}d` : '—'}
              </div>
              <div className="metric-tile-sub">attribution window 7d</div>
            </div>
            <div className="metric-tile" style={{ '--accent-color': 'var(--accent-amber)' } as React.CSSProperties}>
              <div className="metric-tile-label">Monitoring</div>
              <div className="metric-tile-value" style={{ color: 'var(--accent-amber)' }}>
                {metrics.monitoring_cases}
              </div>
              <div className="metric-tile-sub">awaiting attribution</div>
            </div>
            <div className="metric-tile" style={{ '--accent-color': 'var(--accent-rose)' } as React.CSSProperties}>
              <div className="metric-tile-label">Escalated</div>
              <div className="metric-tile-value" style={{ color: 'var(--accent-rose)' }}>
                {metrics.escalated_cases}
              </div>
              <div className="metric-tile-sub">needs human review</div>
            </div>
          </div>

          {/* ── Charts ── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
            {/* Recovery by diagnosis */}
            <div className="card">
              <div className="card-header">
                <span style={{ fontSize: 14, fontWeight: 600 }}>Recovery by Diagnosis</span>
              </div>
              <div className="card-body">
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={metrics.by_diagnosis} layout="vertical" margin={{ left: 12 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.1)" horizontal={false} />
                      <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
                      <YAxis type="category" dataKey="diagnosis_code" tick={{ fontSize: 10, fill: '#94a3b8' }} width={140} tickLine={false} axisLine={false} />
                      <Tooltip
                        contentStyle={{ background: '#0d1220', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 8, fontSize: 12 }}
                        formatter={(val, name) => [val, name === 'recovered' ? 'Recovered' : 'Total']}
                      />
                      <Bar dataKey="total" fill="rgba(99,102,241,0.3)" radius={[0, 4, 4, 0]} />
                      <Bar dataKey="recovered" fill="#10b981" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Interventions by tool */}
            <div className="card">
              <div className="card-header">
                <span style={{ fontSize: 14, fontWeight: 600 }}>Interventions by Tool</span>
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
                        outerRadius={90}
                        innerRadius={50}
                        paddingAngle={3}
                        label={({ tool, percent }) =>
                          `${tool.replace(/_/g, ' ')} ${(percent * 100).toFixed(0)}%`
                        }
                        labelLine={false}
                      >
                        {metrics.by_tool.map((_, i) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: '#0d1220', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 8, fontSize: 12 }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>

          {/* ── Diagnosis breakdown table ── */}
          <div className="card">
            <div className="card-header" style={{ paddingBottom: 16 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>Diagnosis Breakdown</span>
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
                    <tr key={row.diagnosis_code}>
                      <td><span className="font-mono">{row.diagnosis_code}</span></td>
                      <td>{row.total}</td>
                      <td className="text-emerald">{row.recovered}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{
                            width: 60, height: 4, background: 'rgba(99,102,241,0.2)',
                            borderRadius: 2, overflow: 'hidden',
                          }}>
                            <div style={{
                              width: `${row.recovery_rate_pct}%`, height: '100%',
                              background: row.recovery_rate_pct > 50 ? '#10b981' : '#6366f1',
                              borderRadius: 2,
                            }} />
                          </div>
                          <span style={{ fontSize: 12 }}>{row.recovery_rate_pct}%</span>
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
