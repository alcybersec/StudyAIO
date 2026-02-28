# CSIT302 — Week 6: Security Policy

> **Source files:** CSIT302_Week6.pdf, CSIT302_Week6.docx
> **Date summarized:** 2026-02-24

## Overview

This lecture provides a comprehensive treatment of security policy within the broader framework of Governance, Risk, and Compliance (GRC). It covers the full lifecycle of security policies — from creation and review through education, enforcement, monitoring, and continuous improvement. The lecture also examines how security governance structures direct and control an organization's security activities, and includes a hands-on lab on writing security policies aligned with the ISO 27000 series of standards. Understanding security policy is foundational to every domain of cybersecurity, as policies translate high-level strategic objectives into enforceable rules that protect organizational assets.

## Key Concepts

### GRC — Governance, Risk & Compliance

GRC is an integrated framework that aligns three critical organizational functions:

- **Governance** — The strategic framework that defines policies, decision-making authority, and accountability structures. It answers "who decides what" and "who is responsible."
- **Risk Management** — The systematic process of identifying, assessing, and mitigating threats to organizational assets. It answers "what could go wrong" and "how do we reduce the likelihood or impact."
- **Compliance** — Adherence to legal requirements, industry standards, and internal policies. It answers "what rules must we follow."

GRC is critical for cybersecurity because it provides:

1. **Unified Security Posture** — All security activities are coordinated under a single framework rather than operating in silos.
2. **Proactive Risk Management** — Threats are anticipated and mitigated before they materialize into breaches.
3. **Regulatory Alignment** — The organization stays current with legal and industry obligations (e.g., GDPR, PCI-DSS, HIPAA).
4. **Executive Accountability** — Leadership is directly responsible for security outcomes, ensuring adequate resources and attention.

### Security Policy (NIST Definitions)

NIST defines security policy through several complementary lenses:

- A **set of criteria** for the provision of security services
- A **statement of required protection** for information objects
- A **set of rules** governing security-relevant system behaviors
- **Defined objectives and constraints** for a security program

Security policies are important because they:

- **Establish clear guidelines** — Everyone knows what is expected and what is prohibited.
- **Reduce human error** — Organizations with documented incident response plans save an average of **$1.49 million per breach** (IBM Cost of a Data Breach Report, 2024).
- **Ensure compliance** — Policies map to frameworks like ISO 27001 and NIST CSF.
- **Create a security culture** — Policies set the tone that security is an organizational priority, not just an IT concern.

### Maintaining Security Policy

A security policy is a **living document** — it must be revised and updated both regularly (on a scheduled cadence) and on-demand (in response to incidents or environmental changes). A well-maintained policy should:

- Incorporate **industry standards, procedures, and guidelines**
- Align with current frameworks such as **NIST CSF 2.0**, **ISO 27001**, and emerging **AI governance standards**
- Have a **well-defined scope** — clearly stating what systems, users, and data it covers
- Support **incident-driven updates** — when a security event reveals a gap, the policy is revised to close it

### Security Policy Hierarchy

Security documentation follows a layered hierarchy, moving from high-level strategic direction to low-level operational detail. Enforcement authority decreases as technical specificity increases:

```
                          +-------------+
                         /   POLICY      \          Highest enforcement authority
                        /  (Board/Exec)   \         Least technical detail
                       +-----------------+
                      /    STANDARD        \        Mandatory technical requirements
                     /   (Security Eng.)    \
                    +---------------------+
                   /     GUIDELINES          \      Recommended practices
                  /    (Dept. Managers)       \     May be optional
                 +-------------------------+
                /     BEST PRACTICES          \     Role-specific or company-wide
               /    (Teams / Departments)      \    Practical implementation
              +-------------------------------+
             /        PROCEDURE                 \   Step-by-step instructions
            /      (All Employees)               \  Most technical detail
           +-----------------------------------+    Lowest enforcement authority
```

**Policy** — The foundation of the entire security program. Sets high-level expectations, guides decisions, is not overly technical, and is enforced by proper authority (board, executive management).

**Standard** — Establishes mandatory technical requirements that must be complied with. Provides the technical details that security engineers need to implement the policy (e.g., "All passwords must be at least 14 characters with complexity requirements").

**Guidelines** — May be optional or recommended. They are aligned with the policy and standards but offer specific details with practical examples (e.g., "Consider using a password manager to generate and store complex passwords").

**Best Practices** — Implemented by the entire company or specific departments. Can be role-specific (e.g., "Web Server Security Best Practices"). Often incorporated as part of guidelines.

