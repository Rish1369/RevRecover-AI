import { NavLink, useLocation } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '◈' },
  { to: '/cases', label: 'Cases', icon: '⚡' },
  { to: '/audit', label: 'Audit Log', icon: '🔗' },
  { to: '/policies', label: 'Policies', icon: '⚙' },
]

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">⚡</div>
        <div>
          <div className="sidebar-logo-text">RRA</div>
          <div className="sidebar-logo-sub">Revenue Recovery</div>
        </div>
      </div>

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
    </aside>
  )
}
