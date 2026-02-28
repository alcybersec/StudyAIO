# CSIT302 — Week 4: Chasing a User’s Identity & Lateral Movement

> **Source files:** CSIT302_Week4.pdf
> **Date summarized:** 2026-02-24

## Overview

This lecture covers two critical phases in the cyber-attack lifecycle: compromising a user’s identity and performing lateral movement across a network. It begins by examining why identity has become the new security perimeter, cataloguing real-world breaches and credential-theft techniques, then transitions into the methods attackers use to move from an initially compromised host to high-value targets deeper inside an organisation. Understanding these offensive techniques is essential for building effective defensive strategies in enterprise security.

## Key Concepts

### Identity as the New Perimeter

- Over 4,100 publicly disclosed data breaches occurred in 2022 alone, exposing approximately 22 billion records.
- The majority of these breaches trace back to weak, default, or stolen passwords.
- The traditional network perimeter (firewalls, DMZs) is no longer sufficient; identity itself has become the boundary that attackers target.
- Two growing threat vectors:
  - **Enterprise users**: Attackers obtain valid corporate credentials and blend in with legitimate traffic.
  - **Home users**: Banking Trojans and credential stealers harvest personal and financial login data.

### Real-World Breach Examples

- **Twitter**: 5.4 million accounts stolen via credential compromise.
- **UK Government** (June 2017): Government employee credentials stolen and sold on dark web marketplaces.
- **BYOD Risks**: When personal and corporate credentials coexist on the same device, password reuse creates a bridge between personal breaches and corporate compromise.
- **Chrome Vulnerability** (May 2017): A flaw allowed automatic download of a malicious file that could steal the user’s NTLMv2 hash. The stolen hash enabled SMB relay attacks against internal network services.

### Attack Workflow for Credential Exploitation

The typical end-to-end attack chain using stolen credentials follows this sequence:

1. **Steal credentials** (phishing, data breach dumps, malware).
2. **Rent BaaS (Botnet-as-a-Service)** -- approximately $3,000-$4,000 for 50,000 bots over a two-week period.
3. **Create crafted emails** containing a malicious dropper payload.
4. **Perform reconnaissance** to identify and profile the target organisation or individual.
5. **Launch the attack** -- deliver the payload, establish persistence, and begin exploitation.

### Cloud Computing Credential Risks

- Two-factor authentication can be bypassed. The **DeRay Mckesson case** demonstrated SIM swapping: an attacker convinced a mobile carrier to transfer the victim’s phone number to a new SIM, intercepting all SMS-based 2FA codes.
- Cloud environments introduce new trust boundaries where traditional perimeter controls do not apply.

### CI/CD Pipeline Credential Risks

- **Codecov Breach** (April 2021): Attackers modified the Codecov Bash Uploader script to exfiltrate environment variables -- including secrets, tokens, and API keys -- from customers’ CI/CD pipelines.
- Secrets stored in environment variables are a high-value target because they often include database credentials, cloud API keys, and deployment tokens.
- **Mitigation strategies**:
  - Use dedicated secrets management tools: **HashiCorp Vault**, **AWS Secrets Manager**.
  - Adopt **shift-left security**: integrate security scanning and secrets detection early in the development pipeline rather than only at deployment.

### Strategies for Compromising Identity (Three-Stage Model)

| Stage | Objective | Description |
|-------|-----------|-------------|
| Stage 1 | **Adversary profiling** | Determine who is likely to attack the organisation (nation-state, cybercriminal, insider, hacktivist). |
| Stage 2 | **Pattern analysis** | Identify the common attack techniques and TTPs used by those adversary groups. |
| Stage 3 | **Accurate simulation** | Execute realistic attack simulations to test defences against the identified techniques. |

### Hacking Techniques for Credential Compromise

#### Brute Force

- Systematically tests all possible password combinations against a target.
- Used defensively to test monitoring accuracy (do alerts fire?) and password policy strength (how quickly are weak passwords cracked?).

#### Social Engineering

- Uses the **Social Engineering Toolkit (SET)** included in Kali Linux.
- Capabilities include creating custom malware payloads, crafting phishing emails, and cloning legitimate websites.
- Attack flow: create malware with SET, embed it in a convincing email, send to target, wait for execution.

