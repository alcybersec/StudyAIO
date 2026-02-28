# CSIT314 — Week 9: DevOps

> **Source files:** CSIT314_Week9.pptx
> **Date summarized:** 2026-02-24

## Overview

This lecture introduces DevOps as a software engineering methodology that unifies software development (Dev) and IT operations (Ops) into a cohesive, collaborative practice. It examines the fundamental problems with traditional siloed development models — where separate Dev and Ops teams operate with different objectives, tools, and environments — and presents DevOps as the cultural and technical solution. The lecture covers DevOps principles, lifecycle, tooling, comparisons with Agile and CI/CD, and concludes with an in-depth Netflix case study demonstrating real-world adoption of the full-cycle developer model.

## Key Concepts

### "Software is Eating the World"

Marc Andreessen's influential observation that software companies are poised to dominate large segments of the economy sets the stage for why DevOps matters. The lecture provides compelling examples of this trend:

- **Modern cars** contain hundreds of millions of lines of code, making them as much software products as mechanical ones.
- **Domino's Pizza** increased its IT workforce by 240%, reflecting its transformation into a technology-driven company.
- **MAF (Majid Al Futtaim)** more than tripled its Data Science resources.
- **Nike** is turning footwear into a fully connected platform by integrating shoes with lifestyle and fitness applications.

The takeaway: "Every business is a software business." This reality demands faster, more reliable software delivery — which is exactly what DevOps enables.

### Traditional Development Models

In the traditional model, software delivery is divided between two distinct teams:

- **DEV team**: Responsible for Design, Code, and Test.
- **OPS team**: Responsible for Deploy, Support/SysAdmin, and Maintenance.

Between these teams lies the **"Wall of Confusion"** — a barrier created by different mindsets, different tools, and different environments. The traditional pipeline also includes intermediate handoffs through QA teams and Release teams before reaching IT Operations, adding further delays and communication overhead.

### Problems with Traditional Models

The lecture identifies six core problems with the traditional siloed approach:

**Problem 1 — Different Objectives:**
The IT Operations team prioritizes stability and may view each change or new release as a potential threat to system reliability. The Development team, conversely, is incentivized to change and add new features. This fundamental misalignment leads to conflicts between departments.

**Problem 2 — Different Perspectives:**
Operations views the application as a **black box**, monitoring it through external tools (CPU utilization, I/O load, kernel behavior). Development has access to the **source code** and understands the internal workings of the application. Neither side has the complete picture.

**Problem 3 — Different Environments:**
Operations runs the application in the **production environment**, while developers run and test on their **own machines**. These environments may differ vastly in hardware, software, and library versions — leading to the classic "it works on my machine" problem.

**Problem 4 — Driven by Different Requirements:**
Operations is driven by **non-functional requirements** (availability, reliability, system speed), while Development is driven by **functional requirements** (features). These are both essential but are rarely prioritized together.

**Problem 5 — Client Perspective:**
From the client's point of view, when something goes wrong, it is unclear who is really responsible. The fragmented ownership model makes accountability ambiguous.

**Problem 6 — Combining Know-How:**
Operations and Development each possess only their own portion of knowledge and the tools needed to build, test, and run the application. A smooth operation requires the **combined know-how** of both teams, but the traditional model keeps this knowledge separated.

### DevOps Definition

DevOps is a software engineering methodology that aims to **unify software development (Dev) and IT operations (Ops)**. Key characteristics:

- Development and operations teams are **no longer separated** — the "Wall of Confusion" is removed.
- Teams are sometimes **merged into a single team** where DevOps engineers work across the **entire application lifecycle**, from development and test to deployment and operations.
- The focus is on the full software delivery pipeline rather than isolated phases.

### DevOps Cultural Shift

DevOps is not just about tools — it represents a fundamental **cultural shift** in how organizations build and deliver software:

- **Increased collaboration** between development and operations roles
- **Shared responsibility** — everyone owns the outcome, not just their slice
- **Support for autonomous teams** — teams are empowered to make decisions
- **Value feedback** — direct feedback loops replace second-hand information
- **Automation** — repetitive tasks are automated to reduce error and increase speed

### DevOps Principles and Lifecycle

The DevOps lifecycle is represented as a **continuous infinity loop**, emphasizing that software delivery is not a linear process but an ongoing cycle:

**Plan** → **Code** → **Build** → **Test** → **Release** → **Deploy** → **Operate** → **Monitor** → (back to **Plan**)

