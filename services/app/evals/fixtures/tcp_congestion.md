# CSIT314 — Week 7: TCP Congestion Control

## Overview

TCP must share a link without collapsing it. The sender limits data in flight with a congestion window and treats loss as the congestion signal.

## Key Concepts

### The congestion window

The sender keeps a congestion window (cwnd) limiting unacknowledged bytes in flight; the effective send rate is min(cwnd, receiver window).

### Growth phases

Slow start begins at one segment and doubles cwnd every round trip. Despite the name it is exponential growth, ending at the slow start threshold (ssthresh) or on a loss. After ssthresh, congestion avoidance adds roughly one segment per round trip: additive increase.

### Reacting to loss

TCP Tahoe responds to any loss by setting ssthresh to half of cwnd, dropping cwnd to one segment and re-entering slow start, so one lost packet costs the whole window. TCP Reno separates timeouts, treated as in Tahoe, from three duplicate ACKs, which suggest packets are still arriving. Reno then does fast retransmit, resending the missing segment at once, followed by fast recovery that halves cwnd instead of collapsing it.

The cwnd graph is a sawtooth: additive increase, multiplicative decrease (AIMD).

## Definitions

| Term | Definition |
|---|---|
| cwnd | Congestion window: limit on unacknowledged bytes in flight |
| ssthresh | Slow start threshold |
| Fast retransmit | Resend a segment after three duplicate ACKs |
| AIMD | Additive increase, multiplicative decrease |

## Diagrams & Visual Descriptions

```
cwnd
 |      /|      /|
 |    /  |    /  |
 |  /    |  /    |
 |/      |/      |
 +----------------> time   (AIMD sawtooth)
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

send rate = min(cwnd, receiver window). Slow start: cwnd doubles per round trip. Congestion avoidance: cwnd + 1 segment per round trip.

## Key Takeaways

- Loss is the congestion signal.
- Reno halves; Tahoe collapses to one segment.
- AIMD produces the sawtooth.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: tcp_congestion.pdf. Version: 1.*
