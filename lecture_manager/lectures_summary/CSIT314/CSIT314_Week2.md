# CSIT314 — Week 2: Process Modelling

> **Source files:** CSIT314_Week2.pptx
> **Date summarized:** 2026-02-24

## Overview
This lecture introduces the concept of software processes and process modelling, covering the major generic software process models (Waterfall, Evolutionary Development, Component-based/Reuse-oriented), the core software development activities (Specification, Design & Implementation, Validation, Evolution), and strategies for coping with change. It also covers process iteration approaches (plan-driven vs. agile), incremental delivery, prototyping, and process improvement including the Capability Maturity Model. This foundational knowledge is essential for understanding how software projects are organized, managed, and improved throughout their lifecycle.

## Key Concepts

### Software Process
- A **software process** is a structured set of activities/steps carried out in a particular order to produce software as the end result.
- Software processes deal with both **technical and management issues**.
- Multiple processes may exist for software development; a specific project follows a particular process.
- A **software process model** is an abstract representation of a process, presenting a description from some particular perspective.

### Software Process Descriptions
- Process descriptions cover the **activities** (e.g., specifying a data model, designing a user interface) and their **ordering**.
- Process descriptions may also include:
  - **Products**: the outcomes of a process activity
  - **Roles**: the responsibilities of the people involved in the process
  - **Pre- and post-conditions**: statements that are true before and after a process activity has been enacted or a product produced

### Generic Software Process Models

#### Waterfall Model
- A **linear, sequential** model where each phase must be completed before the next begins.
- **Phases:**
  1. Requirements analysis and definition
  2. System and software design
  3. Implementation and unit testing
  4. Integration and system testing
  5. Operation and maintenance
- **Main drawback:** Difficulty of accommodating changes after the process is underway. One phase must be completed before moving to the next.
- **Problems:**
  - Inflexible partitioning into distinct stages makes it difficult to respond to changing customer requirements
  - Only appropriate when requirements are well-understood and changes will be fairly limited
  - Few business systems have truly stable requirements
- **Best suited for:** Large systems engineering projects where a system is developed at several sites

#### Evolutionary Development
- **Two approaches:**
  - **Exploratory development:** The objective is to work with customers and evolve a final system from an initial outline specification. Should start with well-understood requirements and add new features as proposed by the customer.
  - **Throw-away prototyping:** The objective is to understand the system requirements. Should start with poorly understood requirements to clarify what is really needed.
- **Problems:**
  - Lack of process visibility
  - Systems might get poorly structured
  - Special skills (e.g., in languages for rapid prototyping) may be required
- **Applicability:**
  - Small or medium-size interactive systems
  - Parts of large systems (e.g., the user interface)
  - Short-lifetime systems

#### Component-based Software Engineering (Reuse-oriented Development)
- Based on **systematic reuse** where systems are integrated from existing components or **COTS (Commercial-off-the-shelf)** systems.
- **Process stages:**
  1. Component analysis
  2. Requirements modification
  3. System design with reuse
  4. Development and integration
- This approach is becoming increasingly used as component standards have emerged.

### Software Activities

#### Software Specification
- The process of establishing what **services are required** and the **constraints** on the system’s operation and development.
- **Requirements engineering** is a critical stage that feeds into the software process.
- The requirements engineering process involves elicitation, analysis, specification, and validation of requirements.

#### Software Design and Implementation
- **Design** is the process of converting the system specification into an executable system.
- **Software design:** Design a software structure that realises the specification.
- **Implementation:** Translate this structure into an executable program.
- The activities of design and implementation are closely related and may be **inter-leaved**.
#### Design Process Activities
- The software design process involves multiple design activities that take inputs and produce specific outputs:
  - **Inputs:** Platform information, Requirements specification, Data descriptions
  - **Design Activities (sequential flow):**
    1. **Architectural design** -> System architecture
    2. **Abstract specification** -> Software specification
    3. **Interface design** -> Interface specification
    4. **Component design** -> Component specification
    5. **Data structure design** -> Data structure specification
    6. **Algorithm design** -> Algorithm specification
