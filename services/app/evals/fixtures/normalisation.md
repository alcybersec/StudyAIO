# CSIT302 — Week 3: Database Normalisation

## Overview

Imagine a university admin database where a student's address is stored in every row of an enrolment table. The student moves house, and someone updates three of the fifteen rows containing that address. The database now contains contradictory facts — and nobody can say which one is true. This failure mode is what normalisation exists to prevent. **Normalisation** is the process of organising columns and tables to reduce redundancy: storing each fact exactly once, in exactly one place.

Why does redundancy matter so much? Because duplicated data invites **update anomalies** — situations where the same fact is stored twice and changed in one place but not the other. Normalisation attacks this problem systematically through a series of progressively stricter "normal forms" (1NF, 2NF, 3NF), each building on the previous one. The foundational tool for reasoning about all of them is the **functional dependency**, a formal way of saying "this value determines that value."

This week's material sits at the heart of database design: before you write queries or build applications, the structure of your tables determines whether your data can stay consistent at all.

## Key Concepts

### Redundancy and Update Anomalies

The core motivation for normalisation is that redundancy is dangerous. When the same fact appears in multiple rows, an update must touch every copy. Miss one, and the database becomes internally inconsistent — there is no single "truth" about that fact anymore. Normalisation's guiding principle is therefore: *store each fact once, in the table where it belongs*.

### Functional Dependencies: The Language of Normalisation

A **functional dependency** (FD), written $A \rightarrow B$, means that for any given value of $A$ there is exactly one value of $B$. In other words, $A$ determines $B$.

The classic example: in a student table, `student_id → student_name`. One student ID corresponds to exactly one name. FDs are the analytical lens through which we decide whether a table structure is sound — each normal form is essentially a rule about which kinds of dependencies are allowed to exist in a table.

### First Normal Form (1NF): Atomic Values

1NF requires that **every column holds a single atomic value** — no lists, no multi-valued cells.

- Violation: a column containing `'maths, physics, chemistry'`
- Fix: place those values in three separate rows of a separate table

The reason is practical as much as theoretical: a cell holding a comma-separated list cannot be queried, indexed, or constrained properly. You cannot ask "which students take physics?" efficiently when physics is buried inside a text string.

### Second Normal Form (2NF): No Partial Dependencies

2NF requires 1NF **plus no partial dependency**: no non-key column may depend on *only part* of a composite primary key.

Consider an enrolment table keyed by `(student_id, course_code)`:

| student_id | course_code | course_title |
|---|---|---|
| S1 | CS101 | Intro to CS |
| S1 | MA200 | Calculus |

`course_title` depends on `course_code` alone — the `student_id` half of the key is irrelevant to it. That is a partial dependency. The fix is to move `course_title` into its own `course` table, where `course_code` is the full key. Left in place, the course title would be repeated for every student enrolled in the course — exactly the redundancy that causes update anomalies.

### Third Normal Form (3NF): No Transitive Dependencies

3NF requires 2NF **plus no transitive dependency**: no non-key column may depend on another non-key column.

The lecture's example: `student_id → postcode` and `postcode → city`. Although `city` does depend on the key, it does so only *through* `postcode` — a chain: key → postcode → city. Since `postcode` is itself a non-key column, this is transitive, and `city` belongs in a separate postcode table (keyed by postcode).

The rationale mirrors 2NF: if city names were stored alongside students, every change to a city's name (or every fact about a postcode) would be duplicated across all students sharing that postcode.

### How Far to Normalise? The Practical Stopping Point

The normal forms form a strict hierarchy: 2NF implies 1NF, and 3NF implies 2NF. In practice, the lecture notes that **most operational schemas are normalised to 3NF and stop there**. The trade-off is real: going further (stricter normal forms) eliminates more subtle redundancy but forces more table joins at query time — and the cost of those joins can exceed the storage savings. 3NF is the accepted sweet spot between data integrity and query performance.

### Summary of the Normal Forms

