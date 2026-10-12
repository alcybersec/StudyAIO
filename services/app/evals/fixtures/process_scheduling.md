# CSIT203 — Week 3: CPU Scheduling

## Overview

When several processes are ready to run but only one CPU is available, the operating system must decide which process runs next. That decision is made by the scheduler, and the policies it can follow — and their trade-offs — are the subject of this week [p.1]. Scheduling matters because the choice of policy directly shapes how fast programs finish, how long users wait, and whether any process is unfairly ignored.

To compare policies objectively, we use three metrics: turnaround time (completion minus arrival), waiting time (time spent ready but not running), and response time (arrival to first run) [p.1]. This week introduces three classic policies — first-come first-served, shortest job first, and round robin — and shows with a worked example how dramatically they differ in practice [p.1][p.2].

## Key Concepts

### Scheduling Metrics

Before evaluating any policy, we need a yardstick. Three metrics are defined [p.1]:

- **Turnaround time**: how long a process takes from arrival to completion — completion minus arrival [p.1].
- **Waiting time**: the total time a process spends ready but not actually running [p.1].
- **Response time**: how long from arrival until the process first gets to run [p.1].

These metrics can pull in different directions: a policy that improves average waiting time may hurt response time, which is why no single algorithm dominates [p.1][p.2].

### First-Come First-Served (FCFS)

FCFS is the simplest policy: processes run in arrival order, without preemption [p.1]. Its weakness is the **convoy effect**: a long job at the front of the queue makes everything behind it wait [p.1]. Think of a single slow truck on a one-lane road — every car behind it is stuck, no matter how quick their errands are.

### Shortest Job First (SJF)

SJF runs the process with the shortest next CPU burst, which minimises average waiting time [p.2]. However, it faces two problems. First, it needs the burst length in advance, which the system does not actually know [p.2]. Second, long jobs can **starve** — if short jobs keep arriving, a long job may never get to run [p.2].

### Round Robin (RR)

RR gives each process a fixed **time quantum**, then preempts it and moves it to the back of the queue [p.2]. This gives good response time [p.2]. The quantum size is a critical tuning decision:

| Quantum setting | Consequence [p.2] |
|---|---|
| Too large | RR behaves like FCFS |
| Too small | Context-switch overhead dominates |

### Comparing FCFS and SJF: A Worked Example

The lecture illustrates the difference with bursts of 24, 3, and 3 arriving together [p.3]. Under FCFS the order is P1, P2, P3, giving waiting times 0, 24, 27 — an average of 17 [p.3]. Under SJF the order is P2, P3, P1, giving waiting times 0, 3, 6 — an average of just 3 [p.3]. This shows SJF's optimality for waiting time vividly, while also illustrating FCFS's convoy effect: the two short jobs are stuck behind the 24-unit job [p.1][p.3].

## Definitions

| Term | Definition |
|---|---|
| Scheduler | Picks which ready process runs next [p.1] |
| Turnaround time | Completion minus arrival [p.1] |
| Waiting time | Time spent ready but not running [p.1] |
| Response time | Arrival to first run [p.1] |
| FCFS | Runs processes in arrival order, without preemption [p.1] |
| Convoy effect | A long job at the front makes everything behind it wait [p.1] |
| SJF | Runs the process with the shortest next CPU burst; minimises average waiting time [p.2] |
| Starvation | Long jobs can be indefinitely delayed under SJF [p.2] |
| Round robin | Fixed time quantum per process, then preempt and move to the back of the queue [p.2] |
| Time quantum | The fixed slice of CPU time each process receives in RR [p.2] |
| Context-switch overhead | Cost of switching processes; dominates if the quantum is too small [p.2] |

## Diagrams & Visual Descriptions

Timeline of the worked example (bursts 24, 3, 3) under both policies [p.3]:

```
FCFS (P1, P2, P3):      waiting:  0   24  27
|------P1 (24)------|--P2--|--P3--|

SJF  (P2, P3, P1):      waiting:  0    3    6
|--P2--|--P3--|------P1 (24)------|
```

Round robin's circular queue: each process runs for one quantum, then re-joins the back of the queue [p.2].

```
   ┌──────────────────────────────┐
   ▼                              │
[ Quantum runs ] → preempt → [ back of ready queue ]
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

Metrics definitions [p.1]:

```
turnaround time = completion - arrival
waiting time    = time spent ready but not running
response time   = arrival to first run
```

RR quantum behaviour [p.2]:

```
if quantum too large  -> RR behaves like FCFS
if quantum too small  -> context-switch overhead dominates
```

Worked example — bursts 24, 3, 3 arriving together [p.3]:

```
FCFS: order P1, P2, P3 -> waiting times 0, 24, 27 -> average 17
SJF:  order P2, P3, P1 -> waiting times 0, 3, 6   -> average 3
```

## Key Takeaways

- The scheduler's policy choice directly determines turnaround, waiting, and response times — always evaluate a policy against these metrics [p.1].
- FCFS is simple but suffers from the convoy effect: one long job delays everyone behind it [p.1].
- SJF minimises average waiting time (average 3 vs. FCFS's 17 in the example), but it is impractical because burst lengths are unknown in advance, and it risks starving long jobs [p.2][p.3].
- Round robin trades optimality for fairness and responsiveness via time quanta; the quantum size is the crucial tuning knob — too big and it degenerates into FCFS, too small and switching costs take over [p.2].

## Connections

The lecture frames SJF's central weakness — needing burst lengths the system does not know [p.2] — as an open problem, which motivates the practical question of how schedulers estimate or approximate such information. Within this week's material, the convoy effect under FCFS and the starvation risk under SJF show why round robin's preemptive quantum scheme exists as the responsiveness-oriented alternative [p.1][p.2].

This lecture does not link to other named weeks or external material beyond these internal comparisons.

---
*Sources: CSIT203 Week 3 lecture slides (pp. 1–3). Version: 1.*
