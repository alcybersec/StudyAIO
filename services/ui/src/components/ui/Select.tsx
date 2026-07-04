import { useId } from 'react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Check, ChevronDown } from 'lucide-react'

export interface SelectOption {
  value: string
  label: string
}

interface SelectProps {
  options: SelectOption[]
  value?: string
  onValueChange?: (value: string) => void
  label?: string
  error?: string
  placeholder?: string
  id?: string
  disabled?: boolean
  className?: string
}

export function Select({
  options,
  value,
  onValueChange,
  label,
  error,
  placeholder = 'Select…',
  id,
  disabled,
  className = '',
}: SelectProps) {
  const autoId = useId()
  const triggerId = id ?? autoId
  const errId = error ? `${triggerId}-error` : undefined
  const selected = options.find((o) => o.value === value)

  return (
    <div className={className}>
      {label && (
        <label htmlFor={triggerId} className="block text-xs font-medium text-text-muted mb-1.5">
          {label}
        </label>
      )}
      <DropdownMenu.Root modal={false}>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            id={triggerId}
            disabled={disabled}
            aria-invalid={error ? true : undefined}
            aria-describedby={errId}
            className={`w-full flex items-center justify-between gap-2 bg-surface-1 border rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors disabled:opacity-45 disabled:cursor-not-allowed ${
              error ? 'border-red' : 'border-border hover:border-border-strong'
            }`}
          >
            <span className={selected ? 'text-text' : 'text-text-faint'}>
              {selected?.label ?? placeholder}
            </span>
            <ChevronDown size={14} className="text-text-faint shrink-0" aria-hidden />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="start"
            sideOffset={4}
            className="min-w-[var(--radix-dropdown-menu-trigger-width)] bg-surface-1 border border-border-strong rounded-xl shadow-2xl shadow-black/20 py-1.5 z-50"
          >
            <DropdownMenu.RadioGroup value={value} onValueChange={onValueChange}>
              {options.map((o) => (
                <DropdownMenu.RadioItem
                  key={o.value}
                  value={o.value}
                  className="w-full flex items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] text-text-muted outline-none cursor-pointer data-[highlighted]:bg-surface-2 data-[highlighted]:text-text"
                >
                  {o.label}
                  <DropdownMenu.ItemIndicator>
                    <Check size={13} className="text-sage-fg" aria-hidden />
                  </DropdownMenu.ItemIndicator>
                </DropdownMenu.RadioItem>
              ))}
            </DropdownMenu.RadioGroup>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      {error && (
        <p id={errId} role="alert" className="text-xs text-red-fg mt-1.5">
          {error}
        </p>
      )}
    </div>
  )
}
