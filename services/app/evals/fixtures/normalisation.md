# CSIT302 — Week 3: Database Normalisation

## Overview

Database normalisation is the process of organising columns and tables to reduce redundancy. Why does redundancy matter? Because the same fact stored twice can be changed in one place and not the other — these are the classic update anomalies, and they are the central problem this lecture attacks [p.1]. If a customer's address appears in fifty rows and it changes, you must update fifty rows correctly; miss one and your database now contradicts itself.

The lecture builds normalisation as a progression of "normal forms," each adding a constraint on top of the last: 1NF demands atomic values, 2NF removes partial dependencies, and 3NF removes transitive dependencies [p.2][p.3]. Underpinning all of these is the concept of a functional dependency, which gives us a precise language for saying "this column determines that one" [p.1]. The lecture closes with an important practical note: most operational schemas are normalised to 3NF and stop there, because going further can cost more in joins than it saves in storage [p.3].

## Key Concepts

### Redundancy and Update Anomalies

The motivation for normalisation is straightforward: duplicated data is dangerous. Normalisation exists to reduce redundancy by organising how columns and tables are arranged [p.1]. The failure mode redundancy causes is the update anomaly — the same fact stored in multiple places can be updated in one copy but not the others, leaving the database internally inconsistent [p.1]. Normalisation's normal forms are the systematic answer to this problem.

### Functional Dependencies

Everything in normalisation rests on the idea of a functional dependency. A functional dependency A -> B means that for any given value of A there is exactly one value of B [p.1]. In other words, knowing A pins down B uniquely.

The lecture gives a concrete example: in a student table, `student_id -> student_name` is a functional dependency — one id, one name [p.1]. Two students might share a name, but a given student_id always corresponds to exactly one name, so the dependency holds. When you examine any proposed normal form violation, you are really asking questions about which functional dependencies hold among your columns.

### First Normal Form (1NF): Atomic Values

First normal form requires that every column holds a single atomic value [p.2]. The violation to watch for is a column packing multiple values into one cell. A column containing `'maths, physics, chemistry'` violates 1NF [p.2] — one cell is holding three facts.

The fix is structural, not cosmetic: those values belong in three rows of a separate table [p.2]. Splitting them out means each value can be queried, updated and constrained independently, which is exactly what the comma-packed version prevents.

### Second Normal Form (2NF): No Partial Dependencies

Second normal form builds on 1NF: it requires 1NF plus no partial dependency — no non-key column may depend on only part of a composite primary key [p.2]. This only becomes relevant once you have composite keys, since a single-column key has no "part" to depend on.

The lecture's worked scenario uses the key `(student_id, course_code)`. In that table, `course_title` depends on `course_code` alone, which is a partial dependency [p.2]. The title doesn't need to know which student is enrolled — it is a fact about the course, not about the enrolment. The remedy is to move `course_title` to a course table keyed by `course_code` [p.2], where it is stored once instead of repeated per enrolment.

### Third Normal Form (3NF): No Transitive Dependencies

Third normal form adds one more constraint on top of 2NF: 3NF requires 2NF plus no transitive dependency — no non-key column may depend on another non-key column [p.3]. A transitive dependency is an indirect one: the key determines column X, and X determines column Y, so Y depends on the key only through X.

The lecture's example chains two functional dependencies: `student_id -> postcode` and `postcode -> city`, so `city` depends on the key only through `postcode` [p.3]. That is transitive. Both `postcode` and `city` are stored on the student row even though the real fact is the postcode-to-city mapping. The fix: `city` belongs in a postcode table [p.3], keyed by postcode, where each mapping appears exactly once.

### How Far to Normalise?

The lecture closes with practical guidance: in practice most operational schemas are normalised to 3NF and stop there [p.3]. Normalisation further than 3NF is a trade-off — going further can cost more in joins than it saves in storage [p.3]. Each extra level of decomposition splits data into more tables, and reassembling it at query time requires more join operations, which can outweigh the storage savings from removing redundancy.

### The Forms at a Glance

| Form | Requirement | Violation example | Fix |
|---|---|---|---|
| 1NF | Every column holds a single atomic value [p.2] | A column containing 'maths, physics, chemistry' [p.2] | Three rows of a separate table [p.2] |
| 2NF | 1NF plus no partial dependency on part of a composite key [p.2] | Key `(student_id, course_code)`, but `course_title` depends on `course_code` alone [p.2] | Move `course_title` to a course table [p.2] |
| 3NF | 2NF plus no transitive dependency between non-key columns [p.3] | `student_id -> postcode` and `postcode -> city` [p.3] | `city` belongs in a postcode table [p.3] |

