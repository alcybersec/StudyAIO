# CSIT314 — Week 3: Development Methods — Agile, XP, RUP, and Scrum

> **Source files:** CSIT314_Week3.pptx, CSIT314_Week3_v2.pptx, CSIT314_Week3_v3.pptx, CSIT314_Week3_v4.pptx, CSIT314_Week3_v5.pptx
> **Date summarized:** 2026-02-24

## Overview
This lecture covers agile software development methodologies in depth, including the Agile Manifesto and its principles, three major agile/iterative frameworks (Extreme Programming, Rational Unified Process, and Scrum), and the practical challenges of scaling agile methods to large systems. It bridges Week 2's process models with Week 4's requirements engineering by establishing how modern iterative and incremental approaches handle changing requirements, team collaboration, and continuous delivery.

## Key Concepts

### Agile Software Development
- **Definition:** Agile = "able to move quickly and easily"; a method of project management characterized by division of tasks into short phases with frequent reassessment and adaptation
- Rapid development and delivery is now often the most important requirement for software systems
- Businesses operate in fast-changing environments where stable requirements are practically impossible
- Plan-driven development is essential for some types of system but does not meet these business needs
- Over 60% of product or project requirements change during development

### Agile Manifesto — Four Core Values
The Agile Manifesto (agilemanifesto.org) establishes four values, each prioritizing the left side over the right:

| Value | Prioritized | Over |
|-------|------------|------|
| **1** | Individuals and interactions | Process and tools |
| **2** | Working software | Comprehensive documentation |
| **3** | Customer collaboration | Contract negotiation |
| **4** | Responding to change | Following a plan |

**Value 1 — Individuals and interactions:**
- Critical to high-performing teams
- Frequent communication and productive interactions essential
- Inspect-and-adapt cycles: pair programming (every minute), continuous integration (every few hours), stand-up meeting (every day), review and retrospective (every iteration)
- Tools and processes are still important but should fit the team's needs (not the other way around)

**Value 2 — Working software:**
- Documentation is important but working software is even more important
- Delivering small pieces of working software to the customer at regular intervals is essential

**Value 3 — Customer collaboration:**
- Customers should be engaged and collaborate throughout development
- A customer representative should be part of the team
- Ensures the product meets business needs

**Value 4 — Responding to change:**
- Plans and processes must accommodate changes and feedback
- "In order to succeed, we must plan to change"

### Twelve Principles of Agile Methods
1. Highest priority is to satisfy the customer through early and continuous delivery of valuable software
2. Welcome changing requirements, even late in development — harness change for competitive advantage
3. Deliver working software frequently (weeks to months), preferring shorter timescales
4. Business people and developers must work together daily
5. Build projects around motivated individuals — give them environment and support, trust them
6. Face-to-face conversation is the most efficient and effective communication method
7. Working software is the primary measure of progress
8. Promote sustainable development — sponsors, developers, users maintain constant pace indefinitely
9. Continuous attention to technical excellence and good design enhances agility
10. Simplicity — the art of maximizing the amount of work not done — is essential
11. Best architectures, requirements, and designs emerge from self-organizing teams
12. Regular reflection on how to become more effective, then tune and adjust behavior

### Extreme Programming (XP)

#### Overview
- Very influential agile method, developed in late 1990s
- Takes an "extreme" approach to iterative development
- New versions may be built several times per day
- Increments delivered to customers every 2 weeks
- All tests must run for every build; build only accepted if tests pass
- Has a technical focus and is not easy to integrate with management practices in most organizations
- While agile development uses XP practices, the method as originally defined is not widely used

#### XP and Agile Principles
- Incremental development through small, frequent system releases
- Customer involvement = full-time customer engagement with team
- People not process through pair programming, collective ownership, avoiding long working hours
- Change supported through regular system releases
- Maintaining simplicity through constant refactoring

#### Key XP Practices

**User Stories for Requirements:**
- Customer/user is part of the XP team and responsible for requirements decisions
- User requirements expressed as user stories or scenarios
- Written on cards, broken down into implementation tasks
- Tasks are the basis of schedule and cost estimates
- Customer chooses stories for inclusion in next release based on priorities and estimates

