# CSIT302 — Week 8: Active Sensors & Threat Intelligence

> **Source files:** CSIT302_Week8.pdf
> **Date summarized:** 2026-02-24

## Overview

Week 8 concludes the defensive portion of the CSIT302 cybersecurity course by covering **active sensors** (Intrusion Detection Systems, Intrusion Prevention Systems, and User & Entity Behavior Analytics) and **threat intelligence** (Indicators of Compromise, the Pyramid of Pain, and the MITRE ATT&CK framework). This lecture shifts focus entirely to the Blue Team perspective — how defenders detect, analyze, and respond to the attacks studied in Weeks 1-5. The core message is that traditional security monitoring (signature-based, focused on high-profile users) is no longer sufficient; modern defense requires behavior analytics, data correlation, machine learning, and structured threat intelligence applied across **all** users, devices, and environments (on-premises and cloud).

## Key Concepts

### Detection Capabilities — The New Approach

The lecture opens by contrasting traditional and modern detection philosophies:

**Traditional Approach (Insufficient):**
- Focuses on monitoring only high-profile users (executives, admins)
- Relies heavily on signature-based detection
- Accepts high false positive rates as normal
- Monitors known attack patterns only

**Modern Approach (Required):**
- Monitors **all user accounts** across the entire organization
- Profiles normal behavior for every user and entity
- Uses multiple complementary techniques:
  - **Data correlation** from multiple data sources
  - **Profiling** of user and entity behavior
  - **Behavior analytics** to establish baselines
  - **Anomaly detection** to identify deviations
  - **Activity evaluation** for context-aware analysis
  - **Machine learning** for pattern recognition
  - **Artificial Intelligence** for advanced threat detection
- Traditional controls still have value as **one layer** of defense, but must be aggregated with other layers to enhance overall security posture

**Why the shift is necessary:** Current threat actors compromise regular (non-privileged) users first, stay dormant in the network, move laterally, and escalate privileges over time. The Blue Team must have detection mechanisms that identify these behaviors across all devices and locations, raising alerts based on **data correlation** rather than single-point detection.

### Indicators of Compromise (IoCs)

An **Indicator of Compromise (IoC)** is an artifact observed on a network or in an operating system that indicates a computer intrusion **with high confidence**. When new threats emerge, they follow patterns of behavior and leave footprints in target systems. IoCs help organizations detect attacker activity quickly — ideally preventing a breach or stopping it in its earliest stages.

#### The 12 Major IoCs

1. **Unusual Outbound Traffic**
   - Compromised systems connect to Command-and-Control (C&C) servers
   - This traffic may be visible before real damage occurs
   - Monitor both internal network activity and traffic leaving the perimeter

2. **Anomalies in Privileged User Account Activity**
   - Changes in behavior indicate the account may be controlled by someone else
   - Watch for changes in: time of activity, systems accessed, type/volume of information accessed
   - Attackers use compromised privileged accounts to escalate or leapfrog to other accounts

3. **Geographical Irregularities**
   - Unusual geographic patterns in log-ins and access
   - Connections to countries where the company does not conduct business
   - Indicates data may be exfiltrated to foreign locations

4. **Log-in Red Flags**
   - Log-in irregularities and failures indicate network/system probing
   - After-hours activity is suspicious (but requires caution before concluding)
   - Patterns of failed attempts followed by a success suggest brute-force or credential stuffing

5. **Sudden Increase in Database Read Volume**
   - Signs of data exfiltration probing
   - Example: attacker attempting to extract the full credit card database generates massive read volume

6. **Large Number of Requests for the Same File**
   - Indicates an attacker trying different exploits to find one that works
   - Example: single user/IP making 500 requests for `join.php`

7. **Mismatched Port-Application Traffic**
   - An application using an unusual port signals C&C traffic masquerading as normal behavior
   - Example: DNS traffic on port 80 instead of port 53

8. **DNS Request Anomalies**
   - Large spike in DNS requests from a specific host
   - Indicates potential C&C traffic generation
   - Monitor patterns of DNS requests to external hosts

9. **Suspicious Registry or System File Changes**
   - Malware establishes persistence through registry modifications
   - Attackers tamper with host system files to maintain access

10. **Mobile Device Profile Changes**
    - A new configuration profile not provided by the enterprise indicates device compromise
    - Hostile profiles can be installed through phishing or spear-phishing attacks

11. **Wrong Placement of Data**
    - Attackers aggregate data at collection points before exfiltration
    - Example: files appearing in unusual locations like the root folder of the Recycle Bin

12. **Web Traffic with Unhuman Behavior**
    - Traffic patterns that don't match normal human browsing
    - Example: 30-40 browser windows open to different sites simultaneously

#### Case Study: Petya Ransomware IoCs

The Petya ransomware demonstrated specific IoCs that detection systems could identify:

**Scheduled restart commands:**
```cmd
schtasks /Create /SC once /TN "" /TR "<system folder>shutdown.exe /r /f" /ST <time>

cmd.exe /c schtasks /RU "SYSTEM" /Create /SC once /TN "" /TR "C:\Windows\system32\shutdown.exe /r /f" /ST <time>
```

**Network scanning IoC:** Local network scanning on **TCP port 139** and **TCP port 445** (SMB ports), used by Petya to propagate laterally across the network.

Detection systems that monitor for these specific artifacts (scheduled task creation with shutdown commands, internal SMB scanning) can raise alerts when an attack is underway.

#### IoC Community and Databases

The cybersecurity community shares IoC information through several platforms:
- **OpenIOC** (openioc.org) — open framework for sharing IoC definitions
- **ThreatFox** (threatfox.abuse.ch) — community-driven IoC database for sharing indicators associated with malware
- **FireEye IoC Editor** — tool for creating and managing IoC definitions using the OpenIOC format (the lecture shows the IoC Editor displaying the Duqu Trojan with Boolean logic rules matching file certificates, driver device names, registry paths, and event log entries)

