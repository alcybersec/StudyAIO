# CSIT302 — Week 7: Network Segmentation

> **Source files:** CSIT302_Week7.pdf
> **Date summarized:** 2026-02-24

## Overview

This lecture covers network segmentation as a critical defensive strategy within the cybersecurity kill chain, focusing on how organizations can split their networks into isolated subnetworks to limit lateral movement by attackers, reduce the blast radius of breaches, and enforce the principle of least privilege. The material spans physical segmentation (switches, VLANs), virtual segmentation (hypervisor-based virtual switches), remote access security (NAC, VPNs), the Zero Trust network model, and hybrid cloud network security (AWS VPC). Network segmentation sits within the broader defense-in-depth framework introduced earlier in the course and is one of the most impactful controls an organization can deploy to disrupt an attacker's progression through the kill chain.

The lecture connects to the cybersecurity kill chain phases covered in previous weeks — external reconnaissance, system compromise, lateral movement, privilege escalation, and mission execution — and positions network segmentation alongside security policy and active sensors as a primary defensive mechanism.

## Key Concepts

### Cybersecurity Kill Chain Context

Network segmentation is positioned within the defensive side of the cybersecurity kill chain. The kill chain phases are:

1. **External Reconnaissance** — attacker gathers information about the target
2. **Compromising the System** — initial exploitation and foothold
3. **Lateral Movement** — attacker moves across the network to reach valuable assets
4. **Privilege Escalation** — attacker gains higher-level access
5. **Concluding the Mission** — data exfiltration or destruction

