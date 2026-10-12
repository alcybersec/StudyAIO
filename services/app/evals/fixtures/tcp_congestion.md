# CSIT314 — Week 7: TCP Congestion Control

## Overview

When many senders share the same network link, each must limit how aggressively it transmits — otherwise the link collapses under the combined load. TCP solves this by having each sender maintain a congestion window (`cwnd`) that caps the number of unacknowledged bytes it may have in flight; the sender's effective rate is therefore `min(cwnd, receiver window)`, i.e. whichever limit is tighter — the network's or the receiver's [p.1].

This week traces how TCP grows and shrinks that window in response to network conditions. The story has three phases: **slow start** (exponential probing at the beginning of a connection), **congestion avoidance** (cautious linear growth once a safe level is reached), and **loss response**, where the classic Tahoe and Reno implementations differ sharply in how drastically they cut back. The overall behavior that emerges is the famous AIMD sawtooth [p.1][p.2][p.3].

## Key Concepts

### The Congestion Window

TCP cannot know in advance how much capacity the network has, so it must discover and continuously adapt to it. The sender keeps `cwnd`, limiting unacknowledged bytes in flight; the effective send rate is `min(cwnd, receiver window)` — you are throttled by the stricter of network congestion and the receiver's ability to accept data [p.1].

### Slow Start: Exponential Probing

Slow start begins with `cwnd` of one segment and **doubles it every round trip** [p.1]. Despite the modest name, this is exponential growth — the window ramps up quickly because TCP assumes capacity is available until proven otherwise. This phase cannot continue forever: it ends when `cwnd` reaches the **slow start threshold** (`ssthresh`), or when a loss occurs, whichever comes first [p.1].

### Congestion Avoidance: Additive Increase

Once `cwnd` reaches `ssthresh`, the exponential doubling stops. Congestion avoidance increases `cwnd` by roughly **one segment per round trip** — additive rather than multiplicative growth [p.2]. The intuition: we have probed up to a suspected safe level, so now we inch forward, gently testing for more capacity without risking a collapse.

### Loss as the Congestion Signal

TCP treats packet loss as the signal that the network is congested [p.2]. How a TCP implementation reacts to loss defines its character:

#### TCP Tahoe — Drastic Response

On **any** loss, Tahoe:

1. Sets `ssthresh` to half of `cwnd` [p.2].
2. Drops `cwnd` back to one segment [p.2].
3. Re-enters slow start [p.2].

This is drastic: a single lost packet costs the whole window, and the connection must climb back from scratch through exponential growth [p.2].

#### TCP Reno — Two Kinds of Loss

Reno distinguishes two kinds of loss [p.3]:

| Loss type | Signal | Reno's response |
|---|---|---|
| Timeout | No ACKs arriving at all | Treated exactly as Tahoe treats any loss [p.3] |
| Three duplicate ACKs | Packets are still being delivered | **Fast retransmit**: resend the missing segment immediately; **fast recovery**: halve `cwnd` rather than collapsing it to one [p.3] |

The insight behind Reno is that three duplicate ACKs prove the network is still delivering packets — only one segment went missing — so a full collapse to slow start is unnecessary. The connection merely halves its window and keeps going [p.3].

### AIMD: The Sawtooth

The resulting `cwnd` graph is the familiar sawtooth: **additive increase, multiplicative decrease**, written **AIMD** [p.3]. The window climbs slowly and linearly (one segment per RTT), then drops sharply (halving on loss) — producing the characteristic rising slopes with sudden cliff edges.

## Definitions

| Term | Definition |
|---|---|
| Congestion window (`cwnd`) | Sender-side limit on unacknowledged bytes in flight, used to share the link without collapsing it [p.1] |
| Effective send rate | `min(cwnd, receiver window)` — the binding constraint on how fast TCP may send [p.1] |
| Slow start | Phase starting with `cwnd` of one segment, doubling it every round trip (exponential growth) [p.1] |
| Slow start threshold (`ssthresh`) | Window level at which slow start ends and congestion avoidance begins [p.1][p.2] |
| Congestion avoidance | Phase where `cwnd` grows by roughly one segment per round trip [p.2] |
| TCP Tahoe | Loss response: `ssthresh = cwnd/2`, `cwnd` reset to one segment, re-enter slow start on any loss [p.2] |
| TCP Reno | Distinguishes timeouts (Tahoe response) from three duplicate ACKs (fast retransmit + halve `cwnd`) [p.3] |
| Fast retransmit | Resending the missing segment immediately upon three duplicate ACKs [p.3] |
| Fast recovery | Reno's halving of `cwnd` instead of collapsing to one segment [p.3] |
| AIMD | Additive increase, multiplicative decrease — the sawtooth pattern of `cwnd` over time [p.3] |

## Diagrams & Visual Descriptions

The AIMD sawtooth — slow linear climbs (congestion avoidance) punctuated by sharp drops (multiplicative decrease on loss) [p.2][p.3]:

```
cwnd
 |            /\        /\
 |           /  \      /  \      <- additive increase (one segment per RTT)
 |          /    \    /    \
 |         /      \  /      \   <- multiplicative decrease (halve on loss)
 |  /\    /        \/        \
 | /  \  /                  (Reno)   ...or drop to 1 and slow start
 |/    \/                          again (Tahoe)
 +-----------------------------------> time (round trips)
```

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

Effective send rate:

```
effective send rate = min(cwnd, receiver window)
```
[p.1]

Slow start dynamics — initial condition and growth rule [p.1]:

```
cwnd starts at one segment
each round trip: cwnd doubles (exponential growth)
end when: cwnd reaches ssthresh, OR a loss occurs
```

Congestion avoidance growth rule [p.2]:

```
each round trip: cwnd increases by roughly one segment
```

TCP Tahoe loss response [p.2]:

```
on any loss:
    ssthresh = cwnd / 2
    cwnd     = 1 segment
    re-enter slow start
```

TCP Reno loss response [p.3]:

```
on timeout:
    respond as Tahoe does (ssthresh = cwnd/2, cwnd = 1, slow start)
on three duplicate ACKs:
    fast retransmit: resend the missing segment immediately
    fast recovery:   cwnd = cwnd / 2   (not reset to one)
```

Named property: the overall behavior is additive increase, multiplicative decrease (AIMD), giving a sawtooth `cwnd` graph [p.2][p.3].

## Key Takeaways

- TCP self-regulates: `cwnd` makes the sender's rate `min(cwnd, receiver window)`, so congestion control and flow control compose into one effective limit [p.1].
- "Slow" start is a misnomer — it is exponential doubling, ending at `ssthresh` or on loss [p.1].
- After `ssthresh`, growth becomes cautious and linear: one segment per round trip [p.2].
- Loss is the congestion signal; Tahoe's response is drastic — one lost packet costs the whole window [p.2].
- Reno's innovation is recognizing that duplicate ACKs mean the network still works, so only halve `cwnd` instead of collapsing [p.3].
- The emergent AIMD sawtooth is the visual signature of TCP congestion control [p.3].

## Connections

Within this lecture, congestion control is presented alongside the receiver window: the two combine via `min(cwnd, receiver window)`, connecting this week's material to flow control as part of TCP's overall rate management [p.1]. The lecture itself frames Tahoe and Reno as successive refinements of the same loss-response mechanism — Reno keeps Tahoe's timeout behavior and adds fast retransmit/fast recovery on top of it [p.2][p.3].

This lecture does not link to other weeks of the course.

---
*Sources: CSIT314 Week 7 lecture slides, pages 1–3. Version: 1.*