### Intrusion Detection System (IDS)

An IDS is a device or software application that monitors a network or systems for malicious activity or policy violations and **triggers an alert**. The alert depends on the IDS policy.

**Initial IDS Policy Questions:**
1. Who should be monitoring the IDS?
2. Who should have administrative access to the IDS?
3. How will incidents be handled based on IDS alerts?
4. What is the IDS update policy?
5. Where should the IDS be installed?

#### Classification by Analyzed Activity

**Host-based IDS (HIDS):**
- Runs on individual hosts or devices
- Monitors inbound and outbound packets from that device only
- Takes snapshots of system files and compares to previous snapshots
- Alerts administrator if critical system files are modified or deleted
- Ideal for **mission-critical machines** that should not change their configurations

**Network-based IDS (NIDS):**
- Detects intrusions for the network segment where it is installed
- Placed at strategic points to monitor traffic to/from all devices on the network
- Analyzes passing traffic and matches against a library of known attacks
- Uses a **SPAN port** on the network switch (passive listening — does not consume significant bandwidth)

**Priority placement for NIDS:**
1. **DMZ/Perimeter** — protects externally-facing services (mail, web, FTP, DNS servers)
2. **Core corporate network** — monitors internal east-west traffic
3. **Wireless network** — often less controlled than wired networks
4. **Virtualization network** — monitors VM-to-VM traffic
5. **Other critical network segments** — based on organizational risk assessment

```
                    NIDS PLACEMENT ARCHITECTURE
 ================================================================

    INTERNET
       |
  [Firewall]
       |
  +----+----+
  |  DMZ    |  <-- NIDS Sensor 1 (highest priority)
  | Web/Mail|      Monitors all external-facing traffic
  | DNS/FTP |
  +----+----+
       |
  [Firewall]
       |
  +----+--------+--------+--------+
  |             |        |        |
  |  CORE       | WIRELESS| VIRTUAL|
  |  NETWORK    | NETWORK | NETWORK|
  |             |        |        |
  | NIDS        | NIDS   | NIDS   |
  | Sensor 2    | Sensor3| Sensor4|
  +-------------+--------+--------+

  Each NIDS sensor connects to a SPAN port on
  its network switch, receiving a copy of all
  traffic passing through that segment.

  SPAN Port Configuration:
  +------------------+
  | Network Switch   |
  |                  |
  | Port 1 [User A]  |
  | Port 2 [User B]  |  All traffic mirrored
  | Port 3 [Server]  |  ─────────────────────> SPAN Port ──> NIDS
  | Port 4 [User C]  |
  | ...              |
  +------------------+
```

#### Classification by Detection Method

**Signature-based IDS:**
- Queries a database of known attack signatures (byte sequences, malicious instruction sequences)
- Used for identifying **known threats** with high accuracy
- Requires **constant database updates** to remain effective
- Low false positive rate but cannot detect novel attacks

**Behavior-based (Anomaly-based) IDS:**
- Creates a baseline model of trustworthy activity through **machine learning**
- Compares new behavior against the established baseline
- Can detect **previously unknown attacks** (zero-days)
- May suffer from **false positives** — legitimate but unusual activity may be flagged as malicious

### Intrusion Prevention System (IPS)

An IPS uses the same detection concepts as an IDS but adds the ability to **prevent intrusions by taking corrective action** (blocking traffic, dropping packets, resetting connections).

**IPS purposes:**
- Identifying possible incidents and logging information about them
- Reporting attempts to appropriate personnel
- Identifying problems with security policies
- Documenting existing threats
- Deterring individuals from violating security policies

**IPS variants:**
- **HIPS** (Host-based IPS) — protects individual hosts
- **NIPS** (Network-based IPS) — protects network segments
- Same placement guidelines as NIDS apply to NIPS

#### IDS vs. IPS Comparison

```
+---------------------------+---------------------------+
|           IDS             |           IPS             |
+---------------------------+---------------------------+
| Detects and ALERTS        | Detects and TAKES ACTION  |
|                           |                           |
| Passive monitoring        | Active prevention         |
|                           |                           |
| Needs human/automated     | Can accept/reject packets |
| system to interpret and   | based on rules            |
| decide on action          | autonomously              |
|                           |                           |
| Cannot stop attacks       | Can block malicious       |
| in progress               | traffic in real-time      |
+---------------------------+---------------------------+
|              SHARED CAPABILITIES                      |
|  - Both analyze traffic                               |
|  - Both compare against known threats                 |
|  - Both need regular updates                          |
|  - Both use signature and anomaly detection           |
+-------------------------------------------------------+
```

#### Rule-based IPS (Snort)