**Procedure** — Procedural steps outlining exactly how something must be done. The most granular and technical level (e.g., "Step 1: Open Group Policy Management Console. Step 2: Right-click the target OU...").

### NIST SP 800 Series and FIPS

**NIST SP 800-53** (Security and Privacy Controls for Information Systems and Organizations) is a comprehensive catalog of security controls used as the basis for organization-wide security programs. It covers:

- Access control, audit and accountability, awareness and training
- Configuration management, contingency planning, identification and authentication
- Incident response, maintenance, media protection, personnel security
- Physical and environmental protection, planning, risk assessment
- System and communications protection, system and information integrity

The **NIST SP 800 series** broadly provides guidelines, recommendations, and technical specifications for information security.

**FIPS Publication 200** (Minimum Security Requirements for Federal Information and Information Systems) is a **mandatory** federal standard — unlike SP 800 guidelines, FIPS compliance is legally required for federal agencies.

### University of Wollongong (UoW) Cybersecurity Policy — Case Study

The UoW policy demonstrates a real-world institutional security policy structure:

- **Section 1 — Purpose**: States why the policy exists
- **Section 2 — Application and Scope**: Applies to **all users and all devices** connected to UoW systems
- **Section 3 — Policy Principles**: Core tenets guiding security decisions
- **Section 4 — Roles and Responsibilities**:
  - **CIDO** (Chief Information and Digital Officer) — Executive accountability
  - **Cyber Security Team** — Day-to-day security operations
  - **Risk, Audit & Compliance Committee** — Oversight and assurance
  - **Staff managing IT** — Operational security implementation
  - **Users** — Individual responsibility for security
- **Section 5 — Definitions**: Ensures consistent interpretation of terms

### Educating End Users

Security awareness training is classified as a **management control** within NIST SP 800-53 and is considered one of the most important security measures an organization can implement.

Key characteristics of effective training:

- **Delivered to all employees** — not just IT staff
- **Constantly updated** — reflects the latest threat landscape
- **Includes real-world examples** — show actual phishing emails, social engineering attempts
- **Interactive practice** — users interact with simulated threats (e.g., phishing simulations)
- **Documented completion** — all users must acknowledge they have completed the training

Training outcomes should ensure all users:

1. Acknowledge completion of the training program
2. Are aware of current threats and the countermeasures available
3. Understand the consequences of policy violations

#### Case Study: Symantec Internet Security Threat Report (Vol. 24)

- **Spam campaigns** were identified as the top cause of malware delivery
- In 2016, the most common word in malicious spam was **"invoice"** — a social engineering tactic exploiting business processes
- **Social media attacks**: In 2015, diet spam campaigns on Twitter used fake accounts to spread malicious links; by 2019, social media was being weaponized for election influence campaigns
- These examples underscore why end-user education must cover email, social media, and social engineering vectors

### BYOD (Bring Your Own Device)

BYOD policies address the security challenges of employees using personal devices for work:

- Personal devices are **easy targets** because they lack centralized management and may run outdated software
- BYOD **should not be allowed** in environments requiring maximum confidentiality (e.g., classified government systems, sensitive R&D)
- Organizations need **social media guidelines** aligned with HR and legal requirements
- Policies must define **appropriate business behavior** on personal devices
- **Disciplinary actions** must be specified for violations
- Specific provisions needed for dealing with **defamatory, pornographic, or harassment-related** posts made on company-affiliated accounts

### Policy Enforcement

Effective policy enforcement requires a **holistic approach** based on the network architecture:

- Must understand all **endpoints, servers, information flows, storage locations, and data access patterns**
- Many organizations fail by **only enforcing policies at endpoints and servers** while ignoring the broader infrastructure
- Enforcement must extend to **all network components**: switches, routers, printers, IoT devices, cloud services
- A network architecture diagram is essential for mapping where enforcement points exist

### Active Directory (AD)

Active Directory is Microsoft's directory service and the primary tool for policy enforcement in Windows environments.

**Purpose:**
- Arrange network objects into a **logical and hierarchical structure**
- Provide centralized **authentication** (verifying identity) and **authorization** (granting access)

**Objects and Attributes:**
Every entity in AD is an "object" with associated attributes:
- **User** — username, password hash, group memberships, email
- **Computer** — hostname, OS version, domain membership
- **Shared Folder** — path, permissions, description
- **Printer** — location, driver, permissions

**AD Structure:**

