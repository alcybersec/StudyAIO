# CSIT302 — Week 1: Security Posture, Incident Response Process & Cybersecurity Strategy

> **Source files:** CSIT302_Week1.pdf, CSIT302_Week1_v2.pdf
> **Date summarized:** 2026-02-24

## Overview

This opening lecture introduces CSIT302 Cybersecurity, establishing the foundational concepts that underpin the entire course. It covers the distinction between information security and cybersecurity, the CIA Triad, the current threat landscape and its challenges, and how organisations enhance their security posture through Zero Trust Architecture, Red/Blue Team exercises, and structured Incident Response processes. The lecture concludes with cybersecurity strategy — how to assess risk, plan defence, and build a proactive security culture. These topics form the conceptual bedrock for all subsequent weeks, which dive into specific attack and defence techniques.

## Key Concepts

### Course Structure and Context

- **Course:** CSIT302 Cybersecurity, taught by Dr. Mouhannad ALATTAR and Dr. Manoj Kumar.
- **Textbook:** Y. Diogenes and E. Ozkaya, *Cybersecurity -- Attack and Defense Strategies*, Packt Publishing, 2018.
- **Learning Outcomes:**
  - LO1--LO4 covering cybersecurity issues, principles, understanding, and solutions.
- **Weekly Topics (Weeks 1--11):** Security Posture, Kill Chain, Reconnaissance, Compromising Systems, Identity, Lateral Movement, Privilege Escalation, Security Policy, Network Segmentation, Active Sensors, Threat Intelligence, Vulnerability Management, Log Analysis.
- **Assessments:** Labs 25%, Quiz 10%, Report + Presentation 15%, Final Exam 50%.

### Information Security vs. Cybersecurity

- **Information Security** is the broader discipline, defined by frameworks such as COBIT and NIST SP 800-53. It encompasses the protection of all information assets regardless of form (digital, physical, verbal).
- **Cybersecurity** is a subcategory of information security (first known use of the term: 1989). It focuses specifically on the protection of internet-connected systems, including hardware, software, and data, from cyber threats.
- Understanding this distinction matters because cybersecurity strategies operate within the wider governance and risk management structures of information security.

### The CIA Triad

The CIA Triad is the foundational model for information security. Every security control, policy, or architecture decision maps back to one or more of these three properties:

- **Confidentiality** — Ensuring that information is accessible only to those authorised to view it. Controls include encryption, access control lists, and classification schemes.
- **Integrity** — Ensuring that information is accurate, complete, and has not been tampered with. Controls include hashing, digital signatures, and version control.
- **Availability** — Ensuring that information and systems are accessible to authorised users when needed. Controls include redundancy, failover, backups, and DDoS mitigation.

### Basic Cybersecurity Principles

1. **Keep It Simple** — Overly complex architectures create hidden attack surfaces and are harder to audit. Simple designs are easier to secure and maintain.
2. **Defence in Depth** — Layer multiple independent security controls so that if one fails, others still protect the asset. Analogous to a medieval castle: moat, high walls, inner walls, watchtowers, identity checks, limited entry points.
3. **Zero Trust** — Never assume any user, device, or network segment is inherently trustworthy. Every access request must be verified regardless of origin.
4. **Think Like an Adversary** — Anticipate attack techniques by adopting the attacker’s perspective. This mindset drives proactive security measures rather than purely reactive ones.

### Current Threat Landscape

The modern threat landscape is shaped by several converging trends:

- **Remote Access and BYOD (Bring Your Own Device):** The expansion of remote work has created at least four distinct entry points into corporate environments, each requiring its own risk assessment. Personal devices accessing corporate resources blur the traditional network perimeter.
- **Cloud Computing Adoption:** The shift to IaaS (Infrastructure as a Service) and SaaS (Software as a Service) introduces new shared-responsibility risks. Organisations must understand what they control versus what the cloud provider controls.
- **Personal Device Risks:** Email access from personal devices, use of SaaS applications, and password reuse across personal and corporate accounts all increase exposure.
- **Credential as the New Perimeter:** With traditional network perimeters dissolving, identity and credentials have become the primary control point. Countermeasures include Multi-Factor Authentication (MFA) and continuous monitoring of authentication events.
- **Application Security Concerns:**
  - In-house applications (custom-built, potentially unaudited)
  - SaaS applications (third-party risk)
  - BYOD personal applications (unmanaged)
  - Shadow IT (applications adopted without IT approval)
