/** Shared realistic mock data for all prototype screens. */

export const courses = [
  { code: 'CSIT302', name: 'Cybersecurity', weeks: 9, cards: 142, color: 'sage' },
  { code: 'CSCI368', name: 'Network Security', weeks: 8, cards: 98, color: 'peri' },
  { code: 'CSCI317', name: 'Database Performance', weeks: 7, cards: 64, color: 'amber' },
]

export const exams = [
  { id: 'e1', course: 'CSIT302', title: 'CSIT302 Final', daysLeft: 9, readiness: 68 },
  { id: 'e2', course: 'CSCI368', title: 'CSCI368 Final', daysLeft: 21, readiness: 41 },
]

export const deadlines = [
  { course: 'CSIT302', title: 'Assignment 3 — Memory forensics report', due: 'Tue, Jul 8', urgency: 'red' },
  { course: 'CSCI368', title: 'Lab report — TLS interception', due: 'Sat, Jul 12', urgency: 'amber' },
  { course: 'CSIT302', title: 'Final exam', due: 'Sun, Jul 13', urgency: 'muted' },
]

export const weakTopics = [
  { topic: 'Memory forensics', course: 'CSIT302', week: 9, accuracy: 61 },
  { topic: 'TLS handshake', course: 'CSCI368', week: 6, accuracy: 58 },
  { topic: 'ASLR & mitigations', course: 'CSIT302', week: 7, accuracy: 64 },
]

export const activity = [
  { icon: 'check', text: 'Summarized Week 9 — Memory Forensics', when: '2h ago' },
  { icon: 'cards', text: '18 cards reviewed · 89% correct', when: '5h ago' },
  { icon: 'alert', text: '3 items waiting in review inbox', when: '6h ago' },
  { icon: 'upload', text: 'week9_forensics.pdf processed', when: 'yesterday' },
]

export const flashcards = [
  {
    front: 'What does ASLR randomize, and why does it complicate exploitation?',
    back: 'Address Space Layout Randomization randomizes the base addresses of the stack, heap, and shared libraries at process start. Exploits can no longer rely on fixed addresses for gadgets or shellcode, so an attacker needs an info leak before redirecting control flow.',
    course: 'CSIT302',
    week: 7,
  },
  {
    front: 'Which artifacts survive in RAM that make memory forensics valuable?',
    back: 'Running processes, network connections, loaded drivers, decrypted payloads, and encryption keys — all present in volatile memory even when nothing touches disk.',
    course: 'CSIT302',
    week: 9,
  },
]

export const pipelineFiles = [
  {
    name: 'week10_rootkits.pdf',
    size: '4.2 MB',
    stages: [
      { name: 'Ingest', status: 'done', ms: 320 },
      { name: 'Classify', status: 'done', ms: 4100 },
      { name: 'Extract', status: 'running', ms: null },
      { name: 'Summarize', status: 'pending', ms: null },
      { name: 'Index', status: 'pending', ms: null },
      { name: 'Assets', status: 'pending', ms: null },
    ],
  },
  {
    name: 'week10_lab_notes.docx',
    size: '812 KB',
    stages: [
      { name: 'Ingest', status: 'done', ms: 180 },
      { name: 'Classify', status: 'done', ms: 3800 },
      { name: 'Extract', status: 'done', ms: 2400 },
      { name: 'Summarize', status: 'failed', ms: 61000, error: 'AI provider timed out after 60s' },
      { name: 'Index', status: 'pending', ms: null },
      { name: 'Assets', status: 'pending', ms: null },
    ],
  },
] as const

export const reviewItems = [
  {
    id: 'r1',
    file: 'week10_rootkits.pdf',
    guess: { course: 'CSIT302', week: 10, confidence: 54 },
    reason: 'Filename matches CSIT302 pattern but content overlaps CSCI368 week 7 material.',
  },
  {
    id: 'r2',
    file: 'lecture_slides_final.pptx',
    guess: { course: 'CSCI368', week: 8, confidence: 41 },
    reason: 'No week number found; date suggests week 8 or revision material.',
  },
  {
    id: 'r3',
    file: 'scan_0034.pdf',
    guess: { course: 'CSCI317', week: 3, confidence: 22 },
    reason: 'Scanned document, OCR text sparse. Course guess based on upload folder only.',
  },
]

export const chatSessions = [
  { id: 's1', title: 'explain ASLR bypasses', when: '2h ago', count: 6 },
  { id: 's2', title: 'TLS 1.3 handshake walkthrough', when: 'yesterday', count: 11 },
  { id: 's3', title: 'quiz me on rootkit types', when: '3d ago', count: 24 },
]

export const chatMessages = [
  { role: 'user', text: 'How do attackers bypass ASLR in practice?' },
  {
    role: 'assistant',
    text: 'Three practical routes come up again and again:\n\n1. **Info leaks** — a format-string or out-of-bounds read reveals a runtime address, letting the attacker rebase their ROP chain.\n2. **Partial overwrites** — overwriting only the low bytes of a pointer sidesteps randomized high bits.\n3. **Brute force** — on 32-bit targets the entropy is small enough to spray and retry.\n\nYour Week 7 notes cover the info-leak route in the context of the lab exploit.',
    sources: ['CSIT302 · Week 7 — Exploit mitigation', 'CSIT302 · Week 9 — Memory forensics'],
  },
]

export const notifications = [
  { id: 'n1', kind: 'pipeline', text: 'week9_forensics.pdf finished processing', when: '2h ago', unread: true },
  { id: 'n2', kind: 'review', text: '3 files need classification review', when: '6h ago', unread: true },
  { id: 'n3', kind: 'achievement', text: 'Achievement unlocked: Consistency III', when: 'yesterday', unread: false },
  { id: 'n4', kind: 'deadline', text: 'Assignment 3 due in 4 days', when: 'yesterday', unread: false },
]

export const planner = [
  { day: 'Mon', items: [{ course: 'CSIT302', what: '20 cards', done: true }] },
  { day: 'Tue', items: [{ course: 'CSIT302', what: '20 cards', done: true }, { course: 'CSCI368', what: '10 cards', done: false }] },
  { day: 'Wed', items: [{ course: 'CSIT302', what: '15 cards + quiz', done: false }] },
  { day: 'Thu', items: [{ course: 'CSCI368', what: '15 cards', done: false }] },
  { day: 'Fri', items: [{ course: 'CSIT302', what: 'practice quiz wk 7–9', done: false }] },
  { day: 'Sat', items: [{ course: 'CSCI368', what: '15 cards', done: false }] },
  { day: 'Sun', items: [{ course: 'CSIT302', what: 'mock exam', done: false }] },
]
