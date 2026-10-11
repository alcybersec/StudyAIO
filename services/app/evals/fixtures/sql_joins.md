# CSIT302 — Week 4: SQL Queries and Joins

## Overview

The lecture contrasts INNER and LEFT joins on a students and enrolments schema, then adds GROUP BY with aggregates.

## Key Concepts

### INNER JOIN

An INNER JOIN keeps only rows that match on the ON condition, so a student with no enrolment does not appear.

### LEFT JOIN

A LEFT JOIN keeps every row of the left table; where there is no match the right-hand columns are NULL. Adding WHERE e.course IS NULL finds students with no enrolment.

### Grouping

GROUP BY collapses rows into groups so an aggregate such as COUNT is computed per group. WHERE filters rows before grouping; HAVING filters groups after.

## Definitions

| Term | Definition |
|---|---|
| INNER JOIN | Only rows matching the ON condition |
| LEFT JOIN | All left rows; unmatched right columns are NULL |
| GROUP BY | Collapses rows into groups for aggregates |
| HAVING | Filters groups after grouping |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

```sql
SELECT s.name, e.course
FROM students s
LEFT JOIN enrolments e ON e.student_id = s.id   -- keep every student
WHERE e.course IS NULL;                         -- only those with no enrolment

SELECT s.name, COUNT(e.course)                  -- aggregate per group
FROM students s LEFT JOIN enrolments e ON e.student_id = s.id
GROUP BY s.name;
```
The first finds unmatched students; the second counts enrolments per student.

## Formulas & Algorithms

No formulas in this lecture.

## Key Takeaways

- INNER drops unmatched rows; LEFT keeps them with NULLs.
- IS NULL after a LEFT JOIN finds the missing side.
- WHERE is before grouping, HAVING after.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: sql_joins.pdf. Version: 1.*
