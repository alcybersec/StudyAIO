# CSIT302 — Week 5: Privilege Escalation

> **Source files:** CSIT302_Week5.pdf
> **Date summarized:** 2026-02-24

## Overview

This lecture provides a thorough examination of privilege escalation — the process by which attackers elevate their access rights on a compromised system to achieve more destructive or far-reaching objectives. Privilege escalation sits at a critical juncture in the cyber kill chain, occurring after initial system compromise and lateral movement, and directly preceding the final mission objective. Understanding these techniques is essential for both offensive security professionals (penetration testers) and defensive security engineers who must anticipate and prevent such attacks. The lecture covers the two primary classifications (horizontal and vertical), specific technical methods attackers employ on Windows, macOS, and web-based systems, and the post-exploitation activities that follow successful privilege escalation.

## Key Concepts

### Position in the Cyber Kill Chain

Privilege escalation does not occur in isolation. It is a specific phase within a structured attack methodology known as the kill chain. The attacker must first perform reconnaissance, then compromise a system, move laterally through the network, and only then attempt to escalate privileges before concluding the mission.

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │                        CYBER KILL CHAIN                             │
 │                                                                     │
 │  ┌─────────────┐   ┌──────────────┐   ┌─────────────┐              │
 │  │   (External) │   │ Compromising │   │   Lateral   │              │
 │  │    Recon     │──>│    System    │──>│  Movement   │              │
 │  └─────────────┘   └──────────────┘   └──────┬──────┘              │
 │                                               │                     │
 │                                               v                     │
 │                                      ┌────────────────┐             │
 │                                      │   PRIVILEGE    │  <-- YOU    │
 │                                      │  ESCALATION    │      ARE    │
 │                                      │  ************  │      HERE   │
 │                                      └───────┬────────┘             │
 │                                              │                      │
 │                                              v                      │
 │                                     ┌─────────────────┐             │
 │                                     │  Concluding the │             │
 │                                     │    Mission      │             │
 │                                     └─────────────────┘             │
 └──────────────────────────────────────────────────────────────────────┘
```

The key insight is that attackers typically cannot jump directly from initial access to mission completion. Most compromised accounts operate under the principle of least privilege, meaning they have limited rights. Privilege escalation bridges this gap.

### Why Privilege Escalation Matters

Many developers and system administrators employ the **least privilege rule**, meaning user accounts are provisioned with only the minimum permissions necessary to perform their tasks. This means that when an attacker initially compromises a user account, that account usually does not have sufficient rights to achieve the attacker's ultimate objectives. These objectives may include:

- **Mass deletion** of files and data
- **Corruption** of databases and systems
- **Theft of data** (exfiltration of sensitive information)
- **Disabling computers** or critical infrastructure
- **Destroying hardware** (as in the Stuxnet attack)

Because of these limitations, attackers must escalate from a low-privileged account to a higher-privileged one.

### Horizontal Privilege Escalation

Horizontal privilege escalation occurs when an attacker who controls one normal (non-admin) user account gains access to **other users' accounts at the same privilege level**. While the attacker does not gain administrator rights, they significantly expand their foothold.

```
 HORIZONTAL PRIVILEGE ESCALATION
 ────────────────────────────────────────────────────

   Same privilege level, different accounts:

   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │  User A  │───>│  User B  │───>│  User C  │
   │ (Normal) │    │ (Normal) │    │ (Normal) │
   │ Attacker │    │ Victim 1 │    │ Victim 2 │
   └──────────┘    └──────────┘    └──────────┘
        │               │               │
        └───────────────┴───────────────┘
           All at the SAME privilege tier
