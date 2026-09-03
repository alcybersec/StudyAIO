"""Fixtures for golden (structural validation) tests."""

import pytest


@pytest.fixture
def sample_manifest():
    """A complete extraction manifest with all expected fields."""
    return {
        "pages": [
            {
                "page_number": 1,
                "text": "CSIT302 Week 5\nNetwork Security Fundamentals",
                "images": [
                    {
                        "filename": "page1_img1.png",
                        "caption": "Network topology diagram",
                        "position": "page_1",
                    }
                ],
            },
            {
                "page_number": 2,
                "text": "Firewalls are network security systems\nthat monitor traffic.",
                "images": [],
            },
            {
                "page_number": 3,
                "text": "Intrusion Detection Systems\nIDS vs IPS comparison",
                "images": [
                    {"filename": "page3_img1.png", "caption": "", "position": "page_3"},
                    {"filename": "page3_img2.png", "caption": "IPS flow", "position": "page_3"},
                ],
            },
        ],
        "metadata": {"extractor_version": "1.0", "source_type": "pdf"},
    }


@pytest.fixture
def sample_summary_md():
    """A valid summary in the v2.0 format produced by `prompts/summarize.txt`.

    The section list and order here are asserted against the prompt itself by
    `TestPromptContract`, so this fixture cannot drift away from what the
    pipeline actually generates without a test failing.
    """
    return """# CSIT302 — Week 5: Network Security Fundamentals

## Overview

Network security is the practice of protecting data in transit across untrusted
networks. It matters because the perimeter is the first place an attacker meets
a defence, and most intrusions begin with traffic that looked legitimate.

This week situates firewalls, intrusion detection and defence-in-depth inside the
broader security architecture introduced in Week 3.

## Key Concepts

### Perimeter Defence

#### Firewalls

A firewall enforces an access control policy between two networks. It matters
because it is the only control that sees every packet crossing the boundary,
which makes it both the cheapest place to block a class of attack and a single
point of failure if misconfigured.

| Type | Inspects | Cost |
|------|----------|------|
| Packet filter | Headers only | Low |
| Stateful | Connection state | Medium |
| Application proxy | Full payload | High |

### Detection and Response

#### IDS versus IPS

An IDS observes and alerts; an IPS sits inline and drops. The trade-off is
latency against containment speed — an inline device that fails closed takes the
network down with it.

## Definitions

| Term | Definition |
|------|-----------|
| Firewall | A network security device that monitors and controls traffic |
| IDS | Intrusion Detection System — passively monitors and alerts |
| IPS | Intrusion Prevention System — actively blocks threats inline |

## Diagrams & Visual Descriptions

```
  Internet
     |
  [Firewall]  <- policy enforcement
     |
  [  IDS  ]   <- passive tap, alerts only
     |
  Internal LAN
```

The tap placement matters: an IDS behind the firewall only sees traffic the
firewall already allowed, which keeps its alert volume manageable.

![Network topology](page1_img1.png)
*Figure 1: Enterprise network security architecture*

## Code Examples

```python
# Evaluate a packet against an ordered rule list.
def filter_packet(packet, rules):
    for rule in rules:          # First match wins — order is the policy.
        if rule.matches(packet):
            return rule.action
    return "deny"               # Default deny: anything unmatched is dropped.
```

This is the shape of every packet filter: an ordered list plus a default action.
The default matters more than the rules — a default-allow filter is not a filter.

## Formulas & Algorithms

False positive rate for a detector over a sample of benign traffic:

```
FPR = FP / (FP + TN)
```

At realistic base rates a detector with a 1% FPR still buries analysts, which is
why alert triage, not detection accuracy, is usually the bottleneck.

## Key Takeaways

- A firewall's default action defines the policy; the rules only carve exceptions out of it.
- Detection without triage capacity produces noise, not security.
- Layering controls matters because each one fails differently.

## Connections

This builds directly on the threat modelling from Week 3: the controls here are
the mitigations for the network-layer threats enumerated there.

Week 6 moves up the stack to application-layer defences, where the payload
inspection an application proxy performs becomes the default rather than the
expensive option.

---
*Sources: CSIT302_Week5.pdf. Version: 1.*
"""


@pytest.fixture
def sample_flashcard_list():
    """A list of flashcard dicts as returned by the agent adapter."""
    return [
        {
            "front": "What is a firewall?",
            "back": "A network security device that monitors and controls incoming and outgoing network traffic based on predefined security rules.",
            "tags": ["networking", "security", "firewall"],
            "source_page_ref": 1,
        },
        {
            "front": "What is the difference between IDS and IPS?",
            "back": "IDS passively monitors and alerts on threats. IPS actively blocks detected threats in real-time.",
            "tags": ["ids", "ips", "detection"],
            "source_page_ref": 3,
        },
        {
            "front": "Name three types of firewalls.",
            "back": "1. Packet filtering\n2. Stateful inspection\n3. Application layer (proxy)",
            "tags": ["firewall", "types"],
            "source_page_ref": 2,
        },
    ]


@pytest.fixture
def sample_quiz_list():
    """A list of quiz question dicts as returned by the agent adapter."""
    return [
        {
            "question_type": "multiple_choice",
            "question": "Which system actively blocks detected threats?",
            "options": [
                "Intrusion Detection System (IDS)",
                "Intrusion Prevention System (IPS)",
                "Firewall",
                "Antivirus Software",
            ],
            "correct_answer": "Intrusion Prevention System (IPS)",
            "explanation": "IPS actively blocks threats in real-time, while IDS only monitors and alerts.",
            "source_page_ref": 3,
        },
        {
            "question_type": "multiple_choice",
            "question": "What does a stateful firewall track?",
            "options": [
                "Only packet headers",
                "The state of active connections",
                "User passwords",
                "DNS records",
            ],
            "correct_answer": "The state of active connections",
            "explanation": "Stateful firewalls maintain a state table tracking active connections.",
            "source_page_ref": 2,
        },
        {
            "question_type": "short_answer",
            "question": "Explain the concept of defence-in-depth in network security.",
            "options": None,
            "correct_answer": "Defence-in-depth is a layered security strategy using multiple independent security controls so that if one layer fails, others continue to provide protection.",
            "explanation": "This strategy ensures no single point of failure in security architecture.",
            "source_page_ref": 3,
        },
    ]