This loop captures the idea that monitoring in production feeds back into planning for the next iteration, creating a true continuous improvement cycle. Each phase flows into the next without the handoff barriers present in traditional models.

### DevOps Tools

The lecture presents a categorized overview of tools used across the DevOps lifecycle (sometimes visualized as the "DevOps Periodic Table"):

| Category | Purpose | Example Tools |
|----------|---------|---------------|
| **Source Code Repository** | Developers check in and change code; a major component of continuous integration | Git, Subversion, Cloudforce, Bitbucket, TFS |
| **Build Server** | Automatically compiles code in the source repository into an executable code base | Jenkins, SonarQube, Artifactory |
| **Configuration Management** | Defines the configuration of a server or environment | Puppet, Chef |
| **Virtual Infrastructure** | Programmatically creates new virtual machines; provided by cloud vendors | Amazon Web Services (AWS), Microsoft Azure |
| **Test Automation** | Automatically performs all tests | Selenium, Water |

### DevOps vs CI/CD

DevOps **facilitates the implementation of CI/CD** (Continuous Integration / Continuous Delivery). The combined knowledge of Dev and Ops enables optimization:

- **Development knows:** how the application must be configured, and what metrics should be monitored.
- **Operations knows:** the internal structure of the application (since they are now part of the same team).
- **Feedback from operation** can be used directly to optimize further development since all necessary roles are united in one team.

CI/CD is a practice enabled by DevOps; DevOps is the broader cultural and organizational framework.

### DevOps vs Agile

| Feature | DevOps | Agile |
|---------|--------|-------|
| **Agility Scope** | Both Development and Operations | Only Development |
| **Processes** | CI, CD, CT (Continuous Testing), etc. | Agile Scrum, Kanban, etc. |
| **Key Focus** | Timeliness and quality have **equal priority** | Timeliness is the **main priority** |
| **Source of Feedback** | From self (monitoring tools) | From customers |
| **Scope of Work** | Agility and need for automation | Agility only |

The key distinction: Agile primarily addresses the development side, focusing on iterative delivery and customer feedback. DevOps extends agility across the **entire delivery pipeline** — including deployment, operations, and monitoring — and places equal emphasis on quality and automation alongside speed.

### Different Environments (Dev → Production Pipeline)

The lecture highlights the typical environment pipeline in DevOps-oriented organizations:

**Dev** → **QA** → **Staging** → **Production**

Each environment serves a purpose: Dev for active development, QA for quality assurance testing, Staging as a production-like environment for final validation, and Production as the live environment. DevOps tools (especially configuration management and virtual infrastructure) help ensure consistency across these environments, addressing the traditional "different environments" problem.

### Netflix Case Study — Full-Cycle Developers

The Netflix case study is a detailed real-world example of DevOps adoption within their **Edge Engineering** team, which is responsible for the first layer of AWS services required for Netflix streaming.

**The Old Model (Traditional Handoffs):**

In the previous model, releasing a new feature required developers to coordinate with the ops team on metrics, alerts, and capacity considerations, then hand off code for ops to deploy and operate. Ops teams needed ongoing training on new features and bug fixes. When things went well, developers experienced fewer interrupts. However, when things did not go well, the costs accumulated:

- Communication and knowledge transfers between Dev and Ops were **messy**, requiring additional round trips to debug problems or answer partner questions.
- Deployment problems had **higher time-to-detect and time-to-resolve** because ops teams had less direct knowledge of the changes being deployed.
- The gap between code complete and deployed was **much longer** — releases happened on the order of weeks rather than days.
- Feedback was **second-hand**: Ops directly experienced pains (lack of alerting, performance issues, increased latencies), but developers only heard about these problems indirectly.

**The Problem with Segmented Roles:**

Netflix had been segmenting responsibilities, with each functional area owned by a different person or role. While specialists develop expertise in focused areas and optimize what is needed for their segment, software requires the **entire lifecycle to deliver value to customers**. Focusing on a slice creates **silos that slow down end-to-end progress**. Even grouping different specialists into one team introduces communication overhead, bottlenecks, and inhibits feedback loop effectiveness.

**The Solution — "Operate What You Build":**

Edge Engineering optimized for learning and feedback by breaking down silos and encouraging **shared ownership of the full software lifecycle**. Their philosophy: "Operate what you build" — the team that develops a system is also responsible for operating and supporting that system. This means each development team owns:

