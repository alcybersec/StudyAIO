# CSIT203 — Week 3: CPU Scheduling

## Overview

When a modern computer runs, there are typically far more processes ready to execute than there are CPUs to run them. Something must decide which ready process gets the CPU next — that decision-maker is the **scheduler**. CPU scheduling is one of the central responsibilities of an operating system because the choice has a direct, measurable effect on how fast programs finish and how responsive the system feels to users. A bad scheduling decision doesn't just slow one program; it can delay every process waiting behind it.

This week introduces the core vocabulary for evaluating schedules — turnaround time, waiting time, and response time — and then examines three classic scheduling policies: First-Come First-Served (FCFS), Shortest Job First (SJF), and Round Robin (RR). Each policy makes a different trade-off between fairness, efficiency, and responsiveness, and each has well-known failure modes: the convoy effect under FCFS, starvation and impractical knowledge requirements under SJF, and the quantum-size dilemma under Round Robin.

## Key Concepts

### Why We Measure: Scheduling Metrics

Before comparing schedulers, we need objective ways to say one is "better." The lecture defines three metrics:

- **Turnaround time** — the total time from a process's arrival to its completion. This captures how long a user waits for their job to finish overall.
- **Waiting time** — the time a process spends in the ready queue, ready to run but not actually running. This isolates the cost imposed purely by scheduling, since time spent waiting isn't doing useful work for that process.
- **Response time** — the time from arrival until the process first runs. This matters most for interactive systems: a user cares that the system *starts responding* quickly, even if the whole task takes a while.

Notice these metrics can pull in different directions. A policy might keep average waiting time low while letting some individual process sit waiting a very long time — which is exactly what happens with SJF.

### First-Come First-Served (FCFS)

FCFS is the simplest possible policy: processes run in the order they arrive, and once a process gets the CPU it keeps it until it finishes (there is **no preemption**). It's fair in an intuitive queue-at-the-bakery sense, and it's trivially easy to implement.

Its weakness is the **convoy effect**: a single long job at the front of the queue forces every short job behind it to wait for the entire duration of that long job. The name comes from the image of cars stuck behind a slow truck — no matter how fast the small cars could go, they move at the truck's pace.

#### Worked Example

The lecture gives a concrete case. Three processes arrive together with CPU bursts of **24, 3, and 3** (P1 = 24, P2 = 3, P3 = 3). Under FCFS they run in arrival order P1, P2, P3:

| Process | Burst | Waiting time |
|---------|-------|--------------|
| P1 | 24 | 0 |
| P2 | 3 | 24 |
| P3 | 3 | 27 |

Average waiting time = (0 + 24 + 27) / 3 = **17**. The two tiny jobs are punished simply for arriving after one big job — a textbook convoy effect.

### Shortest Job First (SJF)

SJF takes the opposite approach: among all ready processes, run the one with the shortest next CPU burst. Reordering the same example as P2, P3, P1:

| Process | Burst | Waiting time |
|---------|-------|--------------|
| P2 | 3 | 0 |
| P3 | 3 | 3 |
| P1 | 24 | 6 |

Average waiting time = (0 + 3 + 6) / 3 = **3**, versus 17 under FCFS — a dramatic improvement. In fact, SJF **minimises average waiting time**: by getting short jobs out of the way first, it minimises the number of processes that any single job delays.

However, SJF has two serious problems:

1. **It requires knowledge of the future.** The scheduler must know each process's next burst length in advance, but the system genuinely does not know this — a process itself doesn't usually know how long it will run.
2. **Starvation.** A steady stream of short jobs can keep postponing a long job indefinitely, so the long job may never run at all.

### Round Robin (RR)

Round Robin addresses FCFS's unresponsiveness by adding **preemption with a time quantum**: each process runs for at most one fixed quantum, then is preempted and moved to the back of the ready queue, and the next process runs. No process can monopolise the CPU, so every process gets the CPU quickly — which is why RR delivers **good response time**, making it well suited to interactive use.

RR's behaviour hinges critically on the **quantum size**:

- **Quantum too large** → each process effectively runs to completion within its quantum, and RR degenerates into behaving just like FCFS, convoy effect and all.
- **Quantum too small** → processes are switched so frequently that **context-switch overhead dominates**; the CPU spends more time switching between processes than doing their actual work.

Choosing the quantum is therefore a genuine engineering trade-off, balancing responsiveness against switching cost.

### Comparing the Policies

