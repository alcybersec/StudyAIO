import { describe, expect, it } from 'vitest'
import {
  initViewerState,
  parseViewerParams,
  viewerReducer,
  ZOOM_MAX,
  ZOOM_MIN,
  type ViewerState,
} from './viewerReducer'
import type { Artifact } from '../../types'

const makeArtifact = (id: string, fileType = 'pdf'): Artifact => ({
  id,
  course_id: 'c1',
  week: 1,
  title: null,
  original_filename: `${id}.${fileType}`,
  file_type: fileType,
  sha256: 'abc',
  file_size_bytes: 1024,
  status: 'processed',
  created_at: '2026-01-01T00:00:00Z',
})

const base: ViewerState = {
  artifactId: 'a1',
  page: 3,
  zoom: 100,
  open: true,
  totalPages: 10,
  targetPage: 3,
  nav: 1,
}

describe('viewerReducer', () => {
  it('select_artifact resets page, totalPages and bumps nav', () => {
    const next = viewerReducer(base, { type: 'select_artifact', artifactId: 'a2' })
    expect(next).toMatchObject({ artifactId: 'a2', page: 1, targetPage: 1, totalPages: 0, nav: 2 })
  })

  it('select_artifact with the same id is a no-op', () => {
    expect(viewerReducer(base, { type: 'select_artifact', artifactId: 'a1' })).toBe(base)
  })

  it('go_to_page clamps into [1, totalPages] and bumps nav', () => {
    expect(viewerReducer(base, { type: 'go_to_page', page: 99 })).toMatchObject({ page: 10, targetPage: 10, nav: 2 })
    expect(viewerReducer(base, { type: 'go_to_page', page: -5 })).toMatchObject({ page: 1, targetPage: 1 })
  })

  it('go_to_page bumps nav even for the same page so re-scroll re-triggers', () => {
    const next = viewerReducer(base, { type: 'go_to_page', page: 3 })
    expect(next.nav).toBe(2)
  })

  it('page_viewed updates page without touching targetPage or nav', () => {
    const next = viewerReducer(base, { type: 'page_viewed', page: 5 })
    expect(next).toMatchObject({ page: 5, targetPage: 3, nav: 1 })
  })

  it('zoom stays within bounds', () => {
    let s = { ...base, zoom: ZOOM_MAX }
    expect(viewerReducer(s, { type: 'zoom_in' }).zoom).toBe(ZOOM_MAX)
    s = { ...base, zoom: ZOOM_MIN }
    expect(viewerReducer(s, { type: 'zoom_out' }).zoom).toBe(ZOOM_MIN)
    expect(viewerReducer(base, { type: 'zoom_in' }).zoom).toBe(125)
    expect(viewerReducer(base, { type: 'zoom_out' }).zoom).toBe(75)
  })

  it('toggle_open flips open', () => {
    expect(viewerReducer(base, { type: 'toggle_open' }).open).toBe(false)
  })

  it('open_at opens, switches artifact and commands a page', () => {
    const closed = { ...base, open: false }
    const next = viewerReducer(closed, { type: 'open_at', artifactId: 'a2', page: 7 })
    expect(next).toMatchObject({ open: true, artifactId: 'a2', page: 7, targetPage: 7, totalPages: 0, nav: 2 })
  })

  it('open_at on the current artifact keeps totalPages and clamps', () => {
    const next = viewerReducer(base, { type: 'open_at', artifactId: 'a1', page: 42 })
    expect(next).toMatchObject({ artifactId: 'a1', page: 10, totalPages: 10 })
  })

  it('doc_loaded records total pages', () => {
    expect(viewerReducer(base, { type: 'doc_loaded', totalPages: 24 }).totalPages).toBe(24)
  })
})

describe('initViewerState', () => {
  const artifacts = [makeArtifact('doc1', 'docx'), makeArtifact('pdf1'), makeArtifact('pdf2')]

  it('prefers the deep-linked artifact', () => {
    const s = initViewerState({ artifacts, initialArtifactId: 'pdf2', initialPage: 4, initialOpen: true })
    expect(s).toMatchObject({ artifactId: 'pdf2', page: 4, targetPage: 4, open: true, zoom: 100 })
  })

  it('falls back to the first PDF, then the first artifact', () => {
    expect(initViewerState({ artifacts }).artifactId).toBe('pdf1')
    expect(initViewerState({ artifacts: [makeArtifact('d', 'docx')] }).artifactId).toBe('d')
    expect(initViewerState({ artifacts: [] }).artifactId).toBeNull()
  })

  it('ignores an unknown deep-linked artifact id', () => {
    expect(initViewerState({ artifacts, initialArtifactId: 'ghost' }).artifactId).toBe('pdf1')
  })
})

describe('parseViewerParams', () => {
  it('parses artifact and page', () => {
    const p = parseViewerParams(new URLSearchParams('artifact=a1&page=5'))
    expect(p).toEqual({ artifactId: 'a1', page: 5 })
  })

  it('non-numeric page falls back to 1', () => {
    expect(parseViewerParams(new URLSearchParams('page=abc')).page).toBe(1)
    expect(parseViewerParams(new URLSearchParams('page=')).page).toBe(1)
    expect(parseViewerParams(new URLSearchParams('page=-3')).page).toBe(1)
    expect(parseViewerParams(new URLSearchParams('page=2.9')).page).toBe(2)
  })

  it('missing params yield nulls and page 1', () => {
    expect(parseViewerParams(new URLSearchParams())).toEqual({ artifactId: null, page: 1 })
  })
})
