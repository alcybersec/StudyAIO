import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import type { ConceptEdge, ConceptNode } from '../../types'

const CATEGORY_COLORS: Record<string, string> = {
  theory: '#6366f1',
  algorithm: '#f59e0b',
  data_structure: '#10b981',
  pattern: '#8b5cf6',
  tool: '#ef4444',
  language: '#3b82f6',
  protocol: '#ec4899',
  principle: '#14b8a6',
  method: '#f97316',
  general: '#6b7280',
}

interface SimNode extends d3.SimulationNodeDatum {
  id: string
  name: string
  description: string
  category: string
  mention_count: number
  source_weeks: number[]
  course_id: string
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  id: string
  relation_type: string
  confidence: number
}

interface ConceptGraphProps {
  nodes: ConceptNode[]
  edges: ConceptEdge[]
  onNodeClick?: (nodeId: string) => void
  selectedNodeId?: string | null
}

export function ConceptGraph({ nodes, edges, onNodeClick, selectedNodeId }: ConceptGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })

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

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const { width, height } = dimensions

    // Build simulation data
    const simNodes: SimNode[] = nodes.map((n) => ({ ...n }))
    const nodeMap = new Map(simNodes.map((n) => [n.id, n]))

    const simLinks: SimLink[] = edges
      .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map((e) => ({
        ...e,
        source: e.source,
        target: e.target,
      }))

    // Zoom behavior
    const g = svg.append('g')
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })
    svg.call(zoom)

    // Arrow markers for directed edges
    const defs = svg.append('defs')
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#94a3b8')

    // Simulation
    const simulation = d3.forceSimulation<SimNode>(simNodes)
      .force('link', d3.forceLink<SimNode, SimLink>(simLinks).id((d) => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(30))

    // Links
    const link = g.append('g')
      .selectAll('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', '#94a3b8')
      .attr('stroke-opacity', 0.5)
      .attr('stroke-width', (d) => Math.max(1, d.confidence * 2))
      .attr('marker-end', 'url(#arrowhead)')

    // Link labels
    const linkLabel = g.append('g')
      .selectAll('text')
      .data(simLinks)
      .join('text')
      .text((d) => d.relation_type.replace('_', ' '))
      .attr('font-size', '9px')
      .attr('fill', '#94a3b8')
      .attr('text-anchor', 'middle')

    // Nodes
    const node = g.append('g')
      .selectAll<SVGGElement, SimNode>('g')
      .data(simNodes)
      .join('g')
      .style('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, SimNode>()
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
          })
      )

    // Node circles
    node.append('circle')
      .attr('r', (d) => Math.min(8 + d.mention_count * 2, 24))
      .attr('fill', (d) => CATEGORY_COLORS[d.category] || CATEGORY_COLORS.general)
      .attr('stroke', (d) => d.id === selectedNodeId ? '#fff' : 'transparent')
      .attr('stroke-width', (d) => d.id === selectedNodeId ? 3 : 0)
      .attr('opacity', 0.85)

    // Node labels
    node.append('text')
      .text((d) => d.name)
      .attr('dx', (d) => Math.min(8 + d.mention_count * 2, 24) + 4)
      .attr('dy', 4)
      .attr('font-size', '11px')
      .attr('fill', 'currentColor')
      .attr('class', 'text-text')

    // Click handler
    node.on('click', (_event, d) => {
      onNodeClick?.(d.id)
    })

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as SimNode).x!)
        .attr('y1', (d) => (d.source as SimNode).y!)
        .attr('x2', (d) => (d.target as SimNode).x!)
        .attr('y2', (d) => (d.target as SimNode).y!)

      linkLabel
        .attr('x', (d) => ((d.source as SimNode).x! + (d.target as SimNode).x!) / 2)
        .attr('y', (d) => ((d.source as SimNode).y! + (d.target as SimNode).y!) / 2)

      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
    })

    return () => {
      simulation.stop()
    }
  }, [nodes, edges, dimensions, onNodeClick, selectedNodeId])

  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted">
        <div className="text-center">
          <p className="text-lg font-medium">No concepts yet</p>
          <p className="text-sm mt-1">Upload and process lecture files to extract concepts</p>
        </div>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="w-full h-full min-h-[400px]">
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className="bg-surface rounded-lg border border-border"
      />
    </div>
  )
}
