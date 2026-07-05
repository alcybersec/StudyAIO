import { Link, useParams } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAdminUserDetail } from '../hooks/useApi'
import {
  Badge,
  EmptyState,
  ErrorState,
  SectionLabel,
  Skeleton,
  Table,
  TBody,
  TCell,
  THead,
  TRow,
} from '../components/ui'

function SectionCard({ title, children, unavailable }: { title: string; children: ReactNode; unavailable?: boolean }) {
  return (
    <div className="bg-surface-1 rounded-xl border border-border p-4">
      <SectionLabel>{title}</SectionLabel>
      {unavailable ? <p className="text-sm text-text-faint italic">Data unavailable</p> : children}
    </div>
  )
}

function StatRow({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  const display =
    value === null || value === undefined ? '—' : typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)
  return (
    <div className="flex justify-between py-1">
      <span className="text-sm text-text-muted">{label}</span>
      <span className="text-sm font-medium text-text">{display}</span>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading user details">
      <Skeleton height={14} width={220} />
      <Skeleton height={24} width={160} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[0, 1].map((i) => (
          <div key={i} className="bg-surface-1 rounded-xl border border-border p-4 space-y-3">
            <Skeleton height={10} width={80} />
            <Skeleton height={40} width="60%" />
            <Skeleton height={14} width="100%" />
            <Skeleton height={14} width="90%" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="bg-surface-1 rounded-xl border border-border p-4 space-y-3">
            <Skeleton height={10} width={80} />
            <Skeleton height={14} width="100%" />
            <Skeleton height={14} width="80%" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>()
  const { data, isLoading, isError, refetch } = useAdminUserDetail(userId)

  if (isLoading && !data) return <DetailSkeleton />

  if (isError && !data) {
    return <ErrorState title="User details couldn't load" onRetry={() => refetch()} />
  }

  if (!data) {
    return <EmptyState title="User not found" description="This user may have been deleted." actionLabel="Back to Admin" actionTo="/admin" />
  }

  const { profile, subscription, storage, usage, pipeline, study, content, gamification, chat } = data

  return (
    <div className="space-y-6">
      {/* Breadcrumbs */}
      <nav className="flex items-center gap-2 text-sm text-text-muted">
        <Link to="/" className="hover:text-text transition-colors">
          Home
        </Link>
        <span className="text-border">/</span>
        <Link to="/admin" className="hover:text-text transition-colors">
          Admin
        </Link>
        <span className="text-border">/</span>
        <span className="text-text font-medium">{profile.username || profile.email}</span>
      </nav>

      <h1 className="text-xl font-bold tracking-tight text-text">User details</h1>

      {/* Top row: Profile + Subscription */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SectionCard title="Profile">
          <div className="flex items-center gap-3 mb-4">
            {profile.avatar_url ? (
              <img src={profile.avatar_url} alt="" className="w-10 h-10 rounded-full" />
            ) : (
              <div className="w-10 h-10 rounded-full bg-peri-soft flex items-center justify-center text-sm font-bold text-peri-fg">
                {(profile.username || profile.email)[0].toUpperCase()}
              </div>
            )}
            <div>
              <div className="text-sm font-medium text-text">{profile.username || '—'}</div>
              <div className="text-xs text-text-muted">{profile.email}</div>
            </div>
          </div>
          <div className="flex gap-2 mb-3">
            <Badge variant={profile.role === 'admin' ? 'info' : 'default'}>{profile.role}</Badge>
            <Badge variant={profile.tier === 'pro' ? 'success' : 'default'}>{profile.tier}</Badge>
            <Badge variant={profile.is_active ? 'success' : 'danger'}>{profile.is_active ? 'active' : 'inactive'}</Badge>
          </div>
          <StatRow label="Email verified" value={profile.email_verified} />
          <StatRow label="MFA enabled" value={profile.mfa_enabled} />
          <StatRow label="Last login" value={profile.last_login_at ? new Date(profile.last_login_at).toLocaleString() : null} />
          <StatRow label="Created" value={profile.created_at ? new Date(profile.created_at).toLocaleDateString() : null} />
        </SectionCard>

        <SectionCard title="Subscription" unavailable={!subscription}>
          {subscription && (
            <>
              <StatRow label="Plan" value={subscription.plan} />
              <StatRow label="Status" value={subscription.status} />
              <StatRow
                label="Period start"
                value={subscription.current_period_start ? new Date(subscription.current_period_start).toLocaleDateString() : null}
              />
              <StatRow
                label="Period end"
                value={subscription.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : null}
              />
              <StatRow label="Cancel at period end" value={subscription.cancel_at_period_end} />
            </>
          )}
        </SectionCard>
      </div>

      {/* Middle grid: Storage, Usage, Study */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <SectionCard title="Storage" unavailable={!storage}>
          {storage && (
            <>
              <StatRow label="Total files" value={storage.total_files} />
              <StatRow label="Total size" value={`${storage.total_mb} MB`} />
              {Object.keys(storage.status_breakdown).length > 0 && (
                <div className="mt-2 pt-2 border-t border-border">
                  <SectionLabel>By status</SectionLabel>
                  {Object.entries(storage.status_breakdown).map(([status, count]) => (
                    <StatRow key={status} label={status} value={count} />
                  ))}
                </div>
              )}
            </>
          )}
        </SectionCard>

        <SectionCard title="AI / API usage" unavailable={!usage}>
          {usage && (
            <>
              <SectionLabel>Today</SectionLabel>
              <StatRow label="AI calls" value={usage.today.ai_calls} />
              <StatRow label="Tokens in" value={usage.today.tokens_input.toLocaleString()} />
              <StatRow label="Tokens out" value={usage.today.tokens_output.toLocaleString()} />
              <StatRow label="Uploads" value={usage.today.uploads} />
              <div className="mt-3">
                <SectionLabel>Last 30 days</SectionLabel>
              </div>
              <StatRow label="AI calls" value={usage.last_30_days.ai_calls} />
              <StatRow label="Tokens in" value={usage.last_30_days.tokens_input.toLocaleString()} />
              <StatRow label="Tokens out" value={usage.last_30_days.tokens_output.toLocaleString()} />
              <StatRow label="Uploads" value={usage.last_30_days.uploads} />
            </>
          )}
        </SectionCard>

        <SectionCard title="Study activity" unavailable={!study}>
          {study && (
            <>
              <StatRow label="Total sessions" value={study.total_sessions} />
              <StatRow label="Cards reviewed" value={study.cards_reviewed} />
              <StatRow label="Quiz answered" value={study.quiz_questions_answered} />
              <StatRow label="Quiz correct" value={study.quiz_correct} />
              <StatRow label="Quiz accuracy" value={`${study.quiz_accuracy_pct}%`} />
              <StatRow label="Study hours" value={study.total_study_hours} />
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
                  <SectionLabel>Per course</SectionLabel>
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
              <StatRow label="Tokens used" value={chat.total_tokens.toLocaleString()} />
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
                <SectionLabel>Total runs</SectionLabel>
                <div className="text-lg font-bold text-text">{pipeline.total_runs}</div>
              </div>
              <div>
                <SectionLabel>Success</SectionLabel>
                <div className="text-lg font-bold text-sage-fg">{pipeline.success_count}</div>
              </div>
              <div>
                <SectionLabel>Failed</SectionLabel>
                <div className="text-lg font-bold text-red-fg">{pipeline.failed_count}</div>
              </div>
              <div>
                <SectionLabel>Avg duration</SectionLabel>
                <div className="text-lg font-bold text-text font-mono">{pipeline.avg_duration_ms}ms</div>
              </div>
            </div>

            {pipeline.stages.length > 0 && (
              <div className="mb-4">
                <SectionLabel>Per stage</SectionLabel>
                <Table>
                  <THead>
                    <TCell header>Stage</TCell>
                    <TCell header align="right">
                      Total
                    </TCell>
                    <TCell header align="right">
                      Success
                    </TCell>
                    <TCell header align="right">
                      Failed
                    </TCell>
                  </THead>
                  <TBody>
                    {pipeline.stages.map((s) => (
                      <TRow key={s.stage}>
                        <TCell className="font-mono text-[12px] text-text">{s.stage}</TCell>
                        <TCell align="right" className="text-text">
                          {s.total}
                        </TCell>
                        <TCell align="right" className="text-sage-fg">
                          {s.success}
                        </TCell>
                        <TCell align="right" className="text-red-fg">
                          {s.failed}
                        </TCell>
                      </TRow>
                    ))}
                  </TBody>
                </Table>
              </div>
            )}

            {pipeline.recent_failures.length > 0 && (
              <div>
                <SectionLabel>Recent failures</SectionLabel>
                <div className="space-y-2">
                  {pipeline.recent_failures.map((f, i) => (
                    <div key={i} className="text-xs bg-red-soft border border-red/30 rounded-lg p-2">
                      <div className="flex justify-between mb-1">
                        <span className="font-medium text-red-fg">{f.stage}</span>
                        <span className="text-text-muted font-mono text-[11px]">
                          {f.started_at ? new Date(f.started_at).toLocaleString() : '—'}
                        </span>
                      </div>
                      <div className="text-text-muted truncate">{f.error_message || 'No error message'}</div>
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
