# CSIT203 — Week 7: Deadlock

## Overview

Modern operating systems run many processes concurrently, and those processes must share limited resources — memory, files, printers, locks. This sharing creates the possibility of **deadlock**: a situation in which a set of processes is blocked forever because each process is waiting for a resource that another process in the set holds. No process can proceed, no process releases anything, and the system grinds to a halt for everyone involved.

Deadlock matters because it is not a crash you can recover from easily — the processes involved simply stop making progress. Understanding deadlock requires knowing exactly which conditions allow it to arise (there are four, and all must hold simultaneously), and that insight immediately suggests a strategy: if you can prevent even one of those conditions from ever occurring, deadlock becomes impossible. This week introduces both the theory of deadlock and its core prevention technique.

## Key Concepts

### What Is Deadlock?

A set of processes is **deadlocked** when each process in the set is waiting for a resource that is held by another process in the same set. The critical word is *set*: deadlock is a property of a group, not an individual process. A single process waiting for a busy printer is just blocked — it will proceed once the printer frees up. Deadlock occurs only when the waiting is mutual and circular, so no amount of patience resolves it.

Think of two people, each holding a document the other needs to read before continuing. Each politely waits for the other to finish first. Neither will ever proceed — that is the essence of deadlock in a resource-sharing system.

### The Four Necessary Conditions

For deadlock to occur, **four conditions must hold simultaneously**. This is the central theoretical result of the lecture: remove any one condition and deadlock cannot happen.

#### 1. Mutual Exclusion

A resource can be held by only one process at a time. This condition exists because some resources are inherently non-shareable — a printer cannot print two jobs at once, and a lock protects data from concurrent modification. Mutual exclusion is usually a requirement of correctness, not a design flaw, which is why it is rarely the condition we choose to break.

#### 2. Hold and Wait

A process holds at least one resource while simultaneously waiting for another. This is the "greed" condition: a process that grabbed one resource and now wants a second that someone else has. If processes either requested all their resources at once or held nothing while waiting, this condition could not arise.

#### 3. No Preemption

Resources cannot be forcibly taken away from the process holding them. The OS does not snatch a file lock from a running process; the holder must release it voluntarily. Without preemption, a stuck process cannot be relieved of its resources to unblock others.

#### 4. Circular Wait

There is a cycle of processes: P₁ waits for a resource held by P₂, P₂ waits for one held by P₃, ..., and the last waits for a resource held by P₁. This is the condition that ties everything together — the actual "circle" of mutual waiting. The classic two-process case: P₁ holds A and wants B; P₂ holds B and wants A.

#### Why All Four Must Hold Together

Each condition is necessary; jointly they are sufficient. This gives deadlock prevention a clean logical shape:

| Condition | Meaning | Can we break it? |
|---|---|---|
| Mutual exclusion | Resource usable by one process at a time | Hard — often required for correctness |
| Hold and wait | Holding one resource while waiting for another | Possible — request all resources upfront |
| No preemption | Resources can't be forcibly taken | Possible in some cases, disruptive |
| Circular wait | A cycle of waiting processes | **Practical and common** |

### Breaking a Condition: Deadlock Prevention

Since all four conditions are required, imposing any one less is enough to prevent deadlock. Among these, the lecture highlights the most practical technique:

#### Resource Ordering (Breaking Circular Wait)

Impose a **global order** on all resources, and require every process to acquire resources in that order. If resources are numbered 1, 2, 3, ..., a process needing both resources 3 and 7 must take 3 before 7. With this discipline, the circular-wait chain cannot form: in any cycle, resource numbers would have to strictly increase around the loop and return to the start, which is impossible.

For the two-process example: if both P₁ and P₂ must acquire A before B (because A precedes B in the global order), then either P₁ gets both first and P₂ waits (but only until P₁ finishes), or vice versa. One of them always makes progress — no deadlock.

Resource ordering is the technique of choice in practice because it is simple to enforce, has low runtime cost, and only requires programmers to agree on a consistent acquisition order.

## Definitions

| Term | Definition |
|---|---|
| Deadlock | A situation where a set of processes is blocked because each process is waiting for a resource held by another process in the set |
| Mutual exclusion | The condition that a resource can be held by only one process at a time |
| Hold and wait | The condition that a process holds at least one resource while waiting to acquire another |
| No preemption | The condition that resources cannot be forcibly taken from the process holding them |
| Circular wait | The condition that a cycle of processes exists, each waiting for a resource held by the next |
| Deadlock prevention | Guaranteeing deadlock cannot occur by ensuring at least one of the four conditions never holds |
| Resource ordering | A prevention technique that imposes a global order on resources and requires acquisition in that order, breaking circular wait |

## Diagrams & Visual Descriptions

**Circular wait (the deadlock condition):**

```
        ┌──────────┐   wants B    ┌──────────┐
        │    P₁    │ ───────────► │    P₂    │
        │ holds A  │              │ holds B  │
        └──────────┘ ◄─────────── └──────────┘
                          wants A

        P₁ holds A, waits for B.
        P₂ holds B, waits for A.
        Neither can proceed → deadlock.
```

**Breaking the cycle with resource ordering (acquire in global order A → B):**

```
        P₁ acquires A, then B      P₂ tries A, is blocked
        ┌──────────┐               ┌──────────┐
        │    P₁    │               │    P₂    │
        │ A → B ✓  │               │ waits    │
        └──────────┘               └──────────┘
        P₁ finishes, releases both; P₂ proceeds.
        No cycle → no deadlock.
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

The deadlock condition can be stated logically:

$$\text{Deadlock} \Rightarrow (\text{mutual exclusion} \wedge \text{hold and wait} \wedge \text{no preemption} \wedge \text{circular wait})$$

Equivalently, deadlock requires all four conditions:

$$\text{Deadlock} \iff \bigcap_{i=1}^{4} C_i \neq \emptyset$$

**Prevention algorithm (resource ordering):**
1. Assign each resource type a unique number in a global order.
2. A process may request a resource only if its number is greater than all numbers of resources it currently holds.
3. Circular wait becomes impossible: resource numbers would need to strictly increase around any wait cycle, which cannot return to the starting process.

## Key Takeaways

- Deadlock is a property of a *set* of processes: each waits for a resource held by another in the same set, so no one can ever proceed.
- Four conditions — mutual exclusion, hold and wait, no preemption, and circular wait — must **all** hold together for deadlock; this is the foundation for all prevention strategies.
- Breaking any single condition makes deadlock impossible; you don't need to attack all four.
- The most practical condition to break is circular wait, via a **global resource ordering** with acquisition in that order.
- Resource ordering works because a strictly increasing sequence cannot loop back on itself — a cycle of waiting processes can never form.
- Mutual exclusion is usually the hardest condition to remove, since single-exclusivity is often required for correctness.

## Connections

This lecture's topic sits naturally at the intersection of processes and resource management — the same resource-allocation activity that earlier material on processes and scheduling addresses. Here the concern shifts from *efficiency* of resource use to *liveness*: whether progress is possible at all.

The lecture's prevention strategy (resource ordering) relies on the notion of processes acquiring resources in a disciplined way, which connects to how concurrent processes coordinate their access to shared data; the locks processes wait on are exactly the resources at the heart of this week's deadlock conditions.

---
*Sources: CSIT203 Week 7 lecture content (Deadlock). Version: 1.*
