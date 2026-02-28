# CSIT302 — Week 2: Cybersecurity Kill Chain & Reconnaissance

> **Source files:** CSIT302_Week2.pdf, CSIT302_Week2.docx
> **Date summarized:** 2026-02-24

## Overview

This lecture introduces the Cybersecurity Kill Chain framework — a structured model for understanding the stages of a cyberattack from initial reconnaissance through to final objectives — and provides a deep dive into the reconnaissance phase specifically. Originally a military concept adapted by Lockheed Martin for cybersecurity, the kill chain gives defenders a systematic way to detect, prevent, and respond to attacks at each phase. The lecture is complemented by a WannaCry ransomware case study that grounds these concepts in a real-world incident from May 2017.

## Key Concepts

### The Cybersecurity Kill Chain (Lockheed Martin Model)

The kill chain originated as a military concept describing the sequence of target identification, force dispatch, decision to attack, and destruction of the target. Lockheed Martin adapted this to cybersecurity, defining **seven sequential phases** that most cyberattacks follow:

1. **Reconnaissance** — The attacker gathers information about the target to identify vulnerabilities. This includes external research (WHOIS lookups, Google dorking, social media mining) and, after initial compromise, internal network enumeration.

2. **Weaponization** — The attacker selects or creates tools to exploit discovered weaknesses. This involves crafting custom malware, creating exploit payloads, and wrapping malicious code inside legitimate-looking files (e.g., embedding a macro exploit in a Word document).

3. **Delivery** — The weapon is transmitted to the target. Primary delivery vectors include:
   - **Phishing** emails (including spear phishing and vishing)
   - **System compromise** through exposed services
   - **Insider threats** — malicious or compromised employees

4. **Exploitation** — The delivered payload is activated, and the attacker gains initial control of a system. This phase often involves **privilege escalation**:
   - **Vertical escalation**: gaining higher-level permissions (e.g., user to admin/root)
   - **Horizontal escalation**: accessing other accounts or systems at the same privilege level
   - Real-world examples: Ashley Madison breach (2015), SunTrust Banks insider theft (2018), Facebook API exploitation (2018), Yahoo mega-breach (2013/2016, affecting 3 billion accounts)

5. **Installation** — The attacker installs backdoors and persistence mechanisms to maintain access. Key characteristics:
   - **Stealth operation** — avoiding detection by security tools
   - **Multiple access points** — ensuring that losing one entry point does not end the campaign
   - **Persistent access** — surviving reboots, password changes, and routine maintenance

6. **Command and Control (C2)** — The attacker establishes remote control channels through the installed backdoors. C2 infrastructure allows the attacker to issue commands, exfiltrate data, and deploy additional tools without physical access.

