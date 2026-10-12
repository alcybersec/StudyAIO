# CSIT101 — Week 3: Stacks and Queues

## Overview

This week introduces two fundamental abstract data structures: the **stack** and the **queue**. Both are ways of holding items so that the order in which they come out is controlled in a specific, useful way — a stack lets out the most recently added item first, while a queue lets out the item that has been waiting longest [p.1][p.2]. These ordering disciplines matter because many real computational problems have exactly this shape: matching brackets in an expression pairs the *most recent* opening bracket with the next closing one (a stack problem), while processing requests in arrival order respects *waiting time* (a queue problem) [p.1][p.2].

The lecture also covers how these structures are implemented. Both can be built on a linked list with O(1) operations, but a queue on a plain array needs a circular buffer, otherwise dequeue would shift every element [p.2]. Understanding both the behaviour and the implementation cost is what makes these structures practical tools rather than just definitions.

## Key Concepts

### Stacks: Last-In, First-Out (LIFO)

A stack is a last-in first-out (LIFO) structure: the item added most recently is the first one removed [p.1]. Think of it as a pile of plates — you can only take the top plate off, and you always put new plates on top. The LIFO discipline is exactly what makes stacks useful whenever the *latest* item is the one you need to deal with next.

A stack supports three core operations, each acting on the top of the stack [p.1]:

- **push** adds an element to the top [p.1]
- **pop** removes the element from the top [p.1]
- **peek** reads the top element without removing it [p.1]

#### Worked use: matching brackets in an expression

The lecture gives a concrete application: checking that brackets in an expression are properly matched [p.1]. The algorithm works because a closing bracket must match the *most recently opened* unmatched bracket — precisely what a stack's LIFO order provides [p.1]:

1. Push each opening bracket onto the stack [p.1].
2. On a closing bracket, pop from the stack and compare [p.1].

If the popped opening bracket matches the closing bracket, the pair is correct; if the stack is empty or the brackets differ, the expression is malformed. The stack effectively remembers the "open" brackets in the order they were opened, so the newest one is always checked first.

### Queues: First-In, First-Out (FIFO)

A queue is a first-in first-out (FIFO) structure: items leave in the same order they arrived [p.2]. This is the discipline of any fair waiting line — whoever joined first is served first.

A queue supports two core operations at opposite ends of the structure [p.2]:

- **enqueue** adds an element at the back [p.2]
- **dequeue** removes an element from the front [p.2]

#### Worked use: processing requests in arrival order

The lecture's application is processing requests in the order they arrive [p.2]. Each incoming request is enqueued at the back, and the next request to be handled is dequeued from the front, guaranteeing that no request is served before an earlier one — the FIFO property is exactly what "arrival order" means.

### Implementations and Efficiency

#### Linked-list implementation

Both stacks and queues can be built on a linked list, and in that implementation every operation runs in O(1) time [p.2]. Because a linked list grows and shrinks one node at a time, neither push/pop nor enqueue/dequeue ever needs to touch more than a constant number of nodes.

#### Array implementation and the circular buffer

A queue built on a plain array has a problem: if dequeue simply removes the front element, the remaining elements must shift down, so a dequeue would shift every element [p.2]. The fix is a **circular buffer**: the front of the queue moves around the array rather than the data moving, so dequeue does not shift every element [p.2]. Conceptually, the array's two ends are "joined", and the queue wraps from the end of the array back to the beginning as items are enqueued and dequeued.

## Definitions

| Term | Definition |
|---|---|
| Stack | A last-in first-out (LIFO) structure: push adds to the top, pop removes from the top [p.1] |
| LIFO | Last-in first-out ordering — the most recently added item is removed first [p.1] |
| push | Stack operation that adds an element to the top [p.1] |
| pop | Stack operation that removes the element from the top [p.1] |
| peek | Reads the top of the stack without removing it [p.1] |
| Queue | A first-in first-out (FIFO) structure: enqueue adds at the back, dequeue removes from the front [p.2] |
| FIFO | First-in first-out ordering — items leave in arrival order [p.2] |
| enqueue | Queue operation that adds an element at the back [p.2] |
| dequeue | Queue operation that removes an element from the front [p.2] |
| Circular buffer | Array layout for a queue so that dequeue does not shift every element [p.2] |

## Diagrams & Visual Descriptions

Stack discipline (all action at the top) [p.1]:

```
        push →  [ C ]  ← top (pop / peek here)
                [ B ]
                [ A ]  ← bottom
```

Queue discipline (in at the back, out at the front) [p.2]:

```
  front                             back
    ↓                                 ↓
  [ A ] [ B ] [ C ] [ D ]   ←─ enqueue here
    ↑
  dequeue here
```

Circular buffer: the queue wraps around the array so dequeue moves the front pointer instead of shifting every element [p.2]:

```
  indices:   0     1     2     3     4     5
           [ D ] [ . ] [ . ] [ B ] [ C ] [ D' ]
                   ↑front→ dequeued space reused ←back wraps around
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

```
Linked-list implementation: both stack and queue operations are O(1) [p.2]
```

Bracket-matching algorithm [p.1]:
```
Push each opening bracket
On a closing bracket: pop and compare
```

Queue on a plain array [p.2]:
```
Without a circular buffer: dequeue shifts every element
With a circular buffer: dequeue does not shift every element
```

## Key Takeaways

- The only difference between a stack and a queue is the removal rule — LIFO versus FIFO — and that rule alone determines which problems each fits [p.1][p.2].
- Use a stack when the newest item must be handled first, as in bracket matching, where each closing bracket must pair with the most recent opening bracket [p.1].
- Use a queue when arrival order must be preserved, as in request processing [p.2].
- Linked lists give O(1) operations for both structures, making them the natural default implementation [p.2].
- A queue on a plain array is not automatically efficient: without a circular buffer, dequeue shifts every element — the data-structure choice affects the cost of operations, not just correctness [p.2].

## Connections

Within this lecture, the stack and queue are presented as two implementations of the same idea — a linear collection with a controlled access order — and the lecture connects them at the implementation level: both can be built on a linked list with O(1) operations, and the queue additionally motivates the circular-buffer technique when built on an array [p.2].

This lecture does not link to other named weeks or topics beyond the implementation techniques it discusses itself.

---
*Sources: CSIT101 Week 3 lecture slides (pages 1–2). Version: 1.*
