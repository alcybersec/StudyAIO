# CSIT314 — Week 4: Requirements Engineering and Advanced UML (Part 1)

> **Source files:** CSIT314_Week4.pptx
> **Date summarized:** 2026-02-24

## Overview
This lecture covers the requirements engineering process — from feasibility studies through elicitation, specification, validation, and management — and introduces UML use case diagrams and activity diagrams. It bridges the software process models (Week 3) with architectural design (Week 5) by establishing how to capture, document, and validate what a system must do before designing how it does it.

## Key Concepts

### Requirements Engineering Processes
- Processes vary widely depending on application domain, people involved, and organization
- Generic activities common to all: feasibility studies, elicitation, specification, negotiation/validation, management

### Feasibility Studies
- Decides whether the proposed system is worthwhile
- A short, focused study checking:
  - Does the system contribute to organizational objectives?
  - Can it be engineered using current technology and within budget?
  - Can it be integrated with existing systems?
- Based on information assessment, collection, and report writing
- Key questions: What if system wasn't implemented? What are current problems? How will the system help? Integration problems? New technology needed?

### Types of Requirements
- **User requirements:** Statements in natural language + diagrams of services and constraints (written for customers)
- **System requirements:** Structured document with detailed descriptions of functions, services, and constraints (defines what should be implemented; may be part of contract)

### FURPS+ Requirements Categories
| Category | Type | Examples |
|----------|------|----------|
| **Functional (F)** | Functions | Business rules and processes |
| **Usability (U)** | Non-functional | User interface, ease of use |
| **Reliability (R)** | Non-functional | Failure rate, recovery methods |
| **Performance (P)** | Non-functional | Response time, throughput |
| **Security (S)** | Non-functional | Access controls, encryption |
| **Design constraints (+)** | Non-functional | Hardware/software adherence |
| **Implementation (+)** | Non-functional | Programming languages, tools, documentation |
| **Interface (+)** | Non-functional | Interactions among systems |
| **Physical (+)** | Non-functional | Size, weight, power consumption |
| **Supportability (+)** | Non-functional | Installation, configuration, monitoring, updates |

### Form-Based Requirements Description
| Field | Purpose |
|-------|---------|
| Function | Short name reflecting what it does |
| Description | What it does in 1-2 sentences |
| Inputs | Input to the requirement |
| Source | Where the input comes from |
| Outputs | What is the output |
| Destination | Which module is concerned |
| Action | Detailed description of what this requirement does |
| Requires | What is required |
| Pre-condition | What must be satisfied before |
| Post-condition | What happens at the end |
| Side effects | Does this affect something else |

**Example — Insulin Pump:** Compute insulin dose when sugar level is in safe zone (3-7 units). CompDose is zero if sugar stable/falling or rate of increase decreasing. If increasing and rate increasing, CompDose = (current - previous) / 4, rounded.

### Requirements Elicitation
- Also called requirements discovery
- Technical staff work with customers to understand: application domain, required services, operational constraints
- Involves end-users, managers, engineers, domain experts, etc. (stakeholders)

#### Traditional Methods (simple, cost-effective, clear objectives)
- Interviewing customers and domain experts
- Questionnaires
- Observation
- Study of documents and software systems

#### Modern Methods (better insights, higher cost, high project risks)
- Prototyping
- Brainstorming
- Joint Application Development (JAD)
- Rapid Application Development (RAD)

#### Viewpoints
- Structure requirements to represent perspectives of different stakeholders
- Multi-perspective analysis is important — no single correct way
- Identification methods provided

#### Problems of Requirements Analysis
- Stakeholders don't know what they really want
- Requirements expressed in stakeholder's own terms
- Different stakeholders may have conflicting requirements
- Organizational and political factors influence requirements
- Requirements change during analysis; new stakeholders emerge

### Requirements Specification
- Writing down user and system requirements in a requirements document
- User requirements must be understandable by non-technical customers
- System requirements are more detailed/technical
- May be part of a contract

#### Ways of Writing System Requirements
| Method | Description |
|--------|-------------|
| Natural language | Free-form text; flexible but ambiguous |
| Structured natural language | Standardized templates; reduces ambiguity |
| Design description language | Programming-like notation |
| Graphical notations | UML diagrams |
| Mathematical specifications | Formal, precise; difficult to understand |

#### Problems with Natural Language
- Requirements may mix conceptual and detailed information
- Ambiguity, lack of precision

### Requirements Negotiation and Validation
- Needed because requirements overlap, conflict, may be ambiguous/unrealistic, undiscovered, or out of scope
- Often done in parallel with elicitation
- Starts from draft requirement document; validation reviews and stamps it
- **Requirements checking** and **validation techniques** applied

### Requirements Management
- **Identification and classification:** unique identifiers (auto-generated, sequential with hierarchy or category)
- **Requirements hierarchies:** parent-child relationships reflecting abstraction levels
- **Change management:** requirements will change; strong policies needed for documenting changes, assessing impact, effecting changes
- **Traceability:** critically important for change management; suspect traces after changes

