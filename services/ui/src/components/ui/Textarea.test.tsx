import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Textarea } from './Textarea'

describe('Textarea', () => {
  it('associates the label via htmlFor', () => {
    render(<Textarea id="notes" label="Notes" />)
    const el = screen.getByLabelText('Notes')
    expect(el).toBeInstanceOf(HTMLTextAreaElement)
    expect(el.id).toBe('notes')
  })

  it('associates the label without an explicit id', () => {
    render(<Textarea label="Bio" />)
    expect(screen.getByLabelText('Bio')).toBeInstanceOf(HTMLTextAreaElement)
  })

  it('error sets aria-invalid and aria-describedby pointing at a role=alert node', () => {
    render(<Textarea id="msg" label="Message" error="Required" />)
    const el = screen.getByLabelText('Message')
    expect(el).toHaveAttribute('aria-invalid', 'true')
    const alert = screen.getByRole('alert')
    expect(alert.id).toBe(el.getAttribute('aria-describedby'))
    expect(alert).toHaveTextContent('Required')
  })

  it('renders no alert when there is no error', () => {
    render(<Textarea id="c" label="Clean" />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