```

**Two main pathways for horizontal escalation:**

1. **Through software bugs:** A normal user exploits a vulnerability to view or access other users' files and data. For example, an Insecure Direct Object Reference (IDOR) vulnerability in a web application might allow User A to access User B's records simply by changing an ID parameter.

2. **Through compromised administrator accounts:** If the attacker has obtained admin credentials, they can create additional admin-level user accounts, effectively providing persistent horizontal access across the admin tier.

**Common techniques used in horizontal escalation:**

| Technique | Description |
|-----------|-------------|
| Session/cookie theft | Stealing a user's authenticated session token to impersonate them |
| Cross-Site Scripting (XSS) | Injecting malicious scripts to steal credentials or session data |
| Guessing weak passwords | Brute-forcing or dictionary-attacking accounts with poor passwords |
| Keystroke logging | Capturing credentials as users type them via keyloggers |

**Outcomes of successful horizontal escalation:**
- Well-established remote access across multiple accounts
- Access to several user accounts and their associated data
- Knowledge of how to avoid detection through the compromised accounts

### Vertical Privilege Escalation

Vertical privilege escalation is more difficult than horizontal escalation but significantly more rewarding. The attacker moves from a lower privilege level to a **higher privilege level**, ultimately acquiring system-level or administrator rights.

```
 VERTICAL PRIVILEGE ESCALATION
 ────────────────────────────────────────────────────

   Moving UP the privilege hierarchy:

   ┌──────────────────────────────────┐
   │        SYSTEM / ROOT             │  <-- TARGET
   │   (Full control over OS)         │
   └──────────────┬───────────────────┘
                  ^
                  │  Escalation
                  │
   ┌──────────────┴───────────────────┐
   │       ADMINISTRATOR              │  <-- Intermediate
   │   (Elevated privileges)          │
   └──────────────┬───────────────────┘
                  ^
                  │  Escalation
                  │
   ┌──────────────┴───────────────────┐
   │       NORMAL USER                │  <-- STARTING POINT
   │   (Limited privileges)           │      (Attacker begins here)
   └──────────────────────────────────┘
