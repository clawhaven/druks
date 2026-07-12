import type { DashboardHealth } from '../api/types'
import { relTime, secondsSince, formatTokenCount } from '../lib/format'

interface Props {
  health: DashboardHealth
}

type HealthStatus = 'ok' | 'warn' | 'bad'

interface SysItemProps {
  label: string
  value: string
  status?: HealthStatus
  title?: string
}

function SysItem({ label, value, status = 'ok', title }: SysItemProps) {
  return (
    <div className={`sys-item sys-item-${status}`} title={title ?? ''}>
      <span className="sys-item-label mono">{label}</span>
      <span className="sys-item-value mono">{value}</span>
    </div>
  )
}

function webhookStatus(age: number | null): HealthStatus {
  if (age == null) return 'warn'
  if (age > 3600) return 'bad'
  if (age > 600) return 'warn'
  return 'ok'
}

export function SystemStrip({ health }: Props) {
  const spendStatus: HealthStatus =
    health.spendTodayUsd != null && health.spendTodayUsd > 30 ? 'warn' : 'ok'

  return (
    <div className="sys-strip">
      {health.webhookFreshness.sources.map(({ source, lastAt }) => {
        const age = lastAt ? secondsSince(lastAt) : null
        return (
          <SysItem
            key={source}
            label={source}
            value={age == null ? '—' : relTime(age)}
            status={webhookStatus(age)}
            title={`last ${source} webhook delivery`}
          />
        )
      })}
      <SysItem
        label="spend-today"
        value={health.spendTodayUsd == null ? '—' : `$${health.spendTodayUsd.toFixed(2)}`}
        status={spendStatus}
        title="$ spent on agent runs since 00:00 local time"
      />
      <SysItem
        label="tokens-today"
        value={formatTokenCount(health.tokensToday)}
        title={`${health.tokensToday.toLocaleString()} tokens since 00:00 local time`}
      />
    </div>
  )
}