Defense mechanisms that counter these phases include:
- **Security Policy** — governance and rules
- **Network Segmentation** — architectural isolation (this week's focus)
- **Active Sensors** — detection and monitoring

Network segmentation is particularly effective at disrupting **lateral movement**, which is often the most time-consuming phase for attackers and the phase where defenders have the greatest opportunity to detect and contain a breach.

### Network Segmentation Fundamentals

Network segmentation is the practice of splitting a computer network into smaller subnetworks (segments or zones). Each segment operates as a semi-independent unit with controlled boundaries.

**Core Principles:**
- The network **must** be segmented — flat networks are indefensible
- Segments must be **isolated** from one another by default
- Mechanisms must exist to **mitigate intrusion** within and between segments
- Communication between segments must pass through controlled chokepoints (routers, firewalls)

**Types of Segmentation:**

| Type | Mechanism | Example |
|------|-----------|---------|
| Physical | Separate hardware (switches, cables) | Dedicated switch per department |
| Logical | VLANs on shared hardware | VLAN 10 for HR, VLAN 20 for Engineering |
| Virtual | Software-defined in virtualized environments | Hyper-V virtual switches, VMware vSwitch |

**Reasons for Segmentation:**
- **Improved Performance** — high-bandwidth applications get dedicated capacity; congestion in one segment does not affect others
- **Enhanced Security** — enforces the principle that users should not be able to talk directly to database servers or other sensitive resources; each segment can have tailored security controls

### Defense in Depth

Defense in depth is a strategy that deploys multiple layers of protection so that if one layer fails, subsequent layers continue to defend. Each layer has its own security controls and sensors that alert administrators.

**Purpose:** Break the attack kill chain before the attacker can execute their final mission.

```
+============================================================+
|                    DEFENSE IN DEPTH                         |
|                                                             |
|  +------------------------------------------------------+  |
|  |  Layer 1: INFRASTRUCTURE & SERVICES                  |  |
|  |  (Patch management, server protection, network       |  |
|  |   isolation, backups, IaaS security)                  |  |
|  |                                                       |  |
|  |  +------------------------------------------------+  |  |
|  |  |  Layer 2: DOCUMENTS IN TRANSIT                 |  |  |
|  |  |  (Encryption, digital signatures, monitoring,  |  |  |
|  |  |   access control)                              |  |  |
|  |  |                                                |  |  |
|  |  |  +------------------------------------------+  |  |  |
|  |  |  |  Layer 3: ENDPOINTS                      |  |  |  |
|  |  |  |  (EDR, OS hardening, storage encryption, |  |  |  |
|  |  |  |   TPM, corporate/personal separation)    |  |  |  |
|  |  |  |                                          |  |  |  |
|  |  |  |  +------------------------------------+  |  |  |  |
|  |  |  |  |  Layer 4: MICROSEGMENTATION        |  |  |  |  |
|  |  |  |  |  (Identity-based policies,         |  |  |  |  |
|  |  |  |  |   Zero Trust, SDN controls)        |  |  |  |  |
|  |  |  |  +------------------------------------+  |  |  |  |
|  |  |  +------------------------------------------+  |  |  |
|  |  +------------------------------------------------+  |  |
|  +------------------------------------------------------+  |
+============================================================+
```

**Home Analogy for Defense in Depth:**

```
Layer 1: Gate / Fence        --> Perimeter defense (firewall, IDS)
Layer 2: Locked Door         --> Authentication and access control
Layer 3: Alarm System        --> Monitoring and alerting (SIEM, sensors)
Layer 4: Digital Safe Box    --> Encryption and data protection at rest
```

Each layer must be independently effective — the alarm system still works even if the gate is bypassed.

### Section 1: Infrastructure and Services

Attackers target an organization's infrastructure and services as primary attack vectors. The defensive approach involves:

1. **Enumerate all services** — identify every service exposed, both internally and externally
2. **Start from assets** — catalog what you are protecting
3. **Specify potential attackers and techniques** — threat modeling
4. **Add security controls** — layered defenses for each identified risk

**Security Controls for Infrastructure:**
- **Patch Management** — timely application of security updates
- **Server Protection** — hardening, least privilege, access controls
- **Network Isolation** — segmentation of server networks from user networks
- **Backups** — recovery capability for ransomware and destructive attacks

**Deployment Forms:**
- **On-premises** — traditional data center infrastructure
- **IaaS (Infrastructure as a Service)** — cloud-hosted infrastructure (AWS, Azure, GCP)

In a **hybrid environment**, threat modeling must account for both on-premises and cloud infrastructure, with particular attention to the boundaries between them.

**Goals of Infrastructure Defense:**
- **Reduce vulnerability count and severity** — fewer exploitable weaknesses
- **Reduce exposure time** — shorter window between vulnerability disclosure and patching
- **Increase exploitation difficulty and cost** — make attacks more expensive and less likely to succeed

### Section 2: Documents in Transit

Data is vulnerable when it moves across networks (in transit). This applies to any type of data — files, database queries, API calls, emails, etc.

**Protection Mechanisms:**
- **Robust encryption** — TLS 1.3, IPSec, SSH tunnels
- **Digital signatures** — integrity verification and non-repudiation
- **Encryption on both public and internal networks** — do not assume internal networks are safe
- **End-to-end protection** — data is encrypted from source to destination, not just at network boundaries

**Additional Security Controls at Each Layer:**
- Monitoring (DLP, traffic analysis)
- Access control (who can access what data)
- Logging and auditing

### Section 3: Endpoints

An endpoint is any device that consumes data. This extends far beyond traditional computers:
- Desktops and laptops
- Mobile phones and tablets
- IoT devices (sensors, cameras, smart appliances)
- Printers and scanners
- Point-of-sale terminals

**Threat modeling** is essential to uncover attack vectors specific to each endpoint category.

**Countermeasures for Endpoint Security:**
- **Separation of corporate and personal data** — containerization on BYOD devices
- **TPM (Trusted Platform Module)** — hardware-based security for cryptographic keys
- **OS hardening** — disabling unnecessary services, applying CIS benchmarks
- **Storage encryption** — BitLocker, FileVault, LUKS
- **EDR (Endpoint Detection and Response)** — real-time monitoring, threat detection, and automated response on endpoints

### Microsegmentation

Microsegmentation is an advanced defense-in-depth technique that creates fine-grained, isolated network segments based on **resource identity** rather than IP addresses.

**Key Characteristics:**
- **Decoupled from physical infrastructure** — implemented in software via SDN (Software-Defined Networking)
- **Flexible and scalable** — policies follow workloads regardless of physical location
- **Supports Zero Trust model** — every resource boundary is a trust boundary
- **Ensures independent protection** — each microsegment is protected regardless of where it runs
- **Prevents lateral movement** — even if an attacker compromises one workload, they cannot reach adjacent workloads without passing through policy enforcement

**Microsegmentation vs Traditional Segmentation:**

| Aspect | Traditional Segmentation | Microsegmentation |
|--------|--------------------------|-------------------|
| Granularity | Subnet/VLAN level | Individual workload level |
| Based on | IP addresses, port ranges | Identity, labels, attributes |
| Infrastructure | Physical switches, routers | Software-defined, SDN |
| Flexibility | Static, hardware-bound | Dynamic, follows workload |
| Lateral Movement | Possible within segment | Blocked between workloads |

### Physical Network Segmentation

Physical segmentation uses dedicated hardware to separate network zones. As networks grow organically to meet demand, security features are rarely revisited, making it challenging to get an accurate view of the current segmentation state.

**Understanding Logical Distribution is the First Step:**
- Map all network zones and their interconnections
- Identify where data flows between segments
- No data flows between segments unless it passes through a switch or router

**Issues with Physical Segmentation:**
- **Efficiency** — wasted switch ports (a 48-port switch serving a 10-device segment wastes 38 ports)
- **Scalability** — adding new segments requires purchasing and deploying new hardware

### Switch Operation and MAC Address Table

A network switch connects devices on a local network. All devices connect via physical ports. The switch forwards frames by learning which devices are connected to which ports.

**MAC Address Table:** Maps physical ports to MAC (Media Access Control) addresses.

**Switch Learning Process:**

```
Step 1: FLOODING (Unknown Destination)
=========================================
PC-A sends frame to PC-C, but switch doesn't know where PC-C is.

  PC-A (Port 1)           SWITCH              PC-B (Port 2)
  [MAC: AA:AA]  ------>  +--------+  ------>  [MAC: BB:BB]
                         | Port 1 |
                         | Port 2 |  ------>  (frame flooded)
                         | Port 3 |  ------>  (frame flooded)
                         | Port 4 |  ------>  (frame flooded)
                         +--------+
                                      PC-C (Port 3)  PC-D (Port 4)
                                      [MAC: CC:CC]   [MAC: DD:DD]

  - Switch does NOT know which port PC-C is on
  - Switch floods the frame out ALL ports EXCEPT the source port (Port 1)
  - All devices receive the frame; only PC-C processes it

Step 2: LEARNING (Recording Source MAC)
=========================================
  MAC Address Table BEFORE:
  +--------+-----------+
  | Port   | MAC       |
  +--------+-----------+
  | (empty)            |
  +--------+-----------+

  After PC-A sends frame:
  +--------+-----------+
  | Port   | MAC       |
  +--------+-----------+
  | Port 1 | AA:AA     |   <-- Learned from source of incoming frame
  +--------+-----------+

  - Switch records: "MAC AA:AA is reachable via Port 1"
  - Learning happens on EVERY frame received (source MAC + ingress port)

Step 3: FORWARDING (Known Destination)
=========================================
  Later, PC-C sends frame to PC-A. Switch now knows PC-A is on Port 1.

  PC-C (Port 3)           SWITCH              PC-A (Port 1)
  [MAC: CC:CC]  ------>  +--------+  ------>  [MAC: AA:AA]
                         | Port 1 |  ------>  (forwarded directly)
                         | Port 2 |           (NOT sent here)
                         | Port 3 |           (NOT sent here)
                         | Port 4 |           (NOT sent here)
                         +--------+

  MAC Address Table:
  +--------+-----------+
  | Port   | MAC       |
  +--------+-----------+
  | Port 1 | AA:AA     |
  | Port 3 | CC:CC     |   <-- Learned from PC-C's frame
  +--------+-----------+

  - Switch forwards ONLY to Port 1 (unicast)
  - Much more efficient than flooding
```

### MAC Flooding Attack

MAC flooding is an attack that exploits the finite size of a switch's MAC address table (CAM table).

```
NORMAL OPERATION:
=================
  Switch MAC Table (capacity: 8,000 entries)
  +--------+-----------+
  | Port 1 | AA:AA     |
  | Port 2 | BB:BB     |
  | Port 3 | CC:CC     |
  +--------+-----------+
  Frames forwarded to specific ports (unicast)


MAC FLOODING ATTACK:
====================
  Attacker on Port 4 sends thousands of frames,
  each with a DIFFERENT spoofed source MAC:

  Attacker (Port 4)
  [Spoofed MACs: XX:01, XX:02, XX:03, ... XX:9999]
       |
       v
  +--------+-----------+
  | Port 1 | AA:AA     |
  | Port 2 | BB:BB     |
  | Port 3 | CC:CC     |
  | Port 4 | XX:01     |
  | Port 4 | XX:02     |
  | Port 4 | XX:03     |
  | ...    | ...       |   <-- Table fills up!
  | Port 4 | XX:8000   |
  +--------+-----------+
  TABLE FULL! New legitimate entries cannot be learned.


RESULT - SWITCH FAILS OPEN (Hub Mode):
=======================================
  Switch cannot learn new MACs --> all frames FLOODED to all ports

  PC-A --> PC-B traffic:
  +--------+
  | Port 1 | -----> Port 2 (intended)
  | Port 2 | -----> Port 3 (flooded - LEAKED)
  | Port 3 | -----> Port 4 (flooded - ATTACKER SEES THIS)
  | Port 4 | -----> Attacker captures ALL traffic!
  +--------+

  Attacker can now SNIFF all network traffic on the switch.
```

**Mitigation:** Port security features that limit the number of MAC addresses per port, 802.1X authentication, and MAC flooding prevention features on managed switches.

### VLANs (Virtual Local Area Networks)

VLANs provide logical segmentation on shared physical switch hardware. Devices on VLAN 1 cannot communicate with devices on VLAN 2 without passing through a Layer 3 device (router or Layer 3 switch).

```
PHYSICAL SWITCH WITH VLANs:
============================

  One Physical Switch
  +--------------------------------------------------+
  |                                                    |
  |   VLAN 10 (HR)          VLAN 20 (Engineering)     |
  |   +-----------+         +----------------+        |
  |   | Port 1    |         | Port 5         |        |
  |   | Port 2    |         | Port 6         |        |
  |   | Port 3    |         | Port 7         |        |
  |   +-----------+         +----------------+        |
  |                                                    |
  |   VLAN 30 (Servers)     VLAN 40 (Guest WiFi)      |
  |   +-----------+         +----------------+        |
  |   | Port 9    |         | Port 13        |        |
  |   | Port 10   |         | Port 14        |        |
  |   +-----------+         +----------------+        |
  |                                                    |
  +--------------------------------------------------+
             |
             | Trunk Port (carries all VLANs)
             v
        +----------+
        |  ROUTER  |  <-- Required for inter-VLAN communication
        +----------+
             |
        Routing decisions + firewall rules
        control which VLANs can talk to each other
```

**VLAN Assignment Criteria:**
- **Department** — HR, Engineering, Finance, Operations
- **Business objectives** — production systems vs development systems
- **Level of sensitivity** — PCI-compliant systems, healthcare data, classified
- **Location** — building floors, campuses, geographical sites
- **Security zones** — DMZ, internal, management, guest

A **mixed VLAN approach** is recommended — combining multiple criteria for optimal segmentation.

**VLAN Best Practices:**
1. **Use SSH for management** — never use Telnet for switch administration
2. **Restrict management interface access** — limit which IPs/VLANs can manage switches
3. **Disable unused ports** — prevent unauthorized devices from connecting
4. **Leverage MAC flooding prevention** — enable port security features
5. **Port-level security** — enable DHCP snooping to prevent rogue DHCP servers
6. **Update firmware** — keep switch firmware current to patch known vulnerabilities

### Discovering the Network (Internal Reconnaissance)

Once an attacker (or a security auditor) is inside the network, they use internal reconnaissance techniques to map the environment:

- **Nmap** — network scanner that discovers hosts, open ports, running services, and OS fingerprints
- **Traceroute** — maps the path packets take through the network, revealing routers and segmentation boundaries
- **Network Topology Mapper** — tools like SolarWinds NTM that automatically discover and diagram network topology

Understanding these techniques helps defenders design segmentation that limits what an attacker can discover.

### Securing Remote Access

Remote access is required for remote workers, travelers, and increasingly for day-to-day operations. The challenge is ensuring that remote systems meet security requirements before being allowed onto the corporate network.

**NAC (Network Access Control)** is a unified approach to endpoint security enforcement:

```
NAC ARCHITECTURE:
=================

  Remote User                         Corporate Network
  +----------+                        +-----------------+
  |  Laptop  |                        |                 |
  | (unknown |  --- Internet --->     |  NAC Server     |
  |  health) |                        |  +-----------+  |
  +----------+                        |  | Evaluate: |  |
       |                              |  | - Patches |  |
       |                              |  | - AV      |  |
       v                              |  | - Firewall|  |
  +------------------+                |  | - Policy  |  |
  | VPN Gateway /    |                |  +-----------+  |
  | Access Point     | <-- Queries -->|       |         |
  +------------------+                |       v         |
       |                              |  +-----------+  |
       |-- COMPLIANT ---------------->|  | Corporate |  |
       |                              |  | Network   |  |
       |                              |  | (Full     |  |
       |                              |  |  Access)  |  |
       |                              |  +-----------+  |
       |                              |                 |
       |-- NON-COMPLIANT ------------>|  +-----------+  |
                                      |  | Quarantine|  |
                                      |  | Network   |  |
                                      |  | (Limited  |  |
                                      |  |  Access,  |  |
                                      |  | Remediate)|  |
                                      |  +-----------+  |
                                      +-----------------+
```

**NAC Evaluation Criteria:**
- Latest OS and application patches installed
- Antivirus software enabled and definitions current
- Personal firewall enabled and properly configured
- System compliant with organizational security policies

**NAC Components:**
- **Endpoint security** — antivirus, host intrusion prevention, vulnerability assessment
- **User/system authentication** — identity verification (802.1X, certificates)
- **Network security enforcement** — geo-location restrictions, time-based access, role-based policies

**Remote Access Architecture Options:**
1. **NAC validates health state** and performs software-level segmentation — compliant devices get full access, non-compliant devices get quarantined
2. **Isolate remote users in a specific VLAN** with a firewall between the remote segment and the corporate network
3. **MFA (Multi-Factor Authentication) enforcement** — all remote access requires multiple authentication factors
4. **Quarantine network** — non-compliant computers are placed in a restricted network that provides only remediation services (patch downloads, AV updates)

### Site-to-Site VPN

A Site-to-Site VPN creates a secure, encrypted, and digitally signed traffic channel between remote sites.

```
SITE-TO-SITE VPN:
=================

  Main Office                              Branch Office
  +------------------+                     +------------------+
  |                  |                     |                  |
  | Corporate LAN    |                     | Branch LAN       |
  | 10.1.0.0/16      |                     | 10.2.0.0/16      |
  |                  |                     |                  |
  | +------+         |                     |         +------+ |
  | | FW/  |=========|== Encrypted VPN ====|=========| FW/  | |
  | | VPN  |  IPSec  |== Tunnel over   ====|  IPSec  | VPN  | |
  | | GW   |  or TLS |== Public Internet===|  or TLS | GW   | |
  | +------+         |                     |         +------+ |
  |                  |                     |                  |
  +------------------+                     +------------------+
        |                                         |
   Firewall rules                           Firewall rules
   per branch                               per branch
   "Need to know"                           "Need to know"
```

**Key Characteristics:**
- **Works at MAC layer** — all traffic between sites is redirected through the tunnel
- **Uses IPSec or TLS** — industry-standard encryption protocols
- **Transport mode** — note that in transport mode, data itself may not be fully encrypted (only the payload, not the original IP header); tunnel mode provides full encapsulation
- **Each branch office has its own firewall rules** — the VPN does not mean unrestricted access
- **"Need to know" principle enforced** — only traffic that should flow between sites is permitted

### Virtual Network Segmentation

In virtualized environments, segmentation operates within the hypervisor layer. Virtual machines (VMs) run on a host that provides virtual switches for network connectivity.

```
VIRTUAL NETWORK SEGMENTATION:
==============================

  Physical Host (Hypervisor)
  +----------------------------------------------------------+
  |                                                            |
  |  Virtual Switch A              Virtual Switch B            |
  |  (Subnet 10.0.1.0/24)         (Subnet 10.0.2.0/24)       |
  |  +------------------+         +------------------+        |
  |  |  VM1    VM2      |         |  VM3    VM4      |        |
  |  |  Web    Web      |         |  DB     DB       |        |
  |  |  Server Server   |         |  Server Server   |        |
  |  +--------+---------+         +--------+---------+        |
  |           |                            |                   |
  |           | ISOLATED                   | ISOLATED          |
  |           |                            |                   |
  |  +--------+----------------------------+---------+        |
  |  |           Virtual Router                       |        |
  |  |     (Multiple virtual network adapters)        |        |
  |  |     Routes + Firewall rules between            |        |
  |  |     virtual networks                           |        |
  |  +------------------------------------------------+        |
  |           |                                                |
  |           | Physical NIC                                   |
  +-----------|------------------------------------------------+
              |
         Physical Network
```

**Key Points:**
- Traffic from one virtual network is **not visible** to other virtual networks (isolation within the virtual switch)
- Each virtual network has its **own subnet**
- Communication between virtual networks **requires a router** with multiple virtual network adapters
- The approach is **vendor-agnostic** — applies to Hyper-V, VMware ESXi, KVM, etc.

**Virtual Switch Extensions:**
- **Network packet inspection** — deep packet inspection at the virtual switch level
- **Firewall** — stateful firewall rules within the hypervisor
- **Network packet filter** — filter traffic before it reaches VMs

**Advantage:** Packets can be inspected **before** being transferred to the destination VM, providing a security checkpoint that does not exist in traditional physical networking.

**Virtual Network Security Capabilities:**
- **MAC address spoofing prevention** — VMs cannot change their virtual MAC address
- **DHCP guard** — prevents rogue VMs from acting as DHCP servers
- **Router guard** — prevents VMs from advertising themselves as routers
- **Port ACL** — access control lists on virtual switch ports

Note: Traffic from a VM **can traverse to the physical network** — virtual segmentation does not automatically isolate VMs from the physical infrastructure. Proper configuration of both virtual and physical network security is required.

### Zero Trust Network

Zero Trust is a security model that assumes **all networks — both internal and external — are not trustworthy**. This is a fundamental shift from traditional perimeter-based security.

**Core Principles:**
- Networks are hostile by nature
- Attackers may already reside inside the network
- Zero Trust is broader than any single vendor's technology
- **Identity is the new perimeter** — access decisions are based on verified identity, not network location
- Implement access control using **device and user identities**

```
ZERO TRUST ARCHITECTURE:
========================

  +-------------------+
  | Identity Provider |  <-- Authenticates users
  | (IdP)             |      (Azure AD, Okta, etc.)
  +--------+----------+
           |
           | Identity Token
           v
  +-------------------+
  | Conditional       |  <-- Evaluates access conditions
  | Policy Engine     |      (user role, device health,
  |                   |       location, time, risk score)
  +--------+----------+
           |
           | Allow / Deny / Step-up Auth
           v
  +-------------------+       +-------------------+
  | Access Proxy      | <---> | Device Directory   |
  | (Enforces access  |       | (Inventory of all  |
  |  decisions)       |       |  known devices,    |
  |                   |       |  health status)    |
  +--------+----------+       +-------------------+
           |
           | Granted Access (scoped)
           v
  +-------------------+
  | Protected         |
  | Resource          |
  | (App, Data, API)  |
  +-------------------+


  Key: User won't always have the same access.
       Access is re-evaluated continuously.
```

**Main Components:**
1. **Identity Provider (IdP)** — authenticates users and issues identity tokens (e.g., Azure AD, Okta, Ping Identity)
2. **Device Directory** — inventory of all known devices with their health and compliance status
3. **Conditional Policy Engine** — evaluates contextual factors to make access decisions; a user won't always have the same access level
4. **Access Proxy** — enforces the policy engine's decisions by granting or denying access to resources

**Planning Steps for Zero Trust Implementation:**

| Step | Action | Details |
|------|--------|---------|
| 1 | Identify and inventory assets | Catalog all resources requiring protection |
| 2 | Establish access rules | Document historical access patterns, define who needs what |
| 3 | Establish verification methods | Identity verification, device verification, network verification, resource verification |
| 4 | Define policies and controls | Access policies, logging requirements, control rules |
| 5 | Determine access conditions | Who accesses what, how, from which device, location, authentication method |
| 6 | Implement active monitoring | Continuous monitoring of all access events and anomaly detection |

### Hybrid Cloud Network Security

Organizations with hybrid deployments (on-premises + cloud) must secure the connectivity between environments.

**Connectivity Approaches:**

| Approach | Characteristics |
|----------|----------------|
| Site-to-Site VPN | Additional cost, ongoing maintenance, encrypted over public internet |
| Direct Route (e.g., Azure ExpressRoute) | Lower latency, higher performance, increased security, higher cost, complex deployment, private dedicated connection |

### Shared Responsibility Model

Cloud security operates under a shared responsibility model:

- **Security "of" the cloud** — the cloud provider's responsibility (physical data centers, hardware, hypervisor, global network)
- **Security "in" the cloud** — the customer's responsibility

**AWS Customer Responsibilities (Example):**
- EC2 instance operating system patching and configuration
- Applications running on instances
- IAM (Identity and Access Management) configuration
- Security group configuration
- OS, network, and firewall configuration
- Network traffic protection (encryption in transit)
- Client-side and server-side encryption
- Network configurations (VPC design, NACLs, route tables)

### AWS VPC (Virtual Private Cloud)

An AWS VPC is a logically isolated section of the AWS Cloud where customers have full control over their virtual networking environment.

```
AWS VPC ARCHITECTURE:
=====================

  AWS Region (e.g., us-east-1)
  +----------------------------------------------------------+
  |  VPC: 10.0.0.0/16                                        |
  |  (Logically isolated, dedicated to your account)          |
  |                                                            |
  |  Availability Zone A          Availability Zone B          |
  |  +------------------------+  +------------------------+   |
  |  |                        |  |                        |   |
  |  | Public Subnet          |  | Public Subnet          |   |
  |  | 10.0.1.0/24            |  | 10.0.3.0/24            |   |
  |  | +------------------+   |  | +------------------+   |   |
  |  | | Web Server (EC2) |   |  | | Web Server (EC2) |   |   |
  |  | +------------------+   |  | +------------------+   |   |
  |  |    |                   |  |    |                   |   |
  |  |    | Route Table:      |  |    | Route Table:      |   |
  |  |    | 0.0.0.0/0 -> IGW  |  |    | 0.0.0.0/0 -> IGW  |   |
  |  |    |                   |  |    |                   |   |
  |  +----+-------------------+  +----+-------------------+   |
  |       |                           |                        |
  |  +----+-------------------+  +----+-------------------+   |
  |  |    |                   |  |    |                   |   |
  |  | Private Subnet         |  | Private Subnet         |   |
  |  | 10.0.2.0/24            |  | 10.0.4.0/24            |   |
  |  | +------------------+   |  | +------------------+   |   |
  |  | | DB Server (RDS)  |   |  | | DB Server (RDS)  |   |   |
  |  | +------------------+   |  | +------------------+   |   |
  |  |    |                   |  |    |                   |   |
  |  |    | Route Table:      |  |    | Route Table:      |   |
  |  |    | 10.0.0.0/16 local |  |    | 10.0.0.0/16 local |   |
  |  |    | 0.0.0.0/0 -> NAT  |  |    | 0.0.0.0/0 -> NAT  |   |
  |  |    |                   |  |    |                   |   |
  |  +----+-------------------+  +----+-------------------+   |
  |       |                           |                        |
  |  +----+---------------------------+----+                   |
  |  |         Virtual Gateway             |                   |
  |  |    (VPN / Direct Connect)           |                   |
  |  +----+--------------------------------+                   |
  |       |                                                    |
  +-------|----------------------------------------------------+
          |
  +-------+--------+       +------------------+
  | Internet       |       | On-Premises      |
  | Gateway (IGW)  |       | Data Center      |
  +----------------+       | (Customer GW)    |
                           +------------------+
```

**VPC Key Characteristics:**
- **Logically isolated** from other AWS customers
- **Dedicated to your account** — complete control
- **Belongs to a single AWS Region** but spans multiple Availability Zones (AZs)
- Control over: IP address range, subnets, route tables, network gateways

**Subnets:**
- A range of IP addresses that divides the VPC
- Each subnet belongs to a **single Availability Zone**
- Subnets are designated as either **public** (internet-accessible via IGW) or **private** (no direct internet access)

**AWS Site-to-Site VPN Components:**
- **Public subnet route table** — routes internet traffic to Internet Gateway
- **Private subnet route table** — routes internal traffic locally, optionally through NAT gateway for outbound internet
- **Virtual Gateway** — AWS-side VPN endpoint
- **Customer Gateway** — on-premises VPN endpoint

### Network ACLs (Access Control Lists)

Network ACLs operate at the **subnet level** in AWS, providing an additional layer of security beyond security groups.

**Key Characteristics:**
- **Custom ACLs deny all traffic** by default until rules are explicitly added
- Can specify both **allow** and **deny** rules (unlike security groups which only have allow rules)
- Rules are **evaluated in number order** (lowest number first; first match wins)
- **Separate inbound and outbound rules** — each direction is independently controlled
- **Stateless** — return traffic must be explicitly allowed (unlike security groups which are stateful)
- **Default ACLs allow all traffic** — the default NACL created with a VPC permits all inbound and outbound traffic

**Example Network ACL Rules:**

```
INBOUND RULES:
+------+--------+----------+-------------+-------+
| Rule | Type   | Protocol | Source      | Allow |
+------+--------+----------+-------------+-------+
| 100  | HTTP   | TCP 80   | 0.0.0.0/0  | ALLOW |
| 110  | HTTPS  | TCP 443  | 0.0.0.0/0  | ALLOW |
| 120  | SSH    | TCP 22   | 10.1.0.0/16| ALLOW |
| *    | ALL    | ALL      | 0.0.0.0/0  | DENY  |  <-- Default deny
+------+--------+----------+-------------+-------+

OUTBOUND RULES:
+------+--------+----------+-------------+-------+
| Rule | Type   | Protocol | Destination | Allow |
+------+--------+----------+-------------+-------+
| 100  | HTTP   | TCP 80   | 0.0.0.0/0  | ALLOW |
| 110  | HTTPS  | TCP 443  | 0.0.0.0/0  | ALLOW |
| 120  | Custom | TCP 1024-| 0.0.0.0/0  | ALLOW |  <-- Ephemeral ports
|      |        |    65535 |             |       |      for return traffic
| *    | ALL    | ALL      | 0.0.0.0/0  | DENY  |  <-- Default deny
+------+--------+----------+-------------+-------+

Note: Because NACLs are STATELESS, you must explicitly allow
      ephemeral ports for return traffic (unlike Security Groups
      which are stateful and handle this automatically).
```

## Definitions

| Term | Definition |
|------|------------|
| Network Segmentation | The practice of splitting a computer network into smaller subnetworks to improve performance, security, and manageability |
| Defense in Depth | A security strategy that deploys multiple layers of protection so that if one layer is breached, subsequent layers continue to defend |
| Microsegmentation | A fine-grained segmentation technique that creates isolated segments based on resource identity rather than IP addresses, typically implemented via software-defined networking |
| VLAN (Virtual LAN) | A logical subdivision of a physical switch that creates separate broadcast domains, enabling network segmentation without dedicated hardware |
| MAC Address | Media Access Control address; a unique hardware identifier assigned to a network interface controller (NIC) for communication on a network segment |
| MAC Address Table (CAM Table) | A table maintained by a switch that maps physical ports to the MAC addresses of devices connected to those ports |
| MAC Flooding | An attack where an attacker sends thousands of frames with spoofed source MAC addresses to overflow a switch's MAC address table, causing it to fail open and behave like a hub |
| Flooding (Switch) | The process by which a switch forwards a frame out all ports except the source port when the destination MAC address is not in its MAC address table |
| NAC (Network Access Control) | A unified approach to endpoint security that evaluates device health, authenticates users, and enforces network security policies before granting network access |
| VPN (Virtual Private Network) | An encrypted tunnel that provides secure communication over an untrusted network such as the internet |
| Site-to-Site VPN | A VPN that creates a permanent encrypted tunnel between two physical locations (e.g., main office and branch office) |
| IPSec | Internet Protocol Security; a protocol suite that authenticates and encrypts packets at the network layer to secure IP communications |
| TLS | Transport Layer Security; a cryptographic protocol that provides end-to-end encryption for data in transit, operating at the transport layer |
| Zero Trust | A security model that assumes no network, user, or device is inherently trustworthy, requiring continuous verification for all access requests |
| Hypervisor | Software that creates and manages virtual machines, providing virtual hardware resources including virtual network switches |
| Virtual Switch (vSwitch) | A software-based network switch within a hypervisor that connects virtual machines to each other and to the physical network |
| SDN (Software-Defined Networking) | An approach to networking that separates the control plane from the data plane, enabling programmatic network configuration and management |
| EDR (Endpoint Detection and Response) | A security solution that continuously monitors endpoints to detect, investigate, and respond to cyber threats in real time |
| TPM (Trusted Platform Module) | A dedicated hardware chip that provides hardware-based security functions including cryptographic key generation, secure storage, and platform integrity verification |
| AWS VPC (Virtual Private Cloud) | A logically isolated section of the AWS cloud where users can define their own virtual network with full control over IP addressing, subnets, route tables, and gateways |
| Subnet | A range of IP addresses within a VPC or network that segments the address space; in AWS, each subnet resides in a single Availability Zone |
| Network ACL | A stateless firewall that operates at the subnet level in AWS, evaluating rules in number order to allow or deny traffic |
| Security Group | A stateful virtual firewall in AWS that operates at the instance level, allowing only allow rules (implicit deny for everything else) |
| DHCP Snooping | A switch security feature that filters untrusted DHCP messages to prevent rogue DHCP server attacks |
| Port ACL | Access control lists applied at individual switch ports to control which traffic is permitted |
| Shared Responsibility Model | The cloud security framework defining which security obligations belong to the cloud provider ("of" the cloud) versus the customer ("in" the cloud) |
| Azure ExpressRoute | A Microsoft Azure service that provides a private, dedicated connection between on-premises infrastructure and Azure data centers, bypassing the public internet |
| MFA (Multi-Factor Authentication) | An authentication method requiring two or more verification factors (something you know, have, or are) to gain access |
| Quarantine Network | A restricted network segment where non-compliant devices are placed and provided only with remediation services such as patch and antivirus updates |
| IGW (Internet Gateway) | An AWS VPC component that enables communication between instances in the VPC and the internet |
| NAT Gateway | A Network Address Translation service in AWS that allows instances in a private subnet to connect to the internet while preventing inbound connections |
| Availability Zone (AZ) | A distinct data center location within an AWS Region, providing physical redundancy and fault isolation |

## Diagrams & Visual Descriptions

### Defense in Depth Layers Diagram

The lecture includes a castle/fortress-style diagram illustrating defense in depth. The visualization shows concentric protective layers, similar to a medieval castle:

- **Outermost layer (moat/walls):** Infrastructure and Services — the first barrier attackers encounter, including network perimeter defenses, firewalls, and DMZ architecture
- **Second layer (inner walls):** Documents in Transit — encryption and integrity protection for all data moving between zones
- **Third layer (keep/tower):** Endpoints — individual device protections including EDR, OS hardening, and encryption
- **Innermost layer (vault):** Microsegmentation — the most granular protection, identity-based access at the individual resource level

Each layer is depicted with sensors and monitoring points, emphasizing that detection occurs at every boundary.

### Switch/MAC Address Topology Diagram

The lecture includes a topology diagram showing a switch with multiple connected devices and their associated MAC addresses. The diagram illustrates:

- Physical port connections (numbered ports on the switch)
- MAC address assignments for each connected device
- The MAC address table inside the switch
- Arrows showing the learning process as frames traverse the switch
- Visual distinction between flooding (multiple arrows out) and unicast forwarding (single arrow out)

### VLAN Segmentation Diagram

A network diagram showing a single physical switch divided into multiple VLANs:

- Color-coded ports assigned to different VLANs
- A trunk port connecting to a router for inter-VLAN routing
- Broadcast domain boundaries clearly marked
- Devices within the same VLAN shown as able to communicate directly
- Devices in different VLANs shown as requiring the router path

### NAC Architecture Diagram

The NAC architecture diagram depicts the flow of a remote access connection:

1. Remote device initiates connection
2. NAC server intercepts and evaluates the device
3. Decision point: compliant devices are granted corporate network access; non-compliant devices are redirected to the quarantine network
4. The quarantine network provides remediation services
5. After remediation, the device is re-evaluated

### AWS VPC Architecture Diagram

A comprehensive AWS VPC diagram showing:

- VPC boundary within an AWS Region
- Two Availability Zones for redundancy
- Public subnets (with Internet Gateway route) and private subnets (internal only)
- Route tables for each subnet
- Internet Gateway for public-facing resources
- Virtual Gateway for Site-to-Site VPN to on-premises
- Customer Gateway device at the on-premises location
- Security groups around individual instances
- Network ACLs at subnet boundaries

## Code Examples

### VLAN Configuration (Cisco IOS)

The following examples demonstrate how to configure VLANs on a Cisco switch, which is the most common real-world implementation of logical network segmentation:

```cisco
! Create VLANs
Switch(config)# vlan 10
Switch(config-vlan)# name HR_Department
Switch(config-vlan)# exit

Switch(config)# vlan 20
Switch(config-vlan)# name Engineering
Switch(config-vlan)# exit

Switch(config)# vlan 30
Switch(config-vlan)# name Servers
Switch(config-vlan)# exit

Switch(config)# vlan 40
Switch(config-vlan)# name Guest_WiFi
Switch(config-vlan)# exit
```

```cisco
! Assign ports to VLANs (access ports)
Switch(config)# interface FastEthernet 0/1
Switch(config-if)# switchport mode access
Switch(config-if)# switchport access vlan 10
Switch(config-if)# exit

Switch(config)# interface FastEthernet 0/5
Switch(config-if)# switchport mode access
Switch(config-if)# switchport access vlan 20
Switch(config-if)# exit

Switch(config)# interface range FastEthernet 0/9 - 10
Switch(config-if-range)# switchport mode access
Switch(config-if-range)# switchport access vlan 30
Switch(config-if-range)# exit
```

```cisco
! Configure trunk port to router (for inter-VLAN routing)
Switch(config)# interface GigabitEthernet 0/1
Switch(config-if)# switchport mode trunk
Switch(config-if)# switchport trunk allowed vlan 10,20,30,40
Switch(config-if)# exit
```

```cisco
! Security: Disable unused ports
Switch(config)# interface range FastEthernet 0/15 - 24
Switch(config-if-range)# shutdown
Switch(config-if-range)# exit

! Security: Enable port security to prevent MAC flooding
Switch(config)# interface FastEthernet 0/1
Switch(config-if)# switchport port-security
Switch(config-if)# switchport port-security maximum 2
Switch(config-if)# switchport port-security violation shutdown
Switch(config-if)# switchport port-security mac-address sticky
Switch(config-if)# exit
```

The port security configuration above limits port 0/1 to a maximum of 2 MAC addresses. If a third MAC is detected (as would happen during a MAC flooding attack), the port is shut down. The `sticky` option causes learned MAC addresses to be saved to the running configuration.

```cisco
! Enable DHCP Snooping
Switch(config)# ip dhcp snooping
Switch(config)# ip dhcp snooping vlan 10,20,30,40
Switch(config)# interface GigabitEthernet 0/1
Switch(config-if)# ip dhcp snooping trust
Switch(config-if)# exit
```

DHCP snooping marks all ports as untrusted by default. Only the port connected to the legitimate DHCP server (or the trunk/uplink port) should be trusted. Untrusted ports that send DHCP server messages will have those messages dropped.

### Inter-VLAN Routing (Router-on-a-Stick)

```cisco
! Router configuration for inter-VLAN routing
Router(config)# interface GigabitEthernet 0/0
Router(config-if)# no shutdown
Router(config-if)# exit

! Create sub-interfaces for each VLAN
Router(config)# interface GigabitEthernet 0/0.10
Router(config-subif)# encapsulation dot1Q 10
Router(config-subif)# ip address 10.0.10.1 255.255.255.0
Router(config-subif)# exit

Router(config)# interface GigabitEthernet 0/0.20
Router(config-subif)# encapsulation dot1Q 20
Router(config-subif)# ip address 10.0.20.1 255.255.255.0
Router(config-subif)# exit

Router(config)# interface GigabitEthernet 0/0.30
Router(config-subif)# encapsulation dot1Q 30
Router(config-subif)# ip address 10.0.30.1 255.255.255.0
Router(config-subif)# exit
```

This "router-on-a-stick" configuration uses a single physical router interface with multiple sub-interfaces, one per VLAN. Each sub-interface uses 802.1Q encapsulation to tag frames with the correct VLAN ID. The router then makes routing decisions between VLANs, and ACLs can be applied to control which VLANs are allowed to communicate.

### Nmap Network Discovery Commands

```bash
# Discover live hosts on a subnet
nmap -sn 10.0.10.0/24

# Scan for open ports on a specific host
nmap -sV 10.0.10.50

# Aggressive scan with OS detection and service version
nmap -A -T4 10.0.10.0/24

# Scan specific ports across a VLAN
nmap -p 22,80,443,3306,5432 10.0.20.0/24
```

These commands demonstrate how an attacker (or security auditor) would perform internal reconnaissance. Proper network segmentation limits the scope of what Nmap can discover — a device in VLAN 10 should not be able to scan hosts in VLAN 30 unless routing rules explicitly permit it.

### AWS VPC Configuration (AWS CLI)

```bash
# Create a VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications \
  'ResourceType=vpc,Tags=[{Key=Name,Value=Production-VPC}]'

# Create subnets
aws ec2 create-subnet --vpc-id vpc-abc123 --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a --tag-specifications \
  'ResourceType=subnet,Tags=[{Key=Name,Value=Public-Subnet-A}]'

aws ec2 create-subnet --vpc-id vpc-abc123 --cidr-block 10.0.2.0/24 \
  --availability-zone us-east-1a --tag-specifications \
  'ResourceType=subnet,Tags=[{Key=Name,Value=Private-Subnet-A}]'

# Create and attach Internet Gateway
aws ec2 create-internet-gateway
aws ec2 attach-internet-gateway --vpc-id vpc-abc123 \
  --internet-gateway-id igw-xyz789

# Create Network ACL with rules
aws ec2 create-network-acl --vpc-id vpc-abc123

# Add inbound HTTP rule (rule number 100)
aws ec2 create-network-acl-entry --network-acl-id acl-abc123 \
  --rule-number 100 --protocol tcp --port-range From=80,To=80 \
  --cidr-block 0.0.0.0/0 --rule-action allow --ingress

# Add inbound HTTPS rule (rule number 110)
aws ec2 create-network-acl-entry --network-acl-id acl-abc123 \
  --rule-number 110 --protocol tcp --port-range From=443,To=443 \
  --cidr-block 0.0.0.0/0 --rule-action allow --ingress

# Deny all other inbound (explicit deny, rule 200)
aws ec2 create-network-acl-entry --network-acl-id acl-abc123 \
  --rule-number 200 --protocol -1 \
  --cidr-block 0.0.0.0/0 --rule-action deny --ingress
```

This demonstrates the programmatic creation of AWS VPC resources, showing how network segmentation concepts translate directly to cloud infrastructure.

## Formulas & Algorithms

### MAC Address Table Capacity and MAC Flooding

The feasibility of a MAC flooding attack depends on the switch's CAM table capacity:

$$\text{Attack frames required} \geq \text{CAM table size}$$

Typical CAM table sizes:
- Small/unmanaged switches: ~1,000-4,000 entries
- Enterprise switches: ~16,000-128,000 entries

Time to overflow (approximate):

$$t = \frac{\text{CAM table size}}{\text{Frames per second}}$$

For example, with a 16,000-entry table and an attacker sending 10,000 frames/second:

$$t = \frac{16,000}{10,000} = 1.6 \text{ seconds}$$

This demonstrates why MAC flooding prevention is critical — the attack is extremely fast.

### VLAN Broadcast Domain Sizing

When designing VLANs, the broadcast domain size affects performance:

$$\text{Broadcast traffic ratio} = \frac{\text{Broadcast frames}}{\text{Total frames}}$$

Best practice: Keep VLANs to /24 subnets (254 usable hosts) or smaller to limit broadcast domain size. Larger subnets increase broadcast overhead:

- /24 = 254 hosts (recommended)
- /22 = 1,022 hosts (acceptable for some use cases)
- /16 = 65,534 hosts (too large; excessive broadcast traffic)

### NACL Rule Evaluation Algorithm

AWS Network ACL rules are evaluated using a first-match algorithm:

```
ALGORITHM: NACL_Evaluate(packet, rules)
INPUT: incoming/outgoing packet, ordered list of NACL rules
OUTPUT: ALLOW or DENY

1. Sort rules by rule number (ascending)
2. For each rule in sorted order:
   a. If packet matches rule's protocol, port range, and CIDR:
      - If rule action is ALLOW: return ALLOW
      - If rule action is DENY: return DENY
   b. Else: continue to next rule
3. If no rule matched: return DENY (implicit deny - rule *)
```

This is distinct from Security Groups, which aggregate all rules and apply a **default deny with explicit allows only** — there is no deny rule capability in security groups.

### Zero Trust Access Decision Function

The conditional policy engine in a Zero Trust architecture can be modeled as:

```
FUNCTION: ZeroTrustAccessDecision(request)
INPUT: access request with context
OUTPUT: ALLOW, DENY, or STEP_UP_AUTH

1. Verify user identity via Identity Provider
   - If identity invalid: return DENY
2. Verify device via Device Directory
   - If device unknown or non-compliant: return DENY
3. Evaluate conditional policies:
   a. Check user role and permissions
   b. Check device health score
   c. Check network location (internal/external/VPN)
   d. Check geo-location
   e. Check time of access
   f. Calculate risk score = f(role, device, location, time, behavior)
4. If risk_score > HIGH_THRESHOLD: return DENY
5. If risk_score > MEDIUM_THRESHOLD: return STEP_UP_AUTH
6. If all conditions satisfied: return ALLOW (scoped to minimum necessary)
7. Log decision for monitoring and audit
```

### Subnet Calculation for VPC Design

When designing AWS VPCs with multiple subnets across Availability Zones:

$$\text{Total IPs in VPC} = 2^{(32 - \text{VPC prefix})}$$

$$\text{Usable IPs per subnet} = 2^{(32 - \text{Subnet prefix})} - 5$$

AWS reserves 5 IPs per subnet (network address, VPC router, DNS, future use, broadcast).

Example for a /16 VPC with /24 subnets:
- VPC total: $2^{16} = 65,536$ IPs
- Per subnet: $2^{8} - 5 = 251$ usable IPs
- Maximum /24 subnets in a /16 VPC: $256$ subnets

## Key Takeaways

- **Network segmentation is non-negotiable** — flat networks provide no barriers to lateral movement. Every production network must be segmented into zones with controlled traffic flow between them.

- **Defense in depth requires multiple independent layers** — infrastructure security, data-in-transit protection, endpoint hardening, and microsegmentation each provide value independently and compound when layered together.

- **Understand switch fundamentals before defending them** — the MAC address table learning process (flood, learn, forward) is the foundation of LAN switching. MAC flooding attacks exploit this mechanism to turn switches into hubs, enabling traffic sniffing.

- **VLANs are the primary tool for logical segmentation** — they are efficient (no wasted hardware), scalable, and provide strong broadcast domain isolation. However, inter-VLAN communication requires a router, which becomes the security enforcement point.

- **Always apply VLAN best practices** — SSH-only management, disable unused ports, enable port security and DHCP snooping, and keep firmware updated. These prevent common attacks like MAC flooding and rogue DHCP servers.

- **NAC is essential for remote access** — every remote device must be evaluated for compliance before gaining network access. Non-compliant devices must be quarantined and remediated, not simply allowed through.

- **Site-to-Site VPNs secure branch connectivity** — but the VPN tunnel alone is not sufficient; each branch must also have firewall rules enforcing the "need to know" principle.

- **Virtual environments need virtual segmentation** — virtual switches, packet inspection, and port ACLs within the hypervisor are just as important as physical network controls. VM traffic can escape to the physical network if not properly controlled.

- **Zero Trust is the future of network security** — assume all networks are hostile, make identity (not network location) the perimeter, and continuously verify every access request. The four components (Identity Provider, Device Directory, Conditional Policy, Access Proxy) form the enforcement architecture.

- **Cloud segmentation uses VPCs, subnets, and NACLs** — AWS VPCs provide isolation, subnets provide segmentation within a VPC, Network ACLs provide stateless subnet-level filtering, and Security Groups provide stateful instance-level filtering.

- **The Shared Responsibility Model defines who secures what** — the cloud provider secures the infrastructure ("of" the cloud), but the customer is responsible for everything they deploy and configure ("in" the cloud).

- **Microsegmentation prevents lateral movement at the workload level** — by using identity-based policies decoupled from physical infrastructure, microsegmentation provides the most granular protection and directly supports Zero Trust principles.

## Connections

**To Previous Weeks:**
- **Week 1-2 (Cybersecurity Fundamentals/Kill Chain):** Network segmentation directly counters lateral movement, one of the key kill chain phases. The defense-in-depth model introduced this week builds on the kill chain framework by showing where each defensive layer intercepts the attack progression.
- **Week 3-4 (Security Policy):** Security policies define the rules that network segmentation enforces. VLAN assignments, firewall rules, and NAC policies are all implementations of organizational security policy.
- **Week 5-6 (Threat Modeling/Active Sensors):** Threat modeling identifies which segments need the most protection, and active sensors (IDS/IPS) are deployed at segment boundaries to detect cross-segment attacks. The defense-in-depth diagram shows sensors at every layer.

**To Broader CS Topics:**
- **Computer Networks (CSIT fundamentals):** VLANs, switches, MAC addresses, routing, and subnetting are core networking concepts applied here in a security context.
- **Operating Systems:** Hypervisor-based virtual networking ties into OS-level virtualization concepts. Virtual switches are managed by the hypervisor kernel.
- **Cloud Computing:** AWS VPC design is a direct application of network segmentation in cloud infrastructure, relevant to any cloud architecture or DevOps role.
- **Software Engineering:** Microsegmentation and Zero Trust align with the principle of least privilege in software design — components should have only the access they need, nothing more.

**Looking Ahead:**
- **Week 8 (Active Sensors/Monitoring):** Network segmentation creates the boundaries where sensors are deployed. Without segmentation, sensor placement is ineffective because all traffic flows on a flat network. The monitoring and active defense topics in upcoming weeks build directly on the segmented architecture established here.
