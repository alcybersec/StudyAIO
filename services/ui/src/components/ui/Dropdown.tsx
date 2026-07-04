import type { ReactNode } from 'react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'

interface DropdownProps {
  trigger: ReactNode
  children: ReactNode
  align?: 'start' | 'center' | 'end'
  className?: string
}

/**
 * Menu wrapper matching the course manage-menu look: surface-1 panel,
 * strong border, soft shadow, dense 13px rows.
 */
export function Dropdown({ trigger, children, align = 'end', className = '' }: DropdownProps) {
  return (
    <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger asChild>{trigger}</DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align={align}
          sideOffset={6}
          className={`w-56 bg-surface-1 border border-border-strong rounded-xl shadow-2xl shadow-black/20 py-1.5 z-50 ${className}`}
        >
          {children}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}

interface DropdownItemProps {
  children: ReactNode
  onSelect?: () => void
  danger?: boolean
  disabled?: boolean
}

export function DropdownItem({ children, onSelect, danger, disabled }: DropdownItemProps) {
  return (
    <DropdownMenu.Item
      disabled={disabled}
      onSelect={onSelect}
      className={`w-full flex items-center gap-2.5 px-3.5 py-2 text-[13px] outline-none cursor-pointer data-[disabled]:opacity-45 data-[disabled]:cursor-not-allowed ${
        danger
          ? 'text-red-fg data-[highlighted]:bg-red-soft'
          : 'text-text-muted data-[highlighted]:bg-surface-2 data-[highlighted]:text-text'
      }`}
    >
      {children}
    </DropdownMenu.Item>
  )
}

export function DropdownSeparator() {
  return <DropdownMenu.Separator className="h-px bg-border my-1.5" />
}
