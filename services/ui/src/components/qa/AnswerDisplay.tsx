import { Link } from 'react-router-dom'
import type { Citation } from '../../types'

interface AnswerDisplayProps {
  answer: string
  citations: Citation[]
  chunksSearched: number
  onCitationClick?: (artifactId: string, page: number) => void
}

export function AnswerDisplay({ answer, citations, chunksSearched, onCitationClick }: AnswerDisplayProps) {
  // Replace [N] markers with styled citation links
  const renderAnswer = () => {
    const parts = answer.split(/(\[\d+\])/)
    return parts.map((part, i) => {
      const match = part.match(/^\[(\d+)\]$/)
      if (match) {
        const ref = Number(match[1])
        const citation = citations.find((c) => c.ref === ref)
        if (citation) {
          return (
            <sup key={i}>
              <a
                href={`#citation-${ref}`}
                className="text-primary hover:text-primary/80 font-medium"
              >
                [{ref}]
              </a>
            </sup>
          )
        }
      }
      return <span key={i}>{part}</span>
    })
  }

  const handleCitationSourceClick = (c: Citation, e: React.MouseEvent) => {
    if (onCitationClick && c.artifact_id) {
      e.preventDefault()
      onCitationClick(c.artifact_id, c.page_ref)
    }
  }

  return (
    <div className="space-y-4">
      {/* Answer text */}
      <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed">
        <p>{renderAnswer()}</p>
      </div>

      {/* Citation list */}
      {citations.length > 0 && (
        <div className="border-t border-gray-100 pt-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Sources ({chunksSearched} chunks searched)
          </h4>
          <ol className="space-y-2">
            {citations.map((c) => (
              <li key={c.ref} id={`citation-${c.ref}`} className="flex items-start gap-2">
                <span className="text-xs font-bold text-primary mt-0.5 shrink-0">
                  [{c.ref}]
                </span>
                <div className="text-sm">
                  <Link
                    to={`/courses/${c.course_code}/weeks/${c.week}${c.artifact_id ? `?artifact=${c.artifact_id}` : ''}${c.page_ref ? `&page=${c.page_ref}` : ''}`}
                    className="text-primary hover:underline font-medium"
                    onClick={(e) => handleCitationSourceClick(c, e)}
                  >
                    {c.course_code} Week {c.week}, p.{c.page_ref}
                  </Link>
                  {c.text_snippet && (
                    <p className="text-gray-500 text-xs mt-0.5 italic line-clamp-2">
                      "{c.text_snippet}"
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
