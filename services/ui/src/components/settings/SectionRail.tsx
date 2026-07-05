import { NavLink } from 'react-router-dom'
import { DEFAULT_SECTION, SETTINGS_SECTIONS, type SettingsSectionId } from './sectionRegistry'

interface SectionRailProps {
  active: SettingsSectionId
}

/** Left settings navigation rail per the prototype; horizontal scroll on mobile. */
export function SectionRail({ active }: SectionRailProps) {
  return (
    <nav aria-label="Settings sections" className="md:w-44 shrink-0">
      <ul className="flex md:flex-col gap-0.5 md:space-y-0.5 overflow-x-auto md:overflow-visible pb-2 md:pb-0">
        {SETTINGS_SECTIONS.map(({ id, label, icon: Icon }) => {
          const isActive = id === active
          return (
            <li key={id} className="shrink-0">
              <NavLink
                to={id === DEFAULT_SECTION ? '/settings' : `/settings/${id}`}
                end
                aria-current="true"
                className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] whitespace-nowrap transition-colors ${
                  isActive
                    ? 'bg-surface-2 text-text font-medium'
                    : 'text-text-muted hover:text-text hover:bg-surface-2/60'
                }`}
              >
                <Icon size={14} className={isActive ? 'text-sage-fg' : 'text-text-faint'} aria-hidden />
                {label}
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
