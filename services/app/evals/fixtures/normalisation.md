# CSIT302 — Week 3: Database Normalisation

## Overview

Normalisation organises columns and tables to reduce redundancy, which otherwise causes update anomalies. The lecture climbs from 1NF through 3NF.

## Key Concepts

### Why normalise

Redundancy means the same fact is stored twice and can be changed in one place and not the other: an update anomaly. A functional dependency A -> B says each value of A has exactly one value of B, as with student_id -> student_name.

### The normal forms

#### 1NF
Every column holds a single atomic value. A column holding 'maths, physics, chemistry' violates 1NF and belongs in three rows of a separate table.

#### 2NF
1NF plus no partial dependency: no non-key column may depend on only part of a composite primary key. With key (student_id, course_code), course_title depends on course_code alone and must move to a course table.

#### 3NF
2NF plus no transitive dependency: no non-key column may depend on another non-key column. If student_id -> postcode and postcode -> city, city belongs in a postcode table.

In practice most operational schemas are normalised to 3NF and stop there, because going further can cost more in joins than it saves in storage.

## Definitions

| Term | Definition |
|---|---|
| Redundancy | The same fact stored more than once |
| Functional dependency | A -> B: one B value for each A value |
| Partial dependency | A column depending on part of a composite key |
| Transitive dependency | A non-key column depending on another non-key column |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

No formulas in this lecture.

## Key Takeaways

- Normalise to remove redundancy and update anomalies.
- Each form adds one rule: atomic, no partial, no transitive.
- 3NF is where most operational schemas stop.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: normalisation.pdf. Version: 1.*
