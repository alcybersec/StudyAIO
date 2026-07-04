import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Kbd } from './Kbd'

describe('Kbd', () => {
  it('renders a semantic <kbd> element with its text', () => {
    render(<Kbd>⌘K</Kbd>)
    const el = screen.getByText('⌘K')
    expect(el.tagName).toBe('KBD')
  })

  it('merges custom classes', () => {
    render(<Kbd className="ml-1">?</Kbd>)
    expect(screen.getByText('?').className).toContain('ml-1')
  })
})