```
                    +---------------------------+
                    |       FOREST              |
                    |  (Security boundary)       |
                    +---------------------------+
                           |
              +------------+------------+
              |                         |
     +--------+--------+      +--------+--------+
     |   DOMAIN TREE   |      |   DOMAIN TREE   |
     |  (DNS naming)   |      |                  |
     +--------+--------+      +-----------------+
              |
     +--------+--------+
     |  ROOT DOMAIN     |    e.g., corp.example.com
     |  (Parent)        |
     +--------+---------+
              |
     +--------+--------+--------+
     |                           |
  +--+--------+          +-------+------+
  |CHILD DOMAIN|         |CHILD DOMAIN  |
  | sales.corp |         | dev.corp     |
  | .example   |         | .example     |
  | .com       |         | .com         |
  +-----+------+         +------+-------+
        |                        |
   +----+----+              +----+----+
   |   OUs   |              |   OUs   |
   +---------+              +---------+
   | Users   |              | Users   |
   | Computers|             | Computers|
   | Groups  |              | Groups  |
   +---------+              +---------+
```

- **Domain** — A collection of objects sharing a common directory database. Forms the basic unit of AD.
- **Organizational Unit (OU)** — A container within a domain used to organize objects (like subdirectories). OUs can hold users, computers, groups, and other OUs.
- **Domain Tree** — Multiple domains linked in a parent-child hierarchy using contiguous DNS naming (e.g., `corp.example.com` -> `sales.corp.example.com`).
- **Forest** — The top-level container comprising one or more domain trees. Represents the ultimate security boundary.

**Trust Relationships:**
Trusts are secure connections that allow authentication across domain or forest boundaries.

| Trust Type | Direction | Transitivity | Created |
|---|---|---|---|
| Parent-Child | Two-way | Transitive | Automatic (default) |
| Tree-Root | Two-way | Transitive | Automatic |
| External | One-way or Two-way | Non-transitive | Manual |
| Forest | One-way or Two-way | Transitive | Manual |
| Shortcut | One-way or Two-way | Transitive | Manual |

- **Default**: Parent-child domains automatically receive a **transitive two-way trust** — if Domain A trusts Domain B and Domain B trusts Domain C, then Domain A trusts Domain C.
- **One-way trust**: Domain A trusts Domain B, but not the reverse.
- **Non-transitive trust**: Trust does not extend beyond the two domains involved.

### Group Policy and GPOs

**Group Policy** provides centralized control over the working environment of users and computers in an Active Directory domain.

**Historical context**: Group Policy was created to overcome problems with the Windows Registry. Registry changes were **permanent** and difficult to manage at scale. Group Policy provides a manageable, reversible, centralized alternative.

**Group Policy Object (GPO)** — A collection of settings that define what a system looks like and how it behaves for a defined group of users or computers. Administrators create GPOs and distribute them through Active Directory, linking them to specific OUs.

**Key capability**: Different departments can have **different GPOs** applied to their respective OUs. For example, the HR department OU can have a custom GPO restricting USB access, while the Development department OU might have a different GPO allowing local admin rights for testing.

### Application Whitelisting

Application whitelisting ensures that only **licensed, approved software** can execute on organizational systems, as dictated by security policy.

**NIST SP 800-167** (Guide to Application Whitelisting) provides guidance on implementation considerations:

- **Installation path** — Where applications are allowed to be installed
- **Vendor update policy** — How whitelisted applications receive updates
- **Executable files** — Which specific executables are permitted to run

**Platform-specific tools:**

| Platform | Tool | Description |
|---|---|---|
| Windows | **AppLocker** | Built-in application control using three condition types |
| macOS | **Gatekeeper** | Restricts apps to those from identified developers or the App Store |
| Linux | **SELinux** | Security-Enhanced Linux, provides mandatory access control |

**AppLocker Condition Types:**

1. **Publisher** — Evaluates the digital signature of the application. Used for **signed applications**. Can specify rules based on publisher name, product name, file name, and version.
2. **Path** — Evaluates the file system path of the application. Used when the install location is predictable and controlled.
3. **File Hash** — Computes a cryptographic hash of the executable. Used for **unsigned applications** where publisher rules cannot be applied. Must be updated when the application is updated.

### System Hardening

Hardening is a **consequence of policy deployment** — once policies define what is and is not allowed, systems are configured to match, thereby reducing the attack surface.

**CCE (Common Configuration Enumeration):**
- Provides **unique identifiers** for security-related configuration issues
- Published by NIST at **nvd.nist.gov**
- Enables standardized communication about configuration requirements across tools and organizations
- Example: `CCE-38325-4` might identify "Ensure Windows Firewall is enabled for the Domain profile"