```

**Key characteristics of vertical escalation:**

- **Higher chance of staying undetected:** Super user access often allows disabling or bypassing security monitoring
- **Platform-specific techniques:** The exact methods differ depending on the target operating system
  - **Windows:** Buffer overflow exploits (e.g., EternalBlue / WannaCry)
  - **macOS:** Jailbreaking techniques
  - **Web-based systems:** Backend code exploitation
- **Enables unauthorized code execution:** Once elevated, the attacker can deploy malware, ransomware, or other malicious tools
- **Complex operations:** Often requires kernel-level manipulation
- **Stealth requirements:** The attacker must avoid raising alarms, disable security systems where possible, and leverage legitimate system tools to blend in

**EternalBlue and WannaCry:** The EternalBlue exploit, attributed to the NSA and later leaked by the Shadow Brokers group, targeted a buffer overflow vulnerability in the Windows SMB protocol. It became the foundation of the WannaCry ransomware attack in May 2017, which affected over 200,000 computers across 150 countries. This is a textbook example of vertical privilege escalation via buffer overflow.

### How Privilege Escalation Works — Six Core Methods

#### 1. Credential Exploitation

Users require valid credentials (username and password) to access systems. Attackers specifically target administrator accounts because compromised admin credentials provide:
- Elevated privileges immediately upon login
- Ability to move laterally across the network
- Unrestricted access to system resources

**Important note:** Simply resetting passwords is only a temporary fix. If the root cause of the credential compromise (e.g., a keylogger, phishing infrastructure, or credential-stuffing vulnerability) is not eliminated, the attacker will re-compromise the account.

#### 2. Misconfigurations

Security misconfigurations allow attackers to bypass authentication requirements entirely. These are especially dangerous because they require **mitigation** (changing configurations) rather than **remediation** (patching software).

Common misconfigurations include:
- **Poor default settings** that ship with software or hardware
- **Undocumented backdoors** left in firmware or applications
- **Blank or default passwords** on administrative interfaces
- **Insecure access routes** such as open management ports or unprotected API endpoints

#### 3. Vulnerabilities and Exploits

These are mistakes made during the development, design, or configuration of software. The threat posed by a given vulnerability is shaped by three factors:
- **Severity** of the vulnerability (CVSS score)
- **Resources at risk** if the vulnerability is exploited
- **Availability of exploits** (whether public exploit code exists)

Most vulnerabilities enable horizontal escalation, but some critical ones enable vertical escalation.

#### 4. Social Engineering

Manipulating users into revealing credentials or performing actions that grant the attacker elevated access. This can include phishing, pretexting, baiting, or tailgating.

#### 5. Malware

Various types of malicious software are used to facilitate privilege escalation:

| Malware Type | Role in Privilege Escalation |
|-------------|------------------------------|
| Viruses | Attach to legitimate programs, may modify system files |
| Worms | Self-propagate, can exploit vulnerabilities automatically |
| Adware | May serve as initial foothold for further exploitation |
| Spyware | Capture credentials, keystrokes, and sensitive data |
| Ransomware | Encrypt data for extortion, often requires elevated privileges |

Malware is used for data exfiltration, maintaining control, and disrupting operations.

#### 6. Avoiding Alerts

Sophisticated attackers take active steps to avoid triggering security alarms:
- **Disable or evade** security monitoring systems (antivirus, EDR, SIEM)
- **Create or modify files** to resemble legitimate system services
- **Use legitimate tools** (such as PowerShell, WMI, or PsExec) that do not trigger malware alerts — a technique known as "Living off the Land" (LOtL)

### Specific Privilege Escalation Techniques

#### Technique 1: Exploiting Unpatched Operating Systems

Unpatched systems are among the most common vectors for privilege escalation. Tools like **Nessus** (vulnerability scanner) and **Nmap** (network mapper) can identify machines missing critical patches.

**Exploit discovery workflow:**
1. Scan the target with Nessus or Nmap to identify missing patches
2. Search for known exploits using Kali Linux tools or **Searchsploit** (a local mirror of exploit-db.com)
3. Use tools like **PowerUp** (a PowerShell script from the PowerSploit framework) to bypass Windows privilege management mechanisms

**Windows commands to check patch status:**

```powershell
# Using WMIC (Windows Management Instrumentation Command-line)
# Lists all installed hotfixes with their descriptions and install dates
wmic qfe get Caption,Description,HotFixID,InstalledOn
```

```powershell
# Using PowerShell's Get-HotFix cmdlet
# Returns installed updates as PowerShell objects for filtering
get-hotfix
```

**Output example for `wmic qfe`:**
```
Caption                                     Description  HotFixID   InstalledOn
http://support.microsoft.com/?kbid=5001234  Update       KB5001234  3/15/2025
http://support.microsoft.com/?kbid=5001235  Security     KB5001235  3/20/2025
http://support.microsoft.com/?kbid=5001236  Update       KB5001236  4/01/2025
```

An attacker would compare installed patches against known vulnerabilities to identify exploitable gaps.

#### Technique 2: Access Token Manipulation

Windows uses **access tokens** to determine the security context (owner and privileges) of a process. The operating system logs administrator users as normal users but has the capability to execute processes with administrator privileges when explicitly requested (via "Run as administrator").

**How attackers exploit this:**
- If an attacker can fool the system into believing a process was started by an administrator, that process will run with full administrative privileges
- This can also occur when an attacker has stolen administrator credentials
- **Metasploit's Meterpreter** and **Cobalt Strike** heavily utilize access token manipulation

Token manipulation techniques include:
- **Token impersonation:** Duplicating an existing elevated token and applying it to a new process
- **Token theft:** Extracting tokens from running elevated processes
- **Token creation:** Forging tokens with elevated privileges using API calls

#### Technique 3: Exploiting Accessibility Features

Windows provides several accessibility features designed to assist users with disabilities. These features can run **without requiring a user to be logged in**, making them an attractive target for creating backdoors.

**Vulnerable accessibility features:**
- **Magnifier** (`magnify.exe`)
- **On-Screen Keyboard** (`osk.exe`)
- **Display Switch** (`displayswitch.exe`)
- **Narrator** (`narrator.exe`)

**Attack methodology:**
1. Replace the accessibility feature executable with a modified version (or replace it with `cmd.exe`)
2. At the Windows login screen (before authentication), click the accessibility feature button
3. Instead of launching the legitimate tool, an **administrator command prompt** opens
4. From this command prompt, the attacker can:
   - Open browsers to download tools
   - Install programs and backdoors
   - Create new user accounts with admin privileges
   - Modify system configurations

This is particularly dangerous because it requires no authentication whatsoever.

#### Technique 4: Application Shimming

The **Windows Application Compatibility Framework** uses "shims" to provide backward compatibility for legacy applications. A shim acts as a buffer layer between a legacy program and the modern operating system.

**How shimming works normally:**
```
 ┌────────────────┐     ┌───────────┐     ┌──────────────┐
 │ Legacy Program │────>│   Shim    │────>│  Windows OS  │
 │  (Old API      │     │ (Compat   │     │  (Modern     │
 │   calls)       │     │  Layer)   │     │   API)       │
 └────────────────┘     └───────────┘     └──────────────┘
                             │
                     Translates old API
                     calls to new ones