- The general principle is **“Big to Small”** decomposition: starting from the overall system architecture and progressively refining down to detailed algorithm specifications.

#### Structured Methods
- Systematic approaches to developing a software design.
- The design is usually documented as a set of **graphical models**.
- **Possible models:**
  - **Object model** — represents system objects and their relationships
  - **Sequence model** — represents interactions between objects over time
  - **State transition model** — represents system states and transitions between them
  - **Structural model** — represents the static structure of the system
  - **Data-flow model** — represents how data flows through the system

#### Software Validation (Verification and Validation)
- **V & V** is intended to show that a system:
  - Conforms to its specification (verification: “Are we building the product right?”)
  - Meets the requirements of the system customer (validation: “Are we building the right product?”)
- Involves **checking and review processes** and **system testing**.
- System testing involves executing the system with **test cases derived from the specification** of the real data to be processed.

#### Testing Stages
1. **Component (Unit) testing:** Individual components are tested independently. Components may be functions, objects, or coherent groupings of these entities.
2. **System testing:** Testing of the system as a whole. Testing of **emergent properties** is particularly important.
3. **Acceptance testing:** Testing with **customer data** to check that the system meets the customer’s needs.

#### The V-Model of Testing
- The V-model shows the correspondence between **development stages** and **testing stages**:
  - Requirements specification <-> Acceptance test
  - System design <-> System test (System integration test plan)
  - Detailed design <-> Integration test (Sub-system integration test plan)
  - Code <-> Unit test
- Test plans are the **link** between testing and development activities.
- The V-model shows the software validation activities that correspond to each stage of the waterfall process model (“turn it on its side to see the V”).

#### The Debugging Process
- **Debugging** is the process of finding and fixing a bug in the software.
- It is a distinct activity from testing: testing identifies failures, while debugging locates and corrects the underlying faults.

#### Software Evolution
- Software is **inherently flexible** and can change.
- As requirements change through changing business circumstances, the software that supports the business must also evolve and change.
- The traditional demarcation between development and evolution (maintenance) is **increasingly irrelevant** as fewer and fewer systems are completely new.
- System evolution follows a cycle: Define system requirements -> Assess existing systems -> Propose system changes -> Modify systems -> (repeat), with the existing system feeding back into the process.

### Process Iteration

#### Plan-driven vs. Agile Processes
- **Plan-driven processes:** All process activities are planned in advance and progress is measured against this plan.
- **Agile processes:** Planning is incremental and it is easier to change the process to reflect changing customer requirements.
- In practice, most practical processes include **elements of both** plan-driven and agile approaches.
- There are **no right or wrong** software processes — the choice depends on context.

#### Incremental Delivery
- Rather than delivering the system as a single delivery, development and delivery is **broken down into increments**, each delivering part of the required functionality.
- **User requirements are prioritised** and the highest priority requirements are included in early increments.
- Once development of an increment is started, **requirements are frozen** for that increment, though requirements for later increments can continue to evolve.
- Each build follows: Specifications -> Design -> Implementation & Integration -> Deliver to user (Build 1 through Build n).

### Coping with Change
- Change is **inevitable** in all large software projects.
- **Causes of change:**
  - Business changes lead to new and changed system requirements
  - New technologies open new possibilities for improving implementations
  - Changing platforms require application changes
- Change leads to **rework**, so the costs of change include both rework (e.g., re-analysing requirements) and the costs of implementing new functionality.

#### Two Strategies for Reducing the Costs of Rework
1. **Change anticipation:** The software process includes activities that can **anticipate possible changes** before significant rework is required. For example, developing a prototype system to show key features to customers.
2. **Change tolerance:** The process is designed so that changes can be **accommodated at relatively low cost**. This normally involves some form of incremental development. Proposed changes may be implemented in increments not yet developed; if impossible, only a single increment (a small part of the system) may need to be altered.

#### Coping with Changing Requirements — Two Approaches
1. **System prototyping:** A version of the system (or part of it) is developed quickly to check the customer’s requirements and the feasibility of design decisions. This supports **change anticipation**.
2. **Incremental delivery:** System increments are delivered to the customer for comment and experimentation. This supports **both change avoidance and change tolerance**.
### Prototyping

