import { test, expect, deleteCourse, seedStudyItems } from './fixtures'
import type { APIRequestContext, Locator, Page } from '@playwright/test'

// GL#48: edit, delete and add flashcards and quiz questions on the week page.
// Rows are seeded straight into the database (seed_e2e.py studyitems): a lecture
// in week 1 only, so week 2 is the "no lecture to attach it to" case. Every test
// owns a course of its own, so edits never leak between tests, and removes it.

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

function newCode(): string {
  return `QAI${Math.random().toString(36).slice(2, 8).toUpperCase()}`
}

const weekUrl = (code: string, week: number, tab: 'flashcards' | 'quiz') =>
  `/courses/${code}/weeks/${week}?tab=${tab}`

const cardFace = (page: Page): Locator => page.locator('button[aria-label^="Showing"]')

async function counter(page: Page): Promise<string> {
  return (await page.locator('span.font-mono').filter({ hasText: /^\d+ \/ \d+$/ }).first().innerText()).trim()
}

/** Step through the deck with Next until the card showing `front` is on screen. */
async function showCard(page: Page, front: string): Promise<void> {
  for (let i = 0; i < 6; i++) {
    if ((await cardFace(page).innerText()).includes(front)) return
    const next = page.getByRole('button', { name: 'Next', exact: true })
    if (!(await next.isEnabled())) break
    await next.click()
  }
  await expect(cardFace(page)).toContainText(front)
}

async function activeCards(api: APIRequestContext, code: string, week = 1) {
  const resp = await api.get(`${API_URL}/api/assets/flashcards?course_code=${code}&week=${week}`)
  expect(resp.ok()).toBeTruthy()
  return (await resp.json()) as { id: string; front: string; origin: string }[]
}

