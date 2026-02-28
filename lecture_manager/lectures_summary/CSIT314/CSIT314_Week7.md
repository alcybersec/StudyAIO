# CSIT314 — Week 7: Continuous Integration/Delivery (CI/CD) and CMMI

> **Source files:** CSIT314_Week7.pptx
> **Date summarized:** 2026-02-24

## Overview

This lecture covers two major topics in software development methodologies: Continuous Integration/Continuous Delivery (CI/CD) and the Capability Maturity Model Integration (CMMI). The first half explores how modern development teams integrate code frequently, automate builds and testing, and establish deployment pipelines that range from continuous integration through continuous delivery to fully automated continuous deployment. The second half introduces CMMI as a process improvement framework that helps organizations mature their software development processes from ad hoc, person-dependent workflows to institutionalized, optimized practices. Together, these topics address both the technical practices and the organizational maturity needed to deliver high-quality software consistently.

## Key Concepts

### Integration and Integration Approaches

Integration is the process of combining individually developed software components into a working system. When multiple developers work on the same codebase independently, several issues can arise at integration time: merge conflicts, incompatible interfaces, broken dependencies, and unexpected behavioral interactions between modules.

There are three classical approaches to integration:

**Top-Down Integration**
- Starts with the outer UI layers and works inward toward lower-level modules.
- Requires writing numerous **stubs** (placeholder implementations) for the lower layers so the UI can interact with something during testing.
- Advantage: allows testing of user-facing functionality early.
- Disadvantage: postpones tough design and debugging decisions for the core logic layers until later.

**Bottom-Up Integration**
- Starts with low-level data and logic layers and works outward toward the UI.
- Requires writing **test drivers** to exercise these layers in isolation.
- Advantage: core logic and data layers are validated early.
- Disadvantage: high-level UI design flaws will not be discovered until late in the process.

**Sandwich Integration (Hybrid)**
- Connects top-level UI components directly with crucial bottom-level classes first.
- Middle layers are added later as needed.
- Often considered more practical than pure top-down or bottom-up approaches because it validates the most critical end-to-end paths early.

### Continuous Integration (CI)

Continuous Integration is a development practice, pioneered by Martin Fowler as part of Extreme Programming (XP), that requires developers to integrate code into a shared repository several times a day. Each integration is verified by an automated build that includes running tests, allowing teams to detect problems early.

The core principle is that integration is a communication mechanism: by integrating frequently, developers quickly discover conflicts between their changes, and errors, bugs, and incompatibilities can be detected and rectified rapidly.

### Build Types

There are three basic types of builds in a CI environment. All builds are automated, script-driven processes that pull source code from the repository and create deployable artifacts. They differ in where, when, by whom, and for what reason they are run:

| Build Type | Description |
|------------|-------------|
| **Private Build** | Run by individual developers on their local workstations before committing code. Validates that their changes compile and pass basic tests locally. |
| **Integration Build** | Run on a dedicated integration/build server whenever code is committed to the shared repository. Validates that the combined codebase works correctly. |
| **Release Build** | A specially tagged build intended for deployment to staging or production. Typically includes additional quality gates and packaging steps. |

### CI Practices

The lecture identifies the following essential practices for successful Continuous Integration:

1. **Maintain a Single Source Repository** -- Use a version control system such as Git/GitHub. Everything required to build the software application should be in the repository: code, test scripts, test data, properties files, database schemas, third-party libraries, etc.

2. **Automate the Build** -- Automate the entire process of turning source code into a running application. This often includes compiling, moving files, loading database schemas, and more. A single command should trigger the entire build process.

3. **Make Builds Self-Testing** -- Automated tests must be part of the build process so that a successful build implies the software works correctly.

4. **Everyone Commits to the Mainline Every Day** -- Developers should submit their work to the main repository at the end of each day. Frequent commits mean frequent communication about changes.

5. **Every Commit Should Build the Mainline on an Integration Machine** -- Regular builds happen on a dedicated integration machine (using CI servers such as Jenkins, Travis CI, Bamboo, GitLab, etc.). Only if the integration build succeeds should the commit be considered done.

6. **Fix Broken Builds Immediately** -- "Nobody has a higher priority task than fixing the build." A broken build blocks the entire team.

