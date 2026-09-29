import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

// ── Razorpay global type declaration ─────────────────────────────────────────
declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Razorpay: any
  }
}

const RAZORPAY_KEY_ID = import.meta.env.VITE_RAZORPAY_KEY_ID as string

type PaymentState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'success'; paymentId: string; amount: number }
  | { kind: 'error'; message: string }

// ── Load the Razorpay checkout.js script once ─────────────────────────────────
function useRazorpayScript() {
  const loaded = useRef(false)
  useEffect(() => {
    if (loaded.current || document.getElementById('razorpay-script')) return
    const script = document.createElement('script')
    script.id = 'razorpay-script'
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.async = true
    document.body.appendChild(script)
    loaded.current = true
  }, [])
}

export default function Checkout() {
  useRazorpayScript()

  // Amount to charge (editable by the user, stored in rupees for display)
  const [amountRupees, setAmountRupees] = useState(99)
  const [state, setState] = useState<PaymentState>({ kind: 'idle' })

  async function handlePay() {
    if (!RAZORPAY_KEY_ID) {
      setState({ kind: 'error', message: 'VITE_RAZORPAY_KEY_ID is not set in .env' })
      return
    }
    if (!window.Razorpay) {
      setState({ kind: 'error', message: 'Razorpay checkout.js has not loaded yet. Please try again.' })
      return
    }

    const amountPaise = Math.round(amountRupees * 100)
    if (amountPaise < 100) {
      setState({ kind: 'error', message: 'Minimum amount is ₹1.' })
      return
    }

    setState({ kind: 'loading' })

    let order: Awaited<ReturnType<typeof api.payments.createOrder>>
    try {
      order = await api.payments.createOrder(amountPaise)
    } catch (err) {
      setState({ kind: 'error', message: `Failed to create order: ${String(err)}` })
      return
    }

    const options = {
      key: RAZORPAY_KEY_ID,
      amount: order.amount,          // paise
      currency: order.currency,
      name: 'Revenue Recovery',
      description: 'Test Payment',
      order_id: order.order_id,

      handler: async (response: {
        razorpay_payment_id: string
        razorpay_order_id: string
        razorpay_signature: string
      }) => {
        try {
          const verification = await api.payments.verifyPayment({
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
          })
          if (verification.success) {
            setState({ kind: 'success', paymentId: verification.payment_id, amount: amountPaise })
          } else {
            setState({ kind: 'error', message: 'Signature verification failed.' })
          }
        } catch (err) {
          setState({ kind: 'error', message: `Verification error: ${String(err)}` })
        }
      },

      modal: {
        // Called when user clicks the X button or closes the modal
        ondismiss: () => {
          setState((prev) => (prev.kind === 'loading' ? { kind: 'idle' } : prev))
        },
      },

      prefill: {
        name: '',
        email: '',
        contact: '',
      },

      theme: {
        color: '#6366f1', // matches --accent-indigo
      },
    }

    const rzp = new window.Razorpay(options)

    // Explicit payment failure handler
    rzp.on('payment.failed', (resp: { error: { description: string } }) => {
      setState({ kind: 'error', message: `Payment failed: ${resp.error.description}` })
    })

    rzp.open()
  }

  function reset() {
    setState({ kind: 'idle' })
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Razorpay Checkout</h1>
        <p className="page-subtitle">Standard Web Checkout integration — test mode</p>
      </div>

      <div style={{ maxWidth: 520 }}>
        <div className="card">
          <div className="card-body">

            {/* ── Amount input ── */}
            <div style={{ marginBottom: 24 }}>
              <label
                htmlFor="checkout-amount"
                style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}
              >
                Amount (₹)
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: 20, paddingTop: 1 }}>₹</span>
                <input
                  id="checkout-amount"
                  type="number"
                  min={1}
                  step={1}
                  value={amountRupees}
                  onChange={(e) => setAmountRupees(Number(e.target.value))}
                  className="input"
                  style={{ fontSize: 20, fontWeight: 700, letterSpacing: '0.02em' }}
                  disabled={state.kind === 'loading'}
                />
              </div>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                = {amountRupees * 100} paise &nbsp;·&nbsp; minimum ₹1
              </p>
            </div>

            <div className="separator" />

            {/* ── Pay button ── */}
            {(state.kind === 'idle' || state.kind === 'loading') && (
              <button
                id="rzp-pay-btn"
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center', padding: '12px 0', fontSize: 15 }}
                onClick={handlePay}
                disabled={state.kind === 'loading'}
              >
                {state.kind === 'loading' ? (
                  <>
                    <div className="spinner" style={{ width: 16, height: 16 }} />
                    Creating order…
                  </>
                ) : (
                  <>
                    <span>⚡</span> Pay ₹{amountRupees} with Razorpay
                  </>
                )}
              </button>
            )}

            {/* ── Success state ── */}
            {state.kind === 'success' && (
              <div
                style={{
                  background: 'rgba(16,185,129,0.08)',
                  border: '1px solid rgba(16,185,129,0.3)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '20px 24px',
                  marginBottom: 16,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                  <span style={{ fontSize: 24 }}>✅</span>
                  <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--accent-emerald)' }}>
                    Payment Verified!
                  </span>
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Amount:</span>{' '}
                  <strong>₹{state.amount / 100}</strong>
                </p>
                <p style={{ fontSize: 12, fontFamily: 'monospace', color: 'var(--text-muted)', wordBreak: 'break-all' }}>
                  Payment ID: {state.paymentId}
                </p>
                <button
                  className="btn btn-ghost"
                  style={{ marginTop: 16, fontSize: 12 }}
                  onClick={reset}
                >
                  Make another payment
                </button>
              </div>
            )}

            {/* ── Error state ── */}
            {state.kind === 'error' && (
              <div
                style={{
                  background: 'rgba(244,63,94,0.08)',
                  border: '1px solid rgba(244,63,94,0.3)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '16px 20px',
                  marginBottom: 16,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <span style={{ fontSize: 18, flexShrink: 0 }}>⚠️</span>
                  <p style={{ fontSize: 13, color: 'var(--accent-rose)', lineHeight: 1.5 }}>
                    {state.message}
                  </p>
                </div>
                <button
                  className="btn btn-ghost"
                  style={{ marginTop: 12, fontSize: 12 }}
                  onClick={reset}
                >
                  Try again
                </button>
              </div>
            )}

          </div>

          {/* ── Test-mode footer ── */}
          <div
            style={{
              padding: '12px 24px',
              borderTop: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                background: 'rgba(245,158,11,0.12)',
                color: 'var(--accent-amber)',
                border: '1px solid rgba(245,158,11,0.3)',
                borderRadius: 4,
                padding: '2px 6px',
              }}
            >
              TEST MODE
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Use card <strong style={{ color: 'var(--text-secondary)' }}>4111 1111 1111 1111</strong>, any future expiry, any CVV.
            </span>
          </div>
        </div>

        {/* ── Flow info card ── */}
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-body" style={{ padding: '16px 24px' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>
              Integration Flow
            </p>
            {[
              ['POST /payments/create-order', 'Backend creates a Razorpay order via API'],
              ['Razorpay Modal', 'Frontend opens secure hosted checkout with order_id'],
              ['POST /payments/verify-payment', 'Backend verifies HMAC-SHA256 signature'],
            ].map(([step, desc], i) => (
              <div key={i} style={{ display: 'flex', gap: 12, marginBottom: 10 }}>
                <span
                  style={{
                    width: 20, height: 20, borderRadius: '50%',
                    background: 'rgba(99,102,241,0.15)',
                    color: 'var(--accent-indigo-light)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, fontWeight: 700, flexShrink: 0,
                  }}
                >
                  {i + 1}
                </span>
                <div>
                  <code style={{ fontSize: 11, color: 'var(--accent-indigo-light)' }}>{step}</code>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
