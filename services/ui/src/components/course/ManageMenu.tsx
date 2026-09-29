import { Archive, Download, FileText, Merge, MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button, Dropdown, DropdownItem, DropdownSeparator } from '../ui'
import { courseopsApi, exportApi } from '../../api/endpoints'

interface ManageMenuProps {
  courseCode: string
  onRename: () => void
  onMerge: () => void
  onArchive: () => void
  onDelete: () => void
}

/** Course manage menu (⋯) per the prototype: rename, merge, exports, archive, delete. */
export function ManageMenu({ courseCode, onRename, onMerge, onArchive, onDelete }: ManageMenuProps) {
  const { t } = useTranslation()

  return (
    <Dropdown
      trigger={
        <Button variant="ghost" size="sm" aria-label={t('Manage course')}>
          <MoreHorizontal size={15} aria-hidden />
        </Button>
      }
    >
      <DropdownItem onSelect={onRename}>
        <Pencil size={14} className="text-text-faint" aria-hidden /> {t('Rename course')}
      </DropdownItem>
      <DropdownItem onSelect={onMerge}>
        <Merge size={14} className="text-text-faint" aria-hidden /> {t('Merge into another course')}
      </DropdownItem>
      <DropdownItem onSelect={() => window.open(exportApi.obsidianVaultUrl(courseCode), '_blank')}>
        <Download size={14} className="text-text-faint" aria-hidden /> {t('Export — Markdown / Obsidian')}
      </DropdownItem>
      <DropdownItem onSelect={() => window.open(courseopsApi.calendarUrl(courseCode), '_blank')}>
        <FileText size={14} className="text-text-faint" aria-hidden /> {t('Export deadlines (.ics)')}
      </DropdownItem>
      <DropdownItem onSelect={onArchive}>
        <Archive size={14} className="text-text-faint" aria-hidden /> {t('Archive course')}
      </DropdownItem>
      <DropdownSeparator />
      <DropdownItem danger onSelect={onDelete}>
        <Trash2 size={14} aria-hidden /> {t('Delete course…')}
      </DropdownItem>
    </Dropdown>
  )
}