```

- During execution, the **shim cache** is referenced to determine which compatibility layers to apply
- The **shim database** uses APIs to redirect program code calls
- Shims run in **user mode** (not kernel mode)

**How attackers exploit shimming:**
- Create **custom shims** with malicious redirections
- Use shims to **bypass User Account Control (UAC)**
- **Inject DLLs** into processes via shim redirection
- **Interfere with memory addresses** to alter program behavior
- Run malicious programs with **elevated privileges** by shimming them to appear as trusted legacy applications
- **Disable Windows Defender** through shim-based redirection

#### Technique 5: Bypassing User Account Control (UAC)

**UAC** acts as a gatekeeper between normal user operations and administrator-level operations in Windows. It prompts users when a program requests elevated privileges.

**UAC bypass methods:**
- Some Windows programs are **auto-elevated** — they are allowed to escalate privileges without triggering a UAC prompt
- Certain programs can execute **COM (Component Object Model) objects** without UAC prompting
- `rundll32.exe` can load custom DLLs that leverage elevated COM objects
- Attackers can **inject a malicious process into a trusted process** that has auto-elevation privileges

```
 UAC BYPASS FLOW
 ──────────────────────────────────────────────

 Normal flow:
   Program ──> UAC Prompt ──> User Approves ──> Elevated Execution

 Bypass flow:
   Malicious Code ──> Trusted Auto-Elevate Program ──> No UAC Prompt
                         │
                         └──> Elevated Execution (attacker's code
                              runs with admin privileges)
```

#### Technique 6: DLL Injection

A **DLL (Dynamic Link Library)** is a shared library used by the Microsoft Windows operating system (the equivalent on Apple systems is a **Dylib**). DLL injection allows an attacker to run malicious code within the context of a legitimate process.

**Why DLL injection is effective:**
- Malicious actions are **masked by the legitimate process** hosting the injected DLL
- Security tools see the trusted process name, not the malicious code inside it

**DLL injection objectives:**
- Modify the Windows Registry
- Create threads in other processes
- Perform DLL loading operations
- All of these typically require administrator privileges

**Standard DLL injection sequence:**

```
 STANDARD DLL INJECTION
 ──────────────────────────────────────────────

 Step 1: Attach to legitimate process
   Attacker ──> OpenProcess() ──> Target Process (e.g., explorer.exe)

 Step 2: Allocate memory in target
   VirtualAllocEx() ──> Reserved space in target process memory

 Step 3: Copy malicious DLL path to target memory
   WriteProcessMemory() ──> DLL path written to allocated space

 Step 4: Execute the DLL in target process
   CreateRemoteThread() ──> LoadLibrary() ──> Malicious DLL loaded