| Normal Form | Rule | Violation example | Fix |
|---|---|---|---|
| 1NF | All values atomic | `'maths, physics, chemistry'` in one cell | Separate rows in a new table |
| 2NF | 1NF + no partial dependency | `course_title` depends on `course_code`, only part of key `(student_id, course_code)` | Move to a `course` table |
| 3NF | 2NF + no transitive dependency | `student_id → postcode → city` | Move `city` to a postcode table |

## Definitions

| Term | Definition |
|---|---|
| Normalisation | The process of organising columns and tables to reduce redundancy |
| Redundancy | Storing the same fact in multiple places |
| Update anomaly | A consistency error caused by changing a duplicated fact in one place but not the other |
| Functional dependency ($A \rightarrow B$) | A relationship where any given value of $A$ determines exactly one value of $B$ |
| First normal form (1NF) | Every column holds a single atomic value |
| Second normal form (2NF) | 1NF plus no non-key column depends on only part of a composite primary key (no partial dependency) |
| Third normal form (3NF) | 2NF plus no non-key column depends on another non-key column (no transitive dependency) |
| Partial dependency | A non-key column depending on only part of a composite primary key |
| Transitive dependency | A non-key column depending on the key only through another non-key column |
| Composite primary key | A primary key made up of multiple columns |

## Diagrams & Visual Descriptions

**Dependency chains and where each normal form draws the line:**

```
1NF violation (non-atomic cell):
┌──────────────────────────────┐
│ subjects                     │
│ 'maths, physics, chemistry'  │  ✗ one cell, many values
└──────────────────────────────┘
        → split into one row per value in a separate table

2NF violation (partial dependency), key = (student_id, course_code):
  (student_id, course_code) ──┬──> course_title   ✗ depends on
                              │                     course_code ALONE
                        student_id                  → move to course table

3NF violation (transitive dependency):
  student_id ──> postcode ──> city
       key      non-key    non-key
                            ✗ city depends on key only THROUGH postcode
                            → move to postcode table
```

The chain structure of the 3NF example makes the "transitive" naming intuitive: the dependency passes *through* an intermediate non-key column rather than going directly from key to value.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

The normalisation hierarchy can be stated as a progressive constraint check:

```
1NF: all attributes atomic
2NF: 1NF AND ∀ non-key attribute B, no proper subset of the key determines B
3NF: 2NF AND ∀ non-key attributes B, C: no dependency B → C

(With functional dependency notation A → B:
 partial:   (part of key) → non-key attribute
 transitive: key → non-key₁ → non-key₂)
```

The lecture's worked dependency examples: `student_id → student_name` (valid FD); `postcode → city` making `city` transitively dependent on `student_id`.

## Key Takeaways

- Redundancy is the enemy of consistency: every duplicate fact is a chance for an update anomaly.
- Functional dependencies ($A \rightarrow B$: one value of $A$ determines exactly one $B$) are the formal tool for analysing table design.
- Each normal form adds a constraint on the previous one: 1NF (atomic values) → 2NF (no partial dependencies on composite keys) → 3NF (no dependencies between non-key columns).
- Partial dependencies mean a fact belongs with the part of the key that actually determines it (e.g., `course_title` lives in a course table).
- Transitive dependencies mean a chained fact belongs with its intermediate determinant (e.g., `city` lives in a postcode table).
- 3NF is the practical stopping point for most operational schemas — further normalisation trades join cost for storage savings, and the joins usually cost more.

## Connections

This lecture frames normalisation as the structural foundation for storing facts without inconsistency — a concern that presumes a data model exists to be refined. The functional dependency notation introduced here (`student_id → student_name`) is the analytical tool the normal forms are defined in terms of, so mastery of FDs is what makes the 1NF→2NF→3NF progression legible rather than memorised.

The lecture notes that in practice most operational schemas stop at 3NF because further normalisation "can cost more in joins than it saves in storage" — pointing toward query-time considerations as the counterweight to design-time purity, a trade-off the course may develop elsewhere.

---
*Sources: CSIT302 Week 3 lecture content (Database Normalisation). Version: 1.*
