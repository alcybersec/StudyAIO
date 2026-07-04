import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Select } from './Select'

const options = [
  { value: 'a', label: 'Alpha' },
  { value: 'b', label: 'Beta' },
  { value: 'c', label: 'Gamma' },
]

describe('Select', () => {
  it('associates the label with the trigger via htmlFor', () => {
    render(<Select label="Course" options={options} />)
    const trigger = screen.getByLabelText('Course')
    expect(trigger.tagName).toBe('BUTTON')
  })

  it('shows the placeholder when nothing is selected and the selected label otherwise', () => {
    const { rerender } = render(<Select label="Course" options={options} placeholder="Pick one" />)
    expect(screen.getByLabelText('Course')).toHaveTextContent('Pick one')
    rerender(<Select label="Course" options={options} placeholder="Pick one" value="b" />)
    expect(screen.getByLabelText('Course')).toHaveTextContent('Beta')
  })

  it('opens on click and lists the options', async () => {
    const user = userEvent.setup()
    render(<Select label="Course" options={options} />)
    await user.click(screen.getByLabelText('Course'))
    expect(await screen.findByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Gamma')).toBeInTheDocument()
  })

  it('supports keyboard navigation: enter opens, arrows move, enter selects', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    render(<Select label="Course" options={options} onValueChange={onValueChange} />)
    const trigger = screen.getByLabelText('Course')
    trigger.focus()
    await user.keyboard('{Enter}')
    await screen.findByText('Alpha')
    await user.keyboard('{ArrowDown}')
    await user.keyboard('{Enter}')
    expect(onValueChange).toHaveBeenCalledWith('b')
  })

  it('error sets aria-invalid and aria-describedby pointing at a role=alert node', () => {
    render(<Select label="Week" options={options} error="Pick a week" />)
    const trigger = screen.getByLabelText('Week')
    expect(trigger).toHaveAttribute('aria-invalid', 'true')
    const alert = screen.getByRole('alert')
    expect(alert.id).toBe(trigger.getAttribute('aria-describedby'))
    expect(alert).toHaveTextContent('Pick a week')
  })
})
