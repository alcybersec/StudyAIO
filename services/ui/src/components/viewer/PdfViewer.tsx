import { useState, useEffect, useRef, useCallback } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/TextLayer.css'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import { LoadingSpinner } from '../ui'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface PdfViewerProps {
  fileUrl: string
  targetPage?: number
  navToken?: number
  onPageChange?: (page: number) => void
  onTotalPages?: (total: number) => void
}

export function PdfViewer({ fileUrl, targetPage, navToken, onPageChange, onTotalPages }: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number>(0)
  const [containerWidth, setContainerWidth] = useState<number>(600)
  const [pagesRendered, setPagesRendered] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map())
  const observerRef = useRef<IntersectionObserver | null>(null)
  // Use a ref to track page so observer and programmatic nav don't race through state
  const currentPageRef = useRef(1)
  const scrollLockUntil = useRef(0)

  const reportPage = useCallback((page: number) => {
    if (page !== currentPageRef.current) {
      currentPageRef.current = page
      onPageChange?.(page)
    }
  }, [onPageChange])

  // Track container width for responsive page sizing
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        setContainerWidth(entry.contentRect.width)
      }
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  // Set up IntersectionObserver once pages are rendered
  useEffect(() => {
    if (!pagesRendered || numPages === 0) return

    const container = containerRef.current

    observerRef.current = new IntersectionObserver(
      (entries) => {
        // Skip during programmatic scroll
        if (Date.now() < scrollLockUntil.current) return

        let bestEntry: IntersectionObserverEntry | null = null
        for (const entry of entries) {
          if (entry.isIntersecting) {
            if (!bestEntry || entry.intersectionRatio > bestEntry.intersectionRatio) {
              bestEntry = entry
            }
          }
        }
        if (bestEntry) {
          const pageNum = Number(bestEntry.target.getAttribute('data-page'))
          if (pageNum) {
            reportPage(pageNum)
          }
        }
      },
      {
        root: container,
        threshold: [0.3, 0.5, 0.7],
      },
    )

    for (const [, el] of pageRefs.current) {
      observerRef.current.observe(el)
    }

    return () => {
      observerRef.current?.disconnect()
      observerRef.current = null
    }
  }, [pagesRendered, numPages, reportPage])

  // Scroll to target page within the container
  useEffect(() => {
    if (!targetPage || targetPage < 1 || targetPage > numPages) return
    const el = pageRefs.current.get(targetPage)
    const container = containerRef.current
    if (el && container) {
      // Lock observer for 1s to prevent overwrite during smooth scroll
      scrollLockUntil.current = Date.now() + 1000
      const containerRect = container.getBoundingClientRect()
      const elRect = el.getBoundingClientRect()
      const scrollOffset = elRect.top - containerRect.top + container.scrollTop
      container.scrollTo({ top: scrollOffset, behavior: 'smooth' })
      // Immediately report the target page
      currentPageRef.current = targetPage
      onPageChange?.(targetPage)
    }
  }, [targetPage, navToken, numPages]) // eslint-disable-line react-hooks/exhaustive-deps

  const onDocumentLoadSuccess = useCallback(
    ({ numPages: total }: { numPages: number }) => {
      setNumPages(total)
      setPagesRendered(false)
      onTotalPages?.(total)
    },
    [onTotalPages],
  )

  const setPageRef = useCallback((pageNum: number, el: HTMLDivElement | null) => {
    if (el) {
      pageRefs.current.set(pageNum, el)
      queueMicrotask(() => {
        if (pageRefs.current.size > 0) {
          setPagesRendered(true)
        }
      })
    } else {
      pageRefs.current.delete(pageNum)
    }
  }, [])

  return (
    <div ref={containerRef} className="overflow-y-auto h-full bg-gray-100">
      <Document
        file={fileUrl}
        onLoadSuccess={onDocumentLoadSuccess}
        loading={<LoadingSpinner label="Loading PDF..." />}
        error={
          <div className="text-center py-8 text-red-600 text-sm">
            Failed to load PDF. Try downloading the file instead.
          </div>
        }
      >
        {Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
          <div
            key={pageNum}
            ref={(el) => setPageRef(pageNum, el)}
            data-page={pageNum}
            id={`pdf-page-${pageNum}`}
            className="mb-2 shadow-sm bg-white mx-auto"
            style={{ maxWidth: containerWidth }}
          >
            <Page
              pageNumber={pageNum}
              width={containerWidth - 16}
              renderTextLayer={true}
              renderAnnotationLayer={true}
            />
          </div>
        ))}
      </Document>
    </div>
  )
}
