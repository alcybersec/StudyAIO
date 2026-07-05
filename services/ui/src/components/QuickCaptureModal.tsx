import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { uploadApi } from '../api/endpoints'
import { AppApiError } from '../api/errors'
import { captureSchema } from '../lib/schemas'
import { toastMutationError } from '../lib/toast'
import type { CaptureRequest } from '../types'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Modal } from './ui/Modal'
import { Textarea } from './ui/Textarea'

type CaptureMode = 'text' | 'url'

interface QuickCaptureModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Palette quick-capture: paste text or a URL straight into the pipeline. */
export function QuickCaptureModal({ open, onOpenChange }: QuickCaptureModalProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<CaptureMode>('text')
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [errors, setErrors] = useState<{ text?: string; url?: string; title?: string }>({})

  const capture = useMutation({
    mutationFn: (body: CaptureRequest) => uploadApi.capture(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      toast.success('Capturing — processing started', {
        action: { label: 'View pipeline', onClick: () => navigate('/upload') },
      })
      setText('')
      setUrl('')
      setTitle('')
      setErrors({})
      onOpenChange(false)
    },
    onError: (err) => {
      if (err instanceof AppApiError && err.status === 413) {
        toast.error('That capture is too large', {
          description: 'Pasted text must stay under 1 MB — trim it down and retry.',
        })
        return
      }
      toastMutationError(err, handleSubmit)
    },
  })

  const handleSubmit = () => {
    const candidate =
      mode === 'text'
        ? { text, title: title || undefined }
        : { url, title: title || undefined }
    const parsed = captureSchema.safeParse(candidate)
    if (!parsed.success) {
      const fieldErrors: typeof errors = {}
      for (const issue of parsed.error.issues) {
        const field = issue.path[0]
        if (field === 'text' || field === 'url' || field === 'title') {
          fieldErrors[field] ??= issue.message
        }
      }
      setErrors(fieldErrors)
      return
    }
    setErrors({})
    const body: CaptureRequest =
      mode === 'text' ? { text: parsed.data.text } : { url: parsed.data.url }
    if (parsed.data.title) body.title = parsed.data.title
    capture.mutate(body)
  }

  const switchMode = (next: CaptureMode) => {
    setMode(next)
    setErrors({})
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Quick capture"
      description="Paste text or a URL straight into the pipeline."
    >
      <div className="space-y-3">
        <div role="tablist" aria-label="Capture source" className="flex gap-1 p-0.5 rounded-lg bg-surface-2 w-fit">
          {(['text', 'url'] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              onClick={() => switchMode(m)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                mode === m ? 'bg-surface-1 text-text shadow-sm' : 'text-text-muted hover:text-text'
              }`}
            >
              {m === 'text' ? 'Paste text' : 'From URL'}
            </button>
          ))}
        </div>

        {mode === 'text' ? (
          <Textarea
            label="Text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste lecture notes, an article, a snippet…"
            rows={6}
            error={errors.text}
          />
        ) : (
          <Input
            label="URL"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/article"
            error={errors.url}
          />
        )}

        <Input
          label="Title (optional)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Give this capture a name"
          error={errors.title}
        />

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} loading={capture.isPending}>
            Capture
          </Button>
        </div>
      </div>
    </Modal>
  )
}