```

**Reflective DLL Injection:**
A more advanced variant that loads a DLL into a process **without using the standard Windows API calls** (such as `LoadLibrary`). This technique:
- **Bypasses DLL load monitoring** tools and hooks
- Is **significantly more difficult to detect** by security software
- Loads the DLL from memory rather than from disk

**Real-world malware using DLL injection:**

| Malware | Target Process | Context |
|---------|---------------|---------|
| Backdoor.Oldrea (Havex) | `explorer.exe` | Industrial espionage targeting energy sector |
| BlackEnergy | `svchost.exe` | Ukrainian power grid attack (2015) |
| Duqu | Multiple processes | Sophisticated espionage malware related to Stuxnet |

#### Technique 7: DLL Search Order Hijacking

Rather than injecting into a running process, this technique replaces legitimate DLL files with malicious ones or manipulates where the OS searches for DLLs.

**How it works:**
- Windows follows a **specific search order** when loading DLLs (current directory, system directories, PATH directories, etc.)
- The attacker places a malicious DLL **higher in the search path** than the legitimate one
- When the program loads, it finds the malicious DLL first and loads it instead
- Alternatively, attackers can **modify the application manifest** or local configuration files to redirect DLL loading

**Risks and complexity:**
- This is a complex technique that requires caution
- If the malicious DLL does not properly replicate the expected function exports, it can cause **abnormal behavior** or **application crashes**, which could alert defenders

#### Technique 8: Dylib Hijacking on macOS

This technique mirrors DLL hijacking but targets **macOS (OS X)**. It exploits the dynamic library (`.dylib`) search mechanism on Apple systems.

**Attack flow:**
1. Identify a high-privilege program that loads dynamic libraries
2. Determine the library search order
3. Place a malicious `.dylib` file in a location searched before the legitimate library
4. When the high-privilege program loads the hijacked dylib, the attacker's malicious code executes with those elevated privileges

#### Technique 9: Exploitation of Vulnerabilities (Horizontal Focus)

This is one of the few techniques that primarily enables **horizontal** privilege escalation. It is based on programming errors in applications.

**Examples:**
- Some systems incorrectly accept certain phrases or strings as valid passwords
- Attackers can change access levels by modifying URL parameters in web applications (e.g., changing `?role=user` to `?role=admin`)

**Case study — Windows MS14-068:**
A critical programming error in the Windows Kerberos authentication system allowed an attacker to:
- Create their own **Kerberos tickets** (normally only the Key Distribution Center can issue these)
- Assign **domain administrator rights** to those forged tickets
- Accomplish all of this using only **regular user permissions**

This vulnerability demonstrated how a single coding error in an authentication protocol can completely undermine an organization's security model.

### Concluding the Mission (Post-Exploitation)

After successfully escalating privileges, the attacker enters the final phase of the kill chain. There are four primary post-exploitation activities:

#### 1. Exfiltration

The extraction of sensitive data from the compromised environment. Target data includes:
- Trade secrets and intellectual property
- Usernames and passwords (credential databases)
- Personally Identifiable Information (PII)
- Top-secret or classified documents

**Notable data breach examples:**

| Breach | Year | Impact |
|--------|------|--------|
| Ashley Madison | 2015 | 37 million user records exposed, personal/intimate data |
| Yahoo | 2013 (reported 2016) | 3 billion accounts compromised — largest breach in history |
| LinkedIn | 2016 | 164 million email/password combinations leaked |

In all cases, stolen data was put up for sale on dark web marketplaces. Beyond data theft, attackers may also **erase or modify files** to cause additional damage or cover their tracks.

#### 2. Sustainment

After exfiltrating data, sophisticated attackers do not immediately leave. They aim to **remain silent** and maintain persistent access:
- Install **rootkit viruses** that embed deeply into the operating system
- Rootkits are designed to be invisible to standard security tools
- Establish **multiple access points** so that if one backdoor is discovered and removed, others remain
- Security tools become largely ineffective against well-implemented rootkits

#### 3. Assault

This is the **most feared** post-exploitation activity. The attacker moves from data theft to active destruction:
- **Permanently damage** data and software
- **Disable or alter hardware** components
- Cause physical-world consequences

**Case study — Stuxnet:**
The Stuxnet worm is the first recorded example of a digital weapon causing physical damage to real-world infrastructure:
- **Target:** Iranian nuclear enrichment facility (Natanz)
- **Method:** Modified the speed of uranium enrichment centrifuges while reporting normal operations to monitoring systems
- **Delivery:** The nuclear facility was **not connected to the Internet** (air-gapped), so the malware was transmitted via **USB thumb drives**
- **Impact:** Estimated to have destroyed roughly 1,000 centrifuges and set back Iran's nuclear program by several years
- **Significance:** Demonstrated that cyber attacks can have kinetic, physical-world consequences

#### 4. Obfuscation

The final stage involves **covering tracks** and confusing or deterring forensic investigation:
- **Attack outdated servers** in small businesses or educational institutions first, then laterally move to the actual target — this obscures the true origin
- **Use free/public Wi-Fi** networks for command-and-control communications to avoid attribution
- **Dynamic code obfuscation** — constantly changing the malware's code signature to prevent signature-based detection by antivirus tools

## Definitions

| Term | Definition |
|------|------------|
| Privilege Escalation | The act of exploiting a vulnerability, design flaw, or misconfiguration to gain elevated access to resources that are normally protected from a user or application |
| Horizontal Escalation | Gaining access to other accounts at the **same** privilege level as the compromised account |
| Vertical Escalation | Gaining access to accounts or capabilities at a **higher** privilege level than the compromised account |
| Kill Chain | A structured model describing the stages of a cyber attack, from reconnaissance to mission completion |
| Least Privilege | A security principle where users and processes are granted only the minimum permissions necessary to perform their functions |
| Access Token | A Windows security object that identifies the security context (identity and privileges) of a process or thread |
| UAC (User Account Control) | A Windows security feature that prevents unauthorized changes by prompting for approval when elevated privileges are requested |
| DLL (Dynamic Link Library) | A shared library file format used by Windows that contains code and data used by multiple programs simultaneously |
| Dylib (Dynamic Library) | The macOS equivalent of a Windows DLL — a shared library loaded at runtime |
| Shim | A compatibility layer that intercepts API calls between a legacy application and the operating system to ensure backward compatibility |
| Buffer Overflow | A vulnerability where a program writes data beyond the allocated memory buffer, potentially allowing an attacker to execute arbitrary code |
| Rootkit | Malicious software designed to provide continued privileged access to a computer while hiding its presence from security tools |
| Kerberos | A network authentication protocol that uses tickets to allow nodes to prove their identity securely over a non-secure network |
| COM Object (Component Object Model) | A Microsoft binary-interface standard for creating software components that can interact with each other across process and machine boundaries |
| Exfiltration | The unauthorized transfer of data from a compromised system to an attacker-controlled location |
| Obfuscation | Techniques used to make code, data, or attack activity difficult to understand or detect |
| EternalBlue | An NSA-developed exploit targeting the Windows SMB protocol via buffer overflow, leaked by the Shadow Brokers and used in the WannaCry ransomware attack |
| Reflective DLL Injection | An advanced DLL injection technique that loads a DLL from memory without using standard Windows API calls, making it harder to detect |
| Social Engineering | Psychological manipulation of people into performing actions or divulging confidential information |
| PowerUp | A PowerShell script from the PowerSploit framework used to identify and exploit Windows privilege escalation vectors |
| Searchsploit | A command-line tool that searches a local copy of the Exploit Database (exploit-db.com) for known exploits |
| MS14-068 | A critical Windows Kerberos vulnerability that allowed regular users to forge domain admin Kerberos tickets |
| Application Shimming | Abusing the Windows Application Compatibility Framework to intercept and redirect API calls for malicious purposes |
| Air Gap | A physical isolation security measure where a computer or network is not connected to the Internet or any other unsecured networks |
| Living off the Land (LOtL) | An attack technique where attackers use legitimate system tools (PowerShell, WMI, etc.) rather than custom malware to avoid detection |

## Diagrams & Visual Descriptions

### Kill Chain Position Diagram

The lecture presents a linear flow diagram showing the five stages of a cyber attack. Privilege escalation is highlighted as the fourth stage, positioned between lateral movement and mission conclusion. The diagram uses directional arrows to show progression and emphasizes that privilege escalation is a prerequisite for the final stage.

```
 ┌─────────────────────────────────────────────────────────────────┐
 │                                                                 │
 │  [Reconnaissance] ──> [Compromise] ──> [Lateral Movement]      │
 │                                              │                  │
 │                                              v                  │
 │                                    [PRIVILEGE ESCALATION]       │
 │                                         (Week 5 Focus)         │
 │                                              │                  │
 │                                              v                  │
 │                                    [Concluding Mission]         │
 │                                                                 │
 └─────────────────────────────────────────────────────────────────┘