#### Pass-the-Hash

- Instead of cracking a password hash back to plaintext, the attacker **uses the hash directly** to authenticate to services that accept NTLM authentication.
- Key tools:
  - **Mimikatz**: Dumps password hashes from Windows LSASS process memory.
  - **Sysinternals**: Suite of tools (e.g., PsExec) that enable remote command execution using harvested hashes.
  - **PowerShell**: Can be scripted to automate pass-the-hash attacks across multiple hosts.

#### Harvesting Credentials via Unpatched Vulnerabilities

- **CVE-2017-8563**: A vulnerability in the Kerberos/NTLM authentication flow that allowed credential interception.
- **Pass-the-Hash Toolkit**: A collection of utilities purpose-built for extracting and replaying password hashes.
- Underscores the importance of timely patching -- known CVEs are actively exploited in credential-harvesting campaigns.

### Lateral Movement

Lateral movement is the process of moving from device to device within a compromised network to locate and access high-value data or systems.

#### Position in the Kill Chain

```
Reconnaissance --> Compromising System --> Lateral Movement --> Privilege Escalation --> Concluding Mission
```

- Lateral movement sits in the middle of the kill chain, after initial access but before the attacker achieves their final objective.
- In complex enterprise environments, lateral movement can take **weeks to months** as attackers carefully avoid detection.

#### Prerequisites for Lateral Movement

1. **Infiltration**: The attacker must already have a foothold on at least one internal host.
2. **Network mapping**: The attacker must understand the internal network topology -- what hosts exist, what services they run, and how they connect.

### Network Mapping with Nmap

Nmap (Network Mapper) is the primary tool for network reconnaissance. It scans IP ranges, enumerates services and open ports, and fingerprints operating system versions.

#### Port States

| State | Meaning |
|-------|---------|
| **Open** | A service is actively listening and accepting connections on this port. |
| **Closed** | The port is accessible (responds to probes) but no service is listening. |
| **Filtered** | A firewall, packet filter, or other device is blocking probes; Nmap cannot determine if the port is open. |
| **Unfiltered** | The port is accessible but Nmap cannot determine whether it is open or closed (seen in ACK scans). |

#### Nmap Scan Tricks and Commands

| Command | Purpose |
|---------|---------|
| `nmap -p 80 -n IP_address` | Scan port 80 only, skip DNS resolution (-n speeds up the scan by not performing reverse DNS lookups). |
| `nmap --top-ports 100 IP_address` | Scan the 100 most commonly used ports based on Nmap frequency database. |
| `nmap -sT -p 8080 192.168.1.* \| grep open` | Full TCP connect scan on port 8080 across an entire /24 subnet, filtering output for open ports only. |
| `nmap -sV --script=http-malware-host 192.168.1.1` | Service version detection combined with NSE script to check if a web server is hosting known malware. |

#### Defending Against Network Scanning

- **Proactive scanning**: Regularly scan your own network before attackers do; identify and remediate exposed services.
- **Close/block unused ports**: Reduce the attack surface by shutting down unnecessary services.
- **Firewall/VPN/IPS**: Layer multiple network defences.
- **Regular audits**: Continuous compliance checking of exposed services.

#### Blocking Scan Attempts

- **Deny-by-default firewall rules**: Only explicitly allowed traffic passes; all else is dropped.
- **UDP filtering**: Block unsolicited UDP traffic to prevent UDP-based reconnaissance.
- **Dropping vs. rejecting packets**: Dropping (silently discarding) is preferred over rejecting (sending an ICMP unreachable or TCP RST) because dropping reveals less information to the attacker about what is filtered.

#### Detecting Scanning Activity

- **Logging**: Capture connection attempts, especially on unused ports (honeypot ports).
- **Analysis**: Correlate logs to identify scanning patterns (sequential port probes, rapid connection attempts from a single source).
- **Error messages as indicators**: Unusual spikes in connection errors or reset packets can signal active scanning.

### Avoiding Intrusion Detection

- **NIDS (Network Intrusion Detection Systems)**: Limited effectiveness when an attacker scans individual targets slowly rather than sweeping the entire network.
- **HIDS (Host Intrusion Detection Systems)**: Impractical at scale -- generates excessive alerts, requires significant storage, and produces high rates of false positives.
- Industry statistic: **Only 4% of cybersecurity alerts are actually investigated**, meaning the vast majority of detection signals go unexamined.