| Policy | Preemption | Strength | Weakness |
|--------|-----------|----------|----------|
| FCFS | No | Simple, fair ordering | Convoy effect; poor average waiting time |
| SJF | — | Minimises average waiting time | Needs burst lengths in advance; long jobs can starve |
| Round Robin | Yes, per quantum | Good response time | Quantum choice is tricky: too large ≈ FCFS, too small = context-switch overhead |

## Definitions

| Term | Definition |
|------|------------|
| Scheduler | The operating system component that picks which ready process runs next on the CPU. |
| Turnaround time | Completion time minus arrival time — total time a process takes from arrival to finishing. |
| Waiting time | Time a process spends ready but not running (in the ready queue). |
| Response time | Time from a process's arrival until it first runs. |
| FCFS | First-Come First-Served: runs processes in arrival order, without preemption. |
| Convoy effect | The delay inflicted on all short jobs queued behind one long job (as in FCFS). |
| SJF | Shortest Job First: runs the ready process with the shortest next CPU burst; minimises average waiting time but requires burst lengths in advance and can starve long jobs. |
| Starvation | The situation where a process is repeatedly passed over and never gets to run (e.g., long jobs under SJF). |
| Round Robin | Scheduling with a fixed time quantum per process, after which the process is preempted and moved to the back of the queue. |
| Time quantum | The fixed slice of CPU time given to each process in Round Robin. |
| Preemption | Forcibly taking the CPU away from a running process (e.g., at quantum expiry). |
| Context switch | The overhead of switching the CPU from one process to another. |

## Diagrams & Visual Descriptions

**FCFS convoy effect vs SJF, for bursts 24, 3, 3 (P1, P2, P3 arriving together):**

```
FCFS (P1, P2, P3):  waiting = 0, 24, 27  → avg 17
|–––––––P1: 24–––––––|–P2–|–P3–|
0                    24   27   30

SJF (P2, P3, P1):   waiting = 0, 3, 6   → avg 3
|–P2–|–P3–|–––––––P1: 24–––––––|
0    3    6                   30
```

The two Gantt-style timelines show the same three jobs scheduled differently: under FCFS the short jobs wait behind the long one (convoy effect), while SJF clears the short jobs first and the long job absorbs all the delay.

**Round Robin (quantum = 4, illustrative):**

```
Ready queue:  P1 → P2 → P3 → (back to P1 ...)
CPU:  |P1(4)|P2(4)|P3(4)|P1(4)|...
      quantum expires → preempt → move to back of queue
```

No diagrams in the extracted lecture images.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

**Metric formulas** (as defined in the lecture):

- Turnaround time $= \text{completion time} - \text{arrival time}$
- Waiting time = time spent in ready state (not running)
- Response time $= \text{time of first run} - \text{arrival time}$

**Average waiting time** (from the worked example):

```
FCFS: (0 + 24 + 27) / 3 = 17
SJF:  (0 + 3 + 6)  / 3 = 3
```

**Algorithms:**
- FCFS: run processes in arrival order, no preemption.
- SJF: among ready processes, always pick the one with the shortest next CPU burst.
- RR: run each process for one time quantum; on expiry, preempt and place it at the back of the ready queue.

## Key Takeaways

- The scheduler's choices are measured by turnaround time, waiting time, and response time — different policies optimise for different metrics, so "best" depends on your goal.
- FCFS is simple but suffers the convoy effect: one long job makes everything behind it wait, badly inflating average waiting time (17 vs 3 in the lecture's example).
- SJF provably minimises average waiting time, but it's impractical because burst lengths aren't known in advance, and it can starve long jobs.
- Round Robin trades some efficiency for responsiveness by preempting each process after a fixed quantum.
- The quantum size is the whole game in RR: too large and it degenerates into FCFS; too small and context-switch overhead dominates.

## Connections

The lecture's framing of scheduling as choosing among ready processes presupposes the process model the operating system maintains — the ready queue and the act of context-switching between processes are the machinery this week's policies operate on. The convoy and starvation problems also hint that scheduling decisions interact with broader OS resource-management questions about fairness and preventing indefinite delay.

Within this lecture itself, the observation that SJF "needs the burst length in advance, which the system does not know" leaves an obvious open problem — how can a practical scheduler approximate SJF without future knowledge — which the course may address later.

---
*Sources: CSIT203 Week 3 lecture notes (CPU Scheduling). Version: 1.*
