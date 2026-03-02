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
    """A valid summary markdown with all 8 required sections."""
    return """# CSIT302 — Week 5: Network Security Fundamentals

## Key Concepts
- Firewalls filter network traffic based on predefined rules
- IDS monitors traffic for suspicious activity
- IPS actively blocks detected threats

## Definitions

| Term | Definition |
|------|-----------|
| Firewall | A network security device that monitors and controls traffic |
| IDS | Intrusion Detection System — passively monitors and alerts |
| IPS | Intrusion Prevention System — actively blocks threats |

## Code Examples

```python
# Simple packet filter example
def filter_packet(packet, rules):
    for rule in rules:
        if rule.matches(packet):
            return rule.action
    return "deny"
```

## Diagrams & Figures

![Network topology](page1_img1.png)
*Figure 1: Enterprise network security architecture*

## Potential Exam Topics
- Compare and contrast IDS vs IPS
- Explain the three types of firewalls
- Describe a defence-in-depth strategy

## Summary

Network security is a critical component of cybersecurity. This week covers firewalls,
intrusion detection and prevention systems, and defence-in-depth strategies.

Understanding the layered approach to network security is essential for building
resilient enterprise systems.

---
**Sources:** CSIT302_Week5.pdf | **Version:** 1 | **Generated:** 2025-01-15
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