- **Data Threats and Countermeasures:**
  - Data at rest (on device) — encrypt local storage
  - Data in transit — use SSL/TLS and encrypted tunnels
  - Data at rest (on-premises or cloud) — encrypt server-side storage, manage keys properly

### Cybersecurity Challenges

- **Top causes of security incidents:** Viruses/malware/Trojans, untrained employees, phishing and social engineering, targeted attacks, crypto-ransomware.
- **Humans are the weakest link** — Technical controls are only as strong as the people who use (or circumvent) them. Security awareness training is essential.
- **WannaCry Ransomware (May 2017):** Infected over 400,000 machines worldwide. It exploited a vulnerability in SMBv1 (Server Message Block version 1) that Microsoft had patched 59 days before the outbreak. The incident demonstrated the critical importance of timely patch management.
- **Government-Sponsored Attacks:** Nation-state actors possess significant resources and conduct advanced persistent threats (APTs) targeting critical infrastructure, intellectual property, and political targets.
- **Real-World Case Studies:**
  - **T-Mobile breaches** — resulted in a $31.5 million FCC settlement, illustrating regulatory consequences.
  - **MGM/Caesars hacks** — caused over $100 million in combined losses, showing the business impact of successful attacks on large enterprises.
  - **Facebook--Cambridge Analytica** — demonstrated data privacy violations at scale and the reputational/legal consequences of inadequate data protection.

### Enhancing Security Posture

Security Posture is the overall cybersecurity strength and readiness of an organisation. It is composed of three pillars operating in a continuous cycle:

- **Protection** — Preventive controls that stop attacks before they succeed (firewalls, encryption, access controls, hardening).
- **Detection** — Monitoring and alerting mechanisms that identify attacks in progress or indicators of compromise (SIEM, IDS/IPS, log analysis, anomaly detection).
- **Response** — The processes and actions taken to contain, eradicate, and recover from a security incident (incident response plans, forensics, remediation).

These three form a continuous cycle: Protection -> Detection -> Response -> (feed lessons back into) Protection.

### Zero Trust Architecture (NIST 800-207)

Zero Trust is a security model that eliminates the concept of a trusted internal network. Its core tenets:

- There are no inherently trusted networks — even internal traffic must be verified.
- Device diversity is assumed — the network must handle managed, unmanaged, and BYOD devices securely.
- No resource is inherently trusted — every resource access request is evaluated.
- Security policies must be consistent — applied uniformly regardless of user location or device.
- **Identity is the new perimeter** — authentication and authorisation are the primary gatekeepers.
- **Dynamic Trust:** Access decisions depend on context (who, what device, where, when, what resource, what behaviour pattern). Trust is not binary; it is continuously evaluated.

The six areas covered by Zero Trust verification:

1. **Infrastructure** — servers, containers, cloud services
2. **Identities** — users, service accounts, machine identities
3. **Devices** — endpoints, IoT, mobile
4. **Data** — classification, labelling, encryption
5. **Networks** — micro-segmentation, encrypted channels
6. **Applications** — API security, runtime protection

### Cloud Security Posture Management (CSPM)

CSPM is a category of tools and practices for managing security in cloud environments:

- **Compliance assessment** — continuously checking cloud configurations against regulatory and policy requirements.
- **Operational monitoring** — real-time visibility into cloud resource states and changes.
- **DevSecOps integration** — embedding security checks into CI/CD pipelines so misconfigurations are caught before deployment.
- **Multi-Cloud Security Challenges:** When organisations use multiple cloud providers, they face reduced visibility, increased complexity, and inconsistent security tooling across platforms.

### Red Team and Blue Team

Organisations use adversarial simulation to test and improve their defences:

**Red Team (Offensive):**
- Performs penetration testing and attack simulation.
- Uses real-world attack techniques to probe defences.
- Key Metrics:
  - **MTTC (Mean Time to Compromise)** — How quickly the Red Team can gain initial access.
  - **MTTP (Mean Time to Privilege Escalation)** — How quickly initial access can be escalated to higher privileges.