#### Benefits of Prototyping
- Helps clarify requirements and reduce misunderstandings between developers and customers
- Allows early validation of design decisions and feasibility
- Provides a tangible artifact for customer feedback

#### The Prototype Development Process
- The process involves establishing objectives, defining functionality, developing the prototype, and evaluating the prototype.
- May be based on **rapid prototyping languages or tools**.
- May involve **leaving out functionality**:
  - Should focus on areas of the product that are **not well-understood**
  - Error checking and recovery may not be included
  - Focus on **functional rather than non-functional requirements** (e.g., reliability and security may be omitted)

#### Throw-away Prototypes
- Prototypes should be **discarded after development** as they are not a good basis for a production system because:
  - It may be **impossible to tune** the system to meet non-functional requirements
  - Prototypes are normally **undocumented**
  - The prototype structure is usually **degraded through rapid change**
  - The prototype probably will **not meet normal organisational quality standards**

### Process Improvement
- Many software companies have turned to software process improvement to **enhance quality**, **reduce costs**, or **accelerate development**.
- Process improvement means understanding existing processes and changing them to increase product quality and/or reduce costs and development time.

#### Two Approaches to Improvement
1. **Process maturity approach:** Focuses on improving process and project management and introducing good software engineering practice. The level of process maturity reflects the extent to which good technical and management practice has been adopted.
2. **Agile approach:** Focuses on iterative development and the reduction of overheads in the software process. Primary characteristics are rapid delivery of functionality and responsiveness to changing customer requirements.

#### The Process Improvement Cycle
- A three-stage cyclical process:
  1. **Measure** — collect quantitative process data
  2. **Analyse** — assess current process and identify bottlenecks/weaknesses
  3. **Change** — implement process changes to address identified issues
- Then repeat the cycle.

#### Process Measurement
- Wherever possible, **quantitative process data** should be collected.
- Where organisations do not have clearly defined process standards, measurement is difficult because you do not know what to measure.
- A process may have to be **defined before any measurement** is possible.
- Process measurements should be used to **assess process improvements**, but measurements should NOT drive the improvements — the **organizational objectives** should be the improvement driver.

#### Capability Maturity Levels
The Capability Maturity Model (CMM) defines five levels of process maturity:
1. **Level 1 — Initial:** Essentially uncontrolled. Processes are ad hoc and chaotic.
2. **Level 2 — Repeatable:** Product management procedures defined and used.
3. **Level 3 — Defined:** Process management procedures and strategies defined and used.
4. **Level 4 — Managed:** Quality management strategies defined and used.
5. **Level 5 — Optimizing:** Process improvement strategies defined and used.

## Definitions
| Term | Definition |
| ------ | ------------ |
| Software Process | A structured set of activities carried out in a particular order to produce software |
| Software Process Model | An abstract representation of a process, describing it from some particular perspective |
| Waterfall Model | A linear sequential development model where each phase must complete before the next begins |
| Evolutionary Development | A process model where an initial system is developed quickly from abstract specifications, then refined with customer input |
| Exploratory Development | A type of evolutionary development starting with well-understood requirements and adding features based on customer proposals |
| Throw-away Prototyping | A type of evolutionary development starting with poorly understood requirements to clarify what is needed; the prototype is discarded afterward |
| COTS | Commercial Off-The-Shelf — pre-built software components available for purchase and integration |
| Component-based Software Engineering | A development approach based on systematic reuse of existing components or COTS systems |
| Requirements Engineering | The process of establishing what services are required and the constraints on the system’s operation and development |
| Verification | Ensuring the software conforms to its specification (“Are we building the product right?”) |
| Validation | Ensuring the software meets the customer’s requirements (“Are we building the right product?”) |
| V-Model | A testing framework showing correspondence between development stages and testing stages |
| Unit Testing | Testing of individual components (functions, objects, or groupings) independently |
| System Testing | Testing of the system as a whole, particularly emergent properties |
| Acceptance Testing | Testing with customer data to verify the system meets the customer’s needs |
| Debugging | The process of locating and fixing bugs in software |
| Plan-driven Process | A process where all activities are planned in advance and progress is measured against this plan |
| Agile Process | A process where planning is incremental and easily changed to reflect evolving customer requirements |
| Incremental Delivery | Delivering software in increments, each providing part of the required functionality |
| Change Anticipation | Including process activities that anticipate possible changes before significant rework is required |
| Change Tolerance | Designing a process so changes can be accommodated at relatively low cost |
| Process Maturity | The extent to which good technical and management practice has been adopted in software development |
| Capability Maturity Model | A framework defining five levels of organizational process maturity from uncontrolled to optimizing |
| Emergent Properties | System properties that only manifest when components are integrated and tested together |