### Lateral Movement Techniques (Comprehensive List)

#### 1. Sysinternals Suite

- Microsoft’s legitimate remote administration tools (PsExec, PsLoggedOn, PsFile, etc.).
- **Why attackers use it**: These are signed Microsoft binaries; antivirus solutions typically ignore them, and they do not trigger user-visible alerts on the target system.

#### 2. File Shares

- Accessing and writing to network file shares (SMB/CIFS).
- **Why attackers use it**: File share access is a normal, legitimate protocol; detection probability is low. Attackers can plant malware, backdoors, or exfiltrate data through shared folders.

#### 3. Remote Desktop (RDP)

- Provides full GUI-based remote access to the target machine.
- Connection is encrypted, making content inspection difficult for network monitors.
- **Limitation**: The target user may see the session or be disconnected, making this technique more visible than others.

#### 4. PowerShell

- Windows’ built-in object-oriented scripting language with deep system access.
- Offensive frameworks: **PowerSploit** (post-exploitation), **Nishang** (penetration testing).
- Capabilities: execute commands remotely, create scheduled tasks, download and execute payloads in memory.
- **Why attackers use it**: Does not trigger most antivirus solutions, leaves minimal forensic footprints, and is a legitimate system tool present on all modern Windows hosts.

#### 5. WMI (Windows Management Instrumentation)

- A built-in Windows management framework for querying system information and executing remote processes.
- **WMImplant**: A PowerShell-based tool that uses WMI for command-and-control operations.
- Supports persistent malware deployment through WMI event subscriptions.
- **Notable use**: WMI-based lateral movement was employed in the **Sony Pictures hack (2014)**, one of the most destructive corporate cyber-attacks on record.

#### 6. Scheduled Tasks

- Attackers create scheduled tasks on remote systems that run with **SYSTEM-level privileges**.
- Enables data exfiltration over time -- tasks can be set to execute periodically, slowly siphoning data to avoid detection.

#### 7. Remote Registry

- Attackers modify the Windows registry on remote hosts to:
  - Disable security protections (Windows Defender, firewall rules).
  - Disable or reconfigure antivirus software.
  - Configure the system to support persistence mechanisms for malware.

#### 8. Active Directory Exploitation

- Active Directory (AD) is the **richest information source** in a Windows domain -- it contains user accounts, group memberships, computer objects, trust relationships, and Group Policy configurations.
- **PowerShell AD-Recon**: Scripts that enumerate AD objects, trusts, SPNs, and delegation settings.
- **Mimikatz for Kerberos tickets**: Extracts Kerberos Ticket Granting Tickets (TGTs) from memory, enabling the attacker to impersonate any authenticated user.
- **MS14-068 vulnerability**: A critical flaw in the Kerberos Key Distribution Centre (KDC) that allowed any domain user to forge a Privilege Attribute Certificate (PAC) and escalate to Domain Admin.

#### 9. Breached Host Analysis

- After compromising a workstation, attackers search for:
  - **Saved passwords** in web browsers (Chrome, Firefox credential stores).
  - **Credentials in plaintext files** (notes, configuration files, scripts).
  - **Log files** that may contain authentication tokens or session data.
  - **Screen captures** or clipboard history that may reveal passwords or sensitive information.

#### 10. Central Administrator Consoles

- High-value targets include:
  - **ATM controllers**: Access can enable cash-out attacks.
  - **POS (Point-of-Sale) systems**: Access to payment card transaction data.
  - **Network administration tools**: Centralized management consoles often have broad access across the entire infrastructure.

#### 11. Email Pillaging

- Accessing the compromised user’s email to search for:
  - Credentials shared via email.
  - Internal documentation, network diagrams, or security procedures.
  - Contacts and relationships useful for further social engineering.

#### 12. Admin Shares (C$, ADMIN$, IPC$)

- Default administrative shares in Windows:
  - **C$**: Root of the C: drive, accessible to administrators.
  - **ADMIN$**: Points to the Windows installation directory.
  - **IPC$**: Inter-Process Communication share, used for named pipes and remote administration.
