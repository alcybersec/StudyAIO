# CSIT302 — Week 8: Transactions

## Overview

This week introduces transactions — the mechanism that groups multiple database statements into one logical unit of work [p.1]. Transactions matter because real operations rarely consist of a single statement: as the lecture's example shows, transferring 100 from account A to account B requires two separate updates, and without transactions a crash between them could leave money debited but never credited [p.1][p.3].

The guarantees that make this safe are summarised by the ACID properties: Atomicity, Consistency, Isolation, and Durability [p.1]. Together they explain why the database can be trusted to behave correctly even when failures occur and when many users work concurrently. This week examines each property in turn, with particular depth on isolation (which turns out to be a spectrum, not a switch) and durability (which is implemented with a write-ahead log) [p.2][p.3].

## Key Concepts

### The ACID Properties

A transaction groups statements into one logical unit [p.1]. ACID names the four guarantees that make such a unit reliable:

#### Atomicity — all or nothing

Atomicity means the transaction either completes fully or not at all: a failure rolls back every statement in the unit [p.1]. The lecture's worked example makes this concrete: transferring 100 from account A to account B is two updates, and atomicity ensures that the debit never happens without the credit [p.3]. This is why the classic mid-transfer crash scenario — money leaving A but never arriving in B — cannot occur.

#### Consistency — valid states only

Consistency guarantees that a transaction takes the database from one valid state to another, respecting constraints [p.1]. Even if an application writes a series of intermediate, potentially inconsistent values, the database's constraints must hold before and after the transaction as a whole.

#### Isolation — a spectrum, not a switch

Isolation is not simply on or off; it is a spectrum [p.2]. The lecture identifies two anomalies that appear when isolation is weak:

- A **dirty read** happens when one transaction reads another transaction's uncommitted change [p.2].
- A **non-repeatable read** happens when the same query returns different rows within one transaction [p.2].

The fundamental trade-off is that stronger isolation levels prevent more anomalies but allow less concurrency [p.2]. At the top of the spectrum sits SERIALIZABLE, which gives the result of some serial order of the transactions [p.2] — i.e. the outcome is as if the transactions had run one after another.

#### Durability — surviving a crash

Durability means that once COMMIT returns, the change survives a crash [p.3]. This is achieved with a **write-ahead log**: the log record is flushed to disk before commit returns, and after a crash the log is replayed to redo committed work [p.3]. The ordering is essential — the commit cannot acknowledge success until the log entry is safely on disk, which is what makes the guarantee possible.

### The Isolation Trade-off in Practice

Because stronger isolation reduces concurrency [p.2], choosing a level is an engineering decision: how many anomalies you tolerate against how much parallel throughput you need. SERIALIZABLE sits at one extreme, guaranteeing an outcome equivalent to some serial execution [p.2].

## Definitions

| Term | Definition |
|---|---|
| Transaction | Groups statements into one logical unit [p.1] |
| Atomicity | All or nothing; a failure rolls back every statement [p.1] |
| Consistency | A transaction takes the database from one valid state to another, respecting constraints [p.1] |
| Isolation | A spectrum of guarantees controlling how concurrently running transactions interact [p.2] |
| Durability | Once COMMIT returns, the change survives a crash [p.3] |
| Dirty read | One transaction reads another transaction's uncommitted change [p.2] |
| Non-repeatable read | The same query returns different rows within one transaction [p.2] |
| SERIALIZABLE | Isolation level giving the result of some serial order of the transactions [p.2] |
| Write-ahead log | Log record flushed to disk before commit returns; replayed after a crash to redo committed work [p.3] |

## Diagrams & Visual Descriptions

Durability via write-ahead log, as described in the lecture [p.3]:

```
Transaction commits
        |
        v
Log record flushed to disk
        |
        v
COMMIT returns
        |
   (crash occurs)
        |
        v
Log replayed -> committed work redone
```

And the transfer example [p.3]:

```
BEGIN
  UPDATE A: debit 100   \
                          atomicity: both or neither
  UPDATE B: credit 100  /
COMMIT
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

Worked example from the lecture [p.3]:

```
Example: transfer 100 from account A to B is two updates;
atomicity ensures that the debit never happens without the credit.
```

Key properties (no numeric formulas in this lecture):

```
SERIALIZABLE: gives the result of some serial order of the transactions
Durability: log record flushed to disk BEFORE commit returns;
            after a crash, log is replayed to redo committed work
```

## Key Takeaways

- A transaction makes multi-statement operations behave as a single all-or-nothing unit, which is what makes operations like transfers safe [p.1].
- Atomicity and Consistency protect against failures and constraint violations; Durability protects committed results against crashes [p.1][p.3].
- Isolation is a spectrum: dirty reads and non-repeatable reads are the anomalies of weak isolation, and stronger levels trade concurrency for correctness [p.2].
- SERIALIZABLE is the strongest level: the outcome equals some serial order of the transactions [p.2].
- The write-ahead log is the mechanism behind durability — flush the log before acknowledging commit, then replay after a crash [p.3].

## Connections

This lecture frames ACID as the foundation for trustworthy multi-statement database work [p.1]. Within the lecture, atomicity and durability are tied together by the same failure-recovery story: the transfer example shows what atomicity must prevent [p.3], while the write-ahead log shows how durability delivers it [p.3]. The isolation discussion raises the concurrency trade-off (stronger isolation means less concurrency [p.2]) without going further into how levels are implemented.

---
*Sources: CSIT302 Week 8 lecture slides (Transactions). Version: 1.*
