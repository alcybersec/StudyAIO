# CSIT205 — Week 2: Deterministic Finite Automata

## Overview

A Deterministic Finite Automaton (DFA) is a simple abstract machine that reads an input string one symbol at a time and, at the end, either accepts or rejects it. Its power comes from a small set of ingredients: a finite collection of states, rules for moving between states as each symbol is read, a designated starting point, and a set of states that count as "success" [p.1]. Because the machine only ever needs to remember which single state it is in, it is an elegant model of computation that consumes a fixed, finite amount of memory no matter how long the input is.

The DFA is the foundation for the idea of a *regular language*: a language is regular exactly when some DFA accepts it [p.3]. This gives us a precise, mechanical way to define what strings belong to a language — instead of describing patterns in prose, we build a machine that recognizes them, and the language of the machine is simply the set of strings it accepts [p.3].

## Key Concepts

### The Formal Definition of a DFA

#### The 5-tuple

A DFA is formally defined as a 5-tuple (Q, Σ, δ, q0, F). Each component plays a distinct role [p.1]:

- `Q` — a finite set of states: the only "memory" the machine has [p.1].
- `Σ` — the input alphabet: the set of symbols the machine can read [p.1].
- `δ` — the transition function δ: Q × Σ → Q, mapping each (state, symbol) pair to a next state [p.1].
- `q0` — the start state, where processing begins [p.1].
- `F` — a set of accepting states; ending in one of these means the string is accepted [p.1].

#### Determinism: exactly one transition per symbol

The "deterministic" in DFA means that from each state there is exactly one transition per symbol [p.1]. There is never a choice to make and never a missing move: given the current state and the next input symbol, the next state is completely fixed. This is what makes the machine's behaviour on any input fully predictable — a property that contrasts with nondeterministic machines (not covered in this lecture) and is the key structural fact captured by δ being a total function Q × Σ → Q [p.1].

### A Worked Example: Detecting an Odd Number of 1s

#### The machine

The lecture builds a DFA over the alphabet Σ = {0, 1}. It has just two states, q0 and q1; the start state is q0 and the only accepting state is q1 [p.2]. The transitions are [p.2]:

```
q0 --1--> q1
q0 --0--> q0
q1 --0--> q1
q1 --1--> q0
```

Reading these rules, 0 never changes the state — the machine simply stays where it is — while every 1 flips it between q0 and q1 [p.2].

#### What the machine computes

Because each 1 toggles the state and 0 does nothing, the machine is really counting 1s modulo 2: q0 means "even number of 1s seen so far" and q1 means "odd number of 1s seen so far". Since q1 is the only accepting state, the machine accepts strings with an odd number of 1s [p.2].

#### Tracing two inputs

The lecture traces two concrete inputs to show how acceptance is decided:

- Input `0110`: the machine ends in q0 (two 1s), so it rejects [p.2].
- Input `0111`: the machine ends in q1, so it accepts [p.2].

This trace illustrates the general operating principle: run the input through δ symbol by symbol from q0, and the final state alone decides accept/reject.

### Languages and Regularity

The language of a DFA is the set of strings it accepts [p.3]. This turns a machine description into a set of strings — for the example above, the language is exactly the strings over {0, 1} containing an odd number of 1s.

The crucial definition follows: a language is *regular* if some DFA accepts it [p.3]. In other words, regularity is defined by existence — to prove a language is regular, it suffices to exhibit one DFA for it, as the lecture's odd-1s machine does [p.3].

## Definitions

| Term | Definition |
|---|---|
| DFA | A 5-tuple (Q, Σ, δ, q0, F): a finite set of states Q, an input alphabet Σ, a transition function δ: Q × Σ → Q, a start state q0 and a set of accepting states F [p.1] |
| Q | A finite set of states [p.1] |
| Σ | The input alphabet [p.1] |
| δ | The transition function δ: Q × Σ → Q; from each state there is exactly one transition per symbol [p.1] |
| q0 | The start state [p.1] |
| F | The set of accepting states [p.1] |
| Language of a DFA | The set of strings it accepts [p.3] |
| Regular language | A language such that some DFA accepts it [p.3] |

## Diagrams & Visual Descriptions

State diagram of the odd-1s DFA (arrows labelled with input symbols):

```
        0                 1
       ┌─┐               ┌─┐
       │ ▼               │ ▼
      ┌────────┐   1    ┌────────┐
─►    │   q0   │───────►│  ((q1))│      ((q1)) = accepting
      └────────┘◄───────└────────┘
          ▲       1          │
          └────── 0 ─────────┘   (0 loops on q0 and on q1)
```

- Reading a `1` in q0 moves to q1; reading a `1` in q1 moves back to q0 [p.2].
- Reading a `0` leaves the state unchanged, in either q0 or q1 [p.2].
- The double circle marks q1, the only accepting state; the entry arrow marks q0 as the start state [p.2].

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

The DFA definition [p.1]:

```
DFA = (Q, Σ, δ, q0, F)
δ : Q × Σ → Q
```

Determinism condition [p.1]:

```
From each state there is exactly one transition per symbol.
```

Transition table of the example over Σ = {0, 1}; states q0 and q1, start q0, accepting {q1} [p.2]:

```
q0 --1--> q1
q0 --0--> q0
q1 --0--> q1
q1 --1--> q0
```

Worked traces [p.2]:

```
Input 0110: ends in q0 (two 1s) → reject
Input 0111: ends in q1          → accept
```

Language recognized by the example machine [p.2]:

```
Strings over {0, 1} with an odd number of 1s
```

## Key Takeaways

- A DFA is fully specified by five components — states, alphabet, transition function, start state, accepting states — and nothing else is needed to describe its behaviour [p.1].
- Determinism means no ambiguity: every (state, symbol) pair has exactly one outgoing transition, so a run is completely determined by the input [p.1].
- States can encode simple counts — the two-state example tracks parity of the number of 1s, accepting exactly the odd-1s strings [p.2].
- Acceptance is decided solely by the final state after reading the whole input, as the 0110 (reject) vs 0111 (accept) traces show [p.2].
- "Regular" is defined by machines: a language is regular if some DFA accepts it, giving a mechanical criterion for membership in this class of languages [p.3].

## Connections

This lecture establishes the core object of the course's study of languages and automata: the DFA as a recognizer, and the definition of regular languages as exactly those accepted by some DFA [p.3]. The lecture itself does not name any later topics or other weeks, so no further pointers can be drawn from its content.

---
*Sources: CSIT205 Week 2 lecture slides (pages 1–3). Version: 1.*