7. **Keep the Build Fast** -- Fast builds provide rapid feedback. Slow builds discourage frequent commits and reduce the quality of feedback. Long builds can also be a significant roadblock to team acceptance of the CI process.

8. **Test in a Clone of the Production Environment** -- Testing in a different environment introduces risk when the system is deployed to production. The test environment should mirror production as closely as possible.

### Automated Testing Types

Automated testing is a critical component of the CI build cycle. Different test types have different impacts on build speed:

| Test Type | Description | Impact on CI Build |
|-----------|-------------|-------------------|
| **Unit** | Tests discrete units of code to verify correct behavior; written and performed by developers as part of development. | Very low impact on build speed; easily included in every build cycle. |
| **Integration/Component** | Tests that verify specific components and their interaction with other internal and external components; may exercise code not exposed to end users. | Some impact on build speed; tends to run longer than unit tests. |
| **Load** | Subjects the application to usage levels approaching and beyond specification limits to determine maximum workload capacity without significant performance degradation. | Significant impact; appropriate for nightly runs or staged builds, not every commit. |
| **Stress** | Evaluates system behavior under extreme workloads or when hardware/software is compromised; includes resistance to denial-of-service (DoS) attacks. | Significant impact; appropriate for nightly runs or staged builds. |
| **Security** | Includes source-code analyzers, web application (black-box) scanners, database scanners, binary analysis tools, runtime analysis tools, configuration analysis tools, and proxies. | Potentially significant impact; appropriate for nightly runs or staged builds. |

### Improving Build Speed

Three approaches to managing build speed:

1. **Speed up the build** -- Eliminate bottlenecks or run the build on a faster machine with plenty of memory.
2. **Run complete builds less often** -- Execute full builds at times when developers are less likely to be working (e.g., nightly), and run only basic/quick builds on a continuous basis.
3. **Employ a staged build approach** -- Break the build into stages: a basic build runs first (fast feedback), a second stage runs additional processes, and a third stage handles remaining steps (comprehensive validation).

A combination of all three approaches is often used in practice.

### CI Build Cycle

The basic CI build cycle consists of the following key steps:
1. Developer commits code to the shared repository.
2. The CI server detects the change and checks out the latest code.
3. The build is compiled and assembled automatically.
4. Automated tests are executed.
5. Results (pass/fail) are reported back to the team.
6. If the build fails, the team fixes it immediately before any other work.

### Continuous Database Integration

Database changes are treated with the same importance as source code changes:
- A build server can be set up to begin a new CI cycle whenever the database is changed.
- Code and configuration files that modify the database are committed to version control just like application code and can trigger new builds.
- A CI build for database integration can: **drop** an existing database, **inspect** database scripts for compliance with project practices, **create, configure, and populate** the database with test data, and **run automated unit tests** to verify correct behavior.
- A primary benefit is that it frees developers from the fear of making database changes, since errors are caught automatically.

### Continuous Delivery (CD)

Continuous Delivery extends CI by adding a further step:
- Each time changes are pushed to the codebase, the new code is automatically built and tested in environments that closely mirror production (the **staging environment**).
- The staging environment addresses **non-functional requirements** such as security, redundancy, and flexibility -- requirements that may not be covered in development environments.
- Deployment to production still requires a **manual approval step** (e.g., manual testing, business sign-off).

### Continuous Deployment

Continuous Deployment goes one step further beyond Continuous Delivery:
- The software application is deployed to production **fully automatically** -- no manual intervention is required.
- Every time code changes are pushed, built, and tested successfully, they automatically go to production.
- This enables **small, incremental improvements** released regularly, often several times per day.
- The key distinction: in Continuous Delivery, deployment is manual; in Continuous Deployment, deployment is automated.

### Infrastructure as Code (IaC)

Infrastructure as Code treats the entire IT infrastructure (physical machines, devices, operating systems, databases, and any other systems used to run a software application) as software:
- The whole IT environment can be set up, configured, and changed automatically through writing code.
- An IaC model **generates the same environment every time** it is applied, ensuring consistency and reproducibility.
- IaC enables DevOps teams to **test applications in production-like environments early** in the development cycle, reducing deployment risk.
- IaC is considered a **prerequisite for common DevOps practices** including CI/CD.

### CI/CD with GitLab