**Refactoring:**
- XP maintains that designing for change is not worthwhile since changes cannot be reliably anticipated
- Proposes constant code improvement (refactoring) to make changes easier
- Team looks for possible improvements even when no immediate need
- Improves understandability, reduces documentation need
- Changes easier because code is well-structured and clear
- Architecture refactoring is much more expensive
- Examples: reorganize class hierarchy to remove duplicate code, tidy/rename attributes and methods, replace inline code with library method calls

**Test-First Development (TDD):**
- Testing is central to XP
- Test-first development: write tests before code
- Incremental test development from scenarios
- User involvement in test development and validation
- Automated test harnesses run all component tests for each new release
- Writing tests before code clarifies requirements
- Tests written as programs (not data) for automatic execution
- Usually relies on frameworks such as JUnit
- All previous and new tests run when new functionality added

**Problems with TDD:**
- Programmers prefer programming to testing — may write incomplete tests
- Some tests difficult to write incrementally (e.g., complex UI display logic)
- Difficult to judge completeness of a test set

**Customer Involvement in Testing:**
- Customer helps develop acceptance tests for stories in next release
- Customer writes tests as development proceeds
- Limitations: customers have limited time, may feel requirements were enough contribution

**Test Automation:**
- Tests written as executable components before task implementation
- Simulate input submission and check against output specification
- Automated test framework (e.g., JUnit) makes it easy to write and run test sets
- Problems caught immediately when new functionality added

**Pair Programming:**
- Programmers work in pairs, developing code together
- Develops common ownership and spreads knowledge
- Serves as informal review process (each line seen by 2+ people)
- Encourages refactoring (whole team benefits)
- Pairs sit at same computer, created dynamically
- Reduces project risk when team members leave
- Evidence suggests a pair is more efficient than 2 programmers working separately

**Collective Ownership:**
- Pairs work on all areas of the system
- No islands of expertise; all developers responsible for all code
- Anyone can change anything

**Continuous Integration:**
- As soon as work on a task is complete, integrated into whole system
- All unit tests must pass after integration

**Sustainable Pace:**
- Large amounts of overtime not acceptable
- Net effect of overtime is often reduced code quality and medium-term productivity

**On-Site Customer:**
- A representative of the end-user available full-time
- Customer is a member of the development team
- Responsible for bringing system requirements to the team

### Rational Unified Process (RUP)

#### Overview
- A deliberately flexible model for software development process
- Tailored to the needs of the project: activities (what), roles (who), artifacts (results)
- Core defined using UML notations
- Four phases, multiple activities, iterations
- Shares characteristics with software products: designed with UML, delivered online, regular upgrades, modular and configurable

#### Six RUP Principles
1. **Develop iteratively**
2. **Manage requirements** — always keep customer requirements in mind
3. **Use components** — test individual components and reusability
4. **Model visually** — use UML diagrams for components, users, interactions
5. **Verify quality** — testing is a major part at any point in time
6. **Control changes** — changes must be synchronized and verified constantly (teams may be distributed, multi-platform)

#### RUP Building Blocks
- **Roles (who):** set of related skills, competencies, and responsibilities
- **Work Products (what):** documents and models produced while working through the process
- **Tasks (how):** unit of work assigned to a Role that provides a meaningful result

#### RUP Two Dimensions
- **Horizontal axis:** time — lifecycle aspects as the process unfolds (phases)
- **Vertical axis:** core process workflows — activities grouped logically by nature

#### Life-Cycle Phases
Phases are sequential in nature (similar to waterfall), each focusing on a key objective and milestone delivery.

**1. Inception:**
- *Objectives:* Establish software scope and acceptance criteria, main use-case scenarios, evaluate alternative architectures, estimate cost/schedule/risks, produce business case, create work plan for elaboration
- *Activities:* Formulate project scope, prepare business case, evaluate risk management alternatives, synthesize candidate architecture
- *Outcomes:* Vision document (core requirements, key features, constraints), list of use cases and actors, initial business case (context, success criteria, financial forecast), risk assessment, initial project plan
- *Stakeholders:* Persons or organizations affected directly or indirectly

**2. Elaboration:**
- *Objectives:* Define, validate, and baseline system architecture; baseline vision and construction plan; demonstrate architecture supports vision at reasonable cost/time
- *Activities:* Finalize vision, develop solid understanding of critical use cases, set up development environment/tools/test automation, elaborate system architecture (select COTS components, integrate and assess against primary use cases)
- *Outcomes:* Use-case model (80%+ complete), supplementary requirements (non-functional), software architecture description, executable architectural prototype, revised risk list and business case, development plan, preliminary user manual (optional)
- "Baseline" means create it, make it work, put it under version control

