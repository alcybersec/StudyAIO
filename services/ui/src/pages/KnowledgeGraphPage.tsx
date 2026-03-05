import { useState } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import { ConceptGraph } from '../components/concepts/ConceptGraph'
import { ConceptDetailPanel } from '../components/concepts/ConceptDetail'
import { ConceptList } from '../components/concepts/ConceptList'
import { useConceptGraph, useConceptList, useCourses } from '../hooks/useApi'

export function KnowledgeGraphPage() {
  const [courseFilter, setCourseFilter] = useState<string>('')
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(null)
  const [tab, setTab] = useState('graph')
  const [search, setSearch] = useState('')

  const { data: courses } = useCourses()
  const { data: graph, isLoading: graphLoading } = useConceptGraph(courseFilter || undefined)
  const { data: conceptList, isLoading: listLoading } = useConceptList(
    courseFilter || undefined,
    search || undefined
  )

  const handleNodeClick = (nodeId: string) => {
    setSelectedConceptId(nodeId)
  }

  const handleNavigate = (conceptId: string) => {
    setSelectedConceptId(conceptId)
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text">Knowledge Graph</h1>
          <p className="text-sm text-text-muted mt-1">
            Explore concepts and their relationships across your courses
          </p>
        </div>

        {/* Course filter */}
        <select
          value={courseFilter}
          onChange={(e) => {
            setCourseFilter(e.target.value)
            setSelectedConceptId(null)
          }}
          className="px-3 py-2 rounded-lg border border-border bg-surface text-text text-sm"
        >
          <option value="">All courses</option>
          {courses?.map((course) => (
            <option key={course.id} value={course.code}>
              {course.code}{course.name ? ` — ${course.name}` : ''}
            </option>
          ))}
        </select>
      </div>

      {/* Tabs */}
      <Tabs.Root value={tab} onValueChange={setTab}>
        <Tabs.List className="flex gap-1 border-b border-border">
          <Tabs.Trigger
            value="graph"
            className="px-4 py-2 text-sm font-medium text-text-muted hover:text-text transition-colors border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:text-primary"
          >
            Graph View
          </Tabs.Trigger>
          <Tabs.Trigger
            value="list"
            className="px-4 py-2 text-sm font-medium text-text-muted hover:text-text transition-colors border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:text-primary"
          >
            List View
          </Tabs.Trigger>
        </Tabs.List>

        {/* Graph Tab */}
        <Tabs.Content value="graph" className="mt-4">
          <div className="flex gap-4">
            {/* Graph */}
            <div className={`flex-1 ${selectedConceptId ? 'lg:w-2/3' : 'w-full'}`}>
              {graphLoading ? (
                <div className="flex items-center justify-center h-[500px] bg-surface rounded-lg border border-border">
                  <div className="text-text-muted">Loading graph...</div>
                </div>
              ) : (
                <div className="h-[500px] lg:h-[600px]">
                  <ConceptGraph
                    nodes={graph?.nodes || []}
                    edges={graph?.edges || []}
                    onNodeClick={handleNodeClick}
                    selectedNodeId={selectedConceptId}
                  />
                </div>
              )}

              {/* Legend */}
              {graph && graph.nodes.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-text-muted">
                  {Array.from(new Set(graph.nodes.map((n) => n.category))).map((cat) => (
                    <span key={cat} className="flex items-center gap-1.5">
                      <span
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ backgroundColor: getCategoryColor(cat) }}
                      />
                      {cat.replace('_', ' ')}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Detail panel */}
            {selectedConceptId && (
              <div className="hidden lg:block w-80 bg-surface rounded-lg border border-border shrink-0">
                <ConceptDetailPanel
                  conceptId={selectedConceptId}
                  onNavigate={handleNavigate}
                  onClose={() => setSelectedConceptId(null)}
                />
              </div>
            )}
          </div>

          {/* Mobile detail */}
          {selectedConceptId && (
            <div className="lg:hidden mt-4 bg-surface rounded-lg border border-border">
              <ConceptDetailPanel
                conceptId={selectedConceptId}
                onNavigate={handleNavigate}
                onClose={() => setSelectedConceptId(null)}
              />
            </div>
          )}
        </Tabs.Content>

        {/* List Tab */}
        <Tabs.Content value="list" className="mt-4">
          {/* Search */}
          <div className="mb-4">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search concepts..."
              className="w-full sm:w-80 px-3 py-2 rounded-lg border border-border bg-surface text-text text-sm placeholder:text-text-muted"
            />
          </div>

          <div className="flex gap-4">
            <div className={`flex-1 bg-surface rounded-lg border border-border p-4 ${selectedConceptId ? 'lg:w-2/3' : 'w-full'}`}>
              {listLoading ? (
                <div className="text-center py-8 text-text-muted">Loading...</div>
              ) : (
                <ConceptList
                  concepts={conceptList || []}
                  onSelect={handleNodeClick}
                  selectedId={selectedConceptId}
                />
              )}
            </div>

            {selectedConceptId && (
              <div className="hidden lg:block w-80 bg-surface rounded-lg border border-border shrink-0">
                <ConceptDetailPanel
                  conceptId={selectedConceptId}
                  onNavigate={handleNavigate}
                  onClose={() => setSelectedConceptId(null)}
                />
              </div>
            )}
          </div>

          {selectedConceptId && (
            <div className="lg:hidden mt-4 bg-surface rounded-lg border border-border">
              <ConceptDetailPanel
                conceptId={selectedConceptId}
                onNavigate={handleNavigate}
                onClose={() => setSelectedConceptId(null)}
              />
            </div>
          )}
        </Tabs.Content>
      </Tabs.Root>

      {/* Stats */}
      {graph && graph.nodes.length > 0 && (
        <div className="flex gap-6 text-sm text-text-muted">
          <span>{graph.nodes.length} concepts</span>
          <span>{graph.edges.length} relationships</span>
          <span>{Array.from(new Set(graph.nodes.map((n) => n.category))).length} categories</span>
        </div>
      )}
    </div>
  )
}

function getCategoryColor(category: string): string {
  const colors: Record<string, string> = {
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
  return colors[category] || colors.general
}
