# CSIT203 — Week 7: Deadlock

## Overview

Deadlock is a state where processes wait on each other forever. The lecture gives the four conditions that must all hold and one practical way to break them.

## Key Concepts

### Definition

A set of processes is deadlocked when each waits for a resource held by another in the set.

### The four conditions

All four must hold together: mutual exclusion (a resource is held by one process at a time), hold and wait (a process holds one resource while waiting for another), no preemption (resources cannot be taken away) and circular wait (a cycle of processes each waiting on the next).

### Prevention

Breaking any one condition means deadlock cannot occur. Imposing a global order on resources and acquiring them in that order breaks circular wait.

## Definitions

| Term | Definition |
|---|---|
| Deadlock | Each process in a set waits for a resource held by another |
| Hold and wait | Holding one resource while waiting for another |
| Circular wait | A cycle of processes each waiting on the next |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

No formulas in this lecture.

## Key Takeaways

- Deadlock needs all four conditions.
- Break one and it cannot happen.
- A global acquisition order removes circular wait.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: deadlock.pdf. Version: 1.*
