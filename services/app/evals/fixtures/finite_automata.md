# CSIT205 — Week 2: Finite Automata

## Overview

A DFA is a formal machine with one transition per state and symbol. The lecture defines it as a 5-tuple and works one example, a parity checker.

## Key Concepts

### Formal definition

A DFA is a 5-tuple (Q, Σ, δ, q0, F): a finite set of states Q, an input alphabet Σ, a transition function δ: Q × Σ → Q, a start state q0 and a set of accepting states F. From each state there is exactly one transition per symbol.

### Example: parity of 1s

Over Σ = {0, 1} with states q0 (start) and q1 (accepting), reading 1 toggles the state and reading 0 keeps it. The machine accepts strings with an odd number of 1s. On 0110 it ends in q0 (two 1s) and rejects; on 0111 it ends in q1 and accepts.

### Languages

The language of a DFA is the set of strings it accepts. A language is regular if some DFA accepts it.

## Definitions

| Term | Definition |
|---|---|
| DFA | Deterministic finite automaton: a 5-tuple (Q, Σ, δ, q0, F) |
| Transition function | δ: Q × Σ → Q |
| Accepting states | States F in which an input is accepted |
| Regular language | A language some DFA accepts |

## Diagrams & Visual Descriptions

```
        1
  q0 -------> q1 (accepting)
  ^ \  <------  / ^
  | 0    1      0 |
  +--+          +--+
```
Loops on 0 at both states; 1 moves between q0 and q1.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

δ: Q × Σ → Q. Example: q0 -1-> q1, q0 -0-> q0, q1 -0-> q1, q1 -1-> q0.

## Key Takeaways

- A DFA has exactly one transition per state and symbol.
- The example accepts an odd number of 1s.
- Regular languages are those some DFA accepts.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: finite_automata.pdf. Version: 1.*