```

### Horizontal vs. Vertical Escalation Comparison

The lecture includes a diagram contrasting horizontal and vertical privilege escalation. Horizontal escalation is depicted as lateral movement across accounts at the same level, while vertical escalation shows an upward movement through privilege tiers.

```
 HORIZONTAL                          VERTICAL
 ──────────                          ────────

 User A ──> User B ──> User C       ┌─────────────┐
 (same level, different accounts)    │  SYSTEM     │  Level 3
                                     ├─────────────┤
                                     │  ADMIN      │  Level 2
                                     ├─────────────┤
                                     │  USER       │  Level 1
                                     └──────▲──────┘
                                            │
                                       (attacker moves UP)
```

### USB Thumb Drive (Stuxnet Reference)

The lecture includes an image of a USB thumb drive to illustrate the Stuxnet delivery mechanism. This visual emphasizes that even air-gapped networks (those physically isolated from the Internet) can be compromised through physical media, highlighting the importance of physical security controls alongside network security.

## Code Examples

### Checking Windows Patch Status with WMIC

```cmd
wmic qfe get Caption,Description,HotFixID,InstalledOn
```

**Explanation:** This Windows Management Instrumentation Command-line (WMIC) command queries the Quick Fix Engineering (QFE) database on a Windows system. It returns a table of all installed hotfixes including:
- `Caption` — URL to the Microsoft support article for the patch
- `Description` — Type of update (Security Update, Update, Hotfix)
- `HotFixID` — The KB (Knowledge Base) article number identifying the patch
- `InstalledOn` — The date the patch was applied

**Offensive use:** An attacker who has gained initial access to a Windows system runs this command to identify which patches are missing. They then cross-reference missing patches with known exploits (using Searchsploit or exploit-db.com) to find a viable privilege escalation vector.

**Defensive use:** System administrators use this same command during security audits to verify patch compliance across their fleet.

### Checking Patch Status with PowerShell

```powershell
Get-HotFix
```

**Explanation:** The PowerShell equivalent of the WMIC command above. It returns the same information as PowerShell objects, which can be further filtered and processed:

```powershell
# Filter for security updates only
Get-HotFix | Where-Object { $_.Description -eq "Security Update" }