GitLab provides an integrated platform for implementing CI/CD pipelines. It offers built-in CI/CD capabilities that allow teams to define pipeline configurations (typically in a ''.gitlab-ci.yml''  file), automate builds, run tests, and deploy applications -- all within the same platform used for version control. GitLab provides CI/CD examples for different types of applications written in various programming languages.

### CMMI -- Capability Maturity Model Integration

CMMI is a proven industry framework for improving product quality and development efficiency for both hardware and software:
- **Sponsored by** the US Department of Defense in cooperation with Carnegie Mellon University and the Software Engineering Institute (SEI).
- Many major companies (e.g., Ericsson) have been involved in its definition.
- CMMI has been established as a model to **improve business results**.
- It uses **5 maturity levels** to describe the maturity of an organization, with emphasis on business needs, integration, and institutionalization.

### Process Types

The lecture distinguishes three types of organizational processes:

**Ad Hoc Processes**
- Process descriptions are not carefully followed or enforced.
- Can be very different from person to person.
- Understanding of the current status of a project is limited.
- Performance is highly dependent on current participants.
- Example: Extreme Programming (XP) can exhibit ad hoc characteristics.

**Improved Processes**
- Process descriptions are consistent with the way work is actually done.
- Processes are supported visibly by management and others.
- They are well controlled -- process fidelity is evaluated and enforced.
- There is constructive use of product and process measurement.

**Institutionalized Processes**
- The organization builds an infrastructure that contains effective, usable, and consistently applied processes.
- The organizational culture conveys the process.
- Management fosters the culture.
- Culture is conveyed through role models and recognition.

### CMMI 5 Maturity Levels

| Level | Name | Description |
|-------|------|-------------|
| **Level 1** | **Initial** | Processes are uncontrolled, unpredictable, and reactive. Success depends on individual heroics rather than proven processes. The organization typically operates in an ad hoc manner. |
| **Level 2** | **Managed** | Focus on **product management**. Basic project management processes are established. Projects are planned, performed, measured, and controlled. Processes may still differ between projects. |
| **Level 3** | **Defined** | Focus on **process management**. Processes are well characterized, understood, and described in standards, procedures, tools, and methods. A standard process exists for the organization, and projects tailor it to their needs. |
| **Level 4** | **Quantitatively Managed** | Focus on **quality management**. The organization and projects establish quantitative objectives for quality and process performance. Quantitative data is used to understand and control processes. |
| **Level 5** | **Optimizing** | Focus on **process improvement strategies**. The organization continually improves its processes based on a quantitative understanding of variation and common causes of issues. Innovation and continuous improvement are embedded in organizational culture. |

## Definitions

| Term | Definition |
|------|------------|
| Integration | The process of combining independently developed software components into a unified, working system. |
| Stub | A placeholder implementation of a lower-level module used in top-down integration testing. |
| Test Driver | A program that calls and exercises lower-level modules during bottom-up integration testing. |
| Continuous Integration (CI) | A development practice where developers integrate code into a shared repository several times a day, with each integration verified by automated builds and tests. |
| Private Build | A build run by a developer on their local workstation before committing to the shared repository. |
| Integration Build | A build run on a dedicated build server triggered by commits to the shared repository. |
| Release Build | A specially tagged build intended for deployment to staging or production environments. |
| Continuous Delivery (CD) | An extension of CI where code is automatically built and tested in staging environments that mirror production, with manual approval required for production deployment. |
| Continuous Deployment | An extension of Continuous Delivery where code is automatically deployed to production after passing all automated tests, with no manual intervention. |
| Staging Environment | An environment that closely mirrors production, used in Continuous Delivery to test non-functional requirements such as security, redundancy, and flexibility. |
| Infrastructure as Code (IaC) | The practice of managing and provisioning IT infrastructure through machine-readable code rather than manual configuration, ensuring consistent and reproducible environments. |
| CMMI | Capability Maturity Model Integration -- a process improvement framework sponsored by the US DoD and Carnegie Mellon/SEI that uses 5 maturity levels to describe organizational process maturity. |
| Ad Hoc Process | A process that is not formally defined or enforced, varying from person to person and dependent on individual participants. |
| Institutionalized Process | A process embedded in organizational infrastructure and culture, consistently applied and supported by management. |
| Maturity Level | A well-defined evolutionary plateau in CMMI toward achieving a mature software process, ranging from Level 1 (Initial) to Level 5 (Optimizing). |