- Deployment issues
- Performance bugs
- Capacity planning
- Alerting gaps
- Partner support

This creates **direct feedback loops** and **aligns incentives**. Teams are empowered to make changes to the system design or underlying code and take full ownership rather than relying on external parties or waiting for permission.

**Full-Cycle Developers:**

Netflix adopted the **full-cycle developer** model where individual developers are responsible for the complete lifecycle: **design + deploy + support**. This is a significant mindset shift:

- **Before:** Developers saw design, development, and sometimes testing as their primary value creation. Operations was viewed as a **distraction**, with developers favoring short-term fixes to get back to their "real job."
- **After:** Developers use their software development expertise to **solve problems across the full lifecycle** — creating software, writing test cases, and automating operational aspects.

**Centralized Teams for Common Tooling:**

To support full-cycle developers, Netflix maintains **centralized teams** whose mission is developing common tooling and infrastructure (reusable building blocks) that solve problems common to every development team. Other teams leverage these pre-built components, which ensures consistency, standards, and quality. Development teams can then decide if their specific needs warrant a custom solution or if centralized tooling suffices.

**Breadth and On-Call Rotation:**

The full-cycle model requires both **interest and aptitude** in a diverse range of technologies. Breadth increases workload, so Netflix implemented an **on-call rotation** where developers take turns handling deployment, operations, and support responsibilities:

- **When done well:** Creates space for others to do focused, flow-state work.
- **When not done well:** Teams devolve into everyone jumping on high-interrupt production issues, leading to burnout.

Developers who prefer deep specialization in a narrow field may be uncomfortable with this model — Netflix supports them in finding roles that better fit their preferences.

**Results:**

- Deployments became **routine and frequent**.
- Canary releases take **hours instead of days**.
- Developers can **quickly research issues and make changes** without bouncing responsibilities across teams.
- Other groups within Netflix have seen similar benefits after adopting the model.

## Definitions

| Term | Definition |
|------|------------|
| **DevOps** | A software engineering methodology that unifies software development (Dev) and IT operations (Ops), removing the traditional wall between these teams |
| **Wall of Confusion** | The barrier between Dev and Ops teams in traditional models, caused by different mindsets, tools, and environments |
| **CI (Continuous Integration)** | The practice of frequently merging code changes into a shared repository, with automated builds and tests |
| **CD (Continuous Delivery/Deployment)** | The practice of automatically preparing and (optionally) deploying code changes to production |
| **CT (Continuous Testing)** | Automated testing integrated throughout the delivery pipeline |
| **Source Code Repository** | A system where developers check in and manage code versions (e.g., Git, Bitbucket) |
| **Build Server** | A tool that automatically compiles source code into executable code (e.g., Jenkins) |
| **Configuration Management** | Tools that define and maintain server/environment configurations (e.g., Puppet, Chef) |
| **Virtual Infrastructure** | Cloud-based services that programmatically provision virtual machines (e.g., AWS, Azure) |
| **Full-Cycle Developer** | A developer responsible for the entire software lifecycle: design, development, testing, deployment, operations, and support |
| **Canary Release** | A deployment strategy where changes are rolled out to a small subset of users/servers first to detect issues before full rollout |
| **On-Call Rotation** | A scheduling system where developers take turns handling operational responsibilities (deployments, incident response, support) |
| **Non-Functional Requirements** | System qualities like availability, reliability, performance, and speed — traditionally the focus of Ops |
| **Functional Requirements** | Feature specifications and business logic — traditionally the focus of Dev |

## Diagrams & Visual Descriptions

### Traditional Development Model Diagram
The slide depicts two distinct team blocks separated by a barrier:
- **Left side (DEV team):** Three connected phases — Design → Code → Test
- **Right side (OPS team):** Three connected phases — Deploy → Support/SysAdmin → Maintenance
- **Center:** A "Wall of Confusion" separating the two, annotated with "Different mindsets" and "Different tools & environments"

This visual powerfully illustrates how the traditional model creates an artificial divide where each side operates independently with limited visibility into the other's work.

### Traditional Pipeline Flow
A second diagram shows the extended handoff chain: Development team → QA team → Release team → IT Operation Team, illustrating the multiple intermediary steps and handoff points that introduce delay and communication overhead.

### DevOps Lifecycle Infinity Loop
The DevOps lifecycle is shown as a **figure-eight (infinity symbol)** with continuous flow through eight phases:

The left loop represents the **Dev** side (Plan, Code, Build, Test) and the right loop represents the **Ops** side (Release, Deploy, Operate, Monitor). The infinity shape emphasizes the continuous, never-ending nature of software delivery.

### DevOps Periodic Table of Tools
A grid visualization categorizing DevOps tools by function, styled like the periodic table of elements:
- **Sc (Source Control):** Git, Subversion, Bitbucket
- **Bu (Build):** Jenkins, SonarQube, Artifactory
- **Cm (Config Management):** Puppet, Chef
- **Vi (Virtual Infrastructure):** AWS, Azure
- **Ta (Test Automation):** Selenium, Water

Each tool is placed in a "cell" with an abbreviation, making it easy to see the ecosystem at a glance.

### Different Environments Diagram
A linear pipeline showing the progression of code through environments:

Each environment box represents a distinct server configuration, with DevOps practices ensuring consistency across all of them.

### Netflix Segmented Roles Diagram
Shows the software lifecycle as a horizontal chain of responsibilities, with each segment owned by a different person/role. This illustrates the fragmentation problem — while each specialist optimizes their area, end-to-end delivery suffers from handoff delays and communication gaps.

### Netflix Full-Cycle Developer Model
Contrasts with the segmented model by showing a single team/developer responsible for the entire horizontal chain: design → development → test → deploy → operate → support. The elimination of handoff boundaries creates direct feedback loops and shared ownership.

## Code Examples

No specific code examples were presented in this lecture. However, the lecture references a **self-directed in-class activity** where students build their own CI/CD pipeline for a sample application, requiring:

- Git installed on their machine
- Optional: Docker installed
- Internet access

This activity puts DevOps principles into practice by having students set up a working pipeline.

## Formulas & Algorithms

This lecture is conceptual and organizational in nature — no mathematical formulas or algorithms are covered. The focus is on software engineering methodology, organizational structure, and cultural practices rather than computational theory.

## Key Takeaways

- **"Every business is a software business"** — the increasing role of software across all industries demands efficient, reliable delivery practices.
- **The traditional Dev/Ops split creates six fundamental problems:** different objectives, different perspectives, different environments, different requirements, unclear accountability, and fragmented knowledge.
- **The "Wall of Confusion"** between Dev and Ops is the root cause of slow, unreliable software delivery in traditional models.
- **DevOps is a cultural shift first, a technical practice second** — shared responsibility, collaboration, autonomous teams, feedback, and automation are its pillars.
- **DevOps extends Agile** by applying agility to both development AND operations, with equal emphasis on timeliness and quality.
- **DevOps enables CI/CD** by combining the knowledge of Dev and Ops into unified teams that can optimize the entire pipeline.
- **The DevOps lifecycle is continuous** (the infinity loop) — there is no "done"; monitoring feeds back into planning.
- **Netflix's full-cycle developer model** is a powerful real-world example: "Operate what you build" eliminated handoff problems, reduced deployment time from weeks to hours, and empowered teams with direct feedback loops.
- **Centralized tooling teams** complement autonomous DevOps teams by providing reusable infrastructure and ensuring consistency.
- **On-call rotation** is a practical solution to managing the increased breadth of responsibilities in a full-cycle model, but must be implemented carefully to avoid burnout.
- **Not every developer thrives in a full-cycle model** — organizations should support those who prefer deep specialization in finding appropriate roles.

## Connections

- **Week 3 (Software Process Models):** The lecture explicitly references Week 3, connecting the traditional waterfall and sequential process models to the problems that DevOps solves. The rigidity and linearity of traditional models (with distinct phases and handoffs) directly contribute to the "Wall of Confusion."
- **Agile Methodologies (earlier weeks):** DevOps builds upon Agile principles but extends them beyond development into operations. Where Agile focuses on iterative development with customer feedback, DevOps adds operational agility, infrastructure automation, and monitoring-driven feedback.
- **CI/CD:** DevOps provides the organizational and cultural foundation that makes CI/CD practices effective. Without the unified team structure of DevOps, CI/CD implementations face the same handoff problems as traditional models.
- **Software Engineering Ethics and Future Trends (Week 10):** The lecture closes by pointing to the next topic — ethics and future trends — suggesting that as DevOps and automation reshape software delivery, new ethical considerations emerge around reliability, security, and accountability.
- **Broader CS context:** DevOps connects to cloud computing, distributed systems, infrastructure as code, containerization (Docker), and site reliability engineering (SRE) — all critical topics in modern computer science and software engineering practice.