**3. Construction:**
- *Objectives:* Minimize development costs, achieve adequate quality rapidly, achieve useful versions quickly
- *Activities:* Resource management and optimization, complete component development and testing, assess product releases against acceptance criteria
- Each iteration has: list of use-cases, time schedule (time-boxing), leads to a "build"
- Iteration releases are a chance to replan (reduce scope, incorporate feedback)

**4. Transition:**
- Move software product to users when system is mature enough
- Includes: beta testing, parallel operation with existing system, user/maintainer training, rollout to marketing/distribution/sales
- *Evaluation criteria:* Is the user satisfied? Are actual vs planned expenditures acceptable?

#### Iteration Duration Table
| Lines of Code | Number of People | Duration of an Iteration |
|---------------|-----------------|--------------------------|
| 5,000 | 4 | 2 weeks |
| 20,000 | 10 | 1 month |
| 100,000 | 40 | 3 months |
| 1,000,000 | 150 | 6 months |

For small projects (CSIT214): 4 persons, 1-2 week iterations, 2-3 iterations in construction.

#### RUP Workflows and Models
- Inception: Vision, requirements, main use cases, candidate architecture, risks, glossary
- Elaboration: Use-case model, architecture, executable prototype, development plan
- Construction: Component code (individual), integration (team), system testing
- Transition: Beta testing, deployment, training

#### Practical Guide — What to Do in Each Phase
- **Inception:** Talk to users → identify actors and primary use cases → determine requirements → think about architecture → prioritize requirements → complete vision
- **Elaboration:** Pick high-priority/challenging use cases → develop them → identify classes → map to sequence diagrams → build first version → refine → develop construction plan
- **Construction:** Write and test component code → check in to project → integrator builds system → tester performs integration/system tests → regular progress meetings
- **UML diagrams and RUP:** Recommendations from Ivar Jacobson on which diagrams to use, when, and why

### Scrum

#### Overview
- Agile method with three main phases:
  1. **Initial phase:** outline planning, establish general objectives, design software architecture
  2. **Sprint cycles:** each cycle develops an increment of the system
  3. **Project closure:** complete documentation, assess lessons learned
- Rather than doing all of one thing at a time, Scrum teams do a little of everything all the time (overlapping development vs. sequential)

#### Scrum Artifacts

**Product Backlog:**
- List of work to be done on the project
- Comprises: features, bugs, technical work (e.g., "Upgrade workstations"), knowledge acquisition (e.g., "Research JS libraries")
- Prioritized by the product owner
- Reprioritized at the start of each sprint

**Sample Product Backlog:**
| Backlog item | Estimate |
|---|---|
| Allow a guest to make a reservation | 3 |
| As a guest, I want to cancel a reservation | 5 |
| As a guest, I want to change the dates of a reservation | 3 |
| As a hotel employee, I can run RevPAR reports | 8 |
| Improve exception handling | 8 |

**User Stories:**
- Short, simple descriptions of a feature from the user's perspective
- Template: **"As a < type of user >, I want < some goal > so that < some reason >"**
- Examples:
  - "As a site visitor, I can read current news on the home page"
  - "As a trainer, I can create a new course or event..."

**Sprint Backlog:**
- Any team member can add, delete, or change items
- Work emerges during the sprint
- If work is unclear, define a larger item and break it down later
- Update work remaining as more becomes known (burndown chart)

**Sprint Burndown Chart:**
- Visual comparison of work completed vs. total work remaining
- Helps measure team progress
- Shows whether team needs adjustments to complete sprint work

#### Estimation Techniques

**Ideal Days:**
- How long something would take if it's all you worked on, with no interruptions, and everything needed is available
- Analogy: ideal time of a soccer game is 90 minutes, elapsed time is ~2 hours
- Easier to estimate in ideal time than elapsed time

**Story Points:**
- Represent effort to complete a user story
- Influenced by: how hard, how much
- Relative values matter (e.g., login screen = 2, search feature = 8)
- Story point estimation is team-specific

