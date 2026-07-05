import { useState } from 'react'
import { List, Network } from 'lucide-react'
import { ConceptGraph } from '../components/concepts/ConceptGraph'
import { ConceptDetailPanel } from '../components/concepts/ConceptDetail'
import { ConceptList } from '../components/concepts/ConceptList'
import { Card, EmptyState, ErrorState, Input, PageHeader, SectionLabel, Select, Skeleton } from '../components/ui'
import { useConceptGraph, useConceptList, useCourses } from '../hooks/useApi'
import { useOnlineStatus } from '../hooks/useOnlineStatus'

type View = 'graph' | 'list'

function ViewToggle({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  const buttonClass = (active: boolean) =>
    `flex items-center gap-1.5 text-xs font-medium px-3 py-2 cursor-pointer transition-colors ${
      active ? 'bg-surface-2 text-text' : 'text-text-muted hover:text-text hover:bg-surface-2'
    }`

  return (
    <div
      className="flex items-center border border-border rounded-lg overflow-hidden"
      role="group"
      aria-label="View"
    >
      <button
        type="button"
        className={buttonClass(view === 'graph')}
        aria-pressed={view === 'graph'}
        onClick={() => onChange('graph')}
      >
        <Network size={13} aria-hidden /> Graph
      </button>
      <button
        type="button"
        className={`${buttonClass(view === 'list')} border-l border-border`}
        aria-pressed={view === 'list'}
        onClick={() => onChange('list')}
      >
        <List size={13} aria-hidden /> List
      </button>
    </div>
  )
}

function LoadingMirror() {
  return (
    <div className="flex flex-col lg:flex-row gap-4 items-start">
      <Card className="flex-1 w-full" padding>
        <Skeleton className="w-full h-[380px]" />
      </Card>
      <Card className="w-full lg:w-80 shrink-0" padding>
        <Skeleton height={14} width={96} className="mb-3" />
        <div className="space-y-2">
          <Skeleton height={16} width="100%" />
          <Skeleton height={16} width="90%" />
          <Skeleton height={16} width="75%" />
        </div>
        <Skeleton height={32} width="100%" className="mt-4" />
      </Card>
    </div>
  )
}

export function KnowledgeGraphPage() {
  const [courseFilter, setCourseFilter] = useState('')
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(null)
  const [view, setView] = useState<View>('graph')
  const [search, setSearch] = useState('')
  const isOnline = useOnlineStatus()

  const { data: courses } = useCourses()
  const {
    data: graph,
    isLoading: graphLoading,
    error: graphError,
    refetch: refetchGraph,
  } = useConceptGraph(courseFilter || undefined)
  const {
    data: conceptList,
    isLoading: listLoading,
    error: listError,
    refetch: refetchList,
  } = useConceptList(courseFilter || undefined, search || undefined)

  const handleSelect = (conceptId: string) => setSelectedConceptId(conceptId)

  const courseOptions = [
    { value: '', label: 'All courses' },
    ...(courses?.map((c) => ({ value: c.code, label: c.code })) ?? []),
  ]

  const loading = view === 'graph' ? graphLoading : listLoading
  const error = view === 'graph' ? graphError : listError
  const retry = view === 'graph' ? refetchGraph : refetchList
  const isEmpty = view === 'graph' ? graph && graph.nodes.length === 0 && !courseFilter : false

  const sidePanel = (
    <Card className="w-full lg:w-80 shrink-0 self-start" padding>
      {selectedConceptId ? (
        <ConceptDetailPanel
          conceptId={selectedConceptId}
          onNavigate={handleSelect}
          onClose={() => setSelectedConceptId(null)}
        />
      ) : (
        <>
          <SectionLabel>Selected concept</SectionLabel>
          <p className="text-xs text-text-muted leading-relaxed">
            Select a concept to see its description, relationships, and where it appears — then
            scope a study session to it.
          </p>
        </>
      )}
    </Card>
  )

  return (
    <div>
      <PageHeader
        title="Knowledge"
        subtitle="Every extracted concept, linked. Select a node to scope a session."
        actions={
          <>
            <Select
              className="w-40"
              options={courseOptions}
              value={courseFilter}
              onValueChange={(value) => {
                setCourseFilter(value)
                setSelectedConceptId(null)
              }}
              placeholder="All courses"
            />
            <ViewToggle view={view} onChange={setView} />
          </>
        }
      />

      {loading ? (
        <LoadingMirror />
      ) : isEmpty ? (
        <Card>
          <EmptyState
            icon="🕸"
            title="No concepts extracted yet"
            description="Concepts are mined from your summaries. Process a lecture, then extract its concept graph."
            actionLabel="Upload lectures"
            actionTo="/upload"
          />
        </Card>
      ) : (
        <>
          <div className="flex flex-col lg:flex-row gap-4 items-start">
            <div className="flex-1 min-w-0 w-full">
              {error ? (
                // Canvas-only failure — the side panel structure stays put.
                <Card padding>
                  <ErrorState
                    title={
                      isOnline
                        ? `${view === 'graph' ? 'Graph' : 'Concept list'} couldn't load`
                        : "You're offline"
                    }
                    detail={error instanceof Error ? error.message : undefined}
                    onRetry={() => retry()}
                  />
                </Card>
              ) : view === 'graph' ? (
                <Card className="bg-surface-0 overflow-hidden" padding={false}>
                  <div className="h-[500px] lg:h-[560px]">
                    <ConceptGraph
                      nodes={graph?.nodes ?? []}
                      edges={graph?.edges ?? []}
                      onNodeClick={handleSelect}
                      selectedNodeId={selectedConceptId}
                    />
                  </div>
                </Card>
              ) : (
                <Card padding>
                  <Input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search concepts…"
                    aria-label="Search concepts"
                    className="mb-3 sm:max-w-xs"
                  />
                  <ConceptList
                    concepts={conceptList ?? []}
                    onSelect={handleSelect}
                    selectedId={selectedConceptId}
                  />
                </Card>
              )}

              <p className="font-mono text-[11px] text-text-faint mt-3">
                {view === 'graph'
                  ? 'list view is the keyboard/screen-reader twin — arrows navigate, enter opens'
                  : '↑↓ navigate · enter opens · same actions as the graph'}
                {graph && graph.nodes.length > 0 && (
                  <> · {graph.nodes.length} concepts · {graph.edges.length} links</>
                )}
              </p>
            </div>

            {sidePanel}
          </div>
        </>
      )}
    </div>
  )
}