- Attackers with admin credentials can use these shares to transfer files and execute commands remotely.

#### 13. Pass the Ticket

- Steal Kerberos tickets using techniques such as **DCSync** (replicating the domain controller’s credential database via the Directory Replication Service protocol).
- The stolen tickets allow authentication to any service the original ticket holder had access to, without knowing the actual password.

#### 14. Pass-the-Hash

- Use **Mimikatz** to dump NTLM password hashes from LSASS memory.
- Reuse the hashes to authenticate to other systems without cracking the password.
- Particularly effective in environments where local administrator passwords are reused across multiple machines.

### Two-Stage Lateral Movement Model

| Stage | Description | Requirement |
|-------|-------------|-------------|
| **Stage 1: User compromised** | The attacker has the credentials of a regular domain user. | Requires a **user action** -- clicking a phishing link, opening a malicious attachment, etc. |
| **Stage 2: Workstation admin access** | The attacker escalates from regular user to local administrator on the compromised workstation. | Requires an **elevation exploit** -- a local privilege escalation vulnerability or misconfiguration. |

## Definitions

| Term | Definition |
|------|------------|
| BaaS (Botnet-as-a-Service) | A criminal service model where attackers rent access to a botnet (network of compromised machines) for a fee, typically used to distribute malware or conduct DDoS attacks. |
| Pass-the-Hash | An attack technique where the attacker uses a captured NTLM password hash to authenticate to a remote service without needing to know the plaintext password. |
| Pass the Ticket | An attack that steals Kerberos authentication tickets (TGT or service tickets) and replays them to gain unauthorized access to network resources. |
| Lateral Movement | The process of moving from one compromised system to another within a network, seeking access to higher-value targets and data. |
| Kill Chain | A model describing the stages of a cyber-attack from initial reconnaissance through to mission completion. |
| Mimikatz | An open-source post-exploitation tool that extracts plaintext passwords, hashes, Kerberos tickets, and other credentials from Windows memory. |
| NTLM (NT LAN Manager) | A suite of Microsoft authentication protocols that use a challenge-response mechanism based on password hashes. |
| Kerberos | A network authentication protocol that uses tickets issued by a Key Distribution Centre (KDC) to prove identity, used as the default authentication in Active Directory domains. |
| SMB Relay Attack | An attack where the attacker intercepts an SMB authentication request and relays it to another server, authenticating as the victim. |
| SIM Swapping | A social engineering attack where the attacker convinces a mobile carrier to transfer a victim’s phone number to a SIM card the attacker controls, bypassing SMS-based 2FA. |
| NIDS (Network Intrusion Detection System) | A system that monitors network traffic for suspicious activity and known attack signatures. |
| HIDS (Host Intrusion Detection System) | A system installed on individual hosts that monitors file changes, system calls, and local activity for signs of compromise. |
| SET (Social Engineering Toolkit) | An open-source penetration testing framework included in Kali Linux, designed for social engineering attacks such as phishing and payload delivery. |
| DCSync | An attack technique that impersonates a domain controller and uses the Directory Replication Service (DRS) protocol to request password hashes from Active Directory. |
| WMI (Windows Management Instrumentation) | A Windows subsystem that provides a standardized interface for monitoring and managing system resources, often abused by attackers for remote code execution. |
| Shift-Left Security | The practice of integrating security testing and controls earlier in the software development lifecycle, rather than only at deployment or post-deployment. |
| CVE (Common Vulnerabilities and Exposures) | A standardized system for identifying and cataloguing publicly known cybersecurity vulnerabilities. |
| Admin Shares (C$, ADMIN$, IPC$) | Default hidden network shares in Windows that provide administrative access to the file system and inter-process communication. |

## Diagrams & Visual Descriptions

### Attack Workflow Diagram

```
+-------------------+     +------------------+     +---------------------+
| Steal Credentials | --> | Rent BaaS        | --> | Craft Malicious     |
| (phishing, dumps, |     | (~$3-4K for 50K  |     | Emails with Dropper |
|  malware)         |     |  bots / 2 weeks) |     |                     |
+-------------------+     +------------------+     +---------------------+
                                                            |
                                                            v
                          +------------------+     +---------------------+
                          | Launch Attack    | <-- | Recon & Identify    |
                          | (deliver payload)|     | Target              |
                          +------------------+     +---------------------+
```