**Estimation by Analogy:**
- Compare to other stories: "This story is like that story"
- Don't use a single gold standard — triangulate (compare to multiple stories)
- Group like-sized stories on table or whiteboard

**Use the Right Units:**
- Can you distinguish 1-point from 2-point? How about 17 from 18?
- Use a set that makes sense — Fibonacci series commonly used: 1, 2, 3, 5, 8, 13, ...

**Planning Poker:**
- Iterative estimation approach
- Steps: each estimator gets a card deck → customer reads a story → brief discussion → each selects a card → cards turned over → discuss differences (especially outliers) → re-estimate until convergence
- Why it works: those who do the work estimate it, estimates must be justified, group discussion improves estimates, relative estimating emphasized, constrained values prevent meaningless arguments, everyone heard, quick and fun

#### Scrum Sprint Cycle
- Fixed length: normally 2-4 weeks
- Starting point: product backlog
- **Selection phase:** team works with customer to select features/functionality for the sprint
- Team organizes themselves to develop the software
- **No changes during a sprint** — plan sprint durations around how long you can commit to keeping change out
- Team isolated from external distractions; communications channeled through Scrum Master
- At end of sprint: work reviewed and presented to stakeholders
- Next sprint cycle then begins

#### Scrum Roles

**Product Owner:**
- Define features of the product
- Decide on release date and content
- Responsible for profitability (ROI)
- Prioritize features according to market value
- Adjust features and priority every iteration
- Accept or reject work results

**Scrum Master:**
- Represents management to the project
- Responsible for enacting Scrum values and practices
- Removes impediments
- Ensures team is fully functional and productive
- Enables close cooperation across all roles and functions

**The Team:**
- Typically 5-9 people
- Cross-functional: programmers, testers, UX designers, etc.
- Self-organizing
- Ideally no titles (rarely possible)
- Membership should change only between sprints

#### Scrum Ceremonies

**Sprint Planning:**
- Determines what to work on during the sprint
- Output: sprint backlog with selected items and plan

**Daily Scrum Meeting:**
- Short daily meeting for coordination
- Each team member addresses: what they did, what they'll do, any impediments

**Sprint Review Meeting:**
- Demonstrate completed work to stakeholders
- Review what was accomplished

**Sprint Retrospective Meeting:**
- Team reflects on the sprint process
- Discusses what went well, what to improve
- Determines actionable improvements for next sprint

### Agile Project Management

#### Scaling Agile Methods
- Agile methods proven successful for small/medium-sized projects with co-located teams
- Success often attributed to improved communication when everyone works together

**Scaling Up:**
- Using agile methods for developing large software systems that cannot be developed by a small team
- Large systems are collections of separate, communicating systems developed by multiple teams (possibly different locations/time zones)
- Significant fraction of development is system configuration rather than original code
- External regulations may constrain development
- Long development time makes it difficult to maintain coherent teams
- Diverse set of stakeholders — impossible to involve all in development

**Scaling Out:**
- Introducing agile methods across a large organization with many years of software development experience

**When scaling, maintain agile fundamentals:** flexible planning, frequent system releases, continuous integration, test-driven development, good team communications

**Scaling Challenges for Large Systems:**
- Completely incremental approach to requirements engineering is impossible
- Cannot have a single product owner or customer representative
- Cannot focus only on code — cross-team communication mechanisms needed
- Continuous integration is practically impossible (but maintain frequent builds and regular releases)

### Practical Problems with Agile Methods

**Contractual Issues:**
- Most custom software contracts are based on specifications
- This precludes interleaving specification and development
- A contract paying for developer time rather than functionality is needed
- Seen as high risk by legal departments — no guaranteed deliverables

**Agile and Maintenance:**
- Most organizations spend more on maintenance than new development
- Key issues: Are agile-developed systems maintainable given minimal formal documentation? Can agile methods effectively evolve a system in response to change requests?
- Key problems: lack of product documentation, keeping customers involved, maintaining development team continuity
- Agile relies on team knowledge — problematic for long-lifetime systems when original developers leave

### Agile vs. Plan-Driven: Decision Factors

**System Issues:**
- System size: agile effective for small co-located teams
- System type: systems requiring lots of analysis need detailed design
- Expected lifetime: long-lifetime systems need documentation
- External regulation: may require detailed documentation for safety cases

