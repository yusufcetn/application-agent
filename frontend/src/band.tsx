import { createContext, useContext, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

// The shell's blue band sits above the page content; pages send their heading into it.
export const BandContext = createContext<HTMLElement | null>(null)

export function BandPortal({ children }: { children: ReactNode }) {
  const slot = useContext(BandContext)
  return slot ? createPortal(children, slot) : null
}
