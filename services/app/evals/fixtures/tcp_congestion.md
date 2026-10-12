# CSIT314 — Week 7: TCP Congestion Control

## Overview

When many computers share the same network link, something has to prevent them from collectively overwhelming it. TCP congestion control is the mechanism by which each sender police its own transmission rate so that shared links do not collapse under load. Every TCP sender maintains a **congestion window (cwnd)** — a limit on how many unacknowledged bytes it may have "in flight" at any moment. This window, combined with the receiver's advertised window, determines how fast data actually flows: the effective send rate is bounded by **min(cwnd, receiver window)**.

Why does this matter? Without congestion control, a sender blasting packets into a congested network only makes things worse — more packets get dropped, retransmissions pile up, and throughput collapses. TCP's elegance lies in treating packet loss as an implicit congestion signal: no router needs to tell the sender anything explicit; dropped packets speak for themselves. This week builds up the classic congestion control algorithm — slow start, congestion avoidance, and the AIMD (additive increase, multiplicative decrease) behaviour that produces TCP's iconic sawtooth throughput graph — and compares how TCP Tahoe and TCP Reno respond differently to loss.

## Key Concepts

### The Congestion Window

TCP must share links with other flows without causing them (or itself) to collapse. The sender's tool for this is the **congestion window (cwnd)**, which caps the amount of unacknowledged data in flight. The sender cannot simply pick a large window up front — it has no idea how much capacity the network path has, and that capacity changes as other flows come and go.

The practical consequence is that the real sending rate is governed by whichever constraint is tighter:

- **cwnd** — the network's tolerance for congestion (sender-side, inferred from loss)
- **receiver window** — how much data the receiver's buffers can accept (receiver-side, advertised explicitly)

Taking the minimum of the two means TCP never exceeds either limit. The rest of the lecture is about how cwnd evolves over time.

### Slow Start: Probing the Network

#### What it does

Slow start begins conservatively: cwnd starts at **one segment** (typically one MSS). The sender sends one segment, waits for its ACK, and then — here's the key mechanism — every ACK received increases cwnd, so the window roughly **doubles every round trip**.

#### Why the name is misleading

Despite the name, slow start growth is **exponential**: 1, 2, 4, 8, 16 segments... It's "slow" only compared to dumping the whole window at once. The doubling happens because each ACK opens the window a little, and the window full of packets generates a window full of ACKs.

#### When it ends

Slow start stops when either:

- **cwnd reaches ssthresh** (the slow start threshold) — transition to congestion avoidance, or
- **a loss occurs** — the loss response kicks in (see below).

### Congestion Avoidance: Additive Increase

Once cwnd reaches **ssthresh**, exponential growth is judged too reckless — the sender is near where congestion was previously detected. Congestion avoidance instead increases cwnd by roughly **one segment per round trip**: **additive increase**. This linear probing is deliberately gentle. If doubling is like driving at 2× speed to find the edge of a cliff, additive increase is edging forward a centimetre at a time.

### Loss as the Congestion Signal

TCP has no explicit feedback from routers about congestion. Instead, **loss is treated as the congestion signal** — a dropped packet is interpreted as "the network was full." The two TCP variants we study differ in how they respond.

#### TCP Tahoe: the drastic response

TCP Tahoe reacts to **any** loss the same way:

1. Set **ssthresh = cwnd / 2** (remember where the cliff was).
2. Drop **cwnd back to one segment**.
3. Re-enter **slow start**.

This is drastic: a **single lost packet costs the whole window**. Even a trivial loss (say, a bit error or reordering) is treated as full-blown congestion, wiping out throughput gains.

#### TCP Reno: distinguishing two kinds of loss

TCP Reno recognises that not all losses look the same:

- **Timeout** — no ACK at all arrives. Reno treats this exactly like Tahoe: halve ssthresh, collapse cwnd to 1, slow start.
- **Three duplicate ACKs** — the receiver keeps ACKing subsequent packets, which arrive fine. If packets are still getting through, the network is **still delivering packets**, so full collapse is unnecessary. Reno performs:
  - **Fast retransmit** — resend the missing segment immediately (inferred from the duplicate ACKs) rather than waiting for a timeout.
  - **Fast recovery** — **halve cwnd** rather than collapsing it to one, then continue in congestion avoidance.

The payoff: a modest loss costs Reno half a window instead of the whole thing, because the duplicate ACKs prove the pipe is still working.

### AIMD and the Sawtooth

The resulting cwnd trajectory is the familiar **sawtooth** graph: slow ramping up (**additive increase**), sharp drops (**multiplicative decrease**), repeated. This pattern is conventionally written **AIMD**. The sawtooth is not a defect — it's the signature of a protocol continuously probing for available bandwidth and backing off when it finds the limit.

