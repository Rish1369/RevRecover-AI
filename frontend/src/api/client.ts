const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`${res.status}: ${err}`)
  }
  return res.json()
}

export interface RiskCase {
  id: string
  merchant_id: string
  customer_id: string | null
  customer_name: string | null
  customer_email: string | null
  source_type: string
  source_id: string | null
  diagnosis_code: string | null
  diagnosis_confidence: number | null
  risk_score: number | null
  status: string
  attempts_count: number
  created_at: string
  resolved_at: string | null
}

export interface AgentAction {
  id: string
  risk_case_id: string
  tool_name: string
  input_json: Record<string, unknown> | null
  reasoning_summary: string | null
  policy_check_result: string | null
  policy_check_reason: string | null
  output_json: Record<string, unknown> | null
  status: string
  created_at: string
}

export interface AuditEntry {
  id: string
  actor: string
  action: string
  target_id: string | null
  detail: string | null
  hash: string
  prev_hash: string | null
  created_at: string
}

export interface Policy {
  id: string
  key: string
  value: Record<string, unknown>
  updated_at: string
}

export interface RecoveryMetrics {
  total_cases: number
  recovered_cases: number
  escalated_cases: number
  closed_unrecovered_cases: number
  monitoring_cases: number
  recovery_rate_pct: number
  total_at_risk_paise: number
  total_recovered_paise: number
  avg_recovery_days: number | null
  by_diagnosis: Array<{ diagnosis_code: string; total: number; recovered: number; recovery_rate_pct: number }>
  by_tool: Array<{ tool: string; count: number }>
}

// ── Razorpay Checkout ────────────────────────────────────────────────────────

export interface CreateOrderResponse {
  order_id: string
  amount: number
  currency: string
}

export interface VerifyPaymentRequest {
  razorpay_order_id: string
  razorpay_payment_id: string
  razorpay_signature: string
}

export interface VerifyPaymentResponse {
  success: boolean
  payment_id: string
}

export const api = {
  cases: {
    list: (merchantId: string, params?: { status?: string; source_type?: string }) => {
      const qs = new URLSearchParams({ merchant_id: merchantId, ...params }).toString()
      return req<RiskCase[]>(`/cases?${qs}`)
    },
    get: (merchantId: string, caseId: string) =>
      req<RiskCase>(`/cases/${caseId}?merchant_id=${merchantId}`),
    escalate: (merchantId: string, caseId: string) =>
      req<{ status: string }>(`/cases/${caseId}/escalate?merchant_id=${merchantId}`, { method: 'POST' }),
  },
  actions: {
    listForCase: (merchantId: string, caseId: string) =>
      req<AgentAction[]>(`/actions/cases/${caseId}/actions?merchant_id=${merchantId}`),
  },
  audit: {
    list: (merchantId: string) =>
      req<AuditEntry[]>(`/audit?merchant_id=${merchantId}`),
    verifyChain: (merchantId: string) =>
      req<{ chain_valid: boolean; message: string }>(`/audit/verify-chain?merchant_id=${merchantId}`),
  },
  policies: {
    list: (merchantId: string) =>
      req<Policy[]>(`/policies?merchant_id=${merchantId}`),
    upsert: (merchantId: string, key: string, value: Record<string, unknown>) =>
      req<Policy>(`/policies/${key}?merchant_id=${merchantId}`, {
        method: 'PUT',
        body: JSON.stringify({ value }),
      }),
  },
  metrics: {
    recovery: (merchantId: string, days = 30) =>
      req<RecoveryMetrics>(`/metrics/recovery?merchant_id=${merchantId}&days=${days}`),
  },
  payments: {
    createOrder: (amount: number, currency = 'INR') =>
      req<CreateOrderResponse>('/payments/create-order', {
        method: 'POST',
        body: JSON.stringify({ amount, currency }),
      }),
    verifyPayment: (payload: VerifyPaymentRequest) =>
      req<VerifyPaymentResponse>('/payments/verify-payment', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
  },
}