**Platform resources:**
- **Windows**: Microsoft Security Compliance Toolkit, CIS Benchmarks
- **Linux**: Red Hat Security Guide, CIS Benchmarks for Linux distributions

### Monitoring for Compliance

Enforcement without monitoring is incomplete. Organizations must continuously verify that systems remain in their hardened, policy-compliant state.

**CCE vs. CVE — Critical Distinction:**

| Attribute | CCE | CVE |
|---|---|---|
| Full name | Common Configuration Enumeration | Common Vulnerabilities and Exposures |
| Focus | Configuration issues | Software vulnerabilities |
| Remediation | **Configuration change** | **Patch/update** |
| Example | Firewall disabled on a server | Buffer overflow in Apache |
| Managed by | NIST | MITRE |

- **CCE-based policies** can be monitored using tools like **Azure Security Center** (now Microsoft Defender for Cloud)
- Automated scanning identifies configuration drift from the desired policy state

### Enhancing Security Posture

Modern hybrid infrastructures (on-premises + cloud) are constantly changing, making manual compliance checking impractical.

**CSPM (Cloud Security Posture Management):**
- Tools that provide **visibility** into the security state of cloud environments
- Automatically detect misconfigurations, compliance violations, and security risks
- **Microsoft Defender for Cloud** is a leading CSPM tool

**Secure Score Metrics:**
- A **KPI (Key Performance Indicator)** used to measure compliance posture
- Expressed as a percentage where **100% reflects optimal security configuration**
- Actionable — each point deduction comes with a specific remediation recommendation
- Tracked over time to show security posture trends

### Security Policy vs. Security Governance

These are related but distinct concepts:

| Aspect | Security Governance | Security Policy |
|---|---|---|
| Definition | System by which security activities are **directed and controlled** | Documented rules that **translate governance into action** |
| Standard | ISO/IEC 27014 | ISO/IEC 27001 |
| Scope | High-level objectives, risk appetite, strategic direction | Specific rules, requirements, and constraints |
| Relationship | Governance **contains** policy | Policy is a **core component** of governance |

Security governance establishes the "what" and "why" at the strategic level. Security policy translates that into the "how" at the operational level.

### Governance Models

Organizations choose governance models based on their size, industry, and regulatory environment:

```
+-------------------------------------------------------------------+
|                    GOVERNANCE MODELS COMPARISON                     |
+-------------------------------------------------------------------+

  THREE-TIER MODEL                FOUR-TIER MODEL
  ================               =================
  +----------------+             +----------------+
  | Tier 1:        |             | Tier 1:        |
  | EXECUTIVE      |             | EXECUTIVE      |
  | LEADERSHIP     |             | LEADERSHIP     |
  | Board, CEO,    |             | Board, CEO,    |
  | CISO           |             | CISO           |
  +-------+--------+             +-------+--------+
          |                              |
          |                      +-------+--------+
          |                      | Tier 2:        |
          |                      | COMPLIANCE &   |
          |                      | LEGAL OVERSIGHT|
          |                      | DPOs, Legal    |
          |                      | Counsel        |
          |                      +-------+--------+
          |                              |
  +-------+--------+             +-------+--------+
  | Tier 2:        |             | Tier 3:        |
  | SECURITY       |             | SECURITY       |
  | MANAGEMENT     |             | MANAGEMENT     |
  | Security       |             | Security       |
  | Officers, Risk |             | Officers, Risk |
  | Managers       |             | Managers       |
  +-------+--------+             +-------+--------+
          |                              |
  +-------+--------+             +-------+--------+
  | Tier 3:        |             | Tier 4:        |
  | SECURITY       |             | SECURITY       |
  | OPERATIONS     |             | OPERATIONS     |
  | SOC Teams,     |             | SOC Teams,     |
  | Admins, Pen    |             | Admins, Pen    |
  | Testers        |             | Testers        |
  +----------------+             +----------------+


  FEDERATED MODEL                 MATRIX MODEL
  ================               ================
  +----------------+             +-----+-----+-----+-----+
  | CENTRAL        |             | Sec | IT  |Legal| HR  |
  | GOVERNANCE     |             +-----+-----+-----+-----+
  | BODY           |             |           |           |
  | CISO, Central  |             | Security Committees & |
  | Security Team  |             | Cross-Functional      |
  +---+----+---+---+             | Working Groups        |
      |    |   |                 |                       |
  +---+  +-+-+ +---+            +-----------+-----------+
  |BU1|  |BU2| |BU3|                        |
  |Sec|  |Sec| |Sec|            All departments collaborate
  |Team| |Team||Team|           on security decisions
  +----+ +---+ +---+
  Local customization
```