7. **Actions on Objectives** — The attacker achieves their ultimate goal:
   - **Data exfiltration** — stealing sensitive information
   - **System sabotage** — disrupting operations
   - **Hardware destruction** — physically damaging equipment (e.g., Stuxnet, which caused centrifuges at Iran's Natanz nuclear facility to spin out of control and self-destruct)

**Obfuscation (Optional Phase):** Many attackers add an obfuscation phase to cover their tracks:
- Encryption of exfiltrated data
- Steganography (hiding data within images or other files)
- Modifying or deleting system logs
- Tunneling traffic through legitimate protocols
- Wiping drives to destroy forensic evidence

### Security Controls Mapped to the Kill Chain

Defenders can apply five categories of security controls at each phase of the kill chain:

| Control Type | Purpose | Examples |
|---|---|---|
| **Detect** | Identify attacker activity | Network Intrusion Detection Systems (NIDS), web analytics, threat intelligence feeds |
| **Deny** | Block attacker access | Firewalls, Access Control Lists (ACLs), secure configurations, hardening |
| **Disrupt** | Break the attacker's communication channels | DNS monitoring and sinkholing, cutting C2 feedback channels |
| **Degrade** | Slow the attacker down | Rate-limiting connections, strong encryption on sensitive data |
| **Deceive** | Mislead the attacker | Honeypots (fake systems), honeytokens (fake credentials/data), planted decoy files |

### UEBA — User and Entity Behavior Analytics

UEBA is an advanced detection methodology that uses machine learning and statistical analysis to identify threats:

- **Baseline profiling**: Establishes what "normal" behavior looks like for each user and entity (server, application, device) over time
- **Anomaly detection**: Continuously monitors activity and flags deviations from the baseline — e.g., a user logging in at 3 AM from a foreign country, or a server suddenly making thousands of DNS queries
- **Adaptive learning**: The system continuously updates its baselines, reducing false positives over time as it learns legitimate changes in behavior

UEBA is particularly effective at detecting insider threats and compromised accounts, which traditional signature-based tools often miss.

### Threat Lifecycle Management (LogRhythm Model)

The LogRhythm Threat Lifecycle Management framework defines six phases for handling threats once they are suspected or detected:

1. **Forensic Data Collection** — Aggregate logs, network traffic captures, endpoint telemetry, and other evidence from across the environment. Data sources span the **Seven Domains of IT Infrastructure**:
   - User Domain
   - Workstation Domain
   - LAN Domain
   - LAN-to-WAN Domain
   - Remote Access Domain
   - WAN Domain
   - System/Application Domain

2. **Discovery** — Identify potential threats using two complementary approaches:
   - **Search analytics**: Human-driven queries and hypothesis testing against collected data
   - **Machine analytics**: Machine learning models that automatically surface anomalies and suspicious patterns

3. **Qualification** — Assess each discovered threat for:
   - **Impact**: What damage could this cause?
   - **Urgency**: How quickly must we respond?
   - **Mitigation**: What immediate steps can reduce risk?
   - A major challenge at this stage is filtering out **false positives** — alerts that appear malicious but are actually benign activity

4. **Investigation** — Conduct a full, in-depth investigation of qualified threats. Gather additional evidence, determine the scope of compromise, identify affected systems, and establish a timeline of attacker activity.

5. **Neutralization** — Eliminate the threat or reduce its impact. This may involve isolating compromised systems, blocking attacker IP addresses, removing malware, and revoking compromised credentials.

6. **Recovery** — Restore affected systems to normal operation:
   - Restore from clean backups
   - Roll back unauthorized changes
   - Verify that no backdoors remain
   - Validate system integrity before returning to production

### Reconnaissance — Detailed Breakdown

Reconnaissance is the first and arguably most critical phase of the kill chain. It divides into **external reconnaissance** (pre-compromise) and **internal reconnaissance** (post-compromise).

#### External Reconnaissance

External recon is performed before the attacker has any access to the target. It has three sub-phases:

**Footprinting** — Mapping the target's public-facing infrastructure:
- WHOIS lookups to find domain ownership, contact information, and registrar details
- Google dorking (advanced search operators) to discover exposed files, login pages, error messages, and configuration details
- DNS record enumeration to map subdomains and mail servers

**Enumeration** — Active probing to discover network resources:
- NetBIOS enumeration to find shared resources on Windows networks
- DNS enumeration to discover hostnames, zone transfers, and service records

**Scanning** — Technical probing for exploitable weaknesses:
- Port scanning to identify open services
- Network scanning to map the network topology
- Vulnerability scanning to find known weaknesses in discovered services

#### External Reconnaissance Techniques

- **Dumpster Diving**: Recovering information from improperly disposed hardware and documents. Organizations must properly dispose of obsolete devices — Google, for example, uses industrial crushers. For HDDs, **degaussing** (magnetic erasure) is recommended. For SSDs, **encryption followed by secure formatting** is the standard, since degaussing does not work on flash storage.

- **Social Media Mining**: Attackers harvest information from social media platforms for:
  - Data mining (organizational structure, employee names, technologies used)
  - Identity theft
  - Password guessing (using personal details from profiles)
  - Crafting convincing phishing posts and messages

- **Social Engineering**: Manipulating people into divulging information or performing actions. Based on six psychological levers (from Robert Cialdini's influence framework):
  1. **Reciprocation** — People feel obligated to return favors
  2. **Scarcity** — Creating urgency ("Your account will be locked in 24 hours")
  3. **Consistency** — Exploiting a person's desire to be consistent with prior commitments
  4. **Liking** — People comply more readily with those they like or identify with
  5. **Authority** — Impersonating figures of authority (IT admin, CEO, law enforcement)
  6. **Validation (Social Proof)** — "Everyone else has already done this"

  **Social Engineering Attack Types:**
  - **Pretexting**: Creating a fabricated scenario to extract information (e.g., posing as a help desk technician)
  - **Diversion theft**: Redirecting deliveries or information to attacker-controlled destinations
  - **Phishing**: Fraudulent communications impersonating trusted entities
    - **Vishing**: Voice-based phishing (phone calls)
    - **Spear phishing**: Targeted phishing aimed at specific individuals — **70% success rate** compared to only **3% for generic phishing**
  - **Baiting**: Leaving infected USB drives or offering free downloads
  - **Quid pro quo**: Offering something in exchange for information ("I'll fix your computer if you give me your password")
  - **Tailgating**: Physically following authorized personnel through secured doors
  - **Water holing**: Compromising websites frequently visited by the target group

  **Phishing Red Flags:**
  - Asks for sensitive information (passwords, credit card numbers)
  - Sender domain differs from the claimed organization
  - Inconsistent or suspicious links (hover to check actual URL)
  - Generic greeting (not personalized to the recipient)
  - Poor grammar and spelling
  - Creates a sense of panic or urgency

#### Internal Reconnaissance (Post-Exploitation)

Once an attacker has initial access, they perform internal recon to map the internal network:

- **Sniffing**: Capturing network traffic to discover hosts, credentials, and communication patterns. Tools include Prismdump, tcpdump, Nmap, Wireshark, Scanrand, and Cain and Abel.
- **Scanning**: Actively probing internal hosts for open ports and services
- **Packet Analysis**: Deep inspection of captured traffic for sensitive data

**Passive vs. Active Reconnaissance:**

| Aspect | Passive Reconnaissance | Active Reconnaissance |
|---|---|---|
| Interaction | No direct contact with target | Direct interaction with target systems |
| Detection risk | Very low | Higher — may trigger alerts |
| Examples | WHOIS, Google dorking, social media | Port scanning, vulnerability scanning |
| Legal risk | Generally legal | May violate laws without authorization |

### Tools of the Trade

**Offensive Frameworks:**
- **Metasploit**: The most widely used penetration testing framework, containing 1500+ exploits, auxiliary modules, and post-exploitation tools

**Password Cracking:**
- **John the Ripper**: Offline password hash cracker supporting many hash formats
- **Hydra**: Online brute-force tool for network services (SSH, FTP, HTTP, etc.)
- **Cain and Abel**: Windows-based password recovery and network sniffing tool

**Phishing and OSINT:**
- **Twint**: Twitter/X scraping tool for gathering intelligence without API access

**Network Analysis and Scanning:**
- **Wireshark**: Packet capture and deep protocol analysis
- **Nmap**: Network discovery and port scanning
- **Aircrack-ng**: Wireless network security tool suite supporting FMS, KoreK, and PTW attacks against WEP/WPA
- **Kismet**: Passive wireless network detector, sniffer, and intrusion detection system
- **Nikto**: Web server vulnerability scanner

**External Recon Tools:**
- **SAINT**: Network vulnerability scanner
- **Webshag**: Web server auditing tool
- **FOCA**: Metadata extraction from public documents
- **theHarvester**: Email, subdomain, and name harvester from public sources
- **Shodan**: Search engine for internet-connected devices and services
- **DNSRecon / DNSDumpster**: DNS enumeration and zone transfer tools
- **SpiderFoot**: Automated OSINT collection framework
- **Recon-NG**: Full-featured web reconnaissance framework
- **Google Dorks**: Advanced search operators for finding exposed information
- **Keepnet Labs**: Social engineering simulation platform

**Internal Recon Tools:**
- **Nmap**: Internal network mapping and service discovery
- **Cain and Abel**: ARP poisoning, password sniffing, credential recovery
- **Nessus**: Comprehensive vulnerability scanner
- **Netcat**: "Swiss army knife" — network connections, port scanning, file transfers
- **Metasploit**: Post-exploitation modules for pivoting and lateral movement
- **Aircrack-ng**: Internal wireless network auditing
- **Tcpdump**: Command-line packet capture
- **Responder**: LLMNR/NBT-NS/MDNS poisoner for credential harvesting on Windows networks
- **Burp Suite**: Web application security testing proxy
- **Wireshark**: Internal traffic analysis
- **Hak5**: Physical penetration testing hardware (USB Rubber Ducky, LAN Turtle, etc.)

### Combating Reconnaissance

**Detection and Response:**
- **Understand your network**: You cannot defend what you do not know exists. Maintain complete asset inventories and network maps.
- **Centralized log collection**: Aggregate logs from all systems into a SIEM for correlation and alerting
- **Ethical hacking (Red Teaming)**: Proactively simulate attacker reconnaissance to find what they would find

**Prevention:**
- **Penetration testing**: Regular authorized testing to identify vulnerabilities before attackers do
- **Vulnerability scanners**: Automated tools to continuously check for known weaknesses
- **SIEM solutions**: Security Information and Event Management systems for real-time monitoring and correlation

### WannaCry Ransomware Case Study

The case study examines the WannaCry ransomware attack of **May 12, 2017**, applied to a fictional organization (Diogenes & Ozkaya Inc.) for analytical purposes.

**Key Facts:**
- WannaCry was a global ransomware outbreak that affected over 200,000 computers across 150 countries in a single day
- It exploited **EternalBlue** (MS17-010), a vulnerability in the Windows SMB (Server Message Block) protocol
- The exploit was originally developed by the NSA and leaked by the Shadow Brokers group
- WannaCry spread as a **worm** — self-propagating across networks without user interaction
- Demanded Bitcoin ransom to decrypt locked files
- Microsoft had released patch **MS17-003** (referenced in the case study) prior to the attack, but many organizations had not applied it

**Case Study Analysis Questions:**
1. Key features of WannaCry (worm behavior, SMB exploitation, encryption of user files, ransom demand)
2. Immediate containment actions (isolate infected machines, block SMB ports 445/139 at firewalls, disable SMBv1)
3. Initial assessment facts (which systems are affected, what data is encrypted, is the worm still spreading)
4. Containment priorities (network segmentation, patching unaffected systems, preserving forensic evidence)
5. Recovery steps (restore from backups, apply MS17-010 patch, rebuild compromised systems)
6. Lessons learned — Post-incident improvements (patch management policy, network segmentation, backup strategy, incident response plan testing)

## Definitions

| Term | Definition |
|------|------------|
| Kill Chain | A structured model describing the sequential phases of a cyberattack, from initial reconnaissance through achieving the attacker's objectives |
| Reconnaissance | The information-gathering phase where attackers collect data about a target to identify vulnerabilities and plan their attack |
| Footprinting | A sub-phase of reconnaissance focused on mapping the target's public-facing infrastructure using tools like WHOIS and Google dorking |
| Enumeration | Active probing of a target network to discover specific resources, services, users, and shares |
| Weaponization | The phase where attackers create or configure exploit tools and malware tailored to the discovered vulnerabilities |
| Delivery | The phase where the attacker transmits the weaponized payload to the target via phishing, system compromise, or insider access |
| Exploitation | The phase where the delivered malware or exploit is activated, giving the attacker initial control over a target system |
| Privilege Escalation | The process of gaining higher (vertical) or broader (horizontal) access rights beyond what was initially obtained |
| Installation | The phase where attackers establish persistence mechanisms (backdoors) to maintain long-term access |
| Command and Control (C2) | The communication infrastructure that allows an attacker to remotely control compromised systems |
| Actions on Objectives | The final kill chain phase where the attacker achieves their goal — data theft, sabotage, or destruction |
| Obfuscation | Techniques used to hide attacker activity, including log manipulation, encryption, steganography, and evidence destruction |
| UEBA | User and Entity Behavior Analytics — a detection approach that uses machine learning to build behavioral baselines and detect anomalies |
| Honeypot | A decoy system designed to attract and detect attackers, providing early warning and intelligence about attack methods |
| Honeytoken | A piece of fake data (credentials, documents, database records) planted to detect unauthorized access or exfiltration |
| Degaussing | The process of erasing a magnetic storage device (HDD) by exposing it to a strong magnetic field |
| Social Engineering | Psychological manipulation of people into performing actions or divulging confidential information |
| Spear Phishing | A targeted phishing attack directed at a specific individual or organization, with a 70% success rate vs 3% for generic phishing |
| Vishing | Voice phishing — social engineering attacks conducted via phone calls |
| Tailgating | Gaining physical access to a restricted area by following an authorized person through a secured entrance |
| Water Holing | Compromising a website frequented by the target group to deliver malware to visitors |
| Google Dorking | Using advanced Google search operators to find sensitive information inadvertently exposed on the internet |
| Stuxnet | A sophisticated state-sponsored worm that targeted Iran's nuclear centrifuges, causing physical destruction of hardware |
| WannaCry | A 2017 ransomware worm that exploited the EternalBlue (MS17-010) SMB vulnerability, affecting 200,000+ computers globally |
| EternalBlue | An NSA-developed exploit targeting the Windows SMB protocol, leaked by the Shadow Brokers and used by WannaCry |
| SIEM | Security Information and Event Management — a system that aggregates logs and events from across an organization for real-time monitoring, correlation, and alerting |
| Red Teaming | Authorized simulated attacks against an organization to test defenses and identify vulnerabilities from an attacker's perspective |
| Passive Reconnaissance | Information gathering that does not involve direct contact with the target, making it nearly undetectable |
| Active Reconnaissance | Information gathering that involves direct interaction with target systems, which carries a higher risk of detection |

## Diagrams & Visual Descriptions

### Cybersecurity Kill Chain Diagram (7 Phases)

The kill chain is depicted as a linear sequence of seven connected phases, each flowing into the next. This represents the attacker's progression from initial research to final objective:

```
 [1. Reconnaissance] --> [2. Weaponization] --> [3. Delivery] --> [4. Exploitation]
                                                                        |
                                                                        v
       [7. Actions on Objectives] <-- [6. Command & Control] <-- [5. Installation]
```

Each phase represents a potential point of intervention where defenders can detect, deny, disrupt, degrade, or deceive the attacker. Breaking the chain at any phase can prevent the attack from succeeding.

### Threat Lifecycle Management Circular Diagram (6 Phases)

The LogRhythm Threat Lifecycle Management model is shown as a circular/cyclical diagram, emphasizing that threat management is a continuous process:

```
          Forensic Data
           Collection
              |
    Recovery  |  Discovery
         \    |    /
          \   |   /
           [TLM]
          /   |   \
         /    |    \
  Neutrali-   |   Qualification
   zation     |
              |
         Investigation
```

The circular nature indicates that recovery feeds back into data collection, as lessons learned improve future detection and response capabilities.

### Network Switch/MAC Address Topology Diagram

A network topology diagram showing a switch connecting multiple devices, with MAC addresses visible at each port. This illustrates concepts relevant to internal reconnaissance — how network sniffing and ARP table analysis can reveal connected devices and their physical (MAC) addresses on a LAN segment.

```
              [Switch]
             /   |   \
            /    |    \
     [Host A] [Host B] [Host C]
     MAC: AA   MAC: BB   MAC: CC
```

This type of diagram is relevant to understanding how tools like Cain and Abel perform ARP poisoning and how Wireshark captures can reveal the full topology of a network segment.

### WannaCry Ransomware Screenshot

The WannaCry ransom note displayed on an infected system, showing the characteristic red interface demanding Bitcoin payment. The screen displays a countdown timer (creating urgency), the ransom amount in Bitcoin, and instructions for payment. This is a textbook example of ransomware UI designed to pressure victims into paying quickly.

## Code Examples

No programming code examples were included in the Week 2 lecture materials. However, the following tool commands are relevant to the reconnaissance concepts covered:

```bash
# Google Dorking examples (external reconnaissance)
site:target.com filetype:pdf          # Find PDF files on target domain
intitle:"index of" site:target.com    # Find directory listings
inurl:admin site:target.com           # Find admin pages

# Nmap scanning (active reconnaissance)
nmap -sV -p 1-1000 target.com        # Version detection scan on ports 1-1000
nmap -sS target.com                   # SYN stealth scan
nmap -O target.com                    # OS detection

# theHarvester (external OSINT)
theHarvester -d target.com -b google  # Harvest emails and subdomains from Google

# Wireshark capture filter (internal reconnaissance)
# Capture only SMB traffic (relevant to WannaCry/EternalBlue)
tcp port 445 or tcp port 139
```

These examples demonstrate the types of reconnaissance commands discussed in the lecture. They should only be used in authorized penetration testing environments.

## Formulas & Algorithms

### Phishing Success Rate Comparison

$$\text{Spear Phishing Success Rate} \approx 70\%$$

$$\text{Generic Phishing Success Rate} \approx 3\%$$

This approximately **23x difference** in success rate explains why targeted spear phishing is the preferred delivery mechanism for advanced threat actors. The investment in reconnaissance (learning about the target) pays off dramatically during the delivery phase.

### Aircrack-ng Attack Algorithms

The lecture references three cryptographic attacks used by Aircrack-ng against WEP encryption:

- **FMS Attack** (Fluhrer, Mantin, Shamir): Exploits weak initialization vectors (IVs) in the RC4 key scheduling algorithm used by WEP. Requires capturing a large number of packets.
- **KoreK Attack**: An improvement on FMS that uses additional statistical correlations between IVs and key bytes, requiring fewer captured packets.
- **PTW Attack** (Pyshkin, Tews, Weinmann): The most efficient WEP attack, requiring as few as 20,000-40,000 packets to recover the key. Works by analyzing the correlation between captured keystream bytes and the secret key.

## Key Takeaways

- **The Cybersecurity Kill Chain is a defensive framework**, not just an attack model. Its primary value is giving defenders specific intervention points at each phase — break the chain at any stage and the attack fails.
- **Reconnaissance is the foundation of every attack.** The more information an attacker gathers, the more effective their weaponization, delivery, and exploitation will be. Defenders must minimize their public attack surface.
- **Spear phishing is devastatingly effective** at 70% success rate. The human element remains the weakest link in cybersecurity, and social engineering exploits psychology rather than technology.
- **The six psychological levers** (Reciprocation, Scarcity, Consistency, Liking, Authority, Validation) underpin all social engineering — understanding them is essential for both attack simulation and security awareness training.
- **Proper hardware disposal matters.** Degaussing works for HDDs; SSDs require encryption + secure formatting. Dumpster diving is a real and effective reconnaissance technique.
- **Passive reconnaissance is nearly undetectable**, making it extremely difficult to know you are being targeted until the attacker moves to active phases.
- **UEBA and behavioral analytics** represent the evolution of threat detection — moving from signature-based (known bad) to anomaly-based (unusual behavior) detection.
- **The Threat Lifecycle Management model is cyclical** — security is never "done." Recovery feeds into improved data collection and detection for future threats.
- **WannaCry demonstrates the critical importance of patch management.** The vulnerability (MS17-010) had a patch available before the attack, yet hundreds of thousands of systems remained unpatched.
- **Defense in depth**: No single control is sufficient. Organizations need detection, denial, disruption, degradation, and deception working together across all kill chain phases.

## Connections

- **Week 1 Foundations**: Week 1 likely introduced core cybersecurity principles and terminology that this week builds upon. The kill chain framework provides the structured attack model that will be referenced throughout the remainder of the course.
- **Incident Response**: The WannaCry case study connects directly to incident response methodology — the containment, investigation, and recovery questions mirror formal IR frameworks (NIST SP 800-61) that will likely be covered in future weeks.
- **Network Security**: The reconnaissance tools and techniques (Nmap, Wireshark, packet sniffing) connect to networking fundamentals. Understanding TCP/IP, ports, and protocols is prerequisite knowledge for both attack and defense.
- **Operating Systems**: Privilege escalation (vertical and horizontal) ties directly to OS security concepts — user permissions, access controls, kernel vulnerabilities, and process isolation.
- **Software Engineering**: The kill chain's emphasis on exploitation connects to secure coding practices — buffer overflows, input validation, and vulnerability management in the software development lifecycle.
- **Cryptography**: Aircrack-ng's FMS/KoreK/PTW attacks demonstrate real-world cryptographic failures (WEP), while WannaCry's ransomware encryption illustrates how cryptography can be weaponized.
- **Ethics and Law**: The distinction between passive and active reconnaissance has legal implications. Unauthorized active scanning may violate computer fraud laws, while red teaming requires explicit written authorization.
- **Database Security**: SQL injection (referenced via tools like Burp Suite and SQLMap) connects to database security topics that may appear in later weeks.
- **Broader Industry Context**: The Lockheed Martin kill chain is one of several attack frameworks. Students should be aware of MITRE ATT&CK (a more granular, tactics/techniques-based framework) which extends and complements the kill chain model and is widely used in industry.
