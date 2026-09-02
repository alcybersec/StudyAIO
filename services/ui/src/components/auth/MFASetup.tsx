import { useState } from 'react'
import { useMFASetup, useMFAVerify, useMFADisable, useSessionHandoff } from '../../hooks/useAuth'

interface MFASetupProps {
  mfaEnabled: boolean
}

export function MFASetup({ mfaEnabled }: MFASetupProps) {
  const [step, setStep] = useState<'idle' | 'qr' | 'verify' | 'done' | 'disable'>('idle')
  const [secret, setSecret] = useState('')
  const [code, setCode] = useState('')
  const [disableCode, setDisableCode] = useState('')
  const [backupCodes, setBackupCodes] = useState<string[]>([])
  const [error, setError] = useState('')

  const setupMutation = useMFASetup()
  const verifyMutation = useMFAVerify()
  const disableMutation = useMFADisable()
  const endSession = useSessionHandoff()

  const handleSetup = async () => {
    setError('')
    try {
      const result = await setupMutation.mutateAsync()
      setSecret(result.secret)
      setStep('qr')
    } catch {
      setError('Failed to start MFA setup')
    }
  }

  const handleVerify = async () => {
    setError('')
    try {
      const result = await verifyMutation.mutateAsync({ totp_code: code, secret })
      setBackupCodes(result.backup_codes)
      setStep('done')
    } catch {
      setError('Invalid code. Please try again.')
    }
  }

  const handleDisable = async () => {
    setError('')
    try {
      const result = await disableMutation.mutateAsync(disableCode)
      setStep('idle')
      setDisableCode('')
      if (result.session_ended) {
        endSession('mfa_disabled')
      }
    } catch {
      setError('Invalid code. Please try again.')
    }
  }

  if (mfaEnabled && step === 'idle') {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm text-sage-fg font-medium">
          <span>MFA is enabled</span>
        </div>
        <button
          onClick={() => setStep('disable')}
          className="text-sm text-red-fg hover:underline"
        >
          Disable MFA
        </button>
      </div>
    )
  }

  if (step === 'disable') {
    return (
      <div className="space-y-3">
        <p className="text-sm text-text-muted">Enter your TOTP code to disable MFA:</p>
        <input
          type="text"
          value={disableCode}
          onChange={(e) => setDisableCode(e.target.value)}
          placeholder="6-digit code"
          maxLength={6}
          className="w-full px-3 py-2 bg-surface-1 border border-border rounded-lg text-text placeholder:text-text-faint text-sm focus:outline-none focus:ring-2 focus:ring-sage/30"
        />
        {error && <p className="text-sm text-red-fg">{error}</p>}
        <div className="flex gap-2">
          <button
            onClick={handleDisable}
            disabled={disableCode.length !== 6 || disableMutation.isPending}
            className="px-4 min-h-[44px] bg-red text-on-accent rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50"
          >
            {disableMutation.isPending ? 'Disabling...' : 'Disable MFA'}
          </button>
          <button
            onClick={() => { setStep('idle'); setError('') }}
            className="px-4 min-h-[44px] text-sm text-text-muted hover:text-text"
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  if (step === 'done') {
    return (
      <div className="space-y-3">
        <p className="text-sm font-medium text-sage-fg">MFA enabled successfully!</p>
        <p className="text-sm text-text-muted">Save these backup codes in a secure place:</p>
        <div className="bg-surface-2 text-text rounded-lg p-3 font-mono text-sm space-y-1">
          {backupCodes.map((c, i) => (
            <div key={i}>{c}</div>
          ))}
        </div>
        <button
          onClick={() => setStep('idle')}
          className="px-4 min-h-[44px] bg-sage text-on-accent rounded-lg text-sm font-medium hover:bg-sage-hover"
        >
          Done
        </button>
      </div>
    )
  }

  if (step === 'qr') {
    return (
      <div className="space-y-3">
        <p className="text-sm text-text-muted">
          Scan this QR code with your authenticator app:
        </p>
        {setupMutation.data && (
          <div className="flex justify-center">
            <img
              src={`data:image/png;base64,${setupMutation.data.qr_code_base64}`}
              alt="MFA QR Code"
              className="w-48 h-48"
            />
          </div>
        )}
        <p className="text-xs text-text-faint break-all">
          Manual key: {secret}
        </p>
        <div>
          <label className="block text-sm font-medium text-text-muted mb-1">
            Enter the 6-digit code from your app
          </label>
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="000000"
            maxLength={6}
            className="w-full px-3 py-2 bg-surface-1 border border-border rounded-lg text-text placeholder:text-text-faint text-sm focus:outline-none focus:ring-2 focus:ring-sage/30"
          />
        </div>
        {error && <p className="text-sm text-red-fg">{error}</p>}
        <button
          onClick={handleVerify}
          disabled={code.length !== 6 || verifyMutation.isPending}
          className="w-full min-h-[44px] bg-sage text-on-accent rounded-lg text-sm font-medium hover:bg-sage-hover disabled:opacity-50"
        >
          {verifyMutation.isPending ? 'Verifying...' : 'Verify & Enable'}
        </button>
      </div>
    )
  }

  // idle + not enabled
  return (
    <div className="space-y-3">
      <p className="text-sm text-text-muted">
        Add an extra layer of security with two-factor authentication.
      </p>
      <button
        onClick={handleSetup}
        disabled={setupMutation.isPending}
        className="px-4 min-h-[44px] bg-sage text-on-accent rounded-lg text-sm font-medium hover:bg-sage-hover disabled:opacity-50"
      >
        {setupMutation.isPending ? 'Setting up...' : 'Enable MFA'}
      </button>
    </div>
  )
}
