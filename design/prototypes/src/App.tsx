import { useEffect, useState, type ComponentType } from 'react'
import { Moon, Sun } from 'lucide-react'
import { SimProvider, useSim, SIM_STATES } from './lib/sim'

import { Foundations } from './screens/Foundations'
import { ShellNav } from './screens/ShellNav'
import { CommandPalette } from './screens/CommandPalette'
import { Home } from './screens/Home'
import { CoursePage } from './screens/CoursePage'
import { StudyHub } from './screens/StudyHub'
import { WeekView } from './screens/WeekView'
import { PipelineConsole } from './screens/PipelineConsole'
import { ReviewInbox } from './screens/ReviewInbox'
import { Ask } from './screens/Ask'
import { Knowledge } from './screens/Knowledge'
import { Analytics } from './screens/Analytics'
import { Settings } from './screens/Settings'
import { Auth } from './screens/Auth'
import { StatesGallery } from './screens/StatesGallery'

type Screen = { id: string; title: string; group: string; component: ComponentType; simAware?: boolean }

const SCREENS: Screen[] = [
  { id: 'foundations', title: 'Foundations', group: 'System', component: Foundations },
  { id: 'states', title: 'States & errors', group: 'System', component: StatesGallery },
  { id: 'shell', title: 'Shell & navigation', group: 'System', component: ShellNav },
  { id: 'palette', title: '⌘K palette', group: 'System', component: CommandPalette },
  { id: 'home', title: 'Home', group: 'Screens', component: Home, simAware: true },
  { id: 'course', title: 'Course page', group: 'Screens', component: CoursePage, simAware: true },
  { id: 'study', title: 'Study Hub', group: 'Screens', component: StudyHub, simAware: true },
  { id: 'week', title: 'Week view', group: 'Screens', component: WeekView, simAware: true },
  { id: 'pipeline', title: 'Upload · pipeline console', group: 'Screens', component: PipelineConsole, simAware: true },
  { id: 'review', title: 'Review inbox', group: 'Screens', component: ReviewInbox, simAware: true },
  { id: 'ask', title: 'Ask (chat + Q&A)', group: 'Screens', component: Ask, simAware: true },
  { id: 'knowledge', title: 'Knowledge graph', group: 'Screens', component: Knowledge, simAware: true },
  { id: 'analytics', title: 'Analytics & readiness', group: 'Screens', component: Analytics, simAware: true },
  { id: 'settings', title: 'Settings', group: 'Screens', component: Settings },
  { id: 'auth', title: 'Auth', group: 'Screens', component: Auth },
]

function Toolbar({ screen }: { screen: Screen }) {
  const { sim, setSim } = useSim()
  const [dark, setDark] = useState(true)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface-1">
      <div className="text-xs text-text-muted">
        <span className="font-mono text-text-faint">prototype /</span>{' '}
        <span className="font-medium text-text">{screen.title}</span>
      </div>
      <div className="flex items-center gap-2">
        {screen.simAware && (
          <div className="flex items-center rounded-lg border border-border overflow-hidden" role="group" aria-label="Simulated state">
            {SIM_STATES.map((s) => (
              <button
                key={s}
                onClick={() => setSim(s)}
                className={`text-[11px] px-2.5 py-1.5 capitalize cursor-pointer transition-colors ${
                  sim === s ? 'bg-peri-soft text-peri-fg font-medium' : 'text-text-muted hover:bg-surface-2'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        )}
        <button
          onClick={() => setDark(!dark)}
          className="p-2 rounded-lg text-text-muted hover:bg-surface-2 cursor-pointer"
          aria-label="Toggle theme"
        >
          {dark ? <Sun size={14} /> : <Moon size={14} />}
        </button>
      </div>
    </div>
  )
}

export function App() {
  const [active, setActive] = useState('home')
  const screen = SCREENS.find((s) => s.id === active) ?? SCREENS[0]
  const Comp = screen.component
  const groups = [...new Set(SCREENS.map((s) => s.group))]

  return (
    <SimProvider>
      <div className="flex h-screen overflow-hidden">
        {/* prototype index rail */}
        <nav className="w-52 shrink-0 border-r border-border bg-surface-1 flex flex-col" aria-label="Prototype index">
          <div className="px-4 py-4 border-b border-border">
            <div className="text-sm font-bold tracking-tight">StudyAIO</div>
            <div className="text-[10px] font-mono text-text-faint mt-0.5">rework prototypes · v1</div>
          </div>
          <div className="flex-1 overflow-y-auto py-3">
            {groups.map((g) => (
              <div key={g} className="mb-4 px-2">
                <div className="text-[10px] font-mono uppercase tracking-[0.12em] text-text-faint px-2 mb-1">{g}</div>
                {SCREENS.filter((s) => s.group === g).map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setActive(s.id)}
                    className={`w-full text-left text-[13px] px-2 py-1.5 rounded-md cursor-pointer transition-colors ${
                      active === s.id ? 'bg-surface-2 text-text font-medium' : 'text-text-muted hover:text-text'
                    }`}
                  >
                    {s.title}
                  </button>
                ))}
              </div>
            ))}
          </div>
          <div className="px-4 py-3 border-t border-border text-[10px] text-text-faint leading-relaxed">
            Isolated from services/ui.
            <br />
            Use the state switcher to see loading / empty / error / offline.
          </div>
        </nav>

        {/* content */}
        <div className="flex-1 flex flex-col min-w-0">
          <Toolbar screen={screen} />
          <main className="flex-1 overflow-y-auto bg-surface-0">
            <Comp />
          </main>
        </div>
      </div>
    </SimProvider>
  )
}
