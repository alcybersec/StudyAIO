import { createContext, useContext, useState, type ReactNode } from 'react'

/** Simulated data-layer state, toggled from the prototype toolbar. */
export type SimState = 'default' | 'loading' | 'empty' | 'error' | 'offline'

const SimContext = createContext<{ sim: SimState; setSim: (s: SimState) => void }>({
  sim: 'default',
  setSim: () => {},
})

export function SimProvider({ children }: { children: ReactNode }) {
  const [sim, setSim] = useState<SimState>('default')
  return <SimContext.Provider value={{ sim, setSim }}>{children}</SimContext.Provider>
}

export const useSim = () => useContext(SimContext)

export const SIM_STATES: SimState[] = ['default', 'loading', 'empty', 'error', 'offline']