## Definitions

| Term | Definition |
|---|---|
| Normalisation | The process of organising columns and tables to reduce redundancy [p.1] |
| Update anomaly | The problem caused when the same fact stored twice is changed in one place and not the other [p.1] |
| Functional dependency | A -> B means that for any given value of A there is exactly one value of B [p.1] |
| Atomic value | A single, indivisible value in a column, as required by 1NF [p.2] |
| 1NF | First normal form: every column holds a single atomic value [p.2] |
| 2NF | Second normal form: 1NF plus no partial dependency — no non-key column depends on only part of a composite primary key [p.2] |
| Partial dependency | A non-key column depending on only part of a composite primary key, e.g. `course_title` depending on `course_code` alone [p.2] |
| 3NF | Third normal form: 2NF plus no transitive dependency — no non-key column depends on another non-key column [p.3] |
| Transitive dependency | A non-key column depending on the key only through another non-key column [p.3] |
| Composite primary key | A primary key made of multiple columns, e.g. `(student_id, course_code)` [p.2] |

## Diagrams & Visual Descriptions

The dependency chains underlying the normal forms can be drawn as arrow diagrams. Direct versus transitive dependence on the key:

```
2NF problem (partial dependency):
  student_id ──────┐
  course_code ─────┼──> (composite key)      course_code ──> course_title
                   │                         (part of key alone determines title)

3NF problem (transitive dependency):
  student_id ──> postcode ──> city
  (city depends on the key only through postcode)
```

Reading the diagrams: in the 2NF case, `course_title` attaches to only one half of the composite key, so it must move to its own course table [p.2]. In the 3NF case, `city` reaches the key through the intermediate column `postcode`, so it must move to a postcode table [p.3].

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

The lecture's functional dependencies and normal-form conditions, exactly as stated:

Functional dependency definition [p.1]:
```
A -> B  means  for any given value of A there is exactly one value of B
Example:  student_id -> student_name   (one id, one name)
```

Normal form requirements [p.2][p.3]:
```
1NF: every column holds a single atomic value
2NF: 1NF + no partial dependency
     (no non-key column may depend on only part of a composite primary key)
3NF: 2NF + no transitive dependency
     (no non-key column may depend on another non-key column)
```

Worked examples [p.2][p.3]:
```
1NF violation:  a column containing 'maths, physics, chemistry'
                -> belongs in three rows of a separate table

2NF violation:  key = (student_id, course_code)
                course_title depends on course_code alone
                -> move course_title to a course table

3NF violation:  student_id -> postcode
                postcode -> city
                (city depends on the key only through postcode)
                -> city belongs in a postcode table
```

Practical bound [p.3]:
```
Most operational schemas are normalised to 3NF and stop there.
Going further can cost more in joins than it saves in storage.
```

## Key Takeaways

- Normalisation's whole purpose is to reduce redundancy, because duplicated facts invite update anomalies — data changed in one place but not another [p.1].
- Functional dependencies (`A -> B`: one value of A, exactly one of B) are the language in which every normal-form rule is expressed [p.1].
- The forms are cumulative: 2NF = 1NF + no partial dependency, and 3NF = 2NF + no transitive dependency [p.2][p.3].
- A comma-packed cell like 'maths, physics, chemistry' is a 1NF violation; split the values into rows of a separate table [p.2].
- When a non-key column depends on only part of a composite key (like `course_title` on `course_code`), move it to a table keyed by that part [p.2].
- When one non-key column depends on another (`city` via `postcode`), extract the intermediate column and its dependent into their own table [p.3].
- 3NF is the practical stopping point for most operational schemas: decomposing further can cost more in joins than it saves in storage [p.3].

## Connections

This lecture is self-contained within the provided material: it defines its own foundations (functional dependencies) and builds the 1NF–2NF–3NF ladder directly on them [p.1][p.2][p.3]. It does not name any other week or external topic, and no other weeks were available to compare against, so there are no cross-week pointers to follow.

---
*Sources: CSIT302 Week 3 lecture content, pages 1–3. Version: 1.*
