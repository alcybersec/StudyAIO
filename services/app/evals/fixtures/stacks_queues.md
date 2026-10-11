# CSIT101 — Week 3: Stacks and Queues

## Overview

Stacks and queues are two of the most fundamental *abstract data types* in computer science. They both store collections of elements, but they differ in one crucial way: the **order in which elements can be added and removed**. A stack follows **LIFO** (Last-In, First-Out), while a queue follows **FIFO** (First-In, First-Out).

Why does this matter? Because many real-world problems are naturally defined by their ordering constraints. When you match brackets in an expression, the most recently opened bracket must be closed first — that's a stack. When you process requests in the order they arrive, the earliest request must be served first — that's a queue. Choosing the right data structure means recognizing which ordering discipline the problem demands.

This week also introduces an important implementation concern: how these abstractions are actually built. Both can be implemented efficiently (O(1) operations) on a linked list, but a naive array-based queue has a serious performance problem that requires the **circular buffer** technique to fix. Understanding the gap between an abstraction and its implementation is a recurring theme in data structures.

## Key Concepts

### The Stack: Last-In, First-Out

#### What a Stack Is and Why It Works This Way

A stack is a collection where the **last element pushed is the first element removed** — hence Last-In, First-Out (LIFO). Think of a stack of plates in a cafeteria: you add plates to the top and take plates from the top. You never reach into the middle. This restriction is not a weakness — it is precisely what makes stacks useful, because many problems have exactly this "most recent first" structure.

#### Stack Operations

The stack exposes three core operations:

- **push** — adds an element to the top of the stack.
- **pop** — removes and returns the element from the top.
- **peek** — reads the top element *without* removing it.

Note the distinction between `pop` and `peek`: both give you access to the top, but `pop` mutates the stack while `peek` is a non-destructive read. Peeking is useful when you need to inspect before committing to a removal.

#### Classic Use Case: Matching Brackets in an Expression

The lecture gives the canonical stack application: **checking that brackets in an expression are properly matched**. The algorithm works because of the LIFO property:

1. Scan the expression left to right.
2. On each **opening bracket**, push it onto the stack.
3. On each **closing bracket**, pop the stack and compare — the popped opening bracket must match the closing one.
4. If the stack is empty at the end (and every comparison succeeded), the expression is balanced.

Why a stack? Because the *most recently opened* bracket is always the first one that must be closed — exactly the LIFO discipline. For example, in `{ [ ( ) ] }`, when we reach the first `)`, the top of the stack is `(`, and popping confirms the match. A queue would fail here entirely: the *first* opened bracket is not the one we need to close first.

### The Queue: First-In, First-Out

#### What a Queue Is and Why It Works This Way

A queue models a waiting line: the **first element to arrive is the first to be served** — First-In, First-Out (FIFO). Elements are added at the **back** and removed from the **front**. This preserves arrival order exactly, which is essential whenever fairness or chronological processing matters.

#### Queue Operations

- **enqueue** — adds an element at the back of the queue.
- **dequeue** — removes the element from the front of the queue.

The asymmetry (insert at one end, remove at the other) is what distinguishes a queue from a stack, where both operations happen at the same end (the top).

#### Classic Use Case: Processing Requests in Arrival Order

The lecture's motivating example is **processing requests in the order they arrive**. Imagine a server receiving requests: enqueue each incoming request, and dequeue one at a time to handle it. FIFO guarantees no request can be starved or served out of turn — the queue's structure *enforces* fairness by construction.

### Implementing Stacks and Queues

#### Linked List Implementation: O(1) Everywhere

The lecture states that **both stacks and queues can be built on a linked list with O(1) operations**. The trick is to maintain pointers to the right ends:

- For a **stack**, push and pop both operate at the head of the list — naturally O(1).
- For a **queue**, enqueue at the tail and dequeue at the head — both O(1) as long as you keep a tail pointer (dequeuing from the head alone avoids any traversal).

This makes the linked list a clean, uniformly efficient foundation for both abstractions.

#### The Array-Based Queue Problem: Why Circular Buffers Are Needed

A queue on a **plain array** runs into trouble. If you dequeue by removing the front element, every remaining element must shift forward by one — an O(n) operation per dequeue. Repeated dequeues become quadratic overall, defeating the purpose of a queue.

The fix is a **circular buffer**: treat the array as a ring by keeping front and back *indices* that wrap around to the start when they reach the end. Dequeueing then just advances the front index — no elements are moved, and operations return to O(1). This is a beautiful example of a clever implementation rescuing an otherwise inefficient design.