### Cyber Kill Chain (Lateral Movement Context)

```
+-----------------+     +---------------------+     +-------------------+
| Reconnaissance  | --> | Compromising System | --> | Lateral Movement  |
| (target profil- |     | (initial foothold)  |     | (device to device)|
|  ing, scanning) |     |                     |     |                   |
+-----------------+     +---------------------+     +-------------------+
                                                            |
                                                            v
                        +---------------------+     +-------------------+
                        | Concluding Mission  | <-- | Privilege         |
                        | (data exfil, impact)|     | Escalation        |
                        +---------------------+     +-------------------+
```

### Two-Stage Lateral Movement Model

```
+---------------------------+          +-------------------------------+
| STAGE 1: User Compromised |  ------> | STAGE 2: Workstation Admin   |
|                           |          |                               |
| - Phishing click          |          | - Local privilege escalation  |
| - Malicious attachment    |          | - Exploit misconfiguration    |
| - Credential reuse        |          | - Abuse vulnerable service    |
|                           |          |                               |
| Requires: USER ACTION     |          | Requires: ELEVATION EXPLOIT   |
+---------------------------+          +-------------------------------+
```

### Nmap Port State Diagram

```
Probe Sent to Port
        |
        v
  +------------+
  | Response?  |
  +-----+------+
        |
   +----+----+--------------------+
   |         |                    |
   v         v                    v
 SYN/ACK   RST               No Response /
 received  received           ICMP Unreachable
   |         |                    |
   v         v                    v
 [OPEN]   [CLOSED]           [FILTERED]

 ACK Scan:
 RST received but cannot determine open/closed --> [UNFILTERED]
```

## Code Examples

### Nmap Scanning Commands

```bash
# Basic scan on port 80, skip DNS resolution for speed
nmap -p 80 -n 192.168.1.1

# Scan the 100 most commonly used ports
nmap --top-ports 100 192.168.1.1

# Full TCP connect scan on port 8080 across a /24 subnet, filter for open ports
nmap -sT -p 8080 192.168.1.* | grep open

# Service version detection + malware hosting check via NSE script
nmap -sV --script=http-malware-host 192.168.1.1
```

**Explanation:**
- `-p` specifies the port(s) to scan.
- `-n` disables DNS resolution, which speeds up scans when hostnames are not needed.
- `-sT` performs a full TCP connect scan (completes the three-way handshake), which is more reliable but also more detectable than a SYN scan (`-sS`).
- `-sV` probes open ports to determine the service name and version.
- `--script=http-malware-host` runs an Nmap Scripting Engine (NSE) script that checks if the target web server is associated with known malware distribution.
- `192.168.1.*` is a wildcard that expands to scan all 256 addresses in the 192.168.1.0/24 subnet.

### Pass-the-Hash with Mimikatz (Conceptual)

```powershell
# Step 1: Dump NTLM hashes from LSASS memory on the compromised host
mimikatz # sekurlsa::logonpasswords

# Step 2: Use the extracted hash to authenticate to a remote system
mimikatz # sekurlsa::pth /user:Administrator /domain:CORP /ntlm:<hash> /run:cmd.exe
```

**Explanation:**
- `sekurlsa::logonpasswords` extracts all cached credentials (plaintext passwords, NTLM hashes, Kerberos tickets) from the LSASS (Local Security Authority Subsystem Service) process.
- `sekurlsa::pth` (pass-the-hash) creates a new process authenticated with the supplied NTLM hash, without ever needing the plaintext password.
- This is possible because NTLM authentication uses the hash directly in the challenge-response protocol.

### WMI Remote Execution (Conceptual)

```powershell
# Execute a command on a remote system using WMI
Invoke-WmiMethod -ComputerName TARGET_PC -Class Win32_Process -Name Create `
  -ArgumentList "cmd.exe /c whoami > C:	emp\output.txt"
