import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import type { ConceptEdge, ConceptNode } from '../../types'
import { courseToneMap, createSimulation, nodeRadius, type SimLink, type SimNode } from './simulation'

interface ConceptGraphProps {
  nodes: ConceptNode[]
  edges: ConceptEdge[]
  onNodeClick?: (nodeId: string) => void
  selectedNodeId?: string | null
}

type NodeSelection = d3.Selection<SVGGElement, SimNode, SVGGElement, unknown>

/** Selection styling applied via attribute changes only — never a rebuild. */
function applySelection(sel: NodeSelection, selectedId: string | null) {
  sel
    .select<SVGCircleElement>('circle.node-ring')
    .attr('stroke-opacity', (d) => (d.id === selectedId ? 0.55 : 0))
  sel
    .select<SVGCircleElement>('circle.node-dot')
    .attr('fill-opacity', (d) => (d.id === selectedId ? 1 : 0.8))
  sel
    .select<SVGTextElement>('text')
    .attr('fill', (d) => (d.id === selectedId ? 'var(--t-text)' : 'var(--t-text-muted)'))
    .attr('font-size', (d) => (d.id === selectedId ? 12 : 10))
    .attr('font-weight', (d) => (d.id === selectedId ? 600 : 400))
}

export function ConceptGraph({ nodes, edges, onNodeClick, selectedNodeId = null }: ConceptGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 })

  // Live refs so the build effect never depends on callback/selection identity.
  const onNodeClickRef = useRef(onNodeClick)
  const selectedIdRef = useRef<string | null>(selectedNodeId)
  const nodeSelRef = useRef<NodeSelection | null>(null)

  useEffect(() => {
    onNodeClickRef.current = onNodeClick
  }, [onNodeClick])

  // Resize observer
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      setDimensions({ width: Math.max(width, 300), height: Math.max(height, 300) })
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  // Effect 1 — build simulation + elements. Depends on data and dimensions only.
  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const { width, height } = dimensions
    const tones = courseToneMap(nodes)
    const toneOf = (d: SimNode) => tones.get(d.course_id) ?? 'var(--t-sage)'

    const simNodes: SimNode[] = nodes.map((n) => ({ ...n }))
    const nodeMap = new Map(simNodes.map((n) => [n.id, n]))
    const simLinks: SimLink[] = edges
      .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map((e) => ({ ...e, source: e.source, target: e.target }))

    // Zoom behavior
    const g = svg.append('g')
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })
    svg.call(zoom)

    const simulation = createSimulation(simNodes, simLinks, width, height)

    // Edges — quiet token strokes per prototype
    const link = g
      .append('g')
      .selectAll('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', 'var(--t-border-strong)')
      .attr('stroke-opacity', 0.8)
      .attr('stroke-width', (d) => Math.max(1, d.confidence * 1.5))

    // Nodes
    const node = g
      .append('g')
      .selectAll<SVGGElement, SimNode>('g')
      .data(simNodes)
      .join('g')
      .style('cursor', 'pointer')
      .call(
        d3
          .drag<SVGGElement, SimNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart()
            d.fx = d.x
            d.fy = d.y
          })
          .on('drag', (event, d) => {
            d.fx = event.x
            d.fy = event.y
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0)
            d.fx = null
            d.fy = null
          }),
      )

    // Selection ring (revealed by the selection effect, never rebuilt)
    node
      .append('circle')
      .attr('class', 'node-ring')
      .attr('r', (d) => nodeRadius(d.mention_count) + 5)
      .attr('fill', 'none')
      .attr('stroke', (d) => toneOf(d))
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0)

    node
      .append('circle')
      .attr('class', 'node-dot')
      .attr('r', (d) => nodeRadius(d.mention_count))
      .attr('fill', (d) => toneOf(d))
      .attr('fill-opacity', 0.8)

    node
      .append('text')
      .text((d) => d.name)
      .attr('class', 'font-mono')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => nodeRadius(d.mention_count) + 12)
      .attr('font-size', 10)
      .attr('fill', 'var(--t-text-muted)')

    node.on('click', (_event, d) => {
      onNodeClickRef.current?.(d.id)
    })

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as SimNode).x!)
        .attr('y1', (d) => (d.source as SimNode).y!)
        .attr('x2', (d) => (d.target as SimNode).x!)
        .attr('y2', (d) => (d.target as SimNode).y!)

      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
    })

    nodeSelRef.current = node
    applySelection(node, selectedIdRef.current)

    return () => {
      simulation.stop()
      nodeSelRef.current = null
    }
  }, [nodes, edges, dimensions])

  // Effect 2 — selection styling only: attribute updates on existing elements.
  useEffect(() => {
    selectedIdRef.current = selectedNodeId
    if (nodeSelRef.current) {
      applySelection(nodeSelRef.current, selectedNodeId)
    }
  }, [selectedNodeId])

  if (nodes.length === 0) return null

  return (
    <div ref={containerRef} className="w-full h-full min-h-[400px]">
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        role="img"
        aria-label={`Concept graph — ${nodes.length} concepts`}
        className="block"
      />
    </div>
  )
}