**People and Teams:**
- Skill levels: agile may require higher skill than plan-based (no detailed design to translate)
- Team organization: distributed teams may need design documents
- Technology support: IDE support essential if design documentation unavailable

**Organizational Issues:**
- Culture of plan-based development in traditional engineering organizations
- Customer representative availability
- Compatibility of informal agile development with organizational culture

### Lean Software Development Process
- Mentioned as an additional agile approach (covered briefly)
- Focuses on eliminating waste, building quality in, delivering fast, optimizing the whole

## Definitions
| Term | Definition |
|------|------------|
| Agile | Method of project management characterized by short work phases with frequent reassessment and adaptation |
| Agile Manifesto | Declaration of four core values and twelve principles for agile software development |
| Extreme Programming (XP) | Agile method taking an extreme approach to iterative development with practices like TDD, pair programming, and continuous integration |
| Rational Unified Process (RUP) | Deliberately flexible, iterative software development process model with four phases and UML-based artifacts |
| Scrum | Agile framework using fixed-length sprints, defined roles (Product Owner, Scrum Master, Team), and ceremonies for incremental delivery |
| User Story | Short description of a feature from a user's perspective: "As a [user], I want [goal] so that [reason]" |
| Product Backlog | Prioritized list of all work to be done on a Scrum project |
| Sprint Backlog | Set of product backlog items selected for a sprint plus a plan for delivering them |
| Sprint | Fixed-length iteration (typically 2-4 weeks) in Scrum where a potentially releasable increment is created |
| Burndown Chart | Visual chart showing work completed vs. remaining in a sprint |
| Story Points | Unit of measure for expressing effort required to implement a user story, based on relative sizing |
| Ideal Days | Estimation unit representing how long a task would take with no interruptions and all resources available |
| Planning Poker | Consensus-based estimation technique using card decks with Fibonacci-like values |
| Refactoring | Restructuring existing code without changing its external behavior to improve readability and reduce complexity |
| Test-First Development (TDD) | Practice of writing automated tests before writing the code that makes them pass |
| Pair Programming | Practice where two programmers work together at one workstation, reviewing each other's code in real time |
| Collective Ownership | XP practice where any developer can modify any part of the codebase |
| Continuous Integration | Practice of integrating code into a shared repository frequently, with automated tests run on each integration |
| Inception | First RUP phase: establish scope, identify use cases, evaluate architecture, estimate costs and risks |
| Elaboration | Second RUP phase: baseline the architecture, develop critical use cases, set up development environment |
| Construction | Third RUP phase: develop remaining components, integrate, test thoroughly, produce alpha/beta releases |
| Transition | Fourth RUP phase: deploy to users through beta testing, training, and rollout |
| Product Owner | Scrum role responsible for defining features, prioritizing backlog, and accepting/rejecting work |
| Scrum Master | Scrum role responsible for facilitating the process, removing impediments, and shielding the team |
| Scaling Up | Adapting agile methods for large software systems requiring multiple teams |
| Scaling Out | Introducing agile methods across a large organization |
| Time-boxing | Allocating a fixed time period to an activity (e.g., a sprint or iteration) |
| Sustainable Pace | XP principle that teams should not work excessive overtime to maintain code quality |
| COTS | Commercial Off-The-Shelf software — pre-built components selected during RUP elaboration |
| Artifact | Any work product of the software development process (document, model, code) |

## Diagrams & Visual Descriptions

### Agile Manifesto Values Diagram
The lecture uses a visual layout showing each of the four values as paired comparisons, with the left side emphasized and the right side de-emphasized (but not eliminated).

### XP Release Cycle
```
   [User Stories] --> [Release Planning] --> [Iteration Planning]
         ^                                        |
         |                                        v
    [Customer      <-- [Small Releases] <-- [Sprint (2 weeks)]
     Feedback]              ^                     |
                            |                     v
                      [Acceptance        [Pair Programming]
                       Tests]            [TDD] [Refactoring]
                                         [Continuous Integration]
```