## Diagrams & Visual Descriptions

### Software Design Process Diagram
A flow diagram showing the complete design process with inputs, activities, and outputs:
```
INPUTS                    DESIGN ACTIVITIES              OUTPUTS
+-----------------+      +------------------------+     +---------------------------+
| Platform info   |----->| Architectural design   |---->| System architecture       |
| Requirements    |----->| Abstract specification |---->| Software specification    |
|   specification |----->| Interface design       |---->| Interface specification   |
| Data            |----->| Component design       |---->| Component specification   |
|   descriptions  |----->| Data structure design  |---->| Data structure spec.      |
|                 |----->| Algorithm design        |---->| Algorithm specification   |
+-----------------+      +------------------------+     +---------------------------+
```
The activities flow sequentially from top to bottom, following a “Big to Small” decomposition principle — starting with the broadest architectural concerns and progressively refining down to specific algorithm details.

### Design Activities Sequential Flow
```
Requirements       Architectural      Abstract         Interface       Component       Data Structure     Algorithm
Specification  -->   Design      -->  Specification --> Design     --> Design      -->   Design       --> Design
```

### Waterfall Model
A linear cascade of phases, each flowing into the next (with feedback only to the immediately preceding phase):
```
+-----------------------------------+
| Requirements analysis & definition|
+-----------------------------------+
          |
          v
+-----------------------------------+
| System and software design        |
+-----------------------------------+
          |
          v
+-----------------------------------+
| Implementation and unit testing   |
+-----------------------------------+
          |
          v
+-----------------------------------+
| Integration and system testing    |
+-----------------------------------+
          |
          v
+-----------------------------------+
| Operation and maintenance         |
+-----------------------------------+
```
### Evolutionary Development Diagram
A cyclical diagram showing the iterative nature of evolutionary development:
```
    +-------------------+
    | Outline           |
    | description       |
    +--------+----------+
             |
             v
    +-------------------+        +-------------------+
    | Specification     |<------>| Development       |
    +-------------------+        +-------------------+
             ^                          |
             |                          v
             |                  +-------------------+
             +------------------| Validation        |
                                +-------------------+
                                        |
                                        v
                                +-------------------+
                                | Final version     |
                                +-------------------+
    (Concurrent activities with feedback loops between specification,
     development, and validation running simultaneously)
```

### Reuse-oriented Development Flow
```
Requirements --> Component --> Requirements --> System design --> Development --> System
specification   analysis     modification    with reuse       & integration   validation
```

### V-Model Testing Diagram
The V-model shows the relationship between development phases (left descending arm) and testing phases (right ascending arm):
```
Requirements               Acceptance
specification \             / test
               \           /
    System      \         /  System
    design       \       /   integration
                  \     /    test
    Detailed       \   /   Sub-system
    design          \ /    integration test
                     |
                   Code &
                   Unit test

    [Service]     [Test plans]    [Test plans]     [Service]
    acceptance    system          sub-system        acceptance
    test plan     integration     integration       test plan
                  test plan       test plan
```
The left side flows downward through development stages; the right side flows upward through corresponding test stages. Test plans created during each development phase are used during the corresponding test phase.

### Incremental Development Diagram
```
Build 1: Specifications --> Design --> Implementation & Integration --> Deliver to user
Build 2: Specifications --> Design --> Implementation & Integration --> Deliver to user
Build 3: Specifications --> Design --> Implementation & Integration --> Deliver to user
  ...
Build n: Specifications --> Design --> Implementation & Integration --> Deliver to user
```
Each build is a self-contained mini-lifecycle delivering a subset of functionality.

