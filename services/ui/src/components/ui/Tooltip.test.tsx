import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Tooltip } from './Tooltip'

describe('Tooltip', () => {
  it('appears on keyboard focus, not only hover', async () => {
    const user = userEvent.setup()
    render(
      <Tooltip content="Start a study session">
        <button>Study</button>
      </Tooltip>,
    )
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    await user.tab()
    expect(screen.getByRole('button', { name: /Study/ })).toHaveFocus()
    expect(await screen.findByRole('tooltip')).toBeInTheDocument()
  })

  it('hides again on blur', async () => {
    const user = userEvent.setup()
    render(
      <>
        <Tooltip content="Hint">
          <button>Trigger</button>
        </Tooltip>
        <button>Elsewhere</button>
      </>,
    )
    await user.tab()
    await screen.findByRole('tooltip')
    await user.tab()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
})