**Blue Team (Defensive):**
- Responsible for defence, detection, and response.
- Maintains internal network security.
- Key Metrics:
  - **ETTD (Estimated Time to Detection)** — How long it takes to detect an intrusion.
  - **ETTR (Estimated Time to Recovery)** — How long it takes to fully recover from an incident.

**Blue Team Actions Upon Breach Detection:**
1. Save evidence (preserve logs, memory dumps, disk images)
2. Validate evidence and identify Indicators of Compromise (IOCs)
3. Engage relevant teams (management, legal, PR, external responders)
4. Triage the incident (assess severity and impact)
5. Scope the breach (determine what was affected)
6. Develop a remediation plan
7. Execute the remediation plan

**Assume Breach Methodology:** Rather than treating security testing as a one-off exercise, organisations should operate under the assumption that a breach has already occurred or will occur. This drives continuous testing, monitoring, and improvement.

### Incident Response (IR) Process

An incident is defined as a violation or imminent threat of violation of computer security policies, acceptable use policies, or standard security practices.

**IR is not "one size fits all"** — the process must be tailored to the organisation’s size, industry, regulatory requirements, and risk profile.

**Foundational Areas of an IR Plan:**
- Objective — what the IR plan aims to achieve
- Scope — what systems, data, and personnel are covered
- Definitions and Terminology — shared vocabulary to avoid confusion during incidents
- Roles and Responsibilities — who does what (incident commander, analysts, communications, legal)
- Priorities and Severity Levels — how incidents are classified and escalated

**IR Team Composition:** Varies by company size. Smaller organisations may outsource IR to managed security service providers (MSSPs) with defined Service Level Agreements (SLAs).

**Incident Lifecycle (four phases):**

1. **Preparation** — Building IR capabilities before incidents occur. Includes creating playbooks, training staff, deploying detection tools, and establishing communication channels.
2. **Detection** — Identifying that an incident is occurring. Detection systems must understand attack vectors and learn dynamically. Sources include:
   - End users reporting suspicious activity
   - Log correlation across endpoints, servers, firewalls, and network devices
   - Establishing baselines for normal behaviour so anomalies can be flagged
3. **Containment** — Limiting the damage of an ongoing incident. May involve isolating affected systems, blocking malicious IPs, or disabling compromised accounts.
4. **Post-Incident Activity** — Learning from the incident to improve future response:
   - Document lessons learned
   - Key questions: Who identified the incident? Was the right priority assigned? Was the assessment correct? Was containment executed properly? What was the time to resolution?
   - Retain evidence per company policy and regulatory requirements

### Incident Response in the Cloud

Cloud IR follows the same lifecycle but must account for the **shared responsibility model**:

- **IaaS:** The customer is responsible for OS-level and application-level security; the provider handles physical infrastructure and hypervisor.
- **SaaS:** The provider manages nearly everything; the customer is responsible for data, access management, and configuration.

Cloud-specific IR considerations:
- **Preparation:** Maintain up-to-date contact lists for cloud provider security teams; understand provider-specific forensics capabilities.
- **Detection:** Leverage cloud-native monitoring and alerting tools (e.g., AWS CloudTrail, Azure Monitor, GCP Security Command Center).
- **Containment:** Use cloud-native capabilities such as security group modifications, snapshot isolation, and account suspension.

### Cybersecurity Strategy

A cybersecurity strategy is a comprehensive, documented approach to safeguarding an organisation’s digital ecosystem. It rests on three core pillars:

1. **Understand the Business** — Know what assets matter most, what processes are critical, and what regulatory requirements apply.
2. **Understand Threats and Risks** — Identify the threat actors, attack vectors, and vulnerabilities relevant to the organisation.
3. **Proper Documentation** — Formalise policies, procedures, and plans so that security is repeatable, auditable, and not dependent on individual knowledge.

### Risk Assessment

**Risk Formula:**

2Risk = Threat 	imes Vulnerability 	imes Asset2

(Per ISO 31000 framework)

- **Threat:** Any potential cause of an unwanted incident.
- **Vulnerability:** A weakness that can be exploited by a threat.
- **Asset:** Anything of value to the organisation (data, systems, reputation).

