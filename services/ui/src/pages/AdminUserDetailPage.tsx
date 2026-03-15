import { Link, useParams } from 'react-router-dom'
import { useAdminUserDetail } from '../hooks/useApi'
import { ErrorBanner } from '../components/ui/ErrorBanner'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import type { ReactNode } from 'react'

function SectionCard({ title, children, unavailable }: { title: string; children: ReactNode; unavailable?: boolean }) {
  return (
    <div className="bg-surface rounded-xl border border-border p-5">
      <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wide mb-3">{title}</h3>
      {unavailable ? (
        <p className="text-sm text-text-muted italic">Data unavailable</p>
      ) : (
        children
      )}
    </div>
  )
}

function StatRow({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  const display = value === null || value === undefined ? '—' : typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)
  return (
    <div className="flex justify-between py-1">
      <span className="text-sm text-text-muted">{label}</span>
      <span className="text-sm font-medium text-text">{display}</span>
    </div>
  )
}

function Badge({ text, variant }: { text: string; variant: 'green' | 'red' | 'blue' | 'gray' }) {
  const colors = {
    green: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    red: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    blue: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    gray: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[variant]}`}>
      {text}
    </span>
  )
}

export function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>()
  const { data, isLoading, error, refetch } = useAdminUserDetail(userId)

  if (isLoading) {
    return <LoadingSpinner size="lg" label="Loading user details..." />
  }

  if (error) {
    return <ErrorBanner message="Failed to load user details." onRetry={() => refetch()} />
  }

  if (!data) {
    return <ErrorBanner message="User not found." />
  }

  const { profile, subscription, storage, usage, pipeline, study, content, gamification, chat } = data

  return (
    <div className="space-y-6">
      {/* Breadcrumbs */}
      <nav className="flex items-center gap-2 text-sm text-text-muted">
        <Link to="/" className="hover:text-text transition-colors">Dashboard</Link>
        <span>/</span>
        <Link to="/admin" className="hover:text-text transition-colors">Admin</Link>
        <span>/</span>
        <span className="text-text font-medium">{profile.username || profile.email}</span>
      </nav>

      <h1 className="text-2xl font-bold text-text">User Details</h1>

      {/* Top row: Profile + Subscription */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SectionCard title="Profile">
          <div className="flex items-center gap-3 mb-4">
            {profile.avatar_url ? (
              <img src={profile.avatar_url} alt="" className="w-10 h-10 rounded-full" />
            ) : (
              <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-sm font-bold text-primary">
                {(profile.username || profile.email)[0].toUpperCase()}
              </div>
            )}
            <div>
              <div className="text-sm font-medium text-text">{profile.username || '—'}</div>
              <div className="text-xs text-text-muted">{profile.email}</div>
            </div>
          </div>
          <div className="flex gap-2 mb-3">
            <Badge text={profile.role} variant={profile.role === 'admin' ? 'blue' : 'gray'} />
            <Badge text={profile.tier} variant={profile.tier === 'pro' ? 'green' : 'gray'} />
            <Badge text={profile.is_active ? 'Active' : 'Inactive'} variant={profile.is_active ? 'green' : 'red'} />
          </div>
          <StatRow label="Email Verified" value={profile.email_verified} />
          <StatRow label="MFA Enabled" value={profile.mfa_enabled} />
          <StatRow label="Last Login" value={profile.last_login_at ? new Date(profile.last_login_at).toLocaleString() : null} />
          <StatRow label="Created" value={profile.created_at ? new Date(profile.created_at).toLocaleDateString() : null} />
        </SectionCard>

        <SectionCard title="Subscription" unavailable={!subscription}>
          {subscription && (
            <>
              <StatRow label="Plan" value={subscription.plan} />
              <StatRow label="Status" value={subscription.status} />
              <StatRow label="Period Start" value={subscription.current_period_start ? new Date(subscription.current_period_start).toLocaleDateString() : null} />
              <StatRow label="Period End" value={subscription.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : null} />
              <StatRow label="Cancel at Period End" value={subscription.cancel_at_period_end} />
            </>
          )}
        </SectionCard>
      </div>

      {/* Middle grid: Storage, Usage, Study */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <SectionCard title="Storage" unavailable={!storage}>
          {storage && (
            <>
              <StatRow label="Total Files" value={storage.total_files} />
              <StatRow label="Total Size" value={`${storage.total_mb} MB`} />
              {Object.keys(storage.status_breakdown).length > 0 && (
                <div className="mt-2 pt-2 border-t border-border">
                  <div className="text-xs text-text-muted mb-1">By Status</div>
                  {Object.entries(storage.status_breakdown).map(([status, count]) => (
                    <StatRow key={status} label={status} value={count} />
                  ))}
                </div>
              )}
            </>
          )}
        </SectionCard>

        <SectionCard title="AI / API Usage" unavailable={!usage}>
          {usage && (
            <>
              <div className="text-xs text-text-muted mb-1 font-medium">Today</div>
              <StatRow label="AI Calls" value={usage.today.ai_calls} />
              <StatRow label="Tokens In" value={usage.today.tokens_input.toLocaleString()} />
              <StatRow label="Tokens Out" value={usage.today.tokens_output.toLocaleString()} />
              <StatRow label="Uploads" value={usage.today.uploads} />
              <div className="text-xs text-text-muted mb-1 mt-3 font-medium">Last 30 Days</div>
              <StatRow label="AI Calls" value={usage.last_30_days.ai_calls} />
              <StatRow label="Tokens In" value={usage.last_30_days.tokens_input.toLocaleString()} />
              <StatRow label="Tokens Out" value={usage.last_30_days.tokens_output.toLocaleString()} />
              <StatRow label="Uploads" value={usage.last_30_days.uploads} />
            </>
          )}
        </SectionCard>

        <SectionCard title="Study Activity" unavailable={!study}>
          {study && (
            <>
              <StatRow label="Total Sessions" value={study.total_sessions} />
              <StatRow label="Cards Reviewed" value={study.cards_reviewed} />
              <StatRow label="Quiz Answered" value={study.quiz_questions_answered} />
              <StatRow label="Quiz Correct" value={study.quiz_correct} />
              <StatRow label="Quiz Accuracy" value={`${study.quiz_accuracy_pct}%`} />
              <StatRow label="Study Hours" value={study.total_study_hours} />
            </>
          )}
        </SectionCard>
      </div>

      {/* Second grid: Content, Gamification, Chat */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <SectionCard title="Content" unavailable={!content}>
          {content && (
            <>
              <StatRow label="Courses" value={content.courses_count} />
              <StatRow label="Artifacts" value={content.artifacts_count} />
              <StatRow label="Exams" value={content.exams_count} />
              {content.per_course.length > 0 && (
                <div className="mt-2 pt-2 border-t border-border">
                  <div className="text-xs text-text-muted mb-1">Per Course</div>
                  {content.per_course.map((c) => (
                    <StatRow key={c.code} label={c.code} value={`${c.artifact_count} files`} />
                  ))}
                </div>
              )}
            </>
          )}
        </SectionCard>

        <SectionCard title="Gamification" unavailable={!gamification}>
          {gamification && (
            <>
              <StatRow label="Total XP" value={gamification.total_xp.toLocaleString()} />
              <StatRow label="Level" value={gamification.level} />
              <StatRow label="Achievements" value={gamification.achievements_count} />
            </>
          )}
        </SectionCard>

        <SectionCard title="Chat" unavailable={!chat}>
          {chat && (
            <>
              <StatRow label="Sessions" value={chat.total_sessions} />
              <StatRow label="Messages" value={chat.total_messages} />
              <StatRow label="Tokens Used" value={chat.total_tokens.toLocaleString()} />
            </>
          )}
        </SectionCard>
      </div>

      {/* Full width: Pipeline */}
      <SectionCard title="Pipeline" unavailable={!pipeline}>
        {pipeline && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div>
                <div className="text-xs text-text-muted">Total Runs</div>
                <div className="text-lg font-bold text-text">{pipeline.total_runs}</div>
              </div>
              <div>
                <div className="text-xs text-text-muted">Success</div>
                <div className="text-lg font-bold text-green-600 dark:text-green-400">{pipeline.success_count}</div>
              </div>
              <div>
                <div className="text-xs text-text-muted">Failed</div>
                <div className="text-lg font-bold text-red-600 dark:text-red-400">{pipeline.failed_count}</div>
              </div>
              <div>
                <div className="text-xs text-text-muted">Avg Duration</div>
                <div className="text-lg font-bold text-text">{pipeline.avg_duration_ms}ms</div>
              </div>
            </div>

            {pipeline.stages.length > 0 && (
              <div className="mb-4">
                <div className="text-xs text-text-muted mb-2 font-medium">Per Stage</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-1 text-xs text-text-muted font-medium">Stage</th>
                        <th className="text-right py-1 text-xs text-text-muted font-medium">Total</th>
                        <th className="text-right py-1 text-xs text-text-muted font-medium">Success</th>
                        <th className="text-right py-1 text-xs text-text-muted font-medium">Failed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pipeline.stages.map((s) => (
                        <tr key={s.stage} className="border-b border-border/50">
                          <td className="py-1 text-text">{s.stage}</td>
                          <td className="py-1 text-right text-text">{s.total}</td>
                          <td className="py-1 text-right text-green-600 dark:text-green-400">{s.success}</td>
                          <td className="py-1 text-right text-red-600 dark:text-red-400">{s.failed}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {pipeline.recent_failures.length > 0 && (
              <div>
                <div className="text-xs text-text-muted mb-2 font-medium">Recent Failures</div>
                <div className="space-y-2">
                  {pipeline.recent_failures.map((f, i) => (
                    <div key={i} className="text-xs bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800/30 rounded-lg p-2">
                      <div className="flex justify-between mb-1">
                        <span className="font-medium text-red-700 dark:text-red-400">{f.stage}</span>
                        <span className="text-text-muted">{f.started_at ? new Date(f.started_at).toLocaleString() : '—'}</span>
                      </div>
                      <div className="text-red-600 dark:text-red-300 truncate">{f.error_message || 'No error message'}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </SectionCard>
    </div>
  )
}