```

**Explanation:**
- `Invoke-WmiMethod` is a PowerShell cmdlet that calls a WMI method on a local or remote system.
- `Win32_Process` with the `Create` method spawns a new process on the target.
- This executes entirely through WMI, which is a legitimate Windows management protocol and is often not flagged by antivirus or endpoint detection tools.

## Formulas & Algorithms

### Brute Force Complexity

The time to brute force a password depends on the character set size and password length:

$$T = rac{C^L}{R}$$

Where:
- $T$ = time to exhaust all combinations
- $C$ = character set size (e.g., 26 for lowercase, 62 for alphanumeric, 95 for all printable ASCII)
- $L$ = password length
- $R$ = rate of attempts per second

**Example**: A 6-character lowercase password ($C=26, L=6$) at 1 million attempts/second:

$$T = rac{26^6}{10^6} = rac{308,915,776}{1,000,000} pprox 309 	ext{ seconds} pprox 5 	ext{ minutes}$$

An 8-character alphanumeric password ($C=62, L=8$):

$$T = rac{62^8}{10^6} = rac{218,340,105,584,896}{1,000,000} pprox 218,340,106 	ext{ seconds} pprox 6.9 	ext{ years}$$

This exponential growth demonstrates why password length is far more important than complexity alone.

## Key Takeaways

- **Identity is the new perimeter**: With cloud services, BYOD, and remote work, traditional network boundaries are insufficient. Protecting user credentials is now the most critical defensive priority.
- **Credential theft is cheap and scalable**: Attackers can rent botnets for a few thousand dollars and launch credential-harvesting campaigns against millions of targets.
- **Two-factor authentication is not bulletproof**: SIM swapping and other techniques can bypass SMS-based 2FA. Hardware tokens or authenticator apps are more resilient.
- **CI/CD pipelines are high-value targets**: Secrets stored in environment variables (as demonstrated by the Codecov breach) must be managed with dedicated secrets management tools like HashiCorp Vault or AWS Secrets Manager.
- **Lateral movement is the attacker’s primary post-compromise activity**: Once inside a network, attackers move methodically from host to host, leveraging legitimate tools and protocols to avoid detection.
- **Legitimate tools are the attacker’s best friend**: Sysinternals, PowerShell, WMI, RDP, and scheduled tasks are all built into Windows and trusted by security tools, making them ideal for stealthy lateral movement.
- **Nmap is the foundational reconnaissance tool**: Understanding port states (open, closed, filtered, unfiltered) and scan techniques is essential for both attackers and defenders.
- **Only 4% of security alerts are investigated**: This statistic highlights the critical gap in security operations and explains why attackers can operate undetected for months.
- **Active Directory is the crown jewel**: Compromising AD gives an attacker access to all domain credentials, group policies, and trust relationships. Defending AD is paramount.
- **Defence must be proactive**: Regular scanning, deny-by-default firewall rules, timely patching (especially for CVEs like MS14-068 and CVE-2017-8563), and proper secrets management are essential.
- **All 14 lateral movement techniques** (Sysinternals, file shares, RDP, PowerShell, WMI, scheduled tasks, remote registry, Active Directory, breached host analysis, central admin consoles, email pillaging, admin shares, Pass the Ticket, Pass-the-Hash) exploit legitimate Windows functionality, making detection extremely challenging.

## Connections

- **Week 4 builds on earlier reconnaissance concepts** (likely covered in Weeks 1-3) by showing how reconnaissance data is used operationally during lateral movement. The kill chain model positions lateral movement as the natural successor to initial compromise.
- **Kerberos and NTLM authentication** are foundational networking and operating systems concepts. Understanding how these protocols work (and fail) connects to broader computer networking and OS security topics.
- **The Codecov breach and CI/CD risks** connect to software engineering practices. Students studying DevOps or software development will recognise that security is not just an operations concern but must be integrated into the build pipeline (shift-left).
- **Nmap scanning and port analysis** connect to computer networking fundamentals -- TCP/IP, the three-way handshake, UDP, and firewall behaviour. The distinction between dropping and rejecting packets ties directly to network protocol behaviour.
- **Social engineering and phishing** connect to human factors in security, a topic that bridges CS with psychology and organisational behaviour.
- **The Sony Pictures hack (2014)** and other case studies connect theoretical techniques to real-world consequences, reinforcing the practical relevance of every technique covered.
- **Privilege escalation** (referenced as the next step after lateral movement in the kill chain) will likely be covered in upcoming weeks, making this lecture a prerequisite for understanding the full attack lifecycle.