**Snort** (https://www.snort.org/) is the most widely used open-source rule-based IPS. It blocks threats by leveraging rule-based detection.

**Example rule — Snort Sid 1-42329:** Detects the `Win.Trojan.Doublepulsar` variant (associated with the EternalBlue/WannaCry attack chain).

**Basic Snort rule syntax:**
```
log tcp any any -> 192.168.1.0/24 !6000:6010
```

**Breaking down this rule:**

| Component | Meaning |
|-----------|---------|
| `log` | Action: log the matching traffic |
| `tcp` | Protocol: TCP |
| `any any` | Source: any IP address, any port |
| `->` | Direction: from source to destination |
| `192.168.1.0/24` | Destination: the 192.168.1.0/24 subnet |
| `!6000:6010` | Destination ports: everything EXCEPT 6000-6010 |

This rule logs all TCP traffic from any source to the 192.168.1.0/24 network on all ports except 6000-6010 (X Window System ports).

**More complex Snort rules** combine multiple conditions to detect specific threats. Snort publishes rule updates regularly (e.g., Talos Rules) to address newly discovered vulnerabilities and malware.

#### Anomaly-based IPS

- Detection is based on what the IPS categorizes as anomalous
- Takes **random samples** of network traffic and compares to a baseline
- If the sample falls outside the baseline, action is taken (alert followed by blocking)
- **User behavior analytics** plays an important role in establishing and maintaining baselines

### Behavior Analytics On-Premises (UEBA)

**Behavior analytics**, as defined by Gartner, is a cybersecurity process focused on detecting **insider threats**, **targeted attacks**, and **financial fraud**. It examines patterns of human behavior, applies algorithms and statistical analysis to detect meaningful anomalies from those patterns.

Key distinction: Instead of tracking **devices or security events**, behavior analytics tracks a system's **users**.

**Big data platforms** like Apache Hadoop enable behavior analytics to analyze petabytes of data for detecting insider threats and advanced persistent threats (APTs).

#### User and Entity Behavior Analytics (UEBA)

UEBA is a term coined by Gartner that now refers broadly to any technology based on behavior analytics. It:

1. Takes note of the **normal conduct** of users
2. Spots **anomalous behavior** or deviations from normal patterns
3. Alerts immediately when anomalies are detected

**Example:** A user who regularly downloads 10 MB of files per day suddenly downloads gigabytes — the system detects this deviation and alerts immediately.

**Most important advantage:** The capability to detect attacks **in the early stages** and take corrective action before significant damage occurs.

**UEBA Decision Flow:**
```
                    UEBA ANALYSIS ENGINE
  ============================================================

  DATA SOURCES:
  +----------+  +----------+  +----------+  +----------+
  | Network  |  | Endpoint |  | Identity |  | App      |
  | Traffic  |  | Logs     |  | Systems  |  | Logs     |
  +----+-----+  +----+-----+  +----+-----+  +----+-----+
       |             |             |             |
       +------+------+------+------+
              |
       +------v------+
       | Data        |
       | Aggregation |
       | & Correlation|
       +------+------+
              |
       +------v------+
       | Baseline    |     Profile each user/entity:
       | Profiling   | --> - Normal access times
       | (ML-based)  |     - Typical systems accessed
       +------+------+     - Usual data volumes
              |             - Geographic patterns
       +------v------+     - OS/device preferences
       | Real-time   |
       | Comparison  |
       +------+------+
              |
       +------v------+
       | Anomaly     |  Deviation from baseline?
       | Scoring     |
       +---+----+----+
           |    |
      LOW  |    | HIGH
           |    |
     +-----v+  +v--------+
     | Log   |  | ALERT   |
     | Only  |  | + Action|
     +-------+  +---------+
```

**Credit card analogy:** When you use your credit card in a new place or geographic location, the system recognizes the deviation from your established pattern (usual locations, spending averages, purchase types). The transaction is put on hold until you validate it. This is UEBA in action — detecting anomalies early and taking immediate protective action.

**Why on-premises UEBA matters:**
- Core business operations still happen on-premises
- Critical data is located on-premises
- Most users and key assets are on-premises
- Attackers silently infiltrate on-premises networks, move laterally, escalate privileges, and maintain C&C connections until mission execution

#### Case Study 1: Suspicious Administrator Behavior

Microsoft **Advanced Threat Analytics (ATA)**, which uses UEBA, detected suspicious behavior from an administrator account:
- The system profiles what servers users normally access, what shares they visit, what OS they use, and their geographic location
- The alert showed the administrator had not performed these specific activities in the last month
- The behavior was not correlated with other accounts in the organization
- This type of alert cannot be ignored — it strongly indicates the account has been compromised

#### Case Study 2: Pass-the-Ticket Attack Detection

**Attack flow:**
1. **Infect** the target computer via phishing or exploiting a vulnerability
2. **Escalate** to an account with elevated privileges that can access Domain Controllers (DC)
3. **Log into the DC** and dump the password hash for the **KRBTGT** (Kerberos Ticket Granting Ticket) account
4. **Create a Golden Ticket** using the KRBTGT hash (often using **Mimikatz**)
5. **Load the Kerberos token** into any session for any user — gaining access to anything on the network

```
  PASS-THE-TICKET ATTACK FLOW
  =============================================

  [Phishing Email]
        |
        v
  [Victim Workstation] ---> Malware installed
        |
        v
  [Credential Harvesting] ---> Obtain elevated account
        |
        v
  [Domain Controller (DC)]
        |
        v
  [Dump KRBTGT Hash] ---> Using Mimikatz
        |
        v
  [Create Golden Ticket] ---> Forged Kerberos TGT
        |
        v
  [Access ANYTHING] ---> Any user, any resource
```

**UEBA Detection approach:**
- Cannot rely solely on signature detection (too many attack variants)
- Must look for **attack patterns** and what the attacker is trying to do
- Monitors for suspicious behavior from regular users doing tasks they shouldn't
- **Example:** Microsoft ATA detected a regular user (JeffV) running `NetSess.exe` against the local Domain Controller from VICTIM-PC. This constitutes **SMB session enumeration** — a reconnaissance technique. The system identified this as suspicious because regular users do not perform session enumeration, and raised an alert showing 2 exposed accounts on DC1.

#### Case Study 3: Warning — Misconfiguration Detection

Attackers exploit not only vulnerabilities but also **misconfigurations** (bad protocol implementation, lack of hardening). UEBA systems detect systems lacking secure configuration.

**Example:** Microsoft ATA detected a service on SHAREDADMIN-SRV exposing **13 account credentials in cleartext** using **LDAP simple bind** (without encryption) to Domain Controller DC01. This misconfiguration alert enables the Blue Team to remediate before an attacker exploits the exposed credentials.

### Behavior Analytics in a Hybrid Cloud

When securing a hybrid environment, the Blue Team must:
- Expand their view of the current threat landscape
- Validate continuous connectivity with the cloud
- Assess the impact on overall security posture
- Leverage hybrid cloud capabilities to benefit overall security

**Key considerations:**
- IaaS adoption is growing, with security as the main concern
- Longer-term IaaS users report positive security impact
- Need **one central platform** to visualize alerts across all workloads (on-premises + multiple cloud providers)

#### Analytics for PaaS

PaaS workloads (common in cloud migrations) require built-in threat detection. Security monitoring depends on the cloud provider. **Microsoft Defender for Cloud** provides specialized security plans:

| Defender Service | Protection Scope |
|---|---|
| Defender for SQL | Threat detection for SQL databases in Azure |
| Defender for Storage | Threat detection for Azure storage accounts |
| Defender for Containers | Threat detection for Container Registry and Kubernetes |
| Defender for App Services | Threat detection for Azure Web Apps |
| Defender for Key Vault | Threat detection for Azure Key Vault |

### Threat Intelligence

**Cyber Threat Intelligence (CTI)** is the process of analyzing information about adversaries — their context, mechanisms, indicators, implications, and target platforms — to help network defenders and decision-makers.

**The threat intelligence workflow:**
1. **Collect** information from vendor reports, tweets, academic research, internal analysis
2. **Store** relevant intelligence (in databases or structured formats)
3. **Identify IoCs** and integrate them into security tools (IDS, SIEM)
4. **Write reports** specific to adversary groups (e.g., APT 3, APT 9) or specific vulnerabilities

**Challenges in threat intelligence:**
- **Information Overload** — volume of CTI reports makes it difficult to extract and apply relevant intelligence quickly
- **Manual and Fragmented Processes** — IoCs are often buried in text reports, requiring manual extraction
- **Limited Context & Actionability** — reports describe "what" happened but lack "how" or "why"
- **High False Positives** — poorly vetted or decontextualized IoCs trigger excessive false alerts
- **Unstructured Formats** — make automation and sharing (e.g., via STIX/TAXII) difficult

### The Pyramid of Pain

The Pyramid of Pain, created by security researcher David Bianco, describes the **difficulty adversaries face when they need to change their IoCs** to avoid detection. Higher levels of the pyramid cause more operational pain for attackers, making those indicators more valuable for defenders.

```
                    THE PYRAMID OF PAIN
  ============================================================

              /\
             /  \          TOUGH
            / TTP \        Tactics, Techniques & Procedures
           / s     \       Forces adversary to change HOW
          /----------\     they operate (highest pain)
         /            \
        /   Tools      \   CHALLENGING
       /                \  Must find/modify new tools or
      /------------------\ recompile (costly)
     /                    \
    /   Host Artifacts     \ ANNOYING
   /                        \ Registry keys, dropped file
  /--------------------------\ paths, service names
 /                            \
/     Network Artifacts        \ SIMPLE
+------------------------------+ URI patterns, User-Agent
|                              | strings, protocol quirks
|      Domain Names            | EASY
|                              | Needs registration/hosting
+------------------------------+
|  Hash Values, IP Addresses   | TRIVIAL
|  MD5/SHA, Netblocks          | Short-lived, easily rotated
+------------------------------+

  KEY INSIGHT:
  The higher up the pyramid you detect/disrupt,
  the MORE operational pain on the attacker and
  the MORE valuable, durable, and actionable
  the indicator is for defenders.
```

**Level-by-level analysis:**

| Level | Examples | Attacker Pain | Defender Value |
|-------|----------|---------------|----------------|
| Trivial | Hash values (MD5/SHA), IP addresses, netblocks | None — easily rotated, proxies reused | Low — short-lived indicators |
| Easy | Domain names | Low — requires registration/hosting but replaceable | Low-Medium |
| Simple | Network artifacts (URI patterns, User-Agent strings, protocol quirks) | Medium — requires altering tooling or communication format | Medium |
| Annoying | Host artifacts (registry keys, dropped file paths, service names) | Medium-High — forces changes to build/install behaviors | Medium-High |
| Challenging | Tools (malware families, distinct protocols) | High — must find, modify, or develop new tools (costly) | High |
| Tough | TTPs (Tactics, Techniques & Procedures) | Highest — forces adversaries to change **how they operate** | Highest — most durable and actionable |

### MITRE and MITRE ATT&CK

**MITRE** is a nonprofit organization founded in 1958 that operates U.S. Federally Funded Research and Development Centers (FFRDCs). It supports government agencies in defense, cybersecurity, aviation, and public safety.

**MITRE's relationship with NIST:**
- **NIST** sets cybersecurity standards and frameworks
- **MITRE** provides operational models and tools (like ATT&CK) to apply and evaluate those standards in real-world threat defense

#### MITRE ATT&CK Framework

**ATT&CK** (Adversarial Tactics, Techniques, and Common Knowledge) is a globally accessible knowledge base documenting how adversaries operate:
- How adversaries interact with systems
- The various phases of their attack lifecycle
- The platforms they target

ATT&CK is based on **real-world observations** and is used as a foundation for developing threat models and methodologies. New releases are issued every April and October (current version: **v18.0**, released October 28, 2025).

#### ATT&CK Organization

```
  ATT&CK HIERARCHY
  =============================================

  TACTICS (the "WHY" — attacker's goal)
    |
    +-- TECHNIQUES (the "HOW" — actions to achieve goals)
          |
          +-- SUB-TECHNIQUES (more specific descriptions)
                |
                +-- PROCEDURES (the "DETAILS" — specific
                    implementation or in-the-wild usage)


  THREE TECHNOLOGY DOMAINS:
  +------------------+------------------+------------------+
  |    ENTERPRISE    |     MOBILE       |       ICS        |
  |                  |                  |                  |
  | Traditional      | Mobile device    | Industrial       |
  | enterprise       | attack           | Control System   |
  | networks &       | techniques       | attack           |
  | cloud            |                  | techniques       |
  +------------------+------------------+------------------+
```

**ATT&CK Tactics (Enterprise)** represent the attacker's objectives at each phase:
- Reconnaissance, Resource Development, Initial Access, Execution, Persistence, Privilege Escalation, Defense Evasion, Credential Access, Discovery, Lateral Movement, Collection, Command & Control, Exfiltration, Impact

#### ATT&CK Usage for Threat Intelligence

ATT&CK provides a **structured way to describe adversary TTPs**, enabling:
- **Analysts** to structure intelligence about adversary behavior
- **Defenders** to structure detection and mitigation capabilities
- **Overlaying** multiple adversary groups to identify security gaps
- **Common language** for clear communication across the security community
- **Metrics** to make both adversaries and defenders measurable

**Moving from Information to Action (the whole point of threat intelligence):**
1. **Search** which APT groups or malware target a specific industry (e.g., pharmaceutical)
2. **Select and view** APT group details (e.g., APT19)
3. **Search for specific techniques** used by that group (e.g., Registry Run Keys / Startup Folder)
4. **Make it actionable:**
   - Inform defenders about the specific Registry run key APT19 uses
   - Check detection advice: APT19 changes their run key to avoid detection
   - **Action:** Monitor the Registry for new run keys

This workflow transforms raw intelligence into specific, implementable defensive measures.

## Definitions

| Term | Definition |
|------|------------|
| IoC (Indicator of Compromise) | An artifact observed on a network or operating system that indicates a computer intrusion with high confidence |
| C&C (Command and Control) | Infrastructure used by attackers to communicate with and control compromised systems |
| IDS (Intrusion Detection System) | A device or software that monitors a network or systems for malicious activity or policy violations and triggers an alert |
| IPS (Intrusion Prevention System) | A system that detects intrusions like an IDS but also takes corrective action to prevent or block the attack |
| HIDS (Host-based IDS) | An IDS that runs on individual hosts, monitoring inbound/outbound packets and system file integrity on that specific device |
| NIDS (Network-based IDS) | An IDS placed at strategic network points to monitor and analyze traffic across an entire network segment |
| HIPS (Host-based IPS) | An IPS that runs on individual hosts, actively blocking detected threats on that device |
| NIPS (Network-based IPS) | An IPS placed at strategic network points that can actively block malicious traffic across a network segment |
| UEBA (User and Entity Behavior Analytics) | A cybersecurity technology that profiles normal user/entity behavior and detects anomalous deviations using machine learning and statistical analysis |
| SPAN Port | A switch port configured to receive a copy of all traffic passing through other ports, used for passive monitoring by IDS/IPS |
| DMZ (Demilitarized Zone) | A network segment that sits between the internal network and the internet, hosting externally-facing services while protecting the internal LAN |
| Signature-based Detection | Detection method that matches observed activity against a database of known attack signatures (byte sequences, instruction patterns) |
| Anomaly-based Detection | Detection method that establishes a baseline of normal behavior through machine learning and alerts when activity deviates from that baseline |
| Behavior Analytics | A cybersecurity process that analyzes patterns of human behavior using algorithms and statistical analysis to detect threats |
| Snort | An open-source network intrusion prevention system capable of real-time traffic analysis and rule-based threat blocking |
| Petya | A ransomware family that encrypts the Master Boot Record (MBR) and spreads laterally via SMB (ports 139/445) |
| Golden Ticket | A forged Kerberos Ticket Granting Ticket (TGT) created using the KRBTGT account hash, granting unrestricted access to all domain resources |
| Mimikatz | A post-exploitation tool used to extract credentials, hashes, and Kerberos tickets from Windows memory |
| KRBTGT | The Kerberos Ticket Granting Ticket account in Active Directory; its password hash is used to sign all Kerberos tickets in the domain |
| Domain Controller (DC) | A server that responds to security authentication requests (logging in, checking permissions) within a Windows Active Directory domain |
| Pass-the-Ticket | An attack technique where stolen Kerberos tickets are used to authenticate as another user without knowing their password |
| NetSess.exe | A tool that enumerates SMB (Server Message Block) sessions on a target system, revealing connected users and shares — used during reconnaissance |
| OpenIOC | An open framework for sharing Indicators of Compromise definitions in a structured, machine-readable format |
| ThreatFox | A community-driven platform (abuse.ch) for sharing indicators of compromise associated with malware |
| FireEye IoC Editor | A tool for creating and managing IoC definitions using the OpenIOC format with Boolean logic rules |
| Microsoft ATA (Advanced Threat Analytics) | A Microsoft on-premises product that uses UEBA to detect suspicious activities and advanced attacks in Active Directory environments |
| Pyramid of Pain | A model by David Bianco describing the increasing difficulty adversaries face when needing to change different types of IoCs |
| TTP (Tactics, Techniques & Procedures) | The highest-level description of adversary behavior — what they try to achieve, how they do it, and the specific steps they follow |
| MITRE | A nonprofit organization operating U.S. FFRDCs that created the ATT&CK framework and collaborates with NIST on cybersecurity |
| MITRE ATT&CK | Adversarial Tactics, Techniques, and Common Knowledge — a globally accessible knowledge base documenting real-world adversary behavior |
| APT (Advanced Persistent Threat) | A sophisticated, prolonged cyber attack campaign typically conducted by well-resourced threat actors (often nation-state sponsored) |
| SIEM (Security Information and Event Management) | A system that aggregates and analyzes security log data from multiple sources to detect and respond to threats |
| STIX (Structured Threat Information Expression) | A standardized language for representing and sharing cyber threat intelligence |
| TAXII (Trusted Automated Exchange of Indicator Information) | A protocol for exchanging cyber threat intelligence in STIX format over HTTPS |
| FFRDC | Federally Funded Research and Development Center — a nonprofit organization sponsored by the U.S. government to conduct research |
| CSPM (Cloud Security Posture Management) | Tools providing visibility into cloud security configuration and compliance status |
| PaaS (Platform as a Service) | A cloud computing model providing a platform for developing, running, and managing applications without managing infrastructure |
| IaaS (Infrastructure as a Service) | A cloud computing model providing virtualized computing infrastructure (VMs, storage, networks) on demand |
| LDAP (Lightweight Directory Access Protocol) | A protocol for accessing and managing directory services; when used without encryption (simple bind), credentials are exposed in cleartext |
| CTI (Cyber Threat Intelligence) | The process of collecting, analyzing, and applying information about adversaries to improve defensive decision-making |
| Defender for Cloud | Microsoft's cloud-native application protection platform providing CSPM and threat detection for Azure, AWS, and GCP workloads |

## Diagrams & Visual Descriptions

### IoC Editor — Duqu Trojan (FireEye IoC Editor)

The lecture includes a screenshot of the FireEye IoC Editor (IOCe 2.2.0) displaying the **Duqu Trojan** IoC definition. The interface shows:
- **IoC Metadata:** Name "DUQU (METHODOLOGY)", Author "MANDIANT", created 2011-10-21, modified 2012-01-05
- **Description:** Details how the Duqu driver decodes and injects a DLL (marked as .pnf) into a system process (usually services.exe), which then injects another DLL into other processes for backdoor/C2 communication
- **Boolean Logic Tree:** A structured OR/AND tree defining the indicators:
  - File Certificate Subject contains "C-Media Electronics Incorporation" AND File Name contains "cmi4432.sys"
  - OR Driver Device Name is "Gpdl" AND specific device name GUIDs
  - OR Registry Path contains specific Windows CurrentVersion entries with Registry Value Names "CFID"
  - OR EventLog type is "Error" AND EventLog source is "DCOM" AND specific EventLog ID

This demonstrates how IoCs are formally defined with structured Boolean logic for automated detection.

### IDS vs. IPS Venn Diagram

A Venn diagram with two overlapping circles illustrates the relationship between IDS and IPS:
- **IDS only (left circle, red):** Detects and monitors intrusions; won't take action on its own; needs human or automated system to interpret results and decide on action
- **Shared (overlap, green):** Both analyze traffic and compare it to known threats
- **IPS only (right circle, yellow):** Can decide whether to accept/reject packets based on rules; needs to be updated to recognize the latest threats

### IDS Placement Architecture

The lecture includes a network diagram showing IDS sensors deployed at each network segment via SPAN ports on network switches. Sensors are placed at the DMZ/perimeter, core corporate network, wireless network, and virtualization network segments.

### UEBA Entity Analysis Diagram

A diagram shows how UEBA correlates data across multiple entities (users, devices, applications, network segments) to determine whether an alert should be triggered. Multiple data streams feed into a central analytics engine that performs cross-entity correlation.

### SMB Session Enumeration Alert (Microsoft ATA)

A screenshot from Microsoft ATA shows:
- **Alert title:** "Reconnaissance using SMB Session Enumeration"
- **Details:** SMB session enumeration attempts were successfully performed by user **JeffV** from **VICTIM-PC** against **DC1**, exposing **2 accounts**
- **Timestamp:** 6:27 AM, August 23, 2017
- **Visual flow:** JeffV → VICTIM-PC → (Session Enumeration) → DC1
- This demonstrates how UEBA detects reconnaissance activity by regular users

### LDAP Misconfiguration Alert (Microsoft ATA)

A screenshot shows:
- **Alert title:** "Services Exposing Account Credentials"
- **Details:** Services running on **SHAREDADMIN-SRV** exposed **13 accounts' credentials** in cleartext using LDAP simple bind
- **Target:** DC01 (Domain Controller)
- **Timestamp:** 11:37 PM - 11:40 PM, Friday October 20, 2017
- This demonstrates UEBA detecting misconfigurations (not just attacks)

### Pyramid of Pain Diagram

The lecture presents a triangular/pyramid diagram with six levels from bottom (trivial) to top (tough), showing the increasing pain adversaries experience when forced to change each type of indicator. See the ASCII art in the Key Concepts section above for the full representation.

### MITRE ATT&CK Matrix

The lecture includes a screenshot of the ATT&CK Enterprise Matrix — a large table organized by Tactics (columns) and Techniques (rows within each column). Each tactic column (Reconnaissance, Resource Development, Initial Access, Execution, etc.) contains multiple technique entries, creating a comprehensive map of adversary behavior that defenders can use for gap analysis.

## Code Examples

### Petya Ransomware — Scheduled Restart Commands

```cmd
:: Petya schedules a system restart to trigger MBR encryption
:: Method 1: Basic scheduled task
schtasks /Create /SC once /TN "" /TR "<system folder>shutdown.exe /r /f" /ST <time>

:: Method 2: Running as SYSTEM for elevated privileges
cmd.exe /c schtasks /RU "SYSTEM" /Create /SC once /TN "" /TR "C:\Windows\system32\shutdown.exe /r /f" /ST <time>
```

**Explanation:**
- `/Create` — creates a new scheduled task
- `/SC once` — schedule type: run once
- `/TN ""` — task name (empty to avoid easy identification)
- `/TR` — task to run (shutdown with restart `/r` and force `/f`)
- `/ST <time>` — start time for the scheduled restart
- `/RU "SYSTEM"` — run as the SYSTEM account (highest privilege)

**Detection:** Monitor for unexpected `schtasks` commands creating shutdown tasks, especially those running as SYSTEM. This is a clear IoC for Petya and similar ransomware.

### Snort IPS Rules

```snort
# Basic rule: Log all TCP traffic to a subnet (except X Window ports)
log tcp any any -> 192.168.1.0/24 !6000:6010

# Alert on potential DoublePulsar backdoor traffic (conceptual)
alert tcp $EXTERNAL_NET any -> $HOME_NET 445 (
    msg:"MALWARE-BACKDOOR Win.Trojan.Doublepulsar variant";
    sid:1-42329;
    rev:1;
    classtype:trojan-activity;
)

# Alert on DNS traffic on non-standard port (IoC: mismatched port-application)
alert tcp any any -> any 80 (
    msg:"POLICY DNS query over HTTP port - possible C&C";
    content:"|00 01 00 00 00 01 00 00|";  # DNS query header pattern
    sid:1000001;
    rev:1;
)

# Alert on excessive requests to same file (IoC: exploit attempts)
alert tcp $EXTERNAL_NET any -> $HOME_NET $HTTP_PORTS (
    msg:"POLICY Excessive requests for same resource";
    content:"GET /join.php";
    threshold:type threshold, track by_src, count 50, seconds 60;
    sid:1000002;
    rev:1;
)
```

**Snort rule structure:**
```
[action] [protocol] [src_ip] [src_port] -> [dst_ip] [dst_port] ([options])

Actions: alert, log, pass, drop, reject
Protocols: tcp, udp, icmp, ip
```

### Detecting IoCs with PowerShell

```powershell
# Check for suspicious scheduled tasks (Petya IoC)
Get-ScheduledTask | Where-Object {
    $_.Actions.Execute -like "*shutdown*" -and
    $_.Principal.UserId -eq "SYSTEM"
} | Format-Table TaskName, State, @{N='Command';E={$_.Actions.Execute}}

# Check for unusual outbound connections (IoC: C&C traffic)
Get-NetTCPConnection -State Established |
    Where-Object { $_.RemotePort -notin @(80, 443, 53) } |
    Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, OwningProcess |
    Sort-Object RemoteAddress

# Check for suspicious registry changes (IoC: persistence)
Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" |
    Format-List

Get-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" |
    Format-List

# Check for SMB scanning activity (Petya IoC: port 139/445)
Get-NetTCPConnection -LocalPort 445 -State Listen
Get-WinEvent -FilterHashtable @{
    LogName = 'Security'
    Id = 5156  # Windows Filtering Platform connection allowed
} -MaxEvents 100 | Where-Object {
    $_.Message -match "445|139"
}
```

### ATT&CK-Based Detection — Registry Run Key Monitoring

```powershell
# Monitor Registry Run Keys for changes (ATT&CK T1547.001)
# This addresses the APT19 example from the lecture

$registryPaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"
)

# Baseline: capture current state
$baseline = @{}
foreach ($path in $registryPaths) {
    if (Test-Path $path) {
        $baseline[$path] = Get-ItemProperty -Path $path
    }
}

# Compare: check for new entries
foreach ($path in $registryPaths) {
    if (Test-Path $path) {
        $current = Get-ItemProperty -Path $path
        $currentNames = $current.PSObject.Properties.Name
        $baselineNames = $baseline[$path].PSObject.Properties.Name

        $newEntries = $currentNames | Where-Object {
            $_ -notin $baselineNames -and
            $_ -notin @('PSPath','PSParentPath','PSChildName','PSProvider')
        }

        foreach ($entry in $newEntries) {
            Write-Warning "NEW RUN KEY DETECTED: $path\$entry = $($current.$entry)"
        }
    }
}
```

## Formulas & Algorithms

### IDS/IPS Alert Classification Matrix

Every alert generated by an IDS/IPS falls into one of four categories:

```
                        ACTUAL STATE
                   Attack        No Attack
                +-----------+-----------+
   ALERT    Yes | True      | False     |
   RAISED       | Positive  | Positive  |
                | (TP)      | (FP)      |
                +-----------+-----------+
            No  | False     | True      |
                | Negative  | Negative  |
                | (FN)      | (TN)      |
                +-----------+-----------+

Key Metrics:

Detection Rate (Sensitivity) = TP / (TP + FN)
  How many real attacks does the system catch?

False Positive Rate = FP / (FP + TN)
  How often does the system cry wolf?

Precision = TP / (TP + FP)
  When the system alerts, how often is it right?

Accuracy = (TP + TN) / (TP + TN + FP + FN)
  Overall correctness of the system
```

The goal of modern detection (UEBA, behavior analytics) is to **maximize detection rate while minimizing false positives** — the fundamental challenge in cybersecurity monitoring.

### UEBA Anomaly Scoring

UEBA systems typically compute a risk score for each user based on deviations from baseline behavior:

```
Risk Score = w1 * D_time + w2 * D_location + w3 * D_volume +
             w4 * D_resource + w5 * D_pattern

Where:
  D_time     = deviation from normal access time patterns
  D_location = deviation from normal geographic location
  D_volume   = deviation from normal data access volume
  D_resource = deviation from normal resources accessed
  D_pattern  = deviation from normal behavioral patterns
  w1...w5    = weights assigned based on organizational risk priorities

If Risk Score > Threshold:
    Trigger alert and initiate investigation

Example:
  Normal: User downloads 10 MB/day from file server
  Observed: User downloads 5 GB in one hour
  D_volume = (5000 MB - 10 MB) / 10 MB = 499 (extreme deviation)
  → High risk score → Immediate alert
```

### Pyramid of Pain — Indicator Durability

The effectiveness of an IoC-based detection can be estimated by its position on the Pyramid of Pain:

```
Indicator Durability (time before adversary changes it):
  Hash values:       Minutes to hours
  IP addresses:      Hours to days
  Domain names:      Days to weeks
  Network artifacts: Weeks to months
  Host artifacts:    Months
  Tools:             Months to years
  TTPs:              Years (hardest to change)

Detection ROI = Durability * Coverage * Actionability

Where:
  Durability    = how long the indicator remains valid
  Coverage      = how many adversary groups it applies to
  Actionability = how easily defenders can act on it
```

This model explains why TTP-based detection (the ATT&CK approach) provides the highest return on investment for defenders.

### Snort Rule Matching Algorithm

```
ALGORITHM: Snort_Rule_Match(packet, ruleset)
INPUT: network packet, ordered list of Snort rules
OUTPUT: action (alert, log, pass, drop, reject) or no match

1. Parse packet header: extract protocol, src_ip, src_port, dst_ip, dst_port
2. For each rule in ruleset:
   a. Check protocol match
   b. Check source IP/port match (with negation support via '!')
   c. Check direction operator (-> or <>)
   d. Check destination IP/port match
   e. If header matches:
      i.  Check rule options (content match, byte sequences, thresholds)
      ii. If all options match:
          - Execute rule action (alert, log, drop, etc.)
          - Record match for logging
          - BREAK (first match wins in most configurations)
3. If no rule matched: default action (typically pass)
```

## Key Takeaways

- **Traditional security monitoring is no longer sufficient** — monitoring only high-profile users and relying on signatures misses modern attacks that target regular users and use unknown techniques
- **Modern detection requires a multi-technique approach:** data correlation, profiling, behavior analytics, anomaly detection, machine learning, and AI, all working together as aggregated layers
- **The 12 major IoCs provide a practical checklist** for what to monitor: unusual outbound traffic, privileged account anomalies, geographic irregularities, login failures, database read spikes, repeated file requests, port-application mismatches, DNS anomalies, registry changes, mobile profile changes, misplaced data, and unhuman web behavior
- **IDS detects and alerts; IPS detects and acts** — understand the distinction and deploy both appropriately. NIDS/NIPS placement is critical: prioritize DMZ, core network, wireless, and virtualization segments
- **Signature-based detection catches known threats** with low false positives; **anomaly-based detection catches unknown threats** but may produce more false positives. Use both together
- **UEBA is the most advanced detection technology** discussed — it profiles normal user/entity behavior and detects deviations in early attack stages, catching insider threats, lateral movement, privilege escalation, and misconfigurations
- **The credit card analogy** perfectly illustrates UEBA: deviation from established patterns triggers immediate protective action
- **On-premises UEBA is essential** because core business, critical data, and most users remain on-premises, and attackers specifically target on-premises networks for lateral movement
- **Hybrid cloud security requires unified visibility** — one central platform to monitor all workloads across on-premises and cloud environments
- **The Pyramid of Pain** is a critical framework: detecting/disrupting TTPs (the top) forces adversaries to fundamentally change their approach, while hash values and IPs (the bottom) are trivially changed
- **MITRE ATT&CK transforms threat intelligence into action** — by mapping adversary behavior to a structured framework, defenders can identify gaps, prioritize detection engineering, and implement specific countermeasures
- **Threat intelligence must be actionable** — the goal is not just to know about threats but to translate that knowledge into specific defensive measures (e.g., monitor specific registry keys used by APT19)
- **IoC sharing communities** (OpenIOC, ThreatFox) enable collective defense — contributing and consuming IoCs benefits the entire security community

## Connections

**Connection to Week 1-2 (Security Posture & Kill Chain):** Week 8 completes the defensive triad (Security Policy → Network Segmentation → Active Sensors & Threat Intelligence). The kill chain phases studied in Weeks 1-2 (reconnaissance, compromise, lateral movement, privilege escalation, concluding mission) are precisely what the detection capabilities in Week 8 are designed to identify. IoCs map directly to artifacts left by each kill chain phase.

**Connection to Week 3 (Compromising Systems):** The attack techniques from Week 3 (ransomware, SQL injection, XSS, buffer overflows) are what IDS/IPS rules are designed to detect. The Petya ransomware case study in Week 8 directly connects to the ransomware discussion in Week 3, but now from the defender's perspective — identifying IoCs rather than understanding the attack mechanism.

**Connection to Week 4 (Lateral Movement):** The Pass-the-Ticket attack case study in Week 8 directly references lateral movement techniques from Week 4. UEBA's ability to detect SMB session enumeration (a reconnaissance/lateral movement technique) and Golden Ticket attacks demonstrates how behavior analytics counters the specific threats studied earlier.

**Connection to Week 5 (Privilege Escalation):** UEBA's detection of anomalous privileged user behavior directly addresses the privilege escalation techniques from Week 5. The administrator behavior case study shows how UEBA profiles normal admin activity and alerts on deviations — the defensive answer to credential theft and escalation attacks.

**Connection to Week 6 (Security Policy):** Security policies define what IDS/IPS should monitor and how alerts should be handled. The IDS policy questions (who monitors, who has admin access, how incidents are handled, update policy, placement) are direct implementations of the security governance framework from Week 6.

**Connection to Week 7 (Network Segmentation):** NIDS/NIPS placement depends entirely on the network segmentation architecture from Week 7. Sensors are deployed at segment boundaries (DMZ, core network, wireless, virtualization) — the same boundaries created by VLANs, firewalls, and security zones discussed in Week 7.

**Broader CS Context:** The detection and analytics concepts connect to machine learning (baseline modeling, anomaly detection algorithms), databases (SIEM log aggregation and querying), networking (packet analysis, protocol understanding for Snort rules), and software engineering (the MITRE ATT&CK framework as a structured knowledge base). The Pyramid of Pain introduces a strategic framework for prioritizing defensive investments that applies beyond cybersecurity to any adversarial domain.
