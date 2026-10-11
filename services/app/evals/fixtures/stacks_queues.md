# CSIT101 — Week 3: Stacks and Queues

## Overview

Stacks and queues are the two simplest ordered containers, distinguished only by which end removal happens at.

## Key Concepts

### Stack

A stack is last-in first-out (LIFO): push adds to the top, pop removes from the top and peek reads the top without removing it. For matching brackets, push each opening bracket and on a closing bracket pop and compare.

### Queue

A queue is first-in first-out (FIFO): enqueue adds at the back and dequeue removes from the front, as when processing requests in arrival order.

### Implementation

Both can be built on a linked list with O(1) operations. A queue on a plain array needs a circular buffer so dequeue does not shift every element.

## Definitions

| Term | Definition |
|---|---|
| Stack | LIFO container: push, pop, peek |
| Queue | FIFO container: enqueue, dequeue |
| Circular buffer | Array reused cyclically so dequeue does not shift elements |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

No formulas in this lecture.

## Key Takeaways

- Stack = LIFO, queue = FIFO.
- Bracket matching is the stack example.
- Array queues need a circular buffer.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: stacks_queues.pdf. Version: 1.*
