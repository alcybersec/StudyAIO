import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Input } from './Input'

describe('Input', () => {
  it('associates the label via htmlFor', () => {
    render(<Input id="email" label="Email" />)
    const input = screen.getByLabelText('Email')
    expect(input).toBeInstanceOf(HTMLInputElement)
    expect(input.id).toBe('email')
  })

  it('associates the label even without an explicit id (useId fallback)', () => {
    render(<Input label="Name" />)
    expect(screen.getByLabelText('Name')).toBeInstanceOf(HTMLInputElement)
  })

  it('error sets aria-invalid and aria-describedby pointing at a role=alert node', () => {
    render(<Input id="pw" label="Password" error="Too short" />)
    const input = screen.getByLabelText('Password')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    const describedBy = input.getAttribute('aria-describedby')
    expect(describedBy).toBeTruthy()
    const alert = screen.getByRole('alert')
    expect(alert.id).toBe(describedBy)
    expect(alert).toHaveTextContent('Too short')
  })

  it('renders no alert when there is no error', () => {
    render(<Input id="ok" label="Fine" />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Fine')).not.toHaveAttribute('aria-invalid', 'true')
  })
})
