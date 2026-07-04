import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from './Button'

describe('Button', () => {
  it.each([
    ['primary', 'bg-sage'],
    ['secondary', 'bg-surface-1'],
    ['ghost', 'bg-transparent'],
    ['danger', 'bg-red'],
  ] as const)('renders %s variant with token classes', (variant, expected) => {
    render(<Button variant={variant}>Go</Button>)
    expect(screen.getByRole('button', { name: 'Go' }).className).toContain(expected)
  })

  it.each([
    ['sm', 'text-xs'],
    ['md', 'px-3.5'],
    ['lg', 'px-5'],
  ] as const)('renders %s size', (size, expected) => {
    render(<Button size={size}>Go</Button>)
    expect(screen.getByRole('button', { name: 'Go' }).className).toContain(expected)
  })

  it('loading disables the button and shows a spinner', async () => {
    const onClick = vi.fn()
    const { container } = render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Save' })
    expect(button).toBeDisabled()
    expect(container.querySelector('svg.animate-spin')).toBeInTheDocument()
    await userEvent.click(button).catch(() => {})
    expect(onClick).not.toHaveBeenCalled()
  })

  it('shows a visible focus ring class for keyboard focus', () => {
    render(<Button>Focus me</Button>)
    expect(screen.getByRole('button', { name: 'Focus me' }).className).toContain('focus-visible:')
  })

  it('renders a <kbd> hint when kbd prop is given', () => {
    render(<Button kbd="S">Study</Button>)
    const kbd = screen.getByText('S')
    expect(kbd.tagName).toBe('KBD')
  })
})