### Stack vs. Queue at a Glance

| Property | Stack | Queue |
|---|---|---|
| Ordering discipline | LIFO (Last-In, First-Out) | FIFO (First-In, First-Out) |
| Insert operation | push (to top) | enqueue (to back) |
| Remove operation | pop (from top) | dequeue (from front) |
| Read-only access | peek (top, non-destructive) | — |
| Linked list cost | O(1) all operations | O(1) all operations |
| Plain array cost | Efficient (one end) | Needs circular buffer to avoid O(n) shifts |
| Example use | Matching brackets in an expression | Processing requests in arrival order |

## Definitions

| Term | Definition |
|---|---|
| Stack | A LIFO data structure: elements are added and removed only at the top. |
| LIFO | Last-In, First-Out — the most recently added element is removed first. |
| push | Stack operation that adds an element to the top. |
| pop | Stack operation that removes the element from the top. |
| peek | Reads the top element of a stack without removing it. |
| Queue | A FIFO data structure: elements are added at the back and removed from the front. |
| FIFO | First-In, First-Out — the earliest added element is removed first. |
| enqueue | Queue operation that adds an element at the back. |
| dequeue | Queue operation that removes the element at the front. |
| Circular buffer | An array treated as a ring, with front/back indices that wrap around, so dequeue does not shift every element. |

## Diagrams & Visual Descriptions

**Stack (LIFO)** — the top is the only access point:

```
        pop <-- [ C ] <-- push      (top)
                [ B ]
                [ A ]               (bottom)
```
The last element pushed (C) is the first popped — like plates stacked on top of each other.

**Queue (FIFO)** — enter at the back, leave at the front:

```
  dequeue <-- [ A ][ B ][ C ] <-- enqueue
   (front)                       (back)
```
A arrives first, so A leaves first — like a waiting line.

**Circular buffer** — indices wrap around so dequeue never shifts elements:

```
     0   1   2   3   4
   [ D ][ E ][   ][ A ][ B ]        front = 3, back = 1
              ^         ^
              |         |
        front wraps     back wraps
        around          around
```
After dequeuing A and B, the front index advances to slot 3; new elements E, D fill slots 1, 0, wrapping past the end — no shifting required.

## Code Examples

No code examples in this lecture. However, the bracket-matching algorithm from the lecture can be sketched as pseudocode to illustrate the stack workflow:

```
for each character in expression:
    if character is an opening bracket:
        push(character)                # remember it for later
    else if character is a closing bracket:
        top = pop()                    # most recent opening bracket
        if top does not match character:
            return "unbalanced"
if stack is empty:
    return "balanced"                  # every opener was matched
```

*Relevance: this captures the lecture's stated stack use case — push on opening brackets, pop-and-compare on closing brackets.*

## Formulas & Algorithms

**Bracket-matching algorithm (stack):**
1. Push each opening bracket onto the stack.
2. On a closing bracket, pop and compare with the expected match.
3. Balanced iff all comparisons succeed and the stack ends empty.

**Circular buffer wrap-around (array-based queue):** the front/back indices advance circularly so dequeue does not shift every element; conceptually, index movement wraps back to the start of the array.

**Complexity:** linked-list stack and queue operations are all $O(1)$; a plain-array queue's dequeue costs $O(n)$ due to element shifting.

## Key Takeaways

- The choice between a stack and a queue comes down to which ordering discipline your problem needs: most-recent-first (LIFO) or arrival-order (FIFO).
- Stacks solve bracket matching because the *most recently opened* bracket must close first — a queue cannot express this.
- Queues enforce fairness naturally: processing requests via enqueue/dequeue guarantees arrival order.
- `peek` gives you the top of a stack without mutating it, unlike `pop`.
- Linked lists give both structures O(1) operations across the board — an ideal implementation.
- A plain array queue is a trap: naive dequeuing shifts every element (O(n)). The circular buffer restores O(1) — abstraction and implementation are separate concerns.

## Connections

The lecture notes that queues are used for "processing requests in arrival order" — a pattern that generalizes to any system where work must be handled in the order it was submitted; the lecture presents it as the motivating use case for FIFO. The lecture also highlights the circular buffer as the technique required to make an array-based queue efficient, framing implementation strategy (linked list vs. array) as an open design consideration alongside the abstract behavior of the structures.

---
*Sources: CSIT101 Week 3 lecture notes (Stacks and Queues). Version: 1.*
