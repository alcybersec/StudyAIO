import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WriteQueue, type QueueStorage, type QueuedWrite } from './writeQueue'

function createMemoryStorage(): QueueStorage & { rows: QueuedWrite[] } {
  let nextId = 1
  const rows: QueuedWrite[] = []
  return {
    rows,
    async add(item) {
      const id = nextId++
      rows.push({ ...item, id })
      return id
    },
    async getAll() {
      return [...rows].sort((a, b) => (a.id ?? 0) - (b.id ?? 0))
    },
    async delete(id) {
      const idx = rows.findIndex((r) => r.id === id)
      if (idx >= 0) rows.splice(idx, 1)
    },
    async count() {
      return rows.length
    },
  }
}

function okResponse() {
  return new Response('{}', { status: 200 })
}

function statusResponse(status: number) {
  return new Response('{}', { status })
}

const write = (n: number) => ({
  url: `/api/study/review`,
  method: 'POST',
  body: JSON.stringify({ n }),
})

describe('WriteQueue', () => {
  let storage: ReturnType<typeof createMemoryStorage>
  let fetchMock: ReturnType<typeof vi.fn>
  let queue: WriteQueue

  beforeEach(() => {
    vi.useFakeTimers()
    storage = createMemoryStorage()
    fetchMock = vi.fn()
    queue = new WriteQueue(storage, { fetchFn: fetchMock as typeof fetch, autoFlush: false })
  })

  afterEach(() => {
    queue.stop()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('enqueue persists the write and updates reactive size', async () => {
    const listener = vi.fn()
    queue.subscribe(listener)
    await queue.enqueue(write(1))
    expect(storage.rows).toHaveLength(1)
    expect(queue.size()).toBe(1)
    expect(listener).toHaveBeenCalled()
  })

  it('flush replays writes FIFO and removes them on 2xx', async () => {
    await queue.enqueue(write(1))
    await queue.enqueue(write(2))
    fetchMock.mockResolvedValue(okResponse())

    await queue.flush()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    const bodies = fetchMock.mock.calls.map((c) => (c[1] as RequestInit).body)
    expect(bodies).toEqual([JSON.stringify({ n: 1 }), JSON.stringify({ n: 2 })])
    expect(queue.size()).toBe(0)
    expect(storage.rows).toHaveLength(0)
  })

  it('keeps writes on 5xx and stops the flush pass', async () => {
    await queue.enqueue(write(1))
    await queue.enqueue(write(2))
    fetchMock.mockResolvedValue(statusResponse(503))

    await queue.flush()

    // First write failed with 5xx — second is not attempted this pass
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(queue.size()).toBe(2)
  })

  it('keeps writes on network failure', async () => {
    await queue.enqueue(write(1))
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    await queue.flush()

    expect(queue.size()).toBe(1)
    expect(storage.rows).toHaveLength(1)
  })

  it('drops writes on 4xx with a console warning', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    await queue.enqueue(write(1))
    await queue.enqueue(write(2))
    fetchMock.mockResolvedValueOnce(statusResponse(400)).mockResolvedValueOnce(okResponse())

    await queue.flush()

    expect(warn).toHaveBeenCalled()
    expect(queue.size()).toBe(0)
    // The 4xx write was dropped, the next one still replayed
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('backs off exponentially from 1s and caps at 60s', async () => {
    await queue.enqueue(write(1))
    fetchMock.mockResolvedValue(statusResponse(500))

    await queue.flush()
    expect(queue.getBackoffMs()).toBe(1_000)
    await queue.flush()
    expect(queue.getBackoffMs()).toBe(2_000)
    for (let i = 0; i < 10; i++) await queue.flush()
    expect(queue.getBackoffMs()).toBe(60_000)
  })

  it('resets backoff after a successful drain', async () => {
    await queue.enqueue(write(1))
    fetchMock.mockResolvedValueOnce(statusResponse(500)).mockResolvedValue(okResponse())

    await queue.flush()
    expect(queue.getBackoffMs()).toBe(1_000)
    await queue.flush()
    expect(queue.getBackoffMs()).toBe(0)
    expect(queue.size()).toBe(0)
  })

  it('schedules a retry flush after failure when autoFlush is on', async () => {
    const autoQueue = new WriteQueue(storage, {
      fetchFn: fetchMock as typeof fetch,
      autoFlush: true,
    })
    fetchMock.mockResolvedValue(statusResponse(500))
    await autoQueue.enqueue(write(1))
    await autoQueue.flush()
    expect(autoQueue.size()).toBe(1)

    fetchMock.mockResolvedValue(okResponse())
    await vi.advanceTimersByTimeAsync(1_000)
    expect(autoQueue.size()).toBe(0)
    autoQueue.stop()
  })

  it('initializes size from previously persisted writes', async () => {
    await storage.add({ ...write(9), timestamp: Date.now() })
    const restored = new WriteQueue(storage, {
      fetchFn: fetchMock as typeof fetch,
      autoFlush: false,
    })
    await restored.ready()
    expect(restored.size()).toBe(1)
    restored.stop()
  })

  it('notifies subscribers as the queue drains', async () => {
    const sizes: number[] = []
    queue.subscribe(() => sizes.push(queue.size()))
    fetchMock.mockResolvedValue(okResponse())

    await queue.enqueue(write(1))
    await queue.flush()

    expect(sizes[0]).toBe(1)
    expect(sizes[sizes.length - 1]).toBe(0)
  })
})
