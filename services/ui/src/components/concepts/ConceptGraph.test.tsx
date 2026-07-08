import { render } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { ConceptGraph } from './ConceptGraph'
import { courseToneMap, createSimulation, nodeRadius } from './simulation'
import type { ConceptEdge, ConceptNode } from '../../types'

vi.mock('./simulation', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./simulation')>()
  const fakeSimulation = () => ({
    on: vi.fn().mockReturnThis(),
    stop: vi.fn(),
    alphaTarget: vi.fn().mockReturnThis(),
    restart: vi.fn(),
  })
  return {
    ...actual,
    createSimulation: vi.fn(fakeSimulation),
  }
})

function makeNode(id: string, courseId = 'c1'): ConceptNode {
  return {
    id,
    name: id.toUpperCase(),
    description: `About ${id}`,
    category: 'theory',
    mention_count: 3,
    source_weeks: [1],
    course_id: courseId,
    created_at: null,
  }
}

const nodes: ConceptNode[] = [makeNode('aslr'), makeNode('rop')]
const edges: ConceptEdge[] = [
  { id: 'e1', source: 'aslr', target: 'rop', relation_type: 'related_to', confidence: 0.9 },
]

describe('ConceptGraph simulation lifecycle', () => {
  beforeEach(() => {
    vi.mocked(createSimulation).mockClear()
  })

  it('builds the simulation exactly once across multiple selection changes', () => {
    const { rerender } = render(
      <ConceptGraph nodes={nodes} edges={edges} selectedNodeId={null} />,
    )
    expect(createSimulation).toHaveBeenCalledTimes(1)

    rerender(<ConceptGraph nodes={nodes} edges={edges} selectedNodeId="aslr" />)
    rerender(<ConceptGraph nodes={nodes} edges={edges} selectedNodeId="rop" />)
    rerender(<ConceptGraph nodes={nodes} edges={edges} selectedNodeId={null} />)

    expect(createSimulation).toHaveBeenCalledTimes(1)
  })

  it('rebuilds the simulation when the node set changes', () => {
    const { rerender } = render(
      <ConceptGraph nodes={nodes} edges={edges} selectedNodeId={null} />,
    )
    expect(createSimulation).toHaveBeenCalledTimes(1)

    const moreNodes = [...nodes, makeNode('tls', 'c2')]
    rerender(<ConceptGraph nodes={moreNodes} edges={edges} selectedNodeId={null} />)

    expect(createSimulation).toHaveBeenCalledTimes(2)
  })

  it('updates selection styling on existing elements without rebuilding', () => {
    const { container, rerender } = render(
      <ConceptGraph nodes={nodes} edges={edges} selectedNodeId={null} />,
    )

    rerender(<ConceptGraph nodes={nodes} edges={edges} selectedNodeId="aslr" />)

    const rings = container.querySelectorAll('circle.node-ring')
    const visible = Array.from(rings).filter((r) => r.getAttribute('stroke-opacity') !== '0')
    expect(visible).toHaveLength(1)
    expect(createSimulation).toHaveBeenCalledTimes(1)
  })

  it('stops the simulation on unmount', () => {
    const { unmount } = render(
      <ConceptGraph nodes={nodes} edges={edges} selectedNodeId={null} />,
    )
    const sim = vi.mocked(createSimulation).mock.results[0].value
    unmount()
    expect(sim.stop).toHaveBeenCalled()
  })
})

describe('simulation helpers', () => {
  it('assigns stable token tones per course', () => {
    const map = courseToneMap([{ course_id: 'b' }, { course_id: 'a' }, { course_id: 'b' }])
    expect(map.get('a')).toBe('var(--t-sage)')
    expect(map.get('b')).toBe('var(--t-peri)')
  })

  it('clamps node radius to the 6-14 range', () => {
    expect(nodeRadius(0)).toBe(6)
    expect(nodeRadius(3)).toBe(9)
    expect(nodeRadius(50)).toBe(14)
  })
})
