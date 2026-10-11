# CSIT203 — Week 3: CPU Scheduling

## Overview

The scheduler chooses the next ready process, and each policy trades turnaround, waiting and response time differently.

## Key Concepts

### Metrics

Turnaround time is completion minus arrival; waiting time is time spent ready but not running; response time is arrival to first run.

### Policies

| Policy | Preemptive | Strength | Weakness |
|---|---|---|---|
| FCFS | No | Simple, arrival order | Convoy effect: a long job at the front makes everything wait |
| SJF | Not stated | Minimises average waiting time | Burst length unknown in advance; long jobs can starve |
| Round robin | Yes | Good response time | Quantum too large acts like FCFS; too small and context-switch overhead dominates |

Shortest job first (SJF) runs the process with the shortest next CPU burst. It needs the burst length in advance, which the system does not know, and long jobs can starve. Round robin preempts each process after a fixed time quantum and moves it to the back of the queue.

### Worked example

Bursts 24, 3, 3 arriving together: FCFS (P1, P2, P3) gives waiting times 0, 24, 27, average 17; SJF (P2, P3, P1) gives 0, 3, 6, average 3.

## Definitions

| Term | Definition |
|---|---|
| Turnaround time | Completion minus arrival |
| Waiting time | Time ready but not running |
| Response time | Arrival to first run |
| Time quantum | Fixed slice a process runs before preemption in round robin |
| Convoy effect | Short jobs stuck behind one long job |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

FCFS example waiting times 0, 24, 27, average 17; SJF 0, 3, 6, average 3.

## Key Takeaways

- SJF is optimal for waiting time but needs the future.
- Round robin needs a well-chosen quantum.
- FCFS is simple but suffers the convoy effect.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: process_scheduling.pdf. Version: 1.*