#### 1. Three-Tier Model
- **Tier 1 — Executive Leadership**: Board of Directors, CEO, CISO. Responsible for strategy, budgets, and risk appetite.
- **Tier 2 — Security Management**: Security Officers, Risk Managers. Develop policies, conduct risk assessments, manage compliance.
- **Tier 3 — Security Operations**: SOC teams, system administrators, penetration testers. Implement controls, monitor systems, respond to incidents.
- **Use case**: Large enterprises with established hierarchies.
- **Limitation**: Can be rigid and slow to adapt.

#### 2. Four-Tier Model
- Adds a **Compliance & Legal Oversight** tier between Executive Leadership and Security Management.
- This tier includes Compliance Officers, Data Protection Officers (DPOs), and Legal Counsel.
- Focuses on **regulatory compliance** as a distinct function.
- **Use case**: Highly regulated sectors — finance, healthcare, government.
- **Advantage**: Dedicated compliance function ensures regulatory obligations are not overlooked.

#### 3. Federated Model
- A **Central Governance Body** (CISO, central security team) sets overarching policies and standards.
- **Local/Business Unit Security Teams** (regional security managers) customize and implement policies for their specific context.
- **Use case**: Multinational corporations operating across different jurisdictions with varying regulations.
- **Risk**: Inconsistent practices across business units if central oversight is weak.

#### 4. Matrix Model
- **Cross-functional teams** from Security, IT, Legal, HR, and Operations collaborate on security decisions.
- **Security Committees and Working Groups** bring diverse perspectives to policy and risk management.
- **Use case**: DevSecOps environments, agile organizations where security is "everyone's responsibility."
- **Risk**: Blurry accountability — when everyone is responsible, no one may feel responsible.

### ISO 27000 Series (from Lab)

#### ISO/IEC 27001
- Framework for an **Information Security Management System (ISMS)**
- Specifies requirements for establishing, implementing, maintaining, and continually improving an ISMS
- Certification standard — organizations can be audited and certified against it

#### ISO/IEC 27002:2022
- Provides **guidelines for implementing security controls** referenced in ISO 27001
- The 2022 revision reorganized the previous 14 control categories into **4 main themes**

### ISO 27002:2022 Four Main Themes

| Theme | Controls | Examples |
|---|---|---|
| **Organizational** | Policies, roles, asset management, compliance | Information security policies, segregation of duties, contact with authorities |
| **People** | Awareness/training, user responsibilities | Security awareness training, terms and conditions of employment |
| **Physical** | Physical/environmental security, equipment security | Data center security, secure disposal of media, clear desk policy |
| **Technological** | Access control, cryptography, operations/communications security | Access control systems, encryption, network security, vulnerability management |

### Security Policy Lifecycle (ISO 27001)

The ISO 27001 framework defines six key steps for building an effective security policy:

1. **Context Establishment** — Understand the organization's internal and external context, stakeholders, and scope
2. **Risk Assessment** — Identify assets, threats, vulnerabilities, and evaluate likelihood and impact
3. **Policy Definition** — Draft policies that address identified risks and align with business objectives
4. **Approval and Communication** — Top management approves; policies are communicated to all relevant parties
5. **Monitoring and Review** — Continuously check compliance and effectiveness; conduct regular audits
6. **Improvement** — Update policies based on audit findings, incidents, and changing threats

### Roles in Policy Management

| Role | Responsibility |
|---|---|
| **Information Security Officers / ISMS Teams** | Draft and develop security policies |
| **Top Management** | Approve policies, set direction, allocate resources, foster security culture |
| **IT Security Teams / Risk Management** | Review, update, and maintain policies over time |
| **All Employees** | Read, acknowledge, and comply with policies |

## Definitions