### Requirements Document
- Structured document capturing all requirements formally

### UML Use Cases
- Encodes a typical user interaction with the system
- Captures user-visible functions achieving concrete goals
- Maps **actors** to **functions**
- A complete set of use cases largely defines system requirements
- Granularity determines number of use cases

#### Actors
- A role or external system (not necessarily human)
- Single actor can represent multiple users; single user can play multiple roles
- Examples: Trading manager, Trader, Accounting System

#### Extends Relationship
- Used when a use case is similar to another but does a bit more
- "This use case is similar to that use case with the exception of..."
- Capture simple/normal use case first, then ask "what could go wrong?" for each step

#### Uses (Include) Relationship
- Used when a chunk of behavior is similar across several use cases
- Eliminates redundancy and inconsistency
- From actor's viewpoint: extends = both normal and extension performed; uses = often no actor for common case

#### Weather Station Use Case Example
- Actors: Weather Station, Weather Information System, Control System
- Use cases: Report Weather, Report Status, Restart, Shutdown, Reconfigure, Powersave

### Activity Diagrams
- Model the workflow behind the system being designed
- Useful for: analyzing use cases, describing sequential algorithms, modeling parallel processes
- **Elements:** Activity, Transition, Decision
- **Synchronization bars:** Fork (split into parallel paths), Join (combine paths)
- **Swimlanes:** Partition diagram by responsible actor/component

#### Examples
- **Register Course:** Fill form → Select course → Submit to registrar → [approve?] → Yes: Register course / No: loop back
- **ATM Authorization:** Enter card → Read card → Request PIN → Enter PIN → Verify PIN → [valid?] → Yes: Select service / No: loop back

## Definitions
| Term | Definition |
|------|------------|
| Requirements Engineering | Process of establishing required services and constraints on system operation |
| Feasibility Study | Short study to determine if a proposed system is worthwhile |
| User Requirements | Natural language statements of services and constraints for customers |
| System Requirements | Detailed structured descriptions of system functions and constraints |
| Stakeholder | Person or organization affected by the system directly or indirectly |
| Elicitation | Process of discovering requirements from stakeholders |
| Viewpoint | Way of structuring requirements to represent stakeholder perspectives |
| Use Case | Encodes a typical user interaction achieving a concrete goal |
| Actor | Role or external system that interacts with the system |
| Extends | Use case relationship for variations on normal behavior |
| Uses/Include | Use case relationship for shared behavior across use cases |
| Activity Diagram | UML diagram modeling workflow with activities, transitions, decisions |
| Swimlane | Partition in activity diagram grouping activities by responsible entity |
| FURPS+ | Requirements categorization: Functional, Usability, Reliability, Performance, Security + constraints |
| Traceability | Ability to trace requirements through design, implementation, and testing |

## Diagrams & Visual Descriptions

### Weather Station Use Case Diagram
```
                    +---------------------------+
                    |    Weather Station System  |
    [Weather        |                           |
     Station]------>| (Report Weather)          |
                    | (Report Status)           |
    [Weather Info   |                           |
     System]------->| (Restart)                 |
                    | (Shutdown)                |
    [Control        | (Reconfigure)             |
     System]------->| (Powersave)               |
                    +---------------------------+
```

### Activity Diagram — Register Course
```
    (Start)
       |
    [Fill form]
       |
    [Select course]
       |
    [Submit to registrar]
       |
    <approve?>
    /        \
  [No]      [Yes]
   |          |
(loop)    [Register course]
              |
           (End)
```

### Activity Diagram with Swimlanes
Swimlanes partition activities by responsible actor, showing which entity performs which activities in the workflow.

## Code Examples
No explicit code examples in this lecture.

## Formulas & Algorithms
No formulas in this lecture.

## Key Takeaways
- Requirements engineering is a critical process that spans feasibility, elicitation, specification, validation, and management
- Use FURPS+ to categorize requirements comprehensively (functional + non-functional + constraints)
- Form-based requirements descriptions provide structured, unambiguous documentation
- Multiple elicitation methods exist — choose based on project risk and complexity
- Requirements will always change — plan for change management and traceability
- Use cases map actors to system functions and largely define system requirements
- Extends adds variation to normal use cases; Uses/Include factors out common behavior
- Activity diagrams model workflows with parallel paths (fork/join) and decision points
- Swimlanes clarify which actor/component is responsible for each activity

## Connections
- **Week 1:** Requirements engineering applies SE principles of rigor, separation of concerns, and anticipation of change
- **Week 2:** Process models define when requirements engineering occurs in the SDLC
- **Week 3:** Agile methods (XP user stories, Scrum product backlog) provide alternative requirements approaches
- **Week 5:** Requirements drive architectural design decisions
- **Week 6:** Use cases are refined into class diagrams, sequence diagrams, and state diagrams
- **Week 8:** Test cases are derived from use cases and requirements specifications
