# CSIT302 — Week 4: SQL Joins

## Overview

Relational databases split data across multiple tables to avoid redundancy — students live in one table, enrolments in another. But real questions almost always span tables: "Which courses is each student taking?" or "Which students haven't enrolled in anything?" SQL joins are the mechanism that stitches related rows from different tables back together, and mastering them is a foundational skill for almost every query you will write beyond the simplest single-table SELECT.

This week covers the two most important join types — INNER JOIN and LEFT JOIN — and then shows how joins combine naturally with aggregation. A subtle but crucial point emerges: the choice of join type changes your aggregate results, because a join determines which rows exist *before* you count or sum them. Understanding joins and GROUP BY together is essential for writing correct reports.

## Key Concepts

### Setup: The Running Example

The lecture uses two small tables:

- `students(id, name)` — one row per student, with a unique `id`.
- `enrolments(student_id, course)` — one row per enrolment, where `student_id` references a student.

This is a classic one-to-many relationship: a student can have zero, one, or many enrolments. That asymmetry is exactly what makes the difference between join types matter.

### INNER JOIN: Keep Only Matches

An INNER JOIN produces rows where the ON condition is satisfied in **both** tables:

```sql
SELECT s.name, e.course
FROM students s
INNER JOIN enrolments e ON e.student_id = s.id;
```

The key behaviour: **a student with no enrolment does not appear at all.** The join finds no matching row in `enrolments`, so the student is dropped from the result. This is fine when you only care about existing relationships ("list all actual enrolments with student names"), but it silently loses information if you want a complete picture of all students — a common source of bugs in reporting queries.

### LEFT JOIN: Keep Every Left-Hand Row

A LEFT JOIN keeps **every row of the left table** (here, `students`), regardless of whether a match exists:

```sql
SELECT s.name, e.course
FROM students s
LEFT JOIN enrolments e ON e.student_id = s.id;
```

Where there is no match, the right-hand columns are filled with NULL. So a student with no enrolments still appears once, with `e.course = NULL`.

This gives you a powerful pattern: to **find students with no enrolment**, use a LEFT JOIN and filter for the unmatched rows:

```sql
... WHERE e.course IS NULL
```

Only students who failed to match any enrolment survive this filter — an "anti-join" style query that is impossible to express with an INNER JOIN.

### Joins + Aggregation: GROUP BY, WHERE vs HAVING

Once rows are joined, you often want per-entity summaries. GROUP BY collapses rows into groups so an aggregate such as COUNT can be computed per group:

```sql
SELECT s.name, COUNT(e.course)
FROM students s
LEFT JOIN enrolments e ON e.student_id = s.id
GROUP BY s.name;
```

Notice the deliberate use of LEFT JOIN here: because unmatched students still appear (with NULL course), they get counted — as zero. With an INNER JOIN they would vanish entirely and the report would under-report.

Two filtering stages exist around grouping, and confusing them is a classic exam trap:

| Clause | When it filters | Applies to |
|---|---|---|
| `WHERE` | Before grouping | Individual rows |
| `HAVING` | After grouping | Whole groups (e.g. `HAVING COUNT(e.course) > 2`) |

So use WHERE to discard rows you don't want counted at all, and HAVING to keep only groups whose aggregates meet a condition.

## Definitions

| Term | Definition |
|---|---|
| INNER JOIN | A join that keeps only rows where the ON condition matches in both tables. |
| LEFT JOIN | A join that keeps every row of the left table; unmatched right-hand columns become NULL. |
| ON condition | The predicate specifying how rows of the two tables correspond (e.g. `e.student_id = s.id`). |
| NULL | The placeholder value appearing in right-hand columns when a LEFT JOIN finds no match. |
| GROUP BY | A clause that collapses rows into groups so aggregates can be computed per group. |
| Aggregate | A function such as COUNT computed over a group of rows. |
| WHERE | Filters individual rows before grouping occurs. |
| HAVING | Filters whole groups after aggregation. |

## Diagrams & Visual Descriptions

```
students                    enrolments
+----+-------+              +------------+---------+
| id | name  |              | student_id | course  |
+----+-------+              +------------+---------+
|  1 | Ada   |<--- match ---|     1      | DB      |
|  2 | Ben   |<--- match ---|     2      | Networks|
|  3 | Clio  |  NO match    |            |         |
+----+-------+              +------------+---------+

INNER JOIN result:          LEFT JOIN result:
+------+---------+          +------+---------+
| name | course  |          | name | course  |
+------+---------+          +------+---------+
| Ada  | DB      |          | Ada  | DB      |
| Ben  | Networks|          | Ben  | Networks|
+------+---------+          | Clio | NULL    |  <- kept, NULL-filled
                            +------+---------+
```

Adding `WHERE e.course IS NULL` to the LEFT JOIN result leaves only Clio — the students with no enrolment.

## Code Examples

**1. INNER JOIN — matched rows only**

```sql
SELECT s.name, e.course
FROM students s
INNER JOIN enrolments e ON e.student_id = s.id;  -- only pairs where ids match
```
Relevant when you only want existing relationships.

**2. LEFT JOIN — all students, matched or not**

```sql
SELECT s.name, e.course
FROM students s
LEFT JOIN enrolments e ON e.student_id = s.id;   -- unmatched students get NULL course
```

**3. LEFT JOIN anti-join — students with no enrolment**

```sql
SELECT s.name
FROM students s
LEFT JOIN enrolments e ON e.student_id = s.id
WHERE e.course IS NULL;                          -- keeps only unmatched students
```

**4. LEFT JOIN + GROUP BY — enrolment count per student**

```sql
SELECT s.name, COUNT(e.course)                   -- NULL courses count as 0
FROM students s
LEFT JOIN enrolments e ON e.student_id = s.id
GROUP BY s.name;                                 -- one output row per student name
```
Note WHERE would filter rows *before* grouping; HAVING would filter groups *after*.

## Formulas & Algorithms

No formulas in this lecture. (Conceptual rule worth remembering: WHERE applies before grouping, HAVING after — see the table above.)

## Key Takeaways

- INNER JOIN drops non-matching rows entirely; if your data has optional relationships, that's silent data loss.
- LEFT JOIN preserves the whole left table, filling unmatched right columns with NULL.
- `WHERE <right-column> IS NULL` after a LEFT JOIN finds entities with *no* related rows — a pattern INNER JOIN cannot express.
- Join type changes aggregate results: COUNT with LEFT JOIN counts non-enrolled students as 0 instead of omitting them.
- WHERE filters rows before GROUP BY; HAVING filters groups after — pick the one matching the stage you mean.

## Connections

The lecture builds join queries on a foreign-key style link (`enrolments.student_id` referencing `students.id`), the standard mechanism relational tables use to relate to one another. It also leaves an obvious next question open: aggregate results could be further filtered with HAVING (e.g. students with more than N enrolments), which the lecture introduces conceptually but does not explore with examples.

---

*Sources: CSIT302 Week 4 lecture content (SQL Joins, 3 page excerpts). Version: 1.*