| Term | Definition |
|------|------------|
| GRC | Governance, Risk & Compliance — an integrated framework aligning strategic direction, threat management, and regulatory adherence |
| Governance | The strategic framework defining policies, decision-making authority, and accountability within an organization |
| Risk Management | The systematic process of identifying, assessing, and mitigating threats to organizational assets |
| Compliance | Adherence to legal requirements, industry standards, and internal organizational policies |
| Security Policy | A documented set of rules, criteria, and objectives governing an organization's security program |
| NIST CSF | National Institute of Standards and Technology Cybersecurity Framework — a voluntary framework of standards and best practices for managing cybersecurity risk |
| NIST CSF 2.0 | The 2024 update to the NIST Cybersecurity Framework adding governance as a core function |
| ISO 27001 | International standard specifying requirements for an Information Security Management System (ISMS) |
| ISO 27002 | International standard providing guidelines for implementing security controls referenced in ISO 27001 |
| ISO/IEC 27014 | International standard for governance of information security |
| NIST SP 800-53 | Security and Privacy Controls for Information Systems and Organizations — a comprehensive control catalog |
| NIST SP 800-167 | Guide to Application Whitelisting |
| FIPS 200 | Federal Information Processing Standard specifying minimum security requirements for federal systems (mandatory) |
| CIA Triad | Confidentiality, Integrity, and Availability — the three pillars of information security |
| Active Directory (AD) | Microsoft's directory service for managing network objects, authentication, and authorization in Windows domains |
| Domain | A collection of AD objects sharing a common directory database |
| Organizational Unit (OU) | A container within an AD domain used to organize objects and apply Group Policy |
| Domain Tree | A hierarchy of domains sharing contiguous DNS naming within a forest |
| Forest | The top-level AD container and security boundary comprising one or more domain trees |
| Trust Relationship | A secure connection between AD domains or forests enabling cross-domain authentication |
| GPO (Group Policy Object) | A collection of settings in Active Directory that define system appearance and behavior for targeted users or computers |
| AppLocker | Windows application control tool that restricts which applications can run based on publisher, path, or file hash rules |
| Gatekeeper | macOS application control mechanism restricting execution to apps from identified developers or the App Store |
| SELinux | Security-Enhanced Linux — a Linux kernel module providing mandatory access control |
| CCE | Common Configuration Enumeration — unique identifiers for security-related configuration issues (NIST) |
| CVE | Common Vulnerabilities and Exposures — unique identifiers for software vulnerabilities (MITRE) |
| CSPM | Cloud Security Posture Management — tools providing visibility into cloud security configuration and compliance |
| Secure Score | A KPI (0-100%) measuring an organization's security compliance posture |
| BYOD | Bring Your Own Device — policy framework for employees using personal devices for work |
| ISMS | Information Security Management System — a systematic approach to managing sensitive information |
| DPO | Data Protection Officer — role responsible for overseeing data protection strategy and compliance (e.g., GDPR) |
| CISO | Chief Information Security Officer — executive responsible for an organization's information security program |
| CIDO | Chief Information and Digital Officer — executive overseeing both IT and digital transformation |
| SOC | Security Operations Center — a centralized unit monitoring and responding to security events |
| Hardening | The process of reducing a system's attack surface by removing unnecessary services, applying configurations, and enforcing policies |
| Application Whitelisting | A security approach where only pre-approved applications are permitted to execute |
| Transitive Trust | A trust relationship that extends beyond two domains — if A trusts B and B trusts C, then A trusts C |
| Non-transitive Trust | A trust relationship limited to the two domains involved — it does not extend further |

## Diagrams & Visual Descriptions

### Policy Hierarchy Pyramid

The lecture presents a pyramid diagram showing the security documentation hierarchy. At the top (narrowest) is **Policy** with the highest enforcement authority and least technical detail. Moving down, each layer becomes wider (more documents, more detail) and less enforceable: **Standard**, **Guidelines**, **Best Practices**, and **Procedure** at the base. This represents the trade-off between authority and specificity — executives enforce policy, while technicians follow procedures.

See the ASCII pyramid in the Key Concepts section above for the full representation.

### Active Directory Structure Diagram

The lecture includes a hierarchical diagram showing the AD structure from Forest (outermost security boundary) through Domain Trees, Root/Parent Domains, Child Domains, and Organizational Units. The DNS naming hierarchy is illustrated with examples like `corp.example.com` as the root and `sales.corp.example.com` as a child domain.

See the ASCII diagram in the Active Directory section above for the full representation.

### Network Architecture Diagram (Policy Enforcement)

The lecture references a network architecture diagram used as the basis for policy enforcement. It illustrates endpoints (user workstations, mobile devices), servers (web, database, file), network components (switches, routers, firewalls), IoT devices, and printers — all as enforcement points. The key takeaway is that enforcement must be **holistic**, covering every component, not just endpoints and servers.

### Governance Models Comparison

Four governance model diagrams are presented side by side:
- **Three-Tier**: A simple vertical hierarchy (Executive -> Management -> Operations)
- **Four-Tier**: Same vertical structure with an additional Compliance & Legal layer
- **Federated**: A hub-and-spoke model with central governance and distributed business unit teams
- **Matrix**: A grid showing cross-functional collaboration across Security, IT, Legal, HR, and Operations

See the ASCII diagrams in the Governance Models section above for the full representation.

### Azure Security Center / Microsoft Defender for Cloud Dashboard

