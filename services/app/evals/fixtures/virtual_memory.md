# CSIT203 — Week 5: Virtual Memory

## Overview

Virtual memory is one of the foundational abstractions of modern operating systems. It gives every running process the illusion that it has its own large, private, contiguous address space — even though all processes are actually sharing one physical memory. The hardware and OS cooperate to translate each *virtual* address a program uses into a *physical* address in RAM, and they do this using fixed-size blocks called **pages** (in virtual space) and **frames** (in physical space).

Why does this matter? Because decoupling the program's view of memory from the physical hardware allows programs to be larger than physical RAM, allows processes to be isolated and protected from each other, and lets the OS manage memory flexibly. This week we look at how that translation works, what happens when a page isn't in memory (the **page fault**), and how the OS decides which page to evict when RAM is full (**page replacement policies** like FIFO and LRU). Understanding virtual memory also explains why a "bad" memory access pattern can bring an entire system to a crawl through **thrashing**.

## Key Concepts

### Virtual Address Spaces

Each process sees its own **virtual address space**. When a program computes an address, it isn't referring to a physical RAM location at all — it's an address in that process's private virtual world. The OS and hardware handle the mapping behind the scenes. This abstraction is what makes it safe for many processes to run simultaneously: two processes can each use the "same" virtual address without interfering, because they translate to different physical locations.

### Pages and Frames

Memory is divided into **fixed-size pages** (virtual) and **frames** (physical). Pages and frames are the same size, so a page always maps neatly into a frame of equal size.

With a common page size of **4 KB**, address translation has an elegant property:

- The **low 12 bits** of a virtual address (since 2¹² = 4096 = 4 KB) are the **offset** within the page.
- The remaining **high bits** are the **page number**.

This means the offset never needs translation — it stays the same going from virtual to physical. Only the page number part gets rewritten.

```
virtual address = | page number | offset (12 bits) |
```

### Address Translation via the Page Table

The **page table** maps each page number to a frame number. Translation proceeds as follows:

1. Split the virtual address into page number and offset.
2. Look up the page number in the page table to get the frame number.
3. Concatenate the frame number with the (unchanged) offset to form the physical address.

```
page number --> [page table] --> frame number | offset
```

#### The Valid Bit

Each **page table entry (PTE)** contains a **valid bit**. If the valid bit is 1, the page is in memory and the address lookup succeeds normally. If the valid bit is 0, the page is *not* in memory, and the access raises a **page fault** — a trap to the operating system.

### Page Faults

A **page fault** occurs when a process touches a page whose valid bit is 0. The OS responds by:

1. Loading the page from disk into a free frame.
2. Updating the page table to point to that frame (setting the valid bit).
3. **Restarting the instruction** that faulted, which now completes normally.

#### The Cost of a Page Fault

A page fault costs **millions of cycles** — enormously slower than a normal memory access, which takes only a few. This asymmetry is the central performance fact of virtual memory: the system runs beautifully as long as fault rates stay low, but as the fault rate climbs, the CPU spends ever more time waiting on disk.

#### Thrashing

When the fault rate becomes so high that the system spends most of its time servicing page faults rather than doing useful work, the system is **thrashing**. A thrashing system effectively "crawls" — user-visible responsiveness collapses even though the CPU might technically be busy. Avoiding thrashing is why replacement policy and memory sizing matter so much.

### Page Replacement Policies

When a page fault occurs and **no frame is free**, the OS must choose a **victim** page to evict. Two classic policies:

| Policy | Rule | Idea |
|---|---|---|
| **FIFO** | Evicts the **oldest** page (first one loaded, regardless of use) | Simple bookkeeping; a page that arrived long ago is evicted even if heavily used |
| **LRU** | Evicts the **least recently used** page | Exploits locality: a page untouched recently is likely to go untouched again soon |

The trade-off is simplicity vs. quality: FIFO is cheap to implement but blind to usage patterns; LRU approximates optimal behavior by betting on recent usage predicting future usage.

## Definitions

| Term | Definition |
|---|---|
| Virtual address space | The private address space each process sees, independent of physical memory layout |
| Page | A fixed-size block of a process's virtual address space (e.g., 4 KB) |
| Frame | A fixed-size block of physical memory, same size as a page |
| Offset | The low 12 bits of an address; position within a page or frame |
| Page number | The high bits of a virtual address; identifies which page |
| Page table | Structure mapping each page number to a frame number |
| Page table entry (PTE) | A row of the page table; contains frame number and valid bit |
| Valid bit | PTE flag: 1 = page in memory, 0 = page fault on access |
| Page fault | Trap raised when accessing a page not in memory; OS loads it from disk |
| Page replacement policy | Rule for choosing a victim page when no frame is free (FIFO, LRU) |
| FIFO | Replacement policy that evicts the oldest loaded page |
| LRU | Replacement policy that evicts the least recently used page |
| Thrashing | State where a very high page-fault rate makes the system crawl |

## Diagrams & Visual Descriptions

**Virtual address layout (4 KB pages):**

```
virtual address:
+------------------------+--------------------+
|      page number       |   offset (12 bits) |
+------------------------+--------------------+
                            2^12 = 4096 = 4 KB
```

**Address translation flow:**

```
 virtual address
      |
  +---+--------+
  |            |
page #      offset
  |            | (unchanged)
  v            |
[page table]   |
  |            |
frame #        |
  |            |
  +-----+------+
        v
 physical address = frame # | offset
```

**Page fault handling:**

```
CPU access page --> valid bit = 1? --> yes --> use frame
                       |
                       no
                       v
                   page fault
                       |
         OS loads page from disk into frame
                       |
              update page table
                       |
             restart the instruction
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

**Address decomposition (4 KB pages):**

```
virtual address = page number (high bits) | offset (low 12 bits)
physical address = frame number | offset (offset carried over unchanged)
```

**Translation algorithm:**

1. Extract page number and offset from the virtual address.
2. Check the page table entry: if valid bit = 0, take a page fault.
3. Otherwise read the frame number and concatenate with the offset.

**Page fault cost relationship:** page fault ≈ millions of cycles vs. normal memory access (a few cycles) — hence high fault rates dominate system performance.

## Key Takeaways

- Virtual memory gives each process its own address space while pages/frames map virtual onto physical memory — the core abstraction enabling sharing, protection, and programs larger than RAM.
- With 4 KB pages, translation is beautifully simple: only the high bits (page number) change; the 12-bit offset passes through untouched.
- The page table is the translation workhorse, and its valid bit is the trigger that decides between a fast in-memory access and a page fault.
- A page fault costs millions of cycles; the OS loads the page, updates the table, and restarts the faulting instruction.
- Thrashing — a high fault rate — makes the whole system crawl, so replacement policy choices have system-wide consequences.
- FIFO is simple but ignores usage; LRU bets that the least recently used page is the best eviction candidate.

## Connections

This lecture builds directly on the mechanism it names as its subject — paging — and its page table. The valid bit mechanism it describes (a trap to the OS on invalid access) is an example of how the OS intercepts hardware events, a pattern that recurs throughout operating systems material.

The lecture also leaves the replacement question open in an interesting way: it presents FIFO and LRU as policies for choosing a victim but does not evaluate their performance, which invites comparison in later coverage of memory management policies.

---
*Sources: CSIT203 Week 5 lecture notes (Virtual Memory), pages 0. Version: 1.*
