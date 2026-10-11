# CSIT302 — Week 8: Transactions

## Overview

A **transaction** is the database's fundamental unit of reliability: a group of statements bundled together so they execute as one logical unit. Week 8 introduces why this matters. Consider the classic example of transferring 100 from account A to account B — this is really *two* updates: a debit on A and a credit on B. If the system crashes between them, money vanishes. Transactions exist precisely to make such partial outcomes impossible.

The lecture organises transaction guarantees around the **ACID** properties: Atomicity, Consistency, Isolation, and Durability. Each addresses a different way a database could go wrong — partial execution, constraint violations, interleaved concurrent access, and lost writes after crashes. Understanding ACID means understanding not just what each property promises, but *how* the database delivers it (e.g., rollback for atomicity, a write-ahead log for durability) and what trade-offs it involves (stronger isolation means less concurrency).

## Key Concepts

### The Transaction as a Logical Unit

A transaction groups statements so that the database treats them as indivisible work. This abstraction lets an application reason about multi-step operations ("transfer money", "place an order") as if they were single, reliable actions. Without transactions, every failure mid-way through a multi-step operation leaves the database in an arbitrary, possibly corrupt intermediate state that the application would have to detect and repair itself.

### Atomicity — All or Nothing

Atomicity guarantees that either *every* statement in a transaction takes effect or *none* does. If a failure occurs partway through, the transaction **rolls back** — every statement it executed is undone.

The lecture's running example makes this concrete: transferring 100 from A to B is two updates. Atomicity ensures the **debit never happens without the credit**. There is no window in which A has lost 100 but B has not gained it. This is what allows developers to write business logic as a straightforward sequence of statements without hand-writing compensation code for every possible failure point.

### Consistency — Valid State to Valid State

Consistency says a transaction moves the database from one **valid state to another valid state**, respecting all declared constraints. In other words, even if the intermediate steps of a transaction would violate a rule (say, a temporary negative balance during the transfer computation), the state *before* the transaction and the state *after* it both satisfy every constraint.

It's worth noting the division of responsibility here: atomicity is enforced entirely by the database, while consistency is a contract — the database enforces the constraints, but the transaction's logic must be written so the constraints are preserved. A badly written transaction (crediting the wrong account, for example) is still atomic and durable; it's just consistently wrong.

### Isolation — A Spectrum, Not a Switch

Isolation governs what happens when multiple transactions run concurrently. Crucially, the lecture frames isolation as a **spectrum**: stronger levels prevent more anomalies but permit less concurrency. This is an engineering trade-off, not a binary choice.

#### Anomalies Without Isolation

- **Dirty read** — one transaction reads another transaction's *uncommitted* change. If the writer later rolls back, the reader has acted on data that never officially existed.
- **Non-repeatable read** — the *same query* returns different rows within one transaction, because another transaction committed a change in between. A transaction that assumed stable data mid-execution can draw inconsistent conclusions.

#### Isolation Levels

Stronger isolation levels prevent more of these anomalies. The strongest level, **SERIALIZABLE**, guarantees that the result is equivalent to executing the transactions in *some serial order* — as if they had run one after another with no interleaving. This is the gold standard of correctness, achieved at the cost of concurrency: the more the database must prevent interleaving effects, the more it must delay or block transactions, reducing throughput.

| Isolation strength | Anomalies prevented | Concurrency |
|---|---|---|
| Weaker levels | Fewer (dirty reads, non-repeatable reads possible) | Higher |
| SERIALIZABLE | All (behaves like a serial execution) | Lower |

### Durability — Surviving the Crash

Durability promises that **once COMMIT returns, the change survives a crash** — power loss, process death, anything short of physical disk destruction. The user of the database needs this guarantee to trust the acknowledgement of a commit.

#### The Write-Ahead Log (WAL)

Databases achieve durability with a **write-ahead log**: the log record describing the change is **flushed to disk before COMMIT returns**. The rule is "log first, data later" — the durable record of the change exists before the system claims success. After a crash, the database **replays the log to redo committed work**, reconstructing any changes whose data pages hadn't yet been written when the system died.

This design explains a subtle performance point: a commit is only as fast as a disk flush of the log record, which is why the log is kept small and sequential. The expensive random writes to data files can happen lazily, because the log can always recover them.