The lecture references the Secure Score dashboard in Microsoft Defender for Cloud, showing a percentage-based compliance score with actionable recommendations for improving security posture. Each recommendation is linked to a specific CCE identifier and maps to a policy control.

## Code Examples

### PowerShell: Creating and Linking a GPO

```powershell
# Import the Group Policy module
Import-Module GroupPolicy

# Create a new Group Policy Object
New-GPO -Name "HR-Department-Security-Policy" -Comment "Restrict USB and enforce screen lock for HR"

# Link the GPO to the HR Organizational Unit
New-GPLink -Name "HR-Department-Security-Policy" `
           -Target "OU=HR,DC=corp,DC=example,DC=com"

# Configure a specific policy setting: enforce screen lock after 10 minutes
Set-GPRegistryValue -Name "HR-Department-Security-Policy" `
    -Key "HKCU\Software\Policies\Microsoft\Windows\Control Panel\Desktop" `
    -ValueName "ScreenSaveTimeOut" `
    -Type String `
    -Value "600"

# Enable the screensaver requirement
Set-GPRegistryValue -Name "HR-Department-Security-Policy" `
    -Key "HKCU\Software\Policies\Microsoft\Windows\Control Panel\Desktop" `
    -ValueName "ScreenSaveActive" `
    -Type String `
    -Value "1"

# Require password on resume
Set-GPRegistryValue -Name "HR-Department-Security-Policy" `
    -Key "HKCU\Software\Policies\Microsoft\Windows\Control Panel\Desktop" `
    -ValueName "ScreenSaverIsSecure" `
    -Type String `
    -Value "1"
```

This example demonstrates how Active Directory GPOs are used to enforce security policy. The GPO is created, linked to a specific OU (HR department), and configured with registry-based settings that enforce a screen lock timeout — a common security policy requirement.

### PowerShell: Querying GPO Reports

```powershell
# Get a report of all GPOs in the domain
Get-GPO -All | Select-Object DisplayName, GpoStatus, CreationTime

# Generate an HTML report for a specific GPO
Get-GPOReport -Name "HR-Department-Security-Policy" `
              -ReportType HTML `
              -Path "C:\Reports\HR-GPO-Report.html"

# Find all GPOs linked to a specific OU
Get-GPInheritance -Target "OU=HR,DC=corp,DC=example,DC=com"
```

These commands help administrators audit and review Group Policy deployment, supporting the monitoring and compliance aspects of security policy management.

### PowerShell: AppLocker Rules

```powershell
# Get current AppLocker policy
Get-AppLockerPolicy -Effective | Select-Object -ExpandProperty RuleCollections

# Create a publisher-based rule allowing Microsoft-signed applications
$rule = New-AppLockerPolicy -RuleType Publisher `
    -RuleNamePrefix "Allow-Microsoft" `
    -User "Everyone" `
    -AllowWindows

# Create a path-based rule allowing applications from Program Files
$pathRule = New-AppLockerPolicy -RuleType Path `
    -RuleNamePrefix "Allow-ProgramFiles" `
    -User "Everyone" `
    -Path "C:\Program Files\*"

# Export the AppLocker policy to XML for review
Get-AppLockerPolicy -Effective -Xml | Out-File "C:\Reports\AppLocker-Policy.xml"
```

This demonstrates the three AppLocker condition types discussed in the lecture: Publisher (for signed apps), Path (for location-based rules), and how policies can be exported for audit and review.

### PowerShell: Checking Compliance with Azure Security Center

```powershell
# Install the Azure Security module
Install-Module -Name Az.Security -Force

# Connect to Azure
Connect-AzAccount

# Get the current Secure Score
Get-AzSecuritySecureScore

