import { useId, type TextareaHTMLAttributes } from 'react'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
}

export function Textarea({ label, error, id, className = '', ...rest }: TextareaProps) {
  const autoId = useId()
  const areaId = id ?? autoId
  const errId = error ? `${areaId}-error` : undefined
  return (
    <div className={className}>
      {label && (
        <label htmlFor={areaId} className="block text-xs font-medium text-text-muted mb-1.5">
          {label}
        </label>
      )}
      <textarea
        id={areaId}
        aria-invalid={error ? true : undefined}
        aria-describedby={errId}
        className={`w-full bg-surface-1 border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-faint transition-colors resize-y min-h-20 ${
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
