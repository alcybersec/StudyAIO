import { useId } from 'react'
import * as SwitchPrimitive from '@radix-ui/react-switch'

interface SwitchProps {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  label?: string
  id?: string
  disabled?: boolean
  className?: string
}

export function Switch({ checked, onCheckedChange, label, id, disabled, className = '' }: SwitchProps) {
  const autoId = useId()
  const switchId = id ?? autoId
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <SwitchPrimitive.Root
        id={switchId}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        className={`relative h-5 w-9 shrink-0 rounded-full border border-transparent transition-colors cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed ${
          checked ? 'bg-sage' : 'bg-surface-2 border-border-strong'
        }`}
      >
        <SwitchPrimitive.Thumb
          className={`block h-3.5 w-3.5 rounded-full bg-on-accent shadow-sm transition-transform ${
            checked ? 'translate-x-[19px]' : 'translate-x-[3px]'
          }`}
        />
      </SwitchPrimitive.Root>
      {label && (
        <label htmlFor={switchId} className="text-sm text-text cursor-pointer">
          {label}
        </label>
      )}
    </div>
  )
}
