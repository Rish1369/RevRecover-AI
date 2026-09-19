interface StatusBadgeProps {
  status: string
}

const LABELS: Record<string, string> = {
  detected: 'Detected',
  diagnosed: 'Diagnosed',
  action_taken: 'Action Taken',
  monitoring: 'Monitoring',
  recovered: 'Recovered',
  escalated: 'Escalated',
  closed_unrecovered: 'Unrecovered',
  approved: 'Approved',
  denied: 'Denied',
  executed: 'Executed',
  failed: 'Failed',
  skipped_dnc: 'DNC Skip',
  pending: 'Pending',
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`badge badge-${status}`}>
      {LABELS[status] ?? status}
    </span>
  )
}