**Types of Risk Assessment:**
- **Qualitative** — Uses descriptive scales (high/medium/low) to rank risks. Simpler and faster but less precise.
- **Quantitative** — Assigns numerical/monetary values to risks. More precise but requires reliable data.
- **Compliance-Based** — Evaluates risks against regulatory requirements and standards.
- **Dynamic/Continuous** — Ongoing, real-time risk assessment rather than periodic point-in-time evaluations.

**Risk Assessment Methodologies:**
| Methodology | Focus |
|-------------|-------|
| NIST CSF (Cybersecurity Framework) | Identify, Protect, Detect, Respond, Recover |
| ISO/IEC 27005 | Risk management for information security |
| OCTAVE | Operationally Critical Threat, Asset, and Vulnerability Evaluation |
| FAIR | Factor Analysis of Information Risk (quantitative) |
| CSA STAR | Cloud Security Alliance — Security, Trust, Assurance, and Risk |

### Attack and Defence Strategies

**Attack Testing Strategies:**
- **External Testing** — Simulating attacks from outside the network perimeter.
- **Internal Testing** — Simulating attacks from within the network (insider threat).
- **Blind Testing** — Testers have minimal prior knowledge of the target (simulates real attacker).
- **Targeted Testing** — Testers and defenders work together with full knowledge (also called "lights on" testing).

**Defence Strategies:**
- **Defence in Depth** — Multiple layered security controls arranged in series; if one layer fails, the next catches the attack.
- **Defence in Breadth** — Security coverage across all layers of the OSI model, ensuring no layer is left unprotected.

**Top Proactive Strategies for Businesses:**
1. Train employees on security awareness
2. Protect networks with proper architecture
3. Deploy and maintain firewalls
4. Keep software updated and patched
5. Maintain regular backups
6. Enforce physical access restrictions
7. Secure Wi-Fi networks
8. Enforce strong password policies
9. Limit access on a need-to-know basis
10. Use unique user accounts (no shared credentials)

**Benefits of a proactive cybersecurity strategy:**
- Cost savings (preventing breaches is cheaper than responding to them)
- Enhanced security posture
- Clear communication across the organisation about security expectations
- Building a security-aware culture

## Definitions

| Term | Definition |
|------|------------|
| Information Security | The practice of protecting information assets in all forms, governed by frameworks such as COBIT and NIST SP 800-53 |
| Cybersecurity | A subcategory of information security focused on protecting internet-connected systems (hardware, software, data) from cyber threats; term first used in 1989 |
| CIA Triad | The three fundamental properties of secure information: Confidentiality, Integrity, and Availability |
| Confidentiality | Ensuring information is accessible only to authorised parties |
| Integrity | Ensuring information is accurate, complete, and unaltered by unauthorised parties |
| Availability | Ensuring information and systems are accessible to authorised users when needed |
| Defence in Depth | A layered security strategy where multiple independent controls protect assets so that failure of one layer does not compromise the whole system |
| Zero Trust | A security model that assumes no user, device, or network is inherently trustworthy; every access request must be verified |
| BYOD | Bring Your Own Device — the practice of employees using personal devices for work purposes, expanding the attack surface |
| Shadow IT | Technology systems and solutions used within an organisation without explicit IT department approval |
| MFA | Multi-Factor Authentication — requiring two or more verification factors to gain access to a resource |
| SSL/TLS | Secure Sockets Layer / Transport Layer Security — cryptographic protocols for securing data in transit |
| IaaS | Infrastructure as a Service — cloud model where the provider supplies virtualised computing resources |
| SaaS | Software as a Service — cloud model where the provider hosts and manages the application |
| CSPM | Cloud Security Posture Management — tools and practices for continuous compliance and security monitoring in cloud environments |
| DevSecOps | Development, Security, and Operations — integrating security practices into the DevOps pipeline |
| Red Team | An offensive security team that simulates real-world attacks to test an organisation’s defences |
| Blue Team | A defensive security team responsible for detecting, responding to, and recovering from security incidents |
| MTTC | Mean Time to Compromise — a Red Team metric measuring how quickly initial access is gained |
| MTTP | Mean Time to Privilege Escalation — a Red Team metric measuring how quickly elevated privileges are obtained after initial access |
| ETTD | Estimated Time to Detection — a Blue Team metric measuring how long it takes to identify an intrusion |
| ETTR | Estimated Time to Recovery — a Blue Team metric measuring how long it takes to fully recover from an incident |
| IOC | Indicator of Compromise — forensic artefacts (file hashes, IP addresses, domain names, registry changes) that indicate a system has been breached |
| Incident Response (IR) | The structured process of detecting, responding to, and recovering from a security incident |
| SLA | Service Level Agreement — a contract defining the expected level of service between a provider and customer |
| Assume Breach | A security methodology that operates under the assumption that a breach has already occurred, driving continuous testing and monitoring |
| Shared Responsibility Model | A cloud security framework defining which security tasks are handled by the cloud provider versus the customer |
| ISO 31000 | International standard providing principles and guidelines for risk management |
| NIST CSF | NIST Cybersecurity Framework — a voluntary framework of standards and best practices for managing cybersecurity risk |
| OCTAVE | Operationally Critical Threat, Asset, and Vulnerability Evaluation — a risk assessment methodology |
| FAIR | Factor Analysis of Information Risk — a quantitative risk assessment methodology |
| CSA STAR | Cloud Security Alliance Security, Trust, Assurance, and Risk — a cloud-specific security assessment programme |
| Qualitative Risk Assessment | Risk evaluation using descriptive scales (e.g., high/medium/low) rather than numerical values |
| Quantitative Risk Assessment | Risk evaluation using numerical and monetary values for more precise measurement |
| WannaCry | A 2017 ransomware attack that infected 400,000+ machines by exploiting an unpatched SMBv1 vulnerability |
| SMBv1 | Server Message Block version 1 — a legacy network file sharing protocol with known vulnerabilities |

