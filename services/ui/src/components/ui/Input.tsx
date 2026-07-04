import { useId, type InputHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export function Input({ label, error, id, className = '', ...rest }: InputProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const errId = error ? `${inputId}-error` : undefined
  return (
    <div className={className}>
      {label && (
        <label htmlFor={inputId} className="block text-xs font-medium text-text-muted mb-1.5">
          {label}
        </label>
      )}
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={errId}
        className={`w-full bg-surface-1 border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-faint transition-colors ${
          error ? 'border-red' : 'border-border hover:border-border-strong focus:border-peri'
        }`}
        {...rest}
      />
      {error && (
        <p id={errId} role="alert" className="text-xs text-red-fg mt-1.5">
          {error}
        </p>
      )}
    </div>
  )
}
