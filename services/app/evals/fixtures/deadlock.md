# CSIT203 — Week 7: Deadlock

## Overview

Deadlock is a situation in which a set of processes is stuck: each process in the set is waiting for a resource that is held by another process in the same set, so none of them can ever make progress [p.1]. Nothing external interrupts them, and nothing they do on their own can break the cycle — the wait is mutual and permanent [p.1].

This matters because modern systems run many processes concurrently, all competing for limited resources such as devices, files or locks. If the operating system does not manage resource allocation carefully, deadlock can freeze part of a system indefinitely. Understanding what makes deadlock possible — and what makes it impossible — is therefore a core part of studying operating systems, and the key insight of this lecture is elegant: four specific conditions must *all* hold simultaneously for deadlock to exist, so breaking even one of them prevents deadlock entirely [p.1].

## Key Concepts

### What Deadlock Is

A set of processes is deadlocked when each process in the set is waiting for a resource that is held by another process in the set [p.1]. The word "set" is important: it is not enough for one process to be blocked waiting for something. The blocking must form a closed loop among the processes themselves, so that nobody in the group can proceed and release what the others need.

Think of four cars at an intersection, each having entered before the one to its left could clear the way: each car is waiting for the road space held by another car, and no car can move. Translated to processes, each one is stopped, holding a resource somebody else wants, while wanting a resource somebody else holds.

### The Four Conditions for Deadlock

All four of the following conditions must hold together for deadlock to occur [p.1]. They are worth learning as a set, because the practical strategies against deadlock are exactly strategies for defeating one of them.

#### Mutual Exclusion

A resource is held by one process at a time [p.1]. If several processes could share a resource simultaneously, nobody would ever need to wait for it, and this link in the deadlock chain would disappear. Resources that genuinely cannot be shared force processes to queue for exclusive access.

#### Hold and Wait

A process holds one resource while waiting for another [p.1]. This is what makes waits dangerous: a blocked process is not idle and empty-handed — it is gripping resources that other processes may need, while itself unable to continue.

#### No Preemption

Resources cannot be taken away from a process [p.1]. The system cannot forcibly snatch a resource from a process that holds it; the process must release it voluntarily. This means a waiting process cannot be "unlocked" by the operating system reallocating its resources to whoever they are waiting for.

#### Circular Wait

There is a cycle of processes, each waiting on the next [p.1]. This is the structural heart of deadlock: P1 waits for P2, P2 waits for P3, and so on until the last process waits for P1 again. The waiting forms a closed loop with no entry or exit point.

### Preventing Deadlock by Breaking a Condition

Because the four conditions must hold *together*, deadlock cannot occur if any single one of them is broken [p.1]. This turns deadlock prevention into a design question: which condition is easiest and safest to eliminate in a given system?

The lecture highlights one classic technique: imposing a global order on resources and acquiring them in that order breaks circular wait [p.1]. If every process must request resources in the same fixed sequence (say, always request resource A before resource B), then a cycle of waiting processes cannot form — the ordering makes a "wait-for" loop impossible to construct. Each process still holds and waits, and resources are still exclusive and non-preemptible, but the circular structure, the last ingredient, can never arise.

In practice, this is like a building where everyone agrees to always lock corridor doors in numbered order: two people can each hold one door only if both follow the same rule, and the mutual "you first" standoff never happens.

## Definitions

| Term | Definition |
|---|---|
| Deadlock | A situation where a set of processes is deadlocked when each waits for a resource held by another in the set [p.1] |
| Mutual exclusion | A resource is held by one process at a time [p.1] |
| Hold and wait | A process holds one resource while waiting for another [p.1] |
| No preemption | Resources cannot be taken away [p.1] |
| Circular wait | A cycle of processes each waiting on the next [p.1] |
| Deadlock prevention | Breaking any one of the four conditions so deadlock cannot occur [p.1] |
| Resource ordering | Imposing a global order on resources and acquiring them in that order, which breaks circular wait [p.1] |

## Diagrams & Visual Descriptions

The circular wait condition can be drawn as a cycle of processes, each holding a resource the next one wants [p.1]:

```
        holds R1        holds R2
   P1 ─────────────► R1        R2 ◄───────────── P2
    ▲                                            │
    │                                            │ waits for R1
    │ waits for R2                               │
   P4 ◄───────────── R4        R3 ◄───────────── P3
        holds R4        holds R3
        (P4 holds R4, waits for R3's holder's chain back to P1)
```

Each arrow of "waits for" points to a resource held by the next process; following the arrows always returns to the starting process, which is exactly the cycle that defines deadlock [p.1].

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

No formulas in this lecture. The quantitative/logical content of the week is the set of four conditions and the prevention rule:

```
Deadlock occurs only if ALL hold simultaneously:
  1. Mutual exclusion   — a resource is held by one process at a time
  2. Hold and wait      — a process holds one resource while waiting for another
  3. No preemption      — resources cannot be taken away
  4. Circular wait      — a cycle of processes each waiting on the next

Prevention rule: break ANY ONE condition and deadlock cannot occur.
Technique: impose a global order on resources and acquire them in that
order — this breaks circular wait.
```
[p.1]

## Key Takeaways

- Deadlock is a group property, not an individual one: it requires a whole set of processes each waiting on another in the set [p.1].
- Four conditions — mutual exclusion, hold and wait, no preemption, and circular wait — must all hold together for deadlock to exist [p.1].
- Because the conditions are jointly required, breaking any single one prevents deadlock entirely — this is the foundation of deadlock prevention [p.1].
- The most concrete prevention technique from the lecture is resource ordering: define a global order on resources and always acquire them in that order, which makes circular wait impossible [p.1].

## Connections

This lecture is part of the study of processes and resources in operating systems: deadlock arises precisely because concurrent processes compete for resources that can be held by only one process at a time [p.1]. The lecture itself does not name any other week or upcoming topic, and no other weeks were available to compare against.

---
*Sources: Week 7 lecture slides on Deadlock (pages 1). Version: 1.*
