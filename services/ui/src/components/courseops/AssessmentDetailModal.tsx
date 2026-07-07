import { useRef, useState } from 'react'
import { Download, FileText, Loader2, Trash2, Upload } from 'lucide-react'
import { Modal, Button, Badge, SkeletonText, ErrorState, EmptyState } from '../ui'
import {
  useAssessmentDocuments,
  useUpdateAssessment,
  useUploadAssessmentDocument,
  useDeleteDocument,
} from '../../hooks/useApi'
import { courseopsApi } from '../../api/endpoints'
import type { Assessment } from '../../types'

const FIELD =
  'w-full rounded-md border border-border bg-surface-1 text-text px-3 py-2 text-sm focus:border-sage focus:outline-none focus:ring-1 focus:ring-sage'
const TYPES = ['exam', 'assignment', 'quiz', 'project', 'lab', 'presentation', 'other']
const DOC_TYPES = ['brief', 'rubric', 'guideline', 'handbook', 'other']

interface AssessmentDetailModalProps {
  assessment: Assessment
  courseCode: string
  onClose: () => void
}

export function AssessmentDetailModal({ assessment, courseCode, onClose }: AssessmentDetailModalProps) {
  const [title, setTitle] = useState(assessment.title)
  const [type, setType] = useState(assessment.assessment_type)
  const [weight, setWeight] = useState(assessment.weight_pct != null ? String(assessment.weight_pct) : '')
  const [description, setDescription] = useState(assessment.description ?? '')
  const [docType, setDocType] = useState('brief')
  const fileRef = useRef<HTMLInputElement>(null)

  const updateAssessment = useUpdateAssessment(courseCode)
  const docsQuery = useAssessmentDocuments(assessment.id)
  const uploadDoc = useUploadAssessmentDocument(assessment.id)
  const deleteDoc = useDeleteDocument(assessment.id)

  function saveInfo() {
    updateAssessment.mutate({
      assessmentId: assessment.id,
      data: {
        title,
        assessment_type: type,
        weight_pct: weight === '' ? null : Number(weight),
        description: description || null,
      },
    })
  }

  function onFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) uploadDoc.mutate({ file, documentType: docType })
    e.target.value = ''
  }

  const docs = docsQuery.data

  return (
    <Modal open onOpenChange={(o) => !o && onClose()} title="Assessment" className="max-w-lg">
      <div className="space-y-5">
        {/* Info */}
        <section className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_140px] gap-3">
            <label className="block">
              <span className="text-xs font-medium text-text-muted">Title</span>
              <input value={title} onChange={(e) => setTitle(e.target.value)} className={`mt-1 ${FIELD}`} />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-text-muted">Weight %</span>
              <input
                type="number"
                min={0}
                max={100}
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                placeholder="—"
                className={`mt-1 ${FIELD}`}
              />
            </label>
          </div>
          <label className="block">
            <span className="text-xs font-medium text-text-muted">Type</span>
            <select value={type} onChange={(e) => setType(e.target.value)} className={`mt-1 ${FIELD}`}>
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-medium text-text-muted">Notes / info</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Grading criteria, submission details, guidelines…"
              className={`mt-1 ${FIELD}`}
            />
          </label>
          <div className="flex items-center justify-end gap-2">
            {updateAssessment.isSuccess && !updateAssessment.isPending && (
              <span className="text-xs text-sage-fg">Saved</span>
            )}
            <Button size="sm" onClick={saveInfo} loading={updateAssessment.isPending}>
              Save info
            </Button>
          </div>
        </section>

        {/* Documents */}
        <section className="border-t border-border pt-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-text">Documents</h3>
            <div className="flex items-center gap-2">
              <select value={docType} onChange={(e) => setDocType(e.target.value)} className="rounded-md border border-border bg-surface-1 text-text px-2 py-1 text-xs focus:border-sage focus:outline-none">
                {DOC_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
              <Button size="sm" variant="secondary" onClick={() => fileRef.current?.click()} loading={uploadDoc.isPending}>
                <Upload size={13} /> Attach
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx,.pptx"
                onChange={onFilePicked}
                className="sr-only"
              />
            </div>
          </div>

          {uploadDoc.isError && (
            <p className="text-xs text-red-fg mb-2" role="alert">
              {uploadDoc.error instanceof Error ? uploadDoc.error.message : 'Upload failed'}
            </p>
          )}

          {docsQuery.isLoading && <SkeletonText lines={2} />}
          {docsQuery.isError && !docs && (
            <ErrorState compact title="Documents couldn't load" onRetry={() => docsQuery.refetch()} />
          )}
          {docs && docs.length === 0 && (
            <EmptyState
              compact
              icon="📄"
              title="No documents attached"
              description="Attach a brief, rubric, or guideline for this assessment."
            />
          )}
          {docs && docs.length > 0 && (
            <ul className="divide-y divide-border">
              {docs.map((d) => (
                <li key={d.id} className="flex items-center gap-3 py-2">
                  <FileText size={15} className="text-text-faint shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] text-text">{d.original_filename}</div>
                    <div className="text-[11px] text-text-faint">
                      <Badge variant="default">{d.document_type}</Badge>
                    </div>
                  </div>
                  <a
                    href={courseopsApi.documentDownloadUrl(d.id)}
                    className="rounded-md p-1.5 text-text-muted hover:text-text hover:bg-surface-2"
                    title="Download"
                    aria-label={`Download ${d.original_filename}`}
                  >
                    <Download size={14} />
                  </a>
                  <button
                    onClick={() => deleteDoc.mutate(d.id)}
                    disabled={deleteDoc.isPending}
                    className="rounded-md p-1.5 text-red-fg hover:bg-red-soft disabled:opacity-50"
                    title="Remove"
                    aria-label={`Remove ${d.original_filename}`}
                  >
                    {deleteDoc.isPending ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Modal>
  )
}