# Check if a specific KB is installed
Get-HotFix -Id KB5001234

# Sort by installation date to see most recent patches
Get-HotFix | Sort-Object InstalledOn -Descending
```

### Searchsploit Usage (Kali Linux)

```bash
# Search for exploits related to a specific vulnerability
searchsploit ms14-068

# Search for Windows privilege escalation exploits
searchsploit windows privilege escalation

# Search for a specific CVE
searchsploit CVE-2017-0144
```

**Explanation:** Searchsploit is a command-line search tool for the Exploit Database (exploit-db.com). It maintains a local mirror of the database so searches can be performed offline. This is particularly useful during penetration testing engagements where maintaining a low network profile is important.

### DLL Injection Pseudocode

```c
// Simplified DLL injection sequence (pseudocode)

// Step 1: Get a handle to the target process
HANDLE hProcess = OpenProcess(PROCESS_ALL_ACCESS, FALSE, targetPID);

// Step 2: Allocate memory in the target process for the DLL path
LPVOID pRemoteMemory = VirtualAllocEx(hProcess, NULL, dllPathSize,
                                       MEM_COMMIT, PAGE_READWRITE);

// Step 3: Write the DLL path into the allocated memory
WriteProcessMemory(hProcess, pRemoteMemory, dllPath, dllPathSize, NULL);

// Step 4: Get the address of LoadLibraryA in kernel32.dll
FARPROC pLoadLibrary = GetProcAddress(GetModuleHandle("kernel32.dll"),
                                       "LoadLibraryA");

// Step 5: Create a remote thread that calls LoadLibrary with our DLL path
HANDLE hThread = CreateRemoteThread(hProcess, NULL, 0,
                                     (LPTHREAD_START_ROUTINE)pLoadLibrary,
                                     pRemoteMemory, 0, NULL);