test.describe('Flashcards: edit, delete, add', () => {
  let code: string

  test.beforeEach(() => {
    code = newCode()
    seedStudyItems(code)
  })

  test.afterEach(async ({ request }) => {
    await deleteCourse(request, code)
  })

  test('editing a card shows the new text with a Yours badge, and survives a reload', async ({ page, request }) => {
    await page.goto(weekUrl(code, 1, 'flashcards'))
    await expect(cardFace(page)).toBeVisible({ timeout: 10_000 })
    const before = await activeCards(request, code)
    expect(before).toHaveLength(2)
    expect(before.every((c) => c.origin === 'pipeline')).toBe(true)
    await expect(page.getByText('Yours', { exact: true })).toHaveCount(0)

    await page.getByRole('button', { name: 'Edit', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Edit flashcard' })
    await expect(dialog).toBeVisible()
    await dialog.getByLabel('Front').fill('Edited front text')
    await dialog.getByRole('button', { name: 'Save changes' }).click()
    await expect(dialog).toBeHidden()

    await showCard(page, 'Edited front text')
    await expect(page.getByText('Yours', { exact: true })).toBeVisible()
    expect(await counter(page)).toMatch(/ \/ 2$/) // the archived original is not listed

    await page.reload()
    await expect(cardFace(page)).toBeVisible({ timeout: 10_000 })
    await showCard(page, 'Edited front text')
    await expect(page.getByText('Yours', { exact: true })).toBeVisible()

    const after = await activeCards(request, code)
    expect(after).toHaveLength(2)
    expect(after.filter((c) => c.origin === 'user').map((c) => c.front)).toEqual(['Edited front text'])
  })

  test('an empty field is refused in the form and nothing is sent', async ({ page, request }) => {
    await page.goto(weekUrl(code, 1, 'flashcards'))
    await page.getByRole('button', { name: 'Edit', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Edit flashcard' })
    await dialog.getByLabel('Front').fill('   ')
    await dialog.getByRole('button', { name: 'Save changes' }).click()
    await expect(dialog.getByText('This field is required')).toBeVisible()
    await expect(dialog).toBeVisible()
    expect((await activeCards(request, code)).every((c) => c.origin === 'pipeline')).toBe(true)
  })

  test('delete: Cancel holds focus, Escape and Cancel delete nothing, confirming removes the card', async ({
    page,
    request,
  }) => {
    await page.goto(weekUrl(code, 1, 'flashcards'))
    await expect(cardFace(page)).toBeVisible({ timeout: 10_000 })
    expect(await counter(page)).toBe('1 / 2')
    const dialog = page.getByRole('dialog', { name: 'Delete this flashcard?' })
    const open = () => page.getByRole('button', { name: 'Delete', exact: true }).click()

    await open()
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    expect(await counter(page)).toBe('1 / 2')

    // Enter on the focused Cancel dismisses rather than deletes.
    await open()
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(dialog).toBeHidden()
    expect(await counter(page)).toBe('1 / 2')

    await open()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    expect(await activeCards(request, code)).toHaveLength(2)

    await open()
    await dialog.getByRole('button', { name: 'Delete', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect.poll(() => counter(page)).toBe('1 / 1')
    expect(await activeCards(request, code)).toHaveLength(1)
  })

  test('adding a card puts it in the deck marked Yours', async ({ page, request }) => {
    await page.goto(weekUrl(code, 1, 'flashcards'))
    await expect(cardFace(page)).toBeVisible({ timeout: 10_000 })
    await page.getByRole('button', { name: 'Add card', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Add flashcard' })
    await dialog.getByLabel('Front').fill('Brand new front')
    await dialog.getByLabel('Back').fill('Brand new back')
    await dialog.getByRole('button', { name: 'Add card' }).click()
    await expect(dialog).toBeHidden()

    await expect.poll(() => counter(page)).toMatch(/ \/ 3$/)
    await showCard(page, 'Brand new front')
    await expect(page.getByText('Yours', { exact: true })).toBeVisible()
    const cards = await activeCards(request, code)
    expect(cards.find((c) => c.front === 'Brand new front')?.origin).toBe('user')
  })

  test('a week without a lecture says to upload one first, and adds nothing', async ({ page, request }) => {
    await page.goto(weekUrl(code, 2, 'flashcards'))
    await expect(page.getByText('No flashcards yet')).toBeVisible({ timeout: 10_000 })
    await page.getByRole('button', { name: 'Add card', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Add flashcard' })
    await dialog.getByLabel('Front').fill('Orphan front')
    await dialog.getByLabel('Back').fill('Orphan back')
    await dialog.getByRole('button', { name: 'Add card' }).click()
    await expect(dialog.getByRole('alert')).toHaveText('Upload a lecture for this week first')
    await expect(dialog).toBeVisible()
    expect(await activeCards(request, code, 2)).toHaveLength(0)
  })
})

test.describe('Quiz: add, validate, grade', () => {
  let code: string

  test.beforeEach(() => {
    code = newCode()
    seedStudyItems(code)
  })

  test.afterEach(async ({ request }) => {
    await deleteCourse(request, code)
  })

  async function openAdd(page: Page, week = 1) {
    await page.goto(weekUrl(code, week, 'quiz'))
    await page.getByRole('button', { name: 'Add question', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Add question' })
    await expect(dialog).toBeVisible()
    return dialog
  }

  /** Answer and advance through the run until `text` is the question on screen. */
  async function reachQuestion(page: Page, text: string): Promise<void> {
    for (let i = 0; i < 6; i++) {
      if (await page.getByText(text, { exact: true }).isVisible()) return
      await page.getByRole('radio').first().check()
      await page.getByRole('button', { name: 'Submit' }).click()
      await page.getByRole('button', { name: 'Next', exact: true }).click()
    }
    await expect(page.getByText(text, { exact: true })).toBeVisible()
  }

  test('multiple choice needs a question, filled options and a marked answer', async ({ page }) => {
    const dialog = await openAdd(page)
    await dialog.getByRole('button', { name: 'Add question' }).click()
    await expect(dialog.getByText('This field is required')).toBeVisible()
    await expect(dialog.getByText(/Give 2 to 8 options/)).toBeVisible()
    await expect(dialog.getByText('Mark the correct option')).toBeVisible()

    await dialog.getByLabel('Question', { exact: true }).fill('Which is the biggest?')
    await dialog.getByRole('textbox', { name: 'Option 1', exact: true }).fill('Small')
    await dialog.getByRole('textbox', { name: 'Option 2', exact: true }).fill('Large')
    await dialog.getByRole('button', { name: 'Add question' }).click()
    await expect(dialog.getByText('Mark the correct option')).toBeVisible()
    await expect(dialog.getByText(/Give 2 to 8 options/)).toBeHidden()

    // The option list is bounded: a second option cannot be removed below two.
    await expect(dialog.getByRole('button', { name: 'Remove option 1' })).toBeDisabled()
    await dialog.getByRole('button', { name: 'Add option' }).click()
    await expect(dialog.getByRole('textbox', { name: 'Option 3', exact: true })).toBeVisible()
    await dialog.getByRole('button', { name: 'Add question' }).click()
    await expect(dialog.getByText(/Give 2 to 8 options/)).toBeVisible()
    await expect(dialog.getByText('Mark the correct option')).toBeVisible()
    await expect(dialog).toBeVisible()
  })

  test('a hand-made question is graded against the option marked correct', async ({ page, request }) => {
    const dialog = await openAdd(page)
    await dialog.getByLabel('Question', { exact: true }).fill('Which is the biggest?')
    await dialog.getByRole('textbox', { name: 'Option 1', exact: true }).fill('Small')
    await dialog.getByRole('textbox', { name: 'Option 2', exact: true }).fill('Large')
    await dialog.getByRole('radio', { name: 'Option 2 is correct' }).check()
    await dialog.getByRole('button', { name: 'Add question' }).click()
    await expect(dialog).toBeHidden()

    const list = await request.get(`${API_URL}/api/assets/quiz?course_code=${code}&week=1`)
    const questions = (await list.json()) as { question: string; origin: string; correct_answer: string }[]
    expect(questions).toHaveLength(2)
    expect(questions.find((q) => q.question === 'Which is the biggest?')).toMatchObject({
      origin: 'user',
      correct_answer: 'B',
    })

    // wrong first: pick "Small"
    await page.reload()
    await reachQuestion(page, 'Which is the biggest?')
    await expect(page.getByText('Yours', { exact: true })).toBeVisible()
    await page.getByRole('radio', { name: /Small/ }).check()
    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(page.getByTestId('quiz-result')).toContainText('Incorrect.')

    // then correct: restart the run and pick "Large"
    await page.reload()
    await reachQuestion(page, 'Which is the biggest?')
    await page.getByRole('radio', { name: /Large/ }).check()
    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(page.getByTestId('quiz-result')).toContainText('Correct!')
  })

  test('the previous question is cleared after Next', async ({ page, request }) => {
    await request.post(`${API_URL}/api/assets/quiz`, {
      data: {
        course_code: code,
        week: 1,
        question_type: 'multiple_choice',
        question: 'Second?',
        options: ['A. x', 'B. y'],
        correct_answer: 'B',
      },
    })
    await page.goto(weekUrl(code, 1, 'quiz'))
    await expect(page.getByText(/Question 1 \/ 2/)).toBeVisible({ timeout: 10_000 })
    await page.getByRole('radio').first().check()
    await page.getByRole('button', { name: 'Submit' }).click()
    await page.getByRole('button', { name: 'Next', exact: true }).click()
    await expect(page.getByText('Second?', { exact: true })).toBeVisible()
    await expect(page.getByRole('radio')).toHaveCount(2)
    await expect(page.getByTestId('quiz-result')).toHaveCount(0)
  })

  test('a short-answer question can be added and shows its model answer', async ({ page }) => {
    const dialog = await openAdd(page)
    await dialog.getByRole('radio', { name: 'Short answer' }).click()
    await dialog.getByLabel('Question', { exact: true }).fill('Name the layer')
    await dialog.getByLabel('Model answer').fill('Transport')
    await dialog.getByRole('button', { name: 'Add question' }).click()
    await expect(dialog).toBeHidden()
    await page.reload()
    await reachQuestion(page, 'Name the layer').catch(() => undefined)
    // the short-answer view has a textbox rather than radios; reachQuestion stops
    // as soon as the question is on screen, so reaching it is the assertion.
    await expect(page.getByText('Name the layer', { exact: true })).toBeVisible()
    await page.getByPlaceholder('Type your answer...').fill('transport')
    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(page.getByText('Transport', { exact: true })).toBeVisible()
  })

  test('deleting a question asks first, and Escape deletes nothing', async ({ page, request }) => {
    await page.goto(weekUrl(code, 1, 'quiz'))
    await expect(page.getByText('Seed which letter is second?', { exact: true })).toBeVisible({ timeout: 10_000 })
    const dialog = page.getByRole('dialog', { name: 'Delete this question?' })
    await page.getByRole('button', { name: 'Delete', exact: true }).click()
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    let list = await request.get(`${API_URL}/api/assets/quiz?course_code=${code}&week=1`)
    expect(await list.json()).toHaveLength(1)

    await page.getByRole('button', { name: 'Delete', exact: true }).click()
    await dialog.getByRole('button', { name: 'Delete', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(page.getByText('No quiz questions yet')).toBeVisible()
    list = await request.get(`${API_URL}/api/assets/quiz?course_code=${code}&week=1`)
    expect(await list.json()).toHaveLength(0)
  })

  test('a week without a lecture says to upload one first', async ({ page }) => {
    await page.goto(weekUrl(code, 2, 'quiz'))
    await expect(page.getByText('No quiz questions yet')).toBeVisible({ timeout: 10_000 })
    await page.getByRole('button', { name: 'Add question', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Add question' })
    await dialog.getByRole('radio', { name: 'Short answer' }).click()
    await dialog.getByLabel('Question', { exact: true }).fill('Orphan question')
    await dialog.getByLabel('Model answer').fill('Orphan answer')
    await dialog.getByRole('button', { name: 'Add question' }).click()
    await expect(dialog.getByRole('alert')).toHaveText('Upload a lecture for this week first')
  })
})

test.describe('Study-item editors in Russian', () => {
  let code: string

  test.beforeEach(async ({ page }) => {
    code = newCode()
    seedStudyItems(code)
    await page.addInitScript(() => window.localStorage.setItem('studyaio-language', 'ru'))
  })

  test.afterEach(async ({ request }) => {
    await deleteCourse(request, code)
  })

  test('flashcard editor, validation, delete and the no-lecture error are translated', async ({ page }) => {
    await page.goto(weekUrl(code, 1, 'flashcards'))
    await page.getByRole('button', { name: 'Изменить', exact: true }).click()
    const editor = page.getByRole('dialog', { name: 'Изменить карточку' })
    await expect(editor).toBeVisible()
    await expect(editor.getByLabel('Лицевая сторона')).toBeVisible()
    await editor.getByLabel('Лицевая сторона').fill('')
    await editor.getByRole('button', { name: 'Сохранить изменения' }).click()
    await expect(editor.getByText('Обязательное поле')).toBeVisible()
    await editor.getByRole('button', { name: 'Отмена' }).click()

    await page.getByRole('button', { name: 'Удалить', exact: true }).click()
    const del = page.getByRole('dialog', { name: 'Удалить эту карточку?' })
    await expect(del).toBeVisible()
    await expect(del.getByRole('button', { name: 'Отмена' })).toBeFocused()
    await page.keyboard.press('Escape')

    await page.goto(weekUrl(code, 2, 'flashcards'))
    await page.getByRole('button', { name: 'Добавить карточку', exact: true }).click()
    const add = page.getByRole('dialog', { name: 'Добавить карточку' })
    await add.getByLabel('Лицевая сторона').fill('Х')
    await add.getByLabel('Назад').fill('Y')
    await add.getByRole('button', { name: 'Добавить карточку' }).click()
    await expect(add.getByRole('alert')).toHaveText('Сначала загрузите лекцию за эту неделю')
  })

  test('quiz editor is translated', async ({ page }) => {
    await page.goto(weekUrl(code, 1, 'quiz'))
    await page.getByRole('button', { name: 'Добавить вопрос', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Добавить вопрос' })
    await expect(dialog.getByRole('radio', { name: 'Выбор ответа' })).toBeVisible()
    await expect(dialog.getByRole('radio', { name: 'Краткий ответ' })).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Добавить вариант' })).toBeVisible()
    await dialog.getByRole('button', { name: 'Добавить вопрос' }).click()
    await expect(dialog.getByText('Обязательное поле')).toBeVisible()
    await expect(dialog.getByText('Укажите от 2 до 8 вариантов, без пустых')).toBeVisible()
    await dialog.getByRole('textbox', { name: 'Вариант 1', exact: true }).fill('A')
    await dialog.getByRole('textbox', { name: 'Вариант 2', exact: true }).fill('B')
    await dialog.getByRole('button', { name: 'Добавить вопрос' }).click()
    await expect(dialog.getByText('Отметьте правильный вариант')).toBeVisible()
  })
})

test.describe('Study-item dialogs at 375px', () => {
  test.use({ viewport: { width: 375, height: 667 } })

  let code: string

  test.beforeEach(() => {
    code = newCode()
    seedStudyItems(code)
  })

  test.afterEach(async ({ request }) => {
    await deleteCourse(request, code)
  })

  async function expectFits(page: Page, dialog: Locator) {
    const box = await dialog.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.x).toBeGreaterThanOrEqual(0)
    expect(box!.x + box!.width).toBeLessThanOrEqual(375)
    const m = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      inner: window.innerWidth,
    }))
    expect(m.scroll).toBeLessThanOrEqual(m.inner)
  }

  test('flashcard editor and delete dialogs do not overflow', async ({ page }) => {
    await page.goto(weekUrl(code, 1, 'flashcards'))
    await expect(cardFace(page)).toBeVisible({ timeout: 10_000 })
    await page.getByRole('button', { name: 'Edit', exact: true }).click()
    const editor = page.getByRole('dialog', { name: 'Edit flashcard' })
    await editor.getByLabel('Front').fill('word '.repeat(300))
    await expectFits(page, editor)
    await editor.getByRole('button', { name: 'Cancel' }).click()

    await page.getByRole('button', { name: 'Delete', exact: true }).click()
    const del = page.getByRole('dialog', { name: 'Delete this flashcard?' })
    await expectFits(page, del)
    for (const name of ['Cancel', 'Delete']) {
      const b = await del.getByRole('button', { name, exact: true }).boundingBox()
      expect(b!.height).toBeGreaterThanOrEqual(44)
    }
  })

  test('quiz editor with eight options stays inside the viewport', async ({ page }) => {
    await page.goto(weekUrl(code, 1, 'quiz'))
    await page.getByRole('button', { name: 'Add question', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Add question' })
    for (let i = 0; i < 6; i++) await dialog.getByRole('button', { name: 'Add option' }).click()
    await expect(dialog.getByRole('textbox', { name: 'Option 8', exact: true })).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Add option' })).toBeHidden() // capped at 8
    await expectFits(page, dialog)
    const box = await dialog.boundingBox()
    expect(box!.y + box!.height).toBeLessThanOrEqual(667) // scrolls inside itself
  })
})
