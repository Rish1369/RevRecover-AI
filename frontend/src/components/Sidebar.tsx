import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '◈', desc: 'Overview & KPIs' },
  { to: '/cases', label: 'Risk Cases', icon: '⚡', desc: 'Active & historical' },
  { to: '/audit', label: 'Audit Log', icon: '🔍', desc: 'Action trail' },
  { to: '/policies', label: 'Policies', icon: '⚙', desc: 'Merchant guardrails' },
  { to: '/checkout', label: 'Checkout', icon: '💳', desc: 'Test payment flow' },
]

export default function Sidebar() {
  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">⚡</div>
        <div>
          <div className="sidebar-logo-text">RevRecover</div>
          <div className="sidebar-logo-sub">AI Revenue Agent</div>
        </div>
      </div>

      {/* Nav */}
      <div className="nav-section-label">Navigation</div>
      {NAV.map(({ to, label, icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
        >
          <span className="nav-link-icon">{icon}</span>
          {label}
        </NavLink>
      ))}

      {/* AI Engine badge at the bottom */}
      <div className="sidebar-footer">
        <div className="sidebar-ai-badge">
          <div className="sidebar-ai-dot" />
          <div className="sidebar-ai-text">
            AI Engine<br />
            <strong>Groq · Llama 3.3</strong>
          </div>
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-dim)', textAlign: 'center', padding: '0 4px' }}>
          Revenue Recovery Agent v1.0
        </div>
      </div>
    </aside>
  )
}

