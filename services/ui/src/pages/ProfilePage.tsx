import { useState, type FormEvent } from 'react'
import { useAuth, useChangePassword, useUpdateProfile } from '../hooks/useAuth'
import { MFASetup } from '../components/auth/MFASetup'
import { ApiError } from '../api/client'

export function ProfilePage() {
  const { user } = useAuth()
  const updateProfile = useUpdateProfile()
  const changePassword = useChangePassword()

  const [username, setUsername] = useState(user?.username ?? '')
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url ?? '')
  const [profileMsg, setProfileMsg] = useState('')

  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordMsg, setPasswordMsg] = useState('')
  const [passwordError, setPasswordError] = useState('')

  const handleProfileSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setProfileMsg('')
    try {
      await updateProfile.mutateAsync({
        username: username || undefined,
        avatar_url: avatarUrl || undefined,
      })
      setProfileMsg('Profile updated')
    } catch (err) {
      setProfileMsg(err instanceof ApiError ? err.message : 'Update failed')
    }
  }

  const handlePasswordSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setPasswordError('')
    setPasswordMsg('')

    if (newPassword.length < 8) {
      setPasswordError('Password must be at least 8 characters')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match')
      return
    }

    try {
      await changePassword.mutateAsync({
        old_password: oldPassword,
        new_password: newPassword,
      })
      setPasswordMsg('Password changed')
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : 'Change failed')
    }
  }

  if (!user) {
    return (
      <div className="text-center py-12 text-text-muted">
        Not available in self-hosted mode
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-text">Profile</h1>

      {/* Profile Info */}
      <div className="bg-surface-1 rounded-lg border border-border p-6">
        <h2 className="text-lg font-semibold text-text mb-4">Profile Info</h2>
        <form onSubmit={handleProfileSubmit} className="space-y-4">
          <div>
            <label htmlFor="prof-email" className="block text-sm font-medium text-text mb-1">
              Email
            </label>
            <input
              id="prof-email"
              type="email"
              value={user.email}
              disabled
              className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-surface-0 text-text-muted"
            />
          </div>
          <div>
            <label htmlFor="prof-username" className="block text-sm font-medium text-text mb-1">
              Username
            </label>
            <input
              id="prof-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-surface-1 focus:outline-none focus:ring-2 focus:ring-sage/30"
            />
          </div>
          <div>
            <label htmlFor="prof-avatar" className="block text-sm font-medium text-text mb-1">
              Avatar URL
            </label>
            <input
              id="prof-avatar"
              type="url"
              value={avatarUrl}
              onChange={(e) => setAvatarUrl(e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-surface-1 focus:outline-none focus:ring-2 focus:ring-sage/30"
              placeholder="https://..."
            />
          </div>
          {profileMsg && (
            <p className={`text-sm ${updateProfile.isError ? 'text-red-fg' : 'text-sage-fg'}`}>
              {profileMsg}
            </p>
          )}
          <button
            type="submit"
            disabled={updateProfile.isPending}
            className="min-h-[44px] px-4 bg-sage text-on-accent rounded-lg text-sm font-medium hover:bg-sage-hover disabled:opacity-50 transition-colors"
          >
            {updateProfile.isPending ? 'Saving...' : 'Save'}
          </button>
        </form>
      </div>

      {/* Change Password */}
      <div className="bg-surface-1 rounded-lg border border-border p-6">
        <h2 className="text-lg font-semibold text-text mb-4">Change Password</h2>
        <form onSubmit={handlePasswordSubmit} className="space-y-4">
          <div>
            <label htmlFor="pw-old" className="block text-sm font-medium text-text mb-1">
              Current password
            </label>
            <input
              id="pw-old"
              type="password"
              required
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-surface-1 focus:outline-none focus:ring-2 focus:ring-sage/30"
            />
          </div>
          <div>
            <label htmlFor="pw-new" className="block text-sm font-medium text-text mb-1">
              New password
            </label>
            <input
              id="pw-new"
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-surface-1 focus:outline-none focus:ring-2 focus:ring-sage/30"
              placeholder="At least 8 characters"
            />
          </div>
          <div>
            <label htmlFor="pw-confirm" className="block text-sm font-medium text-text mb-1">
              Confirm new password
            </label>
            <input
              id="pw-confirm"
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-surface-1 focus:outline-none focus:ring-2 focus:ring-sage/30"
            />
          </div>
          {passwordError && <p className="text-sm text-red-fg">{passwordError}</p>}
          {passwordMsg && <p className="text-sm text-sage-fg">{passwordMsg}</p>}
          <button
            type="submit"
            disabled={changePassword.isPending}
            className="min-h-[44px] px-4 bg-sage text-on-accent rounded-lg text-sm font-medium hover:bg-sage-hover disabled:opacity-50 transition-colors"
          >
            {changePassword.isPending ? 'Changing...' : 'Change password'}
          </button>
        </form>
      </div>

      {/* MFA */}
      <div className="bg-surface-1 rounded-lg border border-border p-6">
        <h2 className="text-lg font-semibold text-text mb-4">Two-Factor Authentication</h2>
        <MFASetup mfaEnabled={user.mfa_enabled} />
      </div>
    </div>
  )
}
