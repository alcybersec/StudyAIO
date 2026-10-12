# CSIT302 — Week 4: SQL Joins

## Overview

When data lives in more than one table — here, `students(id, name)` and `enrolments(student_id, course)` — a single query usually needs to bring rows from both together. Joins are the SQL mechanism for that: they combine rows of two tables based on a matching condition [p.1]. This week introduces the two fundamental join types, INNER JOIN and LEFT JOIN, and shows how the choice between them changes *which rows* your result contains — a student with no enrolment appears in some results but vanishes from others [p.1][p.2].

The lecture then connects joins to aggregation: once rows are combined, GROUP BY collapses them into groups so aggregates like COUNT can be computed per group, and the lecture distinguishes WHERE (filtering rows before grouping) from HAVING (filtering groups after) [p.3].

## Key Concepts

### The Running Example: Two Related Tables

The lecture works throughout with `students(id, name)` and `enrolments(student_id, course)`. Each enrolment refers to a student via `student_id`, which matches `students.id`. This id-based linkage is exactly what the `ON` condition of a join tests [p.1].

### INNER JOIN: Keeping Only Matches

An INNER JOIN keeps only rows that match on the `ON` condition. The key behavioural consequence: a student with no enrolment does not appear in the result at all, because their row has no matching partner in `enrolments` [p.1].

The query has this shape [p.1]:

```sql
SELECT s.name, e.course
FROM students s
INNER JOIN enrolments e ON e.student_id = s.id;
```

Read it as: walk through `students`, and for each row find enrolment rows whose `student_id` equals that student's `id`; output the name/course pair for each match [p.1].

### LEFT JOIN: Keeping Every Left-Hand Row

A LEFT JOIN keeps every row of the left table (here `students`). Where there is no match, the right-hand columns are filled with NULL — so a student with no enrolment still appears, with `e.course` as NULL [p.2].

The query shape [p.2]:

```sql
SELECT s.name, e.course
FROM students s
LEFT JOIN enrolments e ON e.student_id = s.id;
```

#### Finding Non-Matches with LEFT JOIN + IS NULL

Because unmatched left rows carry NULL in the right-hand columns, LEFT JOIN gives a clean way to find students with no enrolment: add `WHERE e.course IS NULL` to the query [p.2]. This is a pattern worth remembering — the join itself doesn't filter; the WHERE clause on the NULL columns isolates exactly the rows that found no partner [p.2].

### Combining Joins with GROUP BY and Aggregates

GROUP BY collapses rows into groups so an aggregate such as COUNT can be computed per group. The lecture's example counts each student's enrolments [p.3]:

```sql
SELECT s.name, COUNT(e.course)
FROM students s LEFT JOIN enrolments e ON e.student_id = s.id
GROUP BY s.name;
```

Using a LEFT JOIN here matters: every student forms a group, and students with no enrolment get a count of 0 rather than disappearing from the report [p.3].

#### WHERE vs HAVING

The two filter clauses act at different stages [p.3]:

- WHERE filters rows **before** grouping [p.3].
- HAVING filters groups **after** grouping [p.3].

### Comparing the Join Types

| Join type | Rows kept | Unmatched behaviour [p.1][p.2] |
|---|---|---|
| INNER JOIN | Only rows matching on the ON condition; a student with no enrolment does not appear [p.1] | Non-matching rows dropped [p.1] |
| LEFT JOIN | Every row of the left table [p.2] | Right-hand columns become NULL [p.2] |

## Definitions

| Term | Definition |
|---|---|
| INNER JOIN | A join keeping only rows that match on the ON condition [p.1] |
| LEFT JOIN | A join keeping every row of the left table, with NULLs where there is no match [p.2] |
| ON condition | The matching condition (e.g. `e.student_id = s.id`) that determines which rows join [p.1] |
| NULL | The value appearing in right-hand columns when a LEFT JOIN finds no match [p.2] |
| GROUP BY | Collapses rows into groups so an aggregate such as COUNT can be computed per group [p.3] |
| WHERE | Filters rows before grouping [p.3] |
| HAVING | Filters groups after grouping [p.3] |

## Diagrams & Visual Descriptions

```
INNER JOIN: only the overlap survives
 students                 enrolments
  id | name                student_id | course
   1 | Ada                  1 | DB
   2 | Ben   (no match → dropped)
                              3 | Web  (no student 3 → dropped)
 result: Ada–DB rows only [p.1]

LEFT JOIN: every left row survives
   1 | Ada  → matches enrolment 1 → Ada, DB
   2 | Ben  → no match           → Ben, NULL [p.2]
```

No extracted images in this lecture.

## Code Examples

INNER JOIN — list each student's courses, omitting students with no enrolment; relevant when you only care about actual enrolments [p.1]:

```sql
SELECT s.name, e.course
FROM students s
INNER JOIN enrolments e ON e.student_id = s.id;
```

LEFT JOIN — keep all students, with NULL course for the unenrolled; add the WHERE clause to find students with no enrolment; relevant for completeness checks and gap-finding [p.2]:

```sql
SELECT s.name, e.course
FROM students s
LEFT JOIN enrolments e ON e.student_id = s.id;
-- WHERE e.course IS NULL  finds students with no enrolment
```

GROUP BY over a LEFT JOIN — count enrolments per student, keeping students with zero; relevant for per-group aggregate reporting [p.3]:

```sql
SELECT s.name, COUNT(e.course)
FROM students s LEFT JOIN enrolments e ON e.student_id = s.id
GROUP BY s.name;
```

## Formulas & Algorithms

Join condition for the lecture's tables [p.1]:

```
e.student_id = s.id
```

INNER JOIN semantics: keeps only rows that match on the ON condition; a student with no enrolment does not appear [p.1].

LEFT JOIN semantics: keeps every row of the left table; where there is no match the right-hand columns are NULL; `WHERE e.course IS NULL` finds students with no enrolment [p.2].

Aggregation query pattern [p.3]:

```
SELECT s.name, COUNT(e.course)
FROM students s LEFT JOIN enrolments e ON e.student_id = s.id
GROUP BY s.name;
```

Filtering rule: WHERE filters rows before grouping; HAVING filters groups after [p.3].

## Key Takeaways

- Choose your join by asking "should unmatched rows survive?": INNER JOIN drops them, LEFT JOIN keeps them with NULLs [p.1][p.2].
- LEFT JOIN plus `WHERE e.course IS NULL` is the lecture's pattern for finding rows on one side with no match on the other [p.2].
- Counting per-group with COUNT pairs naturally with LEFT JOIN so zero-count students still appear [p.3].
- WHERE and HAVING act at different pipeline stages — rows first, groups after — so which one you need depends on whether your condition is about individual rows or whole groups [p.3].

## Connections

This lecture builds its queries around multi-table data (`students` and `enrolments` linked by `student_id = s.id`), and its aggregation layer (GROUP BY, COUNT, WHERE vs HAVING) operates on the rows that joins produce [p.1][p.3]. Within the lecture itself, the join choice (INNER vs LEFT) directly controls the input to the grouping step, so the two halves of this week's material — joins and aggregation — are one pipeline rather than separate topics [p.2][p.3].

This lecture does not name any other weeks or outside material.

---
*Sources: CSIT302 Week 4 lecture slides (pp.1–3). Version: 1.*
