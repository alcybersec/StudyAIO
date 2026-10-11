# CSIT203 — Week 5: Virtual Memory and Paging

## Overview

Virtual memory gives every process its own address space, mapped to physical frames through a page table.

## Key Concepts

### Pages and frames

Memory is divided into fixed-size pages (virtual) and frames (physical). With 4 KB pages the low 12 bits of a virtual address are the offset within the page and the high bits are the page number.

### Translation

A page table maps each page number to a frame number. The hardware looks up the page number, takes the frame number and appends the unchanged offset. Each entry holds a valid bit; if it is 0 the page is not in memory and the access raises a page fault.

### Faults and replacement

On a page fault the operating system loads the page from disk, updates the page table and restarts the instruction. A fault costs millions of cycles compared with a memory access, so a high fault rate (thrashing) makes the system crawl. When no frame is free a replacement policy picks a victim: FIFO evicts the oldest page, LRU the least recently used.

## Definitions

| Term | Definition |
|---|---|
| Page | Fixed-size block of virtual memory |
| Frame | Fixed-size block of physical memory |
| Page table | Maps page numbers to frame numbers |
| Valid bit | 0 means the page is not in memory |
| Thrashing | A high page-fault rate that makes the system crawl |

## Diagrams & Visual Descriptions

```
virtual address = | page number | offset (12 bits) |

page number --> [ page table ] --> frame number | offset
```
The offset passes through unchanged; only the page number is translated.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

With 4 KB pages: offset = low 12 bits; page number = remaining high bits.

## Key Takeaways

- The page table translates page numbers; offsets pass through.
- A valid bit of 0 raises a page fault.
- Thrashing comes from too many faults.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: virtual_memory.pdf. Version: 1.*