## Diagrams & Visual Descriptions

### CIA Triad Triangle
A triangle diagram with the three vertices labelled **Confidentiality**, **Integrity**, and **Availability**. The triangle represents the balance between these three properties — strengthening one should not come at the expense of the others. All security decisions should be evaluated against this model.

### Defence in Depth — Castle Analogy
A layered diagram using a medieval castle as a metaphor for multi-layered security:
- **Moat** (outermost layer) — Network perimeter defences (firewalls, DMZ)
- **High Hard Walls** — Network segmentation and access controls
- **Inner Walls** — Application-level security controls
- **Watch Towers** — Monitoring and detection systems (SIEM, IDS/IPS)
- **Guards Check Identity** — Authentication and authorisation mechanisms
- **Limited Entry Points** — Minimising attack surface through controlled access paths

Each layer operates independently; an attacker must breach all layers sequentially to reach the protected asset.

### Zero Trust Security Diagram
A hexagonal or radial diagram showing the six domains that require continuous verification under Zero Trust:
1. **Infrastructure** — Verify and harden all servers, containers, and cloud services
2. **Identities** — Authenticate and authorise every user and service account
3. **Devices** — Assess device health and compliance before granting access
4. **Data** — Classify, label, and encrypt data at all stages
5. **Networks** — Micro-segment networks; encrypt all traffic
6. **Applications** — Secure APIs and runtime environments

All six domains converge on the principle: "Never trust, always verify."

### Security Posture Circular Diagram
A cyclical diagram showing three stages in continuous rotation:
- **Protection** (preventive controls) ->
- **Detection** (monitoring and alerting) ->
- **Response** (containment and recovery) ->
- (loop back to Protection with lessons learned)

This cycle emphasises that security is not a one-time implementation but an ongoing, iterative process.

### Red Team vs. Blue Team Infographic
A side-by-side comparison graphic:

| | Red Team | Blue Team |
|---|----------|-----------|
| **Role** | Simulated adversary | Incident response and defence |
| **Approach** | Real-world attack techniques | Maintaining internal network security |
| **Goal** | Find and exploit weaknesses | Detect, contain, and remediate threats |
| **Metrics** | MTTC, MTTP | ETTD, ETTR |

### WannaCry Ransomware Screenshot
A screenshot of the WannaCry ransom demand window displayed to victims. It shows:
- A demand for payment in Bitcoin to decrypt locked files
- A countdown timer creating urgency
- Instructions for payment
- This serves as a real-world example of ransomware impact and why timely patching (the vulnerability was patched 59 days before the attack) is critical

## Code Examples

No programming code examples were included in this week’s lecture. The course introduces code-level content in later weeks when covering specific attack techniques and defensive tools.

## Formulas & Algorithms

### Risk Calculation (ISO 31000)