### System Evolution Diagram
```
+-------------------+     +--------------------+     +-------------------+
| Define system     |---->| Assess existing    |---->| Propose system    |
| requirements      |     | systems            |     | changes           |
+-------------------+     +--------------------+     +-------------------+
        ^                                                     |
        |                                                     v
        |                                             +-------------------+
        +---------------------------------------------| Modify systems    |
                                                      +-------------------+
                    Existing
                    systems (feedback)
```

### Process Improvement Cycle
```
        +----------+
        | Measure  |
        +----+-----+
             |
             v
        +----------+
        | Analyse  |
        +----+-----+
             |
             v
        +----------+
        | Change   |
        +----+-----+
             |
             +-------> (back to Measure)
```

### Capability Maturity Levels Diagram
```
Level 5: Optimizing     | Process improvement strategies defined and used
Level 4: Managed        | Quality management strategies defined and used
Level 3: Defined        | Process management procedures and strategies defined and used
Level 2: Repeatable     | Product management procedures defined and used
Level 1: Initial        | Essentially uncontrolled
```
Each level builds upon the one below it, representing increasing organizational maturity in software development processes.

## Code Examples
No code examples were included in this lecture. The content is focused on software engineering processes and models rather than programming.

## Formulas & Algorithms
No specific mathematical formulas or algorithms were presented in this lecture. However, the following process-related frameworks were covered:

- **Process Improvement Cycle:** Measure -> Analyse -> Change -> (repeat)
- **Prototype Development Process:** Establish objectives -> Define functionality -> Develop prototype -> Evaluate prototype
- **Requirements Engineering Process:** Elicitation -> Analysis -> Specification -> Validation

## Key Takeaways
- A **software process** is a structured set of activities that produces software; process models are abstract representations of these activities.
- The three major generic process models are **Waterfall** (linear, rigid), **Evolutionary Development** (iterative, flexible), and **Component-based/Reuse-oriented** (leverages existing components).
- The **Waterfall model** is only suitable when requirements are stable and well-understood; its rigidity is its biggest weakness.
- **Evolutionary development** works well for small/medium systems but can lead to poor structure and lack of visibility.
- Software development involves four fundamental activities: **Specification**, **Design & Implementation**, **Validation**, and **Evolution**.
- The **V-model** maps each development phase to a corresponding testing phase, emphasizing that test planning should happen alongside development.
- **Three testing stages** exist: Unit/Component testing, System testing, and Acceptance testing — each with distinct scope and purpose.
- **Plan-driven and agile** processes are not mutually exclusive; most real projects combine elements of both.
- **Incremental delivery** prioritises requirements and freezes them per increment, allowing later requirements to evolve.
- Change is inevitable; the two strategies for coping are **change anticipation** (e.g., prototyping) and **change tolerance** (e.g., incremental delivery).
- **Throw-away prototypes** must be discarded — they are undocumented, poorly structured, and cannot meet non-functional requirements.
- **Process improvement** can follow a maturity approach (CMM levels 1-5) or an agile approach; the improvement cycle is Measure -> Analyse -> Change.
- Organisational objectives (not raw metrics) should **drive process improvement**.

## Connections
- This lecture builds on Week 1’s introduction to software engineering by diving deeper into **how** software is developed through structured processes.
- The process models introduced here (Waterfall, Evolutionary, Incremental) will be expanded upon in subsequent weeks, particularly when covering the **Rational Unified Process (RUP)** and **Agile methodologies** (as previewed at the end of this lecture).
- The **V-model** and testing stages connect directly to software quality assurance and testing topics covered later in the course.
- The **Capability Maturity Model** relates to broader software project management and organizational maturity topics.
- Understanding these process models is foundational for topics like **requirements engineering**, **software architecture**, and **project management** that appear throughout the CSIT314 curriculum.
- The tension between plan-driven and agile approaches introduced here sets the stage for detailed coverage of **Agile/Scrum methodologies** in later weeks.
