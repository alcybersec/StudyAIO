import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Table, TBody, TCell, THead, TRow } from './Table'

function renderTable() {
  return render(
    <Table>
      <THead>
        <TCell header>Week</TCell>
        <TCell header>Topic</TCell>
        <TCell header align="right">
          Cards
        </TCell>
      </THead>
      <TBody>
        <TRow>
          <TCell>01</TCell>
          <TCell>Intro</TCell>
          <TCell align="right">12</TCell>
        </TRow>
        <TRow>
          <TCell>02</TCell>
          <TCell>Memory</TCell>
          <TCell align="right">30</TCell>
        </TRow>
      </TBody>
    </Table>,
  )
}

describe('Table', () => {
  it('renders a semantic table with header and body rows', () => {
    renderTable()
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getAllByRole('columnheader')).toHaveLength(3)
    expect(screen.getAllByRole('row')).toHaveLength(3)
    expect(screen.getByRole('cell', { name: 'Memory' })).toBeInTheDocument()
  })

  it('wraps the table in an overflow-x-auto container', () => {
    const { container } = renderTable()
    const wrapper = container.firstElementChild as HTMLElement
    expect(wrapper.className).toContain('overflow-x-auto')
    expect(wrapper.querySelector('table')).not.toBeNull()
  })

  it('styles the header row mono-uppercase per the dense table look', () => {
    renderTable()
    const headerRow = screen.getAllByRole('row')[0]
    expect(headerRow.className).toContain('font-mono')
    expect(headerRow.className).toContain('uppercase')
  })

  it('right-aligns cells with align="right"', () => {
    renderTable()
    expect(screen.getByRole('cell', { name: '12' }).className).toContain('text-right')
  })
})