// The target process now loads and executes our malicious DLL
```

**Explanation:** This pseudocode demonstrates the classic DLL injection technique on Windows. The attacker's code attaches to a legitimate process (e.g., `explorer.exe`), allocates memory within that process, writes the path to a malicious DLL, and then forces the process to load that DLL by creating a remote thread that calls `LoadLibraryA`. Once loaded, the malicious DLL's code executes within the security context of the legitimate process, inheriting its privileges and trust level.

## Formulas & Algorithms

### Vulnerability Risk Assessment

The threat posed by a vulnerability can be conceptually evaluated using three factors:

$$Risk = f(Severity, Resources\_at\_Risk, Exploit\_Availability)$$

Where:
- **Severity** is typically measured using the Common Vulnerability Scoring System (CVSS), scored from 0.0 to 10.0
- **Resources at risk** considers the value and sensitivity of data/systems accessible through the vulnerability
- **Exploit availability** ranges from theoretical (no known exploit) to weaponized (publicly available exploit code)

### DLL Search Order (Windows Default)

When a Windows application loads a DLL without specifying a full path, the system searches in this order:

```
1. The directory from which the application was loaded
2. The system directory (C:\Windows\System32)
3. The 16-bit system directory (C:\Windows\System)
4. The Windows directory (C:\Windows)
5. The current working directory
6. Directories listed in the PATH environment variable
```

An attacker performing DLL search order hijacking places their malicious DLL at position 1 or any position **above** where the legitimate DLL resides, ensuring the malicious version is found first.

### Content Similarity for Duplicate Detection

When comparing files for duplicate detection (as referenced in the course's broader context of data integrity), a common approach uses the Jaccard similarity coefficient:

$$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$

Where A and B are sets of tokens (words or n-grams) from two documents. A similarity score above 0.9 (90%) typically indicates the documents are effectively duplicates.

## Key Takeaways

- **Privilege escalation is a critical phase** in the cyber kill chain — it bridges the gap between initial compromise and the attacker's ultimate objective.
- **Two classifications exist:** Horizontal (same-level access expansion) and Vertical (moving to higher privilege levels). Vertical is harder but far more rewarding for attackers.
- **The least privilege principle** is the primary defense that makes privilege escalation necessary for attackers. Enforcing it properly limits the blast radius of any single compromised account.
- **Six core methods** drive privilege escalation: credential exploitation, misconfigurations, vulnerabilities/exploits, social engineering, malware, and alert avoidance.
- **Nine specific techniques** were covered for performing privilege escalation, each targeting different aspects of operating system trust and execution models.
- **DLL injection and its variants** (standard injection, reflective injection, search order hijacking) are among the most commonly used techniques in real-world attacks and should be thoroughly understood.
- **Windows-specific features** like UAC, access tokens, application shimming, and accessibility features each present unique attack surfaces that differ from other operating systems.
- **Misconfigurations require mitigation** (changing settings) rather than remediation (patching) — this is a critical distinction for incident response.
- **Post-exploitation has four phases:** Exfiltration, Sustainment, Assault, and Obfuscation — each with distinct objectives and techniques.
- **Stuxnet demonstrated** that cyber attacks can cause physical-world damage, even to air-gapped systems, fundamentally changing the threat landscape.
- **Living off the Land** (using legitimate tools like PowerShell) is a key attacker strategy for avoiding detection during privilege escalation.
- **Always check patch status** on Windows systems — the `wmic qfe` and `Get-HotFix` commands are essential for both attackers (finding gaps) and defenders (verifying compliance).

## Connections

**Connection to Week 4 (Lateral Movement):** Privilege escalation directly follows lateral movement in the kill chain. While lateral movement focuses on expanding access across the network horizontally (moving between machines), privilege escalation focuses on deepening access vertically within a specific machine or domain. Techniques from Week 4 (credential harvesting, pass-the-hash) often provide the foundation for the privilege escalation techniques discussed this week.

**Connection to Weeks 1-3 (Reconnaissance and Initial Compromise):** The information gathered during reconnaissance (Week 1-2) directly informs which privilege escalation technique is most likely to succeed. For example, discovering that a target runs an unpatched version of Windows during recon determines whether EternalBlue or similar exploits are viable.

**Broader CS Context — Operating Systems:** Understanding privilege escalation requires deep knowledge of operating system internals — process management, memory management, access control mechanisms, and the Windows security model (tokens, SIDs, ACLs). Students studying OS design should recognize how design decisions in privilege management create or prevent attack surfaces.

**Broader CS Context — Software Engineering:** Many privilege escalation vectors (buffer overflows, DLL hijacking, insecure default configurations) stem from software engineering failures. Secure coding practices, input validation, proper memory management, and defense-in-depth design principles are the developer's primary tools for preventing these vulnerabilities.

**Broader CS Context — Networking:** Kerberos ticket forgery (MS14-068) connects directly to network authentication protocols studied in networking courses. Understanding how Kerberos works at the protocol level is essential to understanding why that vulnerability was so devastating.

**Connection to Future Weeks:** The post-exploitation techniques discussed in this lecture (exfiltration, sustainment, assault, obfuscation) will likely be expanded upon in subsequent weeks, with deeper dives into specific tools and methodologies used in each phase. Understanding privilege escalation is prerequisite knowledge for all of these topics.