### RUP Two-Dimensional View (Hump Chart)
```
Workflows        |  Inception | Elaboration | Construction | Transition
-----------------+------------+-------------+--------------+------------
Business Model   |  ████      |  ██         |              |
Requirements     |  ██████    |  ████████   |  ██          |
Analysis/Design  |     ██     |  ██████████ |  ██████      |  ██
Implementation   |            |  ████       |  ██████████  |  ████
Test             |            |  ██         |  ████████    |  ██████
Deployment       |            |             |  ██          |  ████████
                 |            |             |              |
                 |  Iter #1   | Iter #2 #3  | Iter #4..#n  | Iter #n+1
```
The "hump" shape shows how each workflow's effort peaks at different phases.

### Sequential vs. Overlapping Development (Scrum)
```
Sequential (Waterfall):
  [Requirements] → [Design] → [Code] → [Test]

Overlapping (Scrum):
  [Requirements ======]
     [Design =========]
        [Code ============]
           [Test ============]
```
Scrum teams do a little of everything all the time rather than completing one activity before starting the next.

### Scrum Sprint Cycle
```
  [Product    →  [Sprint     →  [Sprint (2-4 weeks)]  →  [Sprint    →  [Potentially
   Backlog]      Planning]      Daily Scrum meetings       Review]      Shippable
                                Scrum Master shields       Demo work    Increment]
                                No external changes        to stakeholders
                                                                        ↓
                                                                   [Sprint
                                                                    Retrospective]
                                                                        ↓
                                                                   [Next Sprint]
```

### Planning Poker Flow
```
  [Deal cards] → [Read story] → [Discuss] → [Everyone plays card face-down]
       ↑                                            |
       |                                            v
  [Converged?] ←── No ──← [Reveal cards] → [Discuss outliers]
       |
      Yes
       ↓
  [Record estimate]
```

## Code Examples
No explicit code examples in this lecture, though TDD and refactoring are discussed conceptually. The practices would use frameworks like JUnit for test automation.

## Formulas & Algorithms
No mathematical formulas. Estimation uses relative sizing with Fibonacci sequences (1, 2, 3, 5, 8, 13, ...) for story points.

## Key Takeaways
- The Agile Manifesto's four values prioritize people, working software, collaboration, and adaptability — but don't eliminate processes, documentation, contracts, or plans
- The 12 agile principles emphasize early/continuous delivery, welcoming change, face-to-face communication, sustainable pace, simplicity, and self-organizing teams
- **XP** is technically focused: TDD, pair programming, refactoring, continuous integration, collective ownership, and on-site customer are its core practices
- **RUP** provides a structured iterative framework with four phases (Inception → Elaboration → Construction → Transition), each with clear objectives, activities, and outcomes
- RUP's two dimensions (time vs. workflows) show how different activities peak at different phases
- **Scrum** organizes work through roles (Product Owner, Scrum Master, Team), artifacts (product backlog, sprint backlog, burndown chart), and ceremonies (planning, daily scrum, review, retrospective)
- No changes during a sprint — plan sprint duration around how long you can keep change out
- Estimation uses relative sizing (story points with Fibonacci series) and Planning Poker for consensus
- User stories follow the template: "As a [user], I want [goal] so that [reason]"
- Agile methods work best for small co-located teams — scaling up and scaling out introduce significant challenges
- Contractual issues arise because agile precludes specification-based contracts; paying for time rather than functionality is seen as high risk
- Agile maintenance is challenging due to lack of documentation, customer availability, and team continuity
- Most projects use elements of both plan-driven and agile processes — the balance depends on system size, type, lifetime, regulation, team skills, and organizational culture
- RUP iteration duration scales with project size: from 2 weeks (5K LOC, 4 people) to 6 months (1M LOC, 150 people)

## Connections
- **Week 1:** Agile methods embody SE principles of incrementality, anticipation of change, and separation of concerns
- **Week 2:** Agile/iterative models contrast with the waterfall model; RUP combines elements of both plan-driven and incremental approaches; process improvement (CMM) relates to organizational readiness for agile
- **Week 4:** Requirements engineering in agile uses user stories and product backlogs instead of formal specification documents; the challenge of changing requirements motivates agile approaches
- **Week 5:** RUP's architectural focus in the Elaboration phase connects to architectural design; microservices benefit from agile's independent team structure
- **Week 7:** Continuous integration (an XP practice) evolves into CI/CD pipelines
- **Week 8:** TDD from XP directly relates to testing strategies; test automation is foundational to agile
- **Week 9:** DevOps extends agile's "operate what you build" philosophy; Scrum's self-organizing teams align with DevOps culture