## Definitions

| Term | Definition |
|---|---|
| Transaction | A grouping of statements into one logical unit of work executed atomically by the database |
| ACID | The four transaction guarantees: Atomicity, Consistency, Isolation, Durability |
| Atomicity | All-or-nothing execution; a failure rolls back every statement in the transaction |
| Rollback | The undoing of all statements executed by a failed transaction |
| Consistency | A transaction takes the database from one valid state to another, respecting constraints |
| Isolation | The degree to which concurrent transactions are prevented from observing each other's intermediate effects |
| Dirty read | Reading another transaction's uncommitted change |
| Non-repeatable read | The same query returning different rows within a single transaction |
| SERIALIZABLE | The isolation level whose result equals some serial order of the transactions |
| Durability | Once COMMIT returns, the change survives a crash |
| Write-ahead log (WAL) | A log flushed to disk before commit returns; replayed after a crash to redo committed work |
| COMMIT | The operation that makes a transaction's changes permanent |

## Diagrams & Visual Descriptions

**Atomicity of a transfer (all-or-nothing):**

```
Transaction: transfer 100 from A to B

  BEGIN
    UPDATE A: A -= 100   ──┐
    UPDATE B: B += 100   ──┤ treated as ONE unit
  COMMIT                  ──┘

  Success path:   A debit  ──► B credit  ──► COMMIT ok
  Failure path:   A debit  ──► ✖ crash    ──► ROLLBACK (debit undone)
                                 └── debit NEVER persists without credit
```

**Durability via write-ahead log:**

```
1. UPDATE statements execute        (in memory)
2. Log record flushed to DISK       (must complete first)
3. COMMIT returns to caller         ← guarantee point
4. Data pages written lazily

Crash after step 2:  replay log → redo committed work ✔
Crash before step 2: transaction never committed → no effect ✔
```

**The isolation spectrum:**

```
Weaker ────────────────────────────────────────► Stronger
[ dirty reads possible ] ... [ SERIALIZABLE ]
More concurrency ◄────────────► Less concurrency
```

## Code Examples

No code examples in this lecture. (The transfer example can be sketched as:

```sql
BEGIN;
  UPDATE accounts SET balance = balance - 100 WHERE id = 'A';  -- debit
  UPDATE accounts SET balance = balance + 100 WHERE id = 'B';  -- credit
COMMIT;  -- log flushed to disk before this returns
```

The point: if anything fails between the two updates, the whole transaction rolls back, so the debit never happens without the credit.)

## Formulas & Algorithms

No formulas in this lecture. The key algorithmic idea is the **write-ahead logging protocol**:

1. Execute transaction statements.
2. Flush log record to disk.
3. Return from COMMIT.
4. After a crash: replay the log to redo committed work.

## Key Takeaways

- A transaction makes multi-step operations (like a two-update money transfer) behave as a single reliable unit — this is the foundation of database reliability.
- Atomicity eliminates the "partial update" failure mode: the debit can never persist without the credit.
- Consistency is a contract between the database (enforcing constraints) and the transaction logic (preserving validity across its execution).
- Isolation is a spectrum, not a switch: dirty reads and non-repeatable reads are the anomalies weaker levels allow; SERIALIZABLE eliminates all interleaving effects but reduces concurrency.
- Durability is delivered by the write-ahead log: the log hits disk before COMMIT returns, and the log is replayed after a crash to redo committed work.
- Every ACID property is a trade-off or a mechanism: stronger guarantees (isolation, durability) cost concurrency or write latency — understanding *how* they're implemented explains *why* they cost what they do.

## Connections

This lecture is foundational within the database subject: transactions and their ACID properties are the framework that later database material — concurrency control, recovery, and physical logging — hangs off. The lecture itself points forward in two places: it notes that isolation levels form a spectrum whose enforcement mechanisms (how the database actually prevents dirty and non-repeatable reads) are a natural next topic, and it introduces the write-ahead log, noting that "after a crash the log is replayed to redo committed work" — which is the entry point into recovery techniques.

*Sources: CSIT302 Week 8 lecture content (Transactions). Version: 1.*
