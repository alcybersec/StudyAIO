# CSIT302 — Week 8: Transactions and ACID

## Overview

Transactions make multi-statement changes safe. The lecture explains the four ACID properties and stresses that isolation is a spectrum rather than a switch.

## Key Concepts

### Atomicity and consistency

A transaction groups statements into one logical unit. Atomicity is all or nothing: a failure rolls back every statement. Consistency means the transaction takes the database from one valid state to another, respecting constraints. In the transfer of 100 from account A to B, atomicity ensures the debit never happens without the credit.

### Isolation

Isolation is a spectrum, not a switch. Without it a dirty read occurs when one transaction reads another's uncommitted change, and a non-repeatable read when the same query returns different rows within one transaction. Stronger levels prevent more anomalies but allow less concurrency. SERIALIZABLE gives the result of some serial order of the transactions.

### Durability

Once COMMIT returns, the change survives a crash. A write-ahead log makes this work: the log record is flushed to disk before commit returns, and after a crash the log is replayed to redo committed work.

## Definitions

| Term | Definition |
|---|---|
| Atomicity | All statements apply or none do |
| Consistency | Moves the database between valid states |
| Isolation | Degree to which concurrent transactions are shielded from each other |
| Durability | Committed changes survive a crash |
| Write-ahead log | Log flushed to disk before commit returns |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

No formulas in this lecture.

## Key Takeaways

- Isolation is a spectrum with a concurrency price.
- Durability rests on the write-ahead log flush.
- Atomicity keeps a transfer's two halves together.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: acid_transactions.pdf. Version: 1.*