## Definitions

| Term | Definition |
|---|---|
| Congestion window (cwnd) | Sender-side limit on the number of unacknowledged bytes in flight, used to avoid overloading the network |
| Receiver window | The receiver's advertised limit on how much data it can accept; combined with cwnd to bound the send rate |
| Effective send rate | Bounded by min(cwnd, receiver window) |
| Slow start | Phase where cwnd starts at one segment and doubles every round trip (exponential growth), ending at ssthresh or on loss |
| Slow start threshold (ssthresh) | The cwnd value at which slow start ends and congestion avoidance begins |
| Congestion avoidance | Phase where cwnd grows additively — roughly one segment per round trip |
| TCP Tahoe | Loss variant that responds to any loss by halving ssthresh, dropping cwnd to one segment, and re-entering slow start |
| TCP Reno | Loss variant that treats timeouts like Tahoe, but on three duplicate ACKs performs fast retransmit and fast recovery |
| Fast retransmit | Resending the missing segment immediately upon three duplicate ACKs, without waiting for a timeout |
| Fast recovery | Halving cwnd (rather than collapsing to one) after fast retransmit |
| Duplicate ACKs | Repeated acknowledgements of the same data, indicating a segment was lost while later ones arrived |
| AIMD | Additive Increase, Multiplicative Decrease — the sawtooth pattern of TCP's cwnd behaviour |

## Diagrams & Visual Descriptions

```
cwnd
 ^
 |            /\        /\
 |           /  \      /  \      <- fast recovery: halve (Reno)
 |          /    \    /    \        on 3 dup-ACKs
 |         /      \  /             timeout: collapse to 1 (both Tahoe/Reno)
 |        /        \/
 |   ssthresh -------,-------------  <- switch slow start -> cong. avoidance
 |      /  exponential doubling   linear +1/RTT
 |     /   (slow start)           (congestion avoidance)
 |    /
 |   /  cwnd = 1 (start)
 +------------------------------------> time
      AIMD: additive increase, multiplicative decrease => sawtooth
```

**Reading the graph:** the initial steep curve is slow start (exponential); above ssthresh the slope flattens to linear (congestion avoidance). Each loss event causes a drop — a sharp vertical collapse for a timeout, a half-height drop for Reno's fast recovery.

```
Loss events and responses:

3 duplicate ACKs (network still delivering):
  Reno:  fast retransmit missing segment -> cwnd = cwnd/2  -> congestion avoidance

Timeout (nothing getting through):
  Tahoe & Reno: ssthresh = cwnd/2 -> cwnd = 1 -> slow start
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

**Effective send rate:**

$$\text{effective send rate} = \min(\text{cwnd},\ \text{receiver window})$$

**Slow start:** cwnd starts at 1 segment and **doubles every round trip** (exponential growth).

**Congestion avoidance:** cwnd grows by ~1 segment per round trip (additive).

**Tahoe / Reno timeout response:**

$$\text{ssthresh} \leftarrow \text{cwnd} / 2, \qquad \text{cwnd} \leftarrow 1 \text{ segment}, \qquad \text{re-enter slow start}$$

**Reno on three duplicate ACKs:** fast retransmit the missing segment, then cwnd ← cwnd/2 (fast recovery).

## Key Takeaways

- A TCP sender's rate is limited by the **minimum of cwnd and the receiver window** — cwnd is the congestion-control knob.
- "Slow start" is actually **exponential** — the name refers to starting at one segment, not the growth rate.
- Loss is TCP's only congestion signal: no explicit router feedback is required.
- Tahoe overreacts to every loss by collapsing the window to one segment — **a single lost packet costs the whole window**.
- Reno exploits three duplicate ACKs as evidence the network still works, enabling **fast retransmit + fast recovery** (halve instead of collapse).
- The result of additive increase + multiplicative decrease is TCP's characteristic **sawtooth (AIMD)** cwnd graph.

## Connections

The lecture frames the problem as "TCP must share a link with other flows without collapsing it" — placing this material in the context of the transport layer's job of managing data delivery over shared network paths. The dependence on receiver windows ties congestion control to TCP's flow-control mechanics, since both windows jointly bound the sending rate. The lecture leaves open finer details of Reno's fast recovery and modern refinements, but within the material presented, Tahoe vs. Reno is the central comparison: the same loss event produces very different window dynamics depending on which variant is running.

---
*Sources: CSIT314 Week 7 lecture slides (TCP Congestion Control), pages 1–3. Version: 1.*