# Get specific security recommendations
Get-AzSecurityAssessment | Where-Object {
    $_.Status.Code -eq "Unhealthy"
} | Select-Object DisplayName, Status, ResourceDetails
```

This example shows how Secure Score metrics and compliance recommendations are retrieved programmatically, supporting the monitoring for compliance workflow described in the lecture.

## Formulas & Algorithms

### Risk Assessment Formula (Qualitative)

$$Risk = Likelihood \times Impact$$

Where:
- **Likelihood** — Probability of a threat exploiting a vulnerability (typically rated Low/Medium/High or 1-5)
- **Impact** — Consequence to the organization if the threat materializes (rated similarly)
- **Risk** — The product determines prioritization of security controls and policy focus

### Breach Cost Savings Formula

$$Savings = AvgBreachCost - BreachCostWithIRPlan$$

Per IBM 2024 data:
- Organizations with documented incident response plans save an average of **$1.49 million per breach**
- This quantifies the ROI of maintaining security policies and incident response documentation

### Secure Score Calculation

$$SecureScore = \frac{AchievedPoints}{TotalPossiblePoints} \times 100\%$$

Where:
- **Achieved Points** — Security recommendations that have been implemented
- **Total Possible Points** — All available security recommendations
- A score of **100%** reflects optimal security configuration
- Each unimplemented recommendation represents a specific, actionable security improvement

### Trust Transitivity Logic

For **transitive trust**:
$$\text{If } A \xrightarrow{\text{trusts}} B \text{ and } B \xrightarrow{\text{trusts}} C \text{, then } A \xrightarrow{\text{trusts}} C$$

For **non-transitive trust**:
$$\text{If } A \xrightarrow{\text{trusts}} B \text{ and } B \xrightarrow{\text{trusts}} C \text{, then } A \not\xrightarrow{\text{trusts}} C$$

This is important for understanding how authentication propagates across Active Directory domains and forests.

## Key Takeaways

- **GRC integrates governance, risk, and compliance** into a unified framework that is essential for a mature cybersecurity program. These three elements must work together, not in silos.

- **Security policies are living documents** that must be continuously reviewed and updated — both on a regular schedule and in response to security incidents.

- **The policy hierarchy** (Policy -> Standard -> Guidelines -> Best Practices -> Procedure) ensures that high-level strategic intent is translated into actionable, technical implementation steps.

- **End-user education is a management control**, not just an optional "nice to have." It is one of the most cost-effective security measures, with documented IR plans saving organizations $1.49M per breach on average.

- **BYOD introduces significant risk** and requires explicit policies aligned with HR and legal requirements. It should be prohibited in high-confidentiality environments.

- **Policy enforcement must be holistic** — covering every network component (endpoints, servers, switches, printers, IoT), not just user workstations and servers.

- **Active Directory and GPOs** are the primary enforcement mechanism in Windows environments, allowing granular policy application at the OU level.

- **Application whitelisting** (AppLocker, Gatekeeper, SELinux) ensures only approved software runs, using publisher signatures, file paths, or cryptographic hashes.

- **CCE and CVE are different**: CCE addresses configuration issues (fix with configuration change), CVE addresses vulnerabilities (fix with patch). Both must be monitored.

- **CSPM tools and Secure Score** provide quantitative, continuous measurement of security posture in hybrid and cloud environments.

- **Security governance (ISO 27014) directs and controls** the overall security program, while security policies are the core mechanism that translates governance objectives into enforceable rules.

- **Four governance models** exist to suit different organizational contexts: Three-Tier (large enterprises), Four-Tier (regulated industries), Federated (multinationals), and Matrix (agile/DevSecOps organizations).

- **ISO 27002:2022 reorganized controls into four themes**: Organizational, People, Physical, and Technological — simplifying the previous 14-category structure.

- **The security policy lifecycle** (Context -> Risk Assessment -> Definition -> Approval -> Monitoring -> Improvement) is a continuous cycle, not a one-time exercise.

## Connections

**Connection to Week 1-2 (Introduction to Cybersecurity / CIA Triad):** This week's policy hierarchy is built upon the CIA triad introduced in the early weeks. The lecture explicitly states that the foundation of reviewing security policy is the security triad (Confidentiality, Integrity, Availability), and users must protect all three properties.

**Connection to Week 3 (Risk Management):** The GRC framework extends Week 3's risk management concepts by embedding them within a governance and compliance structure. Risk assessment is now seen not as a standalone activity but as a component of a broader organizational framework that includes policy creation and compliance monitoring.

**Connection to Week 4-5 (Threat Landscape / Attack Vectors):** The social engineering case studies (phishing spam campaigns, social media attacks) connect directly to the threat categories discussed in previous weeks. This week explains how policies and end-user training are the organizational response to those threats.

**Connection to Week 7-8 (Network Security / Implementation):** The Active Directory, GPO, and application whitelisting content in this week provides the foundational knowledge for implementing the network security controls that will be covered in upcoming weeks. Understanding how policy maps to AD structure is essential for configuring firewalls, IDS/IPS, and access controls.

**Broader CS Context:** Security policy intersects with software engineering (secure SDLC requires policy-driven security gates), database management (access control policies for data), operating systems (hardening configurations), and cloud computing (CSPM). The ISO 27000 series and NIST frameworks appear repeatedly across cybersecurity certifications (CISSP, CISM, CompTIA Security+) and are foundational knowledge for any cybersecurity professional.
