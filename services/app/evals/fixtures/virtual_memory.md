# CSIT203 — Week 5: Virtual Memory

## Overview

Virtual memory is the mechanism that gives each process the illusion of having its own large, private memory, even though all processes share one physical memory. The lecture explains that each process sees its own *virtual address space*, which the hardware and operating system together translate into actual physical locations [p.1]. This translation is what allows programs to be written as if they own all of memory, while the system quietly manages where things really live.

The topic matters because it underpins how modern systems run many processes at once. To make translation efficient, memory is divided into fixed-size units — *pages* on the virtual side and *frames* on the physical side — and a *page table* maps one to the other [p.1][p.2]. But virtual memory is not only about translation: when a needed page is missing from memory, the system must fetch it from disk, and that operation is enormously expensive, which is why fault handling and page replacement policies like FIFO and LRU are central to system performance [p.3].

## Key Concepts

### Virtual and Physical Memory Layout

#### Pages and Frames

The foundational idea of this week is that both virtual and physical memory are chopped into identically sized pieces. Virtual memory is divided into fixed-size *pages*, and physical memory into matching fixed-size *frames* [p.1]. Because the sizes match, any page can be placed into any frame — the mapping is what the hardware maintains, not the placement.

With 4 KB pages, the address split becomes natural: the low 12 bits of an address are the offset within the page, and the remaining high bits are the page number [p.1]. Why 12 bits? Because 2^12 = 4096 bytes = 4 KB, so exactly 12 bits are needed to select any byte within one page. So every virtual address has the layout [p.1]:

```
virtual address = | page number | offset (12 bits) |
```

This split is the key to how translation works: the page number tells you *which* page, the offset tells you *where within* that page. The offset never changes during translation — only the page number is rewritten.

### Address Translation

#### The Page Table

A page table maps each page number to a frame number [p.2]. Conceptually it is a lookup array indexed by page number, where each entry holds the frame where that page currently resides.

The translation itself is beautifully simple, because of the offset invariance noted above [p.2]:

```
page number --> [page table] --> frame number | offset
```

In words: look up the page number in the page table, take the resulting frame number, and append the unchanged offset [p.2]. For example, if page 5 maps to frame 9, then virtual address (page 5, offset 100) becomes physical address (frame 9, offset 100) — only the page-number part is replaced.

#### The Valid Bit and Page Faults

Each page table entry also holds a *valid bit* [p.2]. This bit answers the question "is this page actually in physical memory right now?" If the valid bit is 0, the page is not in memory, and the access raises a *page fault* [p.2].

A page fault is not an error in the usual sense — it is a normal, recoverable event. But it is a signal that the fast hardware translation path has hit a wall and the operating system must step in.

### Page Fault Handling and Performance

#### The Fault Handling Sequence

On a page fault, the operating system performs three steps [p.3]:

1. Loads the page from disk [p.3].
2. Updates the page table to reflect the new location (setting the entry valid) [p.3].
3. Restarts the instruction that faulted, so it can now complete normally [p.3].

#### The Cost of Faulting: Thrashing

The reason page faults dominate performance discussions is their sheer cost: a page fault costs millions of cycles, compared with a single memory access [p.3]. That is a difference of many orders of magnitude — one fault can wipe out the benefit of millions of ordinary accesses. Consequently, a high fault rate — a condition called *thrashing* — makes the entire system crawl [p.3]. A thrashing system spends nearly all its time moving pages between disk and memory rather than doing useful work.

### Page Replacement

#### Choosing a Victim

When a page fault occurs and no frame is free, something must be evicted. A page replacement policy chooses a victim page [p.3]. The lecture presents two policies:

| Policy | Eviction rule |
|---|---|
| FIFO | Evicts the oldest page (the one that has been in memory longest) [p.3] |
| LRU | Evicts the least recently used page (the one not accessed for the longest time) [p.3] |

The difference is philosophical: FIFO depends only on arrival time, while LRU tries to exploit locality of reference — if a page hasn't been used recently, it's a good bet it won't be needed soon. Choosing a bad victim means the evicted page is likely to fault again soon, feeding the thrashing cycle described above [p.3].

## Definitions

| Term | Definition |
|---|---|
| Virtual address space | The private memory view that each process sees [p.1] |
| Page | A fixed-size unit of virtual memory [p.1] |
| Frame | A fixed-size unit of physical memory [p.1] |
| Offset | The low 12 bits of an address; the position within a page with 4 KB pages [p.1] |
| Page number | The high bits of an address; identifies which page [p.1] |
| Page table | Structure that maps each page number to a frame number [p.2] |
| Valid bit | Page table entry bit; 0 means the page is not in memory and a page fault is raised [p.2] |
| Page fault | Exception raised when an access touches a page not in memory [p.2] |
| Thrashing | A high page-fault rate that makes the system crawl [p.3] |
| Page replacement policy | The rule that chooses a victim page when no frame is free [p.3] |
| FIFO | Replacement policy that evicts the oldest page [p.3] |
| LRU | Replacement policy that evicts the least recently used page [p.3] |

## Diagrams & Visual Descriptions

Virtual address structure and translation pipeline:

```
Virtual address:
+--------------+------------------+
| page number  | offset (12 bits) |
+--------------+------------------+
        |                  |
        v                  |  (offset passes through unchanged)
   [page table]
        |
        v
+--------------+------------------+
| frame number | offset (12 bits) |   Physical address
+--------------+------------------+
```

The diagram captures the whole week in one picture: the page number is translated through the page table, while the offset is copied through unchanged [p.1][p.2].

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

Virtual address layout with 4 KB pages — the low 12 bits are the offset, the high bits the page number [p.1]:

```
virtual address = | page number | offset (12 bits) |
```

Address translation through the page table — look up the page number, take the frame number, append the unchanged offset [p.2]:

```
page number --> [page table] --> frame number | offset
```

Page fault handling sequence [p.3]:

```
1. Load the page from disk
2. Update the page table
3. Restart the instruction
```

Page replacement policies [p.3]:

```
FIFO: evicts the oldest page
LRU:  evicts the least recently used page
```

Named quantitative facts: a page fault costs millions of cycles versus a single memory access [p.3]; a high fault rate is called thrashing and makes the system crawl [p.3].

## Key Takeaways

- Virtual memory decouples the address a program uses from where data physically lives — every process gets its own virtual address space [p.1].
- The 4 KB page size fixes the address split: 12 offset bits, the rest page number — remembering this split makes translation trivial to reason about [p.1].
- Translation replaces only the page number; the offset rides through untouched, so the same offset bits appear in the physical address [p.2].
- The valid bit is how hardware tells the OS "fetch this page for me" — a valid bit of 0 triggers a page fault [p.2].
- A fault is recoverable (load, update table, restart the instruction), but at millions of cycles it must stay rare [p.3].
- Thrashing is the failure mode where faults dominate execution; keeping the fault rate low is the real performance goal [p.3].
- When memory is full, FIFO and LRU are the two victim-selection strategies: oldest-arrived vs. least-recently-used [p.3].

## Connections

This lecture presupposes an understanding of processes and memory hierarchy from earlier course material, since it defines the virtual address space as something "each process sees" [p.1]. The page fault mechanism — load from disk, update the table, restart — sits at the boundary between hardware and the operating system, showing how OS software services exceptions raised by the memory system [p.2][p.3].

The lecture itself does not name any future topics or other weeks, so no further links can be drawn from the source material.

---
*Sources: CSIT203 Week 5 lecture slides, pages 1–3. Version: 1.*