2Risk = Threat 	imes Vulnerability 	imes Asset2

- **Threat ($):** The probability or likelihood of a threat event occurring.
- **Vulnerability ($):** The degree to which the asset is exposed (weakness exploitability).
- **Asset ($):** The value of the asset being protected.

In **quantitative risk assessment**, each factor is assigned a numerical value, and the product gives a risk score that can be compared across different scenarios to prioritise mitigation efforts.

In **qualitative risk assessment**, each factor is assigned a descriptive level (e.g., High/Medium/Low), and a risk matrix is used to derive the overall risk level.

### Red Team / Blue Team Metrics

-  = rac{	ext{Total time to achieve compromise across tests}}{	ext{Number of tests}}$
-  = rac{	ext{Total time from initial access to privilege escalation}}{	ext{Number of escalation attempts}}$
-  = rac{	ext{Total detection time across incidents}}{	ext{Number of incidents}}$
-  = rac{	ext{Total recovery time across incidents}}{	ext{Number of incidents}}$

Lower MTTC and MTTP values indicate a weaker defensive posture (Red Team succeeds quickly). Lower ETTD and ETTR values indicate a stronger defensive posture (Blue Team detects and recovers quickly).

## Key Takeaways

- **Cybersecurity is a subset of information security**, focused specifically on internet-connected systems. All cybersecurity work exists within the broader information security governance framework.
- **The CIA Triad (Confidentiality, Integrity, Availability)** is the foundational model against which every security control is evaluated.
- **Defence in Depth** means layering multiple independent controls; no single control should be a single point of failure.
- **Zero Trust Architecture** eliminates the concept of a trusted network. Identity, not network location, is the new perimeter. Every access request is verified regardless of source.
- **The threat landscape is expanding** due to cloud adoption, BYOD, remote work, and Shadow IT. Credential theft and social engineering remain dominant attack vectors.
- **Humans are the weakest link** — the WannaCry case study demonstrates that even when patches are available, failure to apply them (a human/process failure) leads to catastrophic outcomes.
- **Security Posture = Protection + Detection + Response**, operating as a continuous cycle, not a one-time implementation.
- **Red and Blue Teams** provide adversarial simulation to continuously test and improve defences. The Assume Breach methodology makes this an ongoing practice.
- **Incident Response** follows a structured lifecycle: Preparation -> Detection -> Containment -> Post-Incident. IR plans must be tailored to the organisation and updated based on lessons learned.
- **Cloud IR** adds complexity through the shared responsibility model — know what the provider handles versus what you must handle.
- **Cybersecurity Strategy** is built on understanding the business, understanding threats and risks, and proper documentation. Risk is calculated as Threat x Vulnerability x Asset.
- **Proactive security** (training, patching, layered defence, continuous monitoring) is always more cost-effective than reactive incident response.

## Connections

- **Week 2 (Kill Chain)** will build directly on the attack concepts introduced here, formalising the stages an attacker follows from reconnaissance through to objective completion. The Red Team methodology introduced this week is operationalised through the Kill Chain model.
- **Weeks 3--5 (Reconnaissance, Compromising Systems, Identity)** map to specific phases of the attack lifecycle that the current week’s threat landscape discussion previewed. The credential-focused threats discussed here (MFA, password reuse) connect directly to Week 5’s identity-focused content.
- **Weeks 6--7 (Lateral Movement, Privilege Escalation)** relate to the MTTP metric introduced in the Red/Blue Team section. Understanding how attackers escalate privileges is central to both offensive testing and defensive containment.
- **Weeks 8--9 (Security Policy, Network Segmentation)** operationalise the Zero Trust and Defence in Depth principles introduced this week. Network segmentation is one of the key implementation mechanisms for Zero Trust.
- **Weeks 10--11 (Active Sensors, Threat Intelligence, Vulnerability Management, Log Analysis)** connect to this week’s Detection pillar of security posture. Log correlation, baseline establishment, and dynamic detection systems discussed in the IR section are foundational to these later topics.
- **Broader CS Context:** The risk management frameworks (NIST CSF, ISO 27005, FAIR) connect to software engineering and project management courses. The shared responsibility model for cloud IR connects to cloud computing and distributed systems courses. The human factors discussion connects to HCI and organisational behaviour.
