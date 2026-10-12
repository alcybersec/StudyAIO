# CSIT205 — Week 2: Deterministic Finite Automata

## Overview

A Deterministic Finite Automaton (DFA) is one of the simplest models of computation: an abstract machine with a finite number of states that reads an input string one symbol at a time and ends in either an accepting or a rejecting state. Despite its simplicity, the DFA is the foundational object of automata theory — it gives a precise, mechanical definition of what it means to "recognize" a language, and it leads directly to the class of *regular languages*.

Why does this matter? Many practical problems — validating input, scanning text, checking simple properties of strings — boil down to deciding whether a string belongs to some set. DFAs provide a rigorous framework for exactly this kind of decision problem, and their "determinism" (one and only one move at each step) makes them easy to implement and reason about. This week establishes the formal definition, works through a complete example, and defines what it means for a language to be regular.

## Key Concepts

### The Formal Definition: A 5-Tuple

A DFA is formally defined as a 5-tuple $(Q, \Sigma, \delta, q_0, F)$. Each component plays a distinct and essential role:

- **$Q$** — a finite set of *states*. Think of these as the machine's "memory": since $Q$ is finite, a DFA can only remember a bounded amount of information about the input seen so far.
- **$\Sigma$** — the *input alphabet*, a finite set of symbols the machine can read (e.g., $\{0, 1\}$).
- **$\delta$** — the *transition function*, $\delta: Q \times \Sigma \to Q$. Given a current state and the next input symbol, it returns exactly one next state.
- **$q_0$** — the *start state*, where the machine begins before reading any input.
- **$F$** — the set of *accepting states* (also called final states). If the machine finishes reading the input in a state in $F$, the string is accepted.

The critical property is **determinism**: from each state there is *exactly one* transition per symbol. There is never a choice, and there is never a missing transition. This is what makes the machine's behavior on any given input completely predictable — which is why we call it "deterministic."

#### Why the formalism matters

The 5-tuple isn't bureaucratic detail — each piece is needed to make "machine" mathematically precise. Without $F$ we couldn't say which computations succeed; without a total transition function $\delta$ we couldn't guarantee the machine always has a well-defined next move. When proving things about DFAs later in the course, you'll manipulate exactly these components.

### A Worked Example: Detecting Odd Numbers of 1s

The lecture's example is a two-state DFA over $\Sigma = \{0, 1\}$ with states $Q = \{q_0, q_1\}$, start state $q_0$, and accepting states $F = \{q_1\}$. The transitions are:

| State | On 0 | On 1 |
|-------|------|------|
| $q_0$ | $q_0$ | $q_1$ |
| $q_1$ | $q_1$ | $q_0$ |

The intuition: **each state remembers the parity of the number of 1s seen so far**. State $q_0$ means "even number of 1s so far," and $q_1$ means "odd number of 1s so far." Reading a `0` doesn't change the parity, so it loops in place; reading a `1` flips the parity, so it swaps states. Since the start state is $q_0$ (zero 1s — an even count) and the accepting state is $q_1$ (odd), the machine accepts exactly those strings containing an odd number of 1s.

#### Tracing inputs

How the machine processes input illustrates the mechanics:

- **Input `0110`**: start at $q_0$; `0` keeps us at $q_0$; `1` moves to $q_1$; `1` moves back to $q_0$; `0` stays at $q_0$. The input has two 1s (even), so we end in $q_0$ — **rejected**.
- **Input `0111`**: `0` → $q_0$; `1` → $q_1$; `1` → $q_0$; `1` → $q_1$. Three 1s (odd), end in $q_1$ — **accepted**.

Notice that `0`s are entirely irrelevant to the machine's decision — the DFA structure makes that abstraction visible and automatic.

### Languages and Regularity

The **language** of a DFA is simply the set of all strings it accepts. This turns a machine into a set-definition device: instead of describing a language by rules, we can define it by a process that decides membership.

This leads to the week's central definition: **a language is regular if some DFA accepts it**. The word "some" is important — regularity is an existence claim. To show a language is regular, you construct one DFA that recognizes it; to understand the limits of regular languages, you would need to show that no DFA can recognize a given language. The two-state parity example demonstrates that "odd number of 1s" is a regular language.

## Definitions

| Term | Definition |
|------|------------|
| DFA | A 5-tuple $(Q, \Sigma, \delta, q_0, F)$ — a finite automaton with exactly one transition per state per symbol. |
| States ($Q$) | The finite set of internal configurations of the machine. |
| Alphabet ($\Sigma$) | The finite set of input symbols the machine reads. |
| Transition function ($\delta$) | Function $\delta: Q \times \Sigma \to Q$ mapping each (state, symbol) pair to exactly one next state. |
| Start state ($q_0$) | The state the machine begins in before reading input. |
| Accepting states ($F$) | The subset of states $F \subseteq Q$; ending in one of these means the input is accepted. |
| Determinism | The property that from every state there is exactly one transition per input symbol. |
| Language of a DFA | The set of all strings the DFA accepts. |
| Regular language | A language for which there exists some DFA that accepts it. |

## Diagrams & Visual Descriptions

The two-state DFA as a state diagram:

```
        0                    0
       ┌─┐                  ┌─┐
       │ ▼                  │ ▼
      ┌────┐      1        ┌────┐
 ---> │ q0 │ ────────────> │ q1 │  (( accepting ))
      └────┘ <──────────── └────┘
                1
```

State $q_0$ (even number of 1s) loops on `0` and moves to $q_1$ on `1`. State $q_1$ (odd number of 1s) loops on `0` and returns to $q_0$ on `1`. $q_1$ is accepting, drawn with a double circle in standard notation.

Trace of the rejected input `0110`:

```
Input: 0  1  1  0
State: q0→q0→q1→q0→q0   → ends in q0 (not in F): REJECT
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

Formal DFA definition: $M = (Q, \Sigma, \delta, q_0, F)$ with transition function

$$\delta: Q \times \Sigma \to Q$$

Acceptance: an input $w = a_1 a_2 \dots a_n$ is accepted if, starting from $q_0$ and following $\delta$ through $a_1, \dots, a_n$, the machine ends in a state in $F$. The language of $M$ is $L(M) = \{ w : \delta^*(q_0, w) \in F \}$.

Parity invariant (from the example): state tracks parity of the count of 1s — reading `0` preserves parity; reading `1` flips it.

## Key Takeaways

- A DFA is fully specified by five components: states, alphabet, transitions, start state, and accepting states — every piece is required.
- Determinism (exactly one transition per symbol from each state) makes DFA behavior on any input completely predictable.
- DFA states are its only memory; clever state design (like parity tracking) is how DFAs "remember" properties of the input.
- Always trace a DFA on concrete inputs to verify what language it accepts — the lecture's `0110` vs `0111` traces show how quickly the outcome flips.
- A language is regular precisely when at least one DFA accepts it; constructing a DFA is how you prove regularity.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: CSIT205 Week 2 lecture slides (Deterministic Finite Automata). Version: 1.*
