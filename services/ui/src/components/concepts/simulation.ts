import * as d3 from 'd3'
import type { ConceptNode } from '../../types'

export interface SimNode extends d3.SimulationNodeDatum {
  id: string
  name: string
  description: string
  category: string
  mention_count: number
  source_weeks: number[]
  course_id: string
}

export interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  id: string
  relation_type: string
  confidence: number
}

/**
 * Force-simulation factory. Kept as a separate module so the graph component
 * can prove (via a test spy) that selection changes never rebuild the
 * simulation — only node/edge/dimension changes do.
 */
export function createSimulation(
  nodes: SimNode[],
  links: SimLink[],
  width: number,
  height: number,
): d3.Simulation<SimNode, SimLink> {
  return d3
    .forceSimulation<SimNode>(nodes)
    .force(
      'link',
      d3
        .forceLink<SimNode, SimLink>(links)
        .id((d) => d.id)
        .distance(120),
    )
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(30))
}

/** Token CSS vars cycled per course — node colour communicates course. */
const COURSE_TONES = ['var(--t-sage)', 'var(--t-peri)', 'var(--t-amber)', 'var(--t-red)']

export function courseToneMap(nodes: Pick<ConceptNode, 'course_id'>[]): Map<string, string> {
  const ids = Array.from(new Set(nodes.map((n) => n.course_id))).sort()
  return new Map(ids.map((id, i) => [id, COURSE_TONES[i % COURSE_TONES.length]]))
}

/** Node radius scales with mention count, clamped to the prototype's 6–14 range. */
export function nodeRadius(mentionCount: number): number {
  return Math.min(6 + mentionCount, 14)
}
