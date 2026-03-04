import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { OAuthButtons } from '../components/auth/OAuthButtons'
import { ApiError } from '../api/client'

export function LoginPage() {
  const navigate = useNavigate()
  const { login, authConfig } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [showMFA, setShowMFA] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await login({ email, password, totp_code: showMFA ? totpCode : undefined })
      navigate('/')
    } catch (err) {
      if (err instanceof ApiError && err.status === 403 && err.detail.toLowerCase().includes('mfa')) {
        setShowMFA(true)
        setError('Enter your MFA code to continue')
      } else if (err instanceof ApiError) {
        setError(err.detail)
      } else {
        setError('Login failed')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-6">Sign in</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>
        {showMFA && (
          <div>
            <label htmlFor="totp" className="block text-sm font-medium text-gray-700 mb-1">
              MFA Code
            </label>
            <input
              id="totp"
              type="text"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              placeholder="6-digit code"
              maxLength={6}
              autoFocus
            />
          </div>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full min-h-[44px] bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark disabled:opacity-50 transition-colors"
        >
          {loading ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
      <OAuthButtons providers={authConfig?.oauth_providers ?? []} />
      <div className="mt-4 text-center text-sm text-gray-500 space-y-1">
        <p>
          <Link to="/forgot-password" className="text-primary hover:underline">
            Forgot password?
          </Link>
        </p>
        {authConfig?.registration_enabled && (
          <p>
            Don&apos;t have an account?{' '}
            <Link to="/register" className="text-primary hover:underline">
              Register
            </Link>
          </p>
        )}
      </div>
    </div>
  )
}
