import type { AuditEntry } from '../api/client'
import { formatDistanceToNow } from 'date-fns'

const ACTION_COLORS: Record<string, string> = {
  'policy.approved': 'var(--accent-emerald)',
  'policy.dnc_block': 'var(--accent-amber)',
  'policy.cooldown_block': 'var(--accent-amber)',
  'policy.attempt_cap': 'var(--accent-rose)',
  'policy.auto_escalate': 'var(--accent-rose)',
  'policy.playbook_block': 'var(--accent-rose)',
  'action.executed': 'var(--accent-emerald)',
  'action.failed': 'var(--accent-rose)',
  'action.denied': 'var(--accent-rose)',
  'case.recovered': 'var(--accent-emerald)',
  'case.closed_unrecovered': 'var(--text-muted)',
  'risk_case.diagnosed': 'var(--accent-cyan)',
  'payment.captured': 'var(--accent-emerald)',
}

function dotColor(action: string): string {
  for (const [prefix, color] of Object.entries(ACTION_COLORS)) {
    if (action.startsWith(prefix)) return color
  }
  return 'var(--accent-indigo)'
}

interface AuditTimelineProps {
  entries: AuditEntry[]
}

export default function AuditTimeline({ entries }: AuditTimelineProps) {
  if (!entries.length)
    return <p className="text-muted" style={{ fontSize: 13 }}>No audit entries yet.</p>

  return (
    <div className="timeline">
      {entries.map((entry) => (
        <div key={entry.id} className="timeline-item">
          <div
            className="timeline-dot"
            style={{ borderColor: dotColor(entry.action) }}
          />
          <div className="timeline-time">
            {formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })} · {entry.actor}
          </div>
          <div className="timeline-action">{entry.action}</div>
          {entry.detail && (
            <div className="timeline-detail">{entry.detail}</div>
          )}
          <div className="font-mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
            #{entry.hash.slice(0, 16)}
          </div>
        </div>
      ))}
    </div>
  )
}
