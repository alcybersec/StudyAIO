# CSIT314 — Week 1: Software Engineering Principles

> **Source files:** CSIT314_Week1.pptx
> **Date summarized:** 2026-02-24

## Overview

This lecture introduces the foundational principles of software engineering, establishing why software is fundamentally different from other industrial products and why disciplined engineering practices are essential. It covers the formal definitions of software engineering from IEEE, Fritz Bauer, and Boehm, then systematically explores seven key SE principles — Rigor and Formality, Separation of Concerns, Modularity, Abstraction, Anticipation of Change, Generality, and Incrementality — that form the bedrock of all software development methodologies studied in CSIT314. Understanding these principles is critical because every process model, design pattern, and development methodology covered in later weeks builds directly upon them.

## Key Concepts

### Software Characteristics
Software is fundamentally different from traditional industrial products in five important ways:
- **Invisible:** Software is intangible — you cannot physically see or touch it, unlike hardware components.
- **Does not age:** Software does not degrade physically over time the way hardware does. A program written 20 years ago still runs the same way (though it may become obsolete in other ways).
- **Not deteriorated by use:** Unlike machinery or physical tools that wear out with repeated use, software remains intact regardless of how often it is executed or tested.
- **Easy to modify:** Software can be changed relatively easily compared to physical products, though this ease can also introduce risk if not managed properly.
- **Expensive:** Despite being intangible, software development requires significant investment in skilled labor, tools, and time.
### Software as Product and Process
Software has two complementary dimensions:
- **Product (What is built):** The deliverable artifact — the application, system, or tool that end users interact with.
- **Process (How it is built):** The methodology, activities, and practices used to develop the product.
- The KISS principle (Keep It Simple, Stupid) is highlighted as a guiding philosophy for both dimensions.

### Criteria for Software Project Success
A software project is considered successful if it meets three criteria:
- Development costs were **within budget**
- The software is delivered **on schedule**
- The software **meets the needs of users** in both scope and quality

### Software Development Activities
The core development activities follow a logical progression:
1. **Requirement Analysis** — Understanding what stakeholders need
2. **Specification** — Formally documenting the requirements
3. **Architecture** — Defining the high-level structure of the system
4. **Design, Implementation, and Testing** — Building and verifying the system
5. **Deployment and Maintenance** — Releasing and evolving the system

These activities can be organized through various process models: Build and Fix, Waterfall, Prototyping, Incremental/Iterative Models, Agile Models, Spiral Model, and Extreme Programming.

### Software Engineering Defined
Three authoritative definitions establish the scope of the discipline:
- **IEEE Standard 610.12-1990:** "The application of a systematic, disciplined, computable approach for the development, operation, and maintenance of software."
- **Fritz Bauer:** "The establishment and use of standard engineering principles. It helps you to obtain, economically, software which is reliable and works efficiently on the real machines."
- **Boehm:** "The practical application of scientific knowledge to the creative design and building of computer programs. It also includes associated documentation needed for developing, operating, and maintaining them."

### SE Roles Beyond Programming
Software engineering requires skills far beyond coding:
- Understanding requirements and writing specifications
- Deriving models and reasoning about them
- Operating at various abstraction levels
- Being an effective team member
- Communication and management skills
- This is described as "programming-in-the-large"

### Principle 1: Rigor and Formality
- **Rigor** helps produce more reliable products, control costs, and increase confidence in products.
- Examples of rigor: detailed code reviews, automated testing, applying design principles.
- **Formality** is "rigor at the highest degree" — the software process is driven and evaluated by mathematical laws.
- Examples of formality: mathematical (formal) analysis of program correctness (critical in aviation, healthcare, finance), systematic test data derivation, rigorous documentation of development steps.

### Principle 2: Separation of Concerns
- Trying to do too many things simultaneously leads to mistakes, which software development cannot tolerate.
- The core idea is "divide and conquer" — separate complexities and concentrate on one at a time.
- Example: keep product requirements separate (functionality, performance, usability).
- Benefits: supports parallelization of efforts, separation of responsibilities, and creating an understanding of how parts depend on each other.

### Principle 3: Modularity (Cornerstone Principle)
- A complex system is divided into simpler pieces called **modules**; a system composed of modules is **modular**.
- Modularity supports the application of separation of concerns.
- **Cohesion:** Each module should be highly cohesive — all elements within a module should be strongly related, grouped together for a logical reason (the function of the module).
- **Coupling:** Modules should exhibit low coupling — low interactions with others, understandable separately.
- **High cohesion + Low coupling** achieves: composability, decomposability, understandability, and modifiability.
- **Top-down approach:** Decompose the whole design into modules first, then concentrate on individual module design.
- **Bottom-up approach:** Concentrate on modules first, then on their composition.
- Both are complementary phases of the whole design process.
- Real-world analogy: Car manufacturing — assembling parts designed and built separately, with parts reused from model to model.
- **Main benefits of modularity:**
  - Decomposability: decomposing a complex system into simpler pieces
  - Composability: composing a complex system from existing modules
  - Understandability: understanding a system in terms of its pieces
  - Modifiability: modifying a system by changing only a small number of its pieces

### Principle 4: Abstraction
- Identify the important aspects of a phenomenon and ignore its details.
- Abstraction is a special case of separation of concerns.
- The type of abstraction to apply depends on purpose or role (user vs. designer).
- **Case Study — Cloud Storage (Google Drive, Dropbox):** Users simply "upload" or "download" files without understanding how data is split into chunks, replicated across servers, or recovered in case of failure. Developers interact with high-level API commands like `uploadFile()` or `getFile()` without handling storage architecture, redundancy, or server communication.

### Principle 5: Anticipation of Change
- "Change is the only constant" — changes are unavoidable in software development.
- The ability to support software evolution requires anticipating potential future changes.
- Guidelines: minimize changes to existing modules, leave spots in the program for future features, plan for correcting errors, old requirements changing, and new requirements emerging.
- Not anticipating change leads to high cost and unmanageable software.
- Benefits: creates software infrastructure that absorbs changes easily, enhances reusability of components, controls cost in the long run.

### Principle 6: Generality
- Not generalizing leads to continuous redevelopment of similar solutions.
- When solving a problem, try to discover if it is an instance of a more general problem whose solution can be reused in other cases.
- Example: Asked to write a serial port data transfer program — consider generalizing to a broader data communication solution.
- General trend: for every application area, general packages providing standard solutions to common problems are increasingly available (spreadsheets, databases, word processors).
- Benefits: increased reusability, increased reliability, faster development, reduced cost.

### Principle 7: Incrementality
- Delivering a large product as a whole and in one shot often leads to dissatisfaction and a product that is "not quite right."
- In most practical cases, there is no way to get all requirements right before development — requirements emerge as the application is available for experimentation.
- Benefits: development of better products, early identification of problems, increase in customer satisfaction, active involvement of customer.
- **Example — Game Design:** First release a 2D version, then work on 3D; first use coarse-grained textures, then fine-grained.
- Process examples: deliver subsets of a system early for feedback, deal first with functionality then performance, deliver a prototype then incrementally turn it into a product.

## Definitions

| Term | Definition |
|------|------------|
| Software Engineering | The application of systematic, disciplined, computable approaches for the development, operation, and maintenance of software (IEEE 610.12-1990) |
| Rigor | A disciplined approach to software development that produces more reliable products, controls costs, and increases confidence |
| Formality | Rigor at the highest degree, where the software process is driven and evaluated by mathematical laws |
| Separation of Concerns | The principle of dividing a problem into parts that can be dealt with separately, concentrating on one complexity at a time |
| Modularity | Dividing a complex system into simpler, self-contained pieces (modules) that can be developed, understood, and modified independently |
| Cohesion | The degree to which elements within a single module are related to each other and grouped for a logical reason |
| Coupling | The degree of interaction and dependency between modules; low coupling is desirable |
| Abstraction | Identifying the important aspects of a phenomenon while ignoring unnecessary details |
| Anticipation of Change | Designing software to accommodate future modifications, new requirements, and error corrections |
| Generality | Solving problems in a general way so solutions can be reused across multiple contexts |
| Incrementality | Delivering software in successive, expanding subsets rather than as a single monolithic release |
| Decomposability | The capability of breaking a complex system into simpler, manageable pieces |
| Composability | The capability of assembling a complex system from existing modules |
| Top-down Design | An approach that decomposes the whole system into modules first, then designs individual modules |
| Bottom-up Design | An approach that designs individual modules first, then composes them into a complete system |
| KISS | "Keep It Simple, Stupid" — a design principle favoring simplicity in software products and processes |

## Diagrams & Visual Descriptions

### Growth Chart (Slide 13)
A chart from the Bureau of Labor Statistics / App Academy showing the projected growth for software engineering roles from 2017 to 2030. The chart illustrates significant projected growth in the field, reinforcing the argument that software engineering is an increasingly important and in-demand discipline. This growth is driven by the increasing complexity of modern systems and the flooding of software into society, controlling critical machines (aircraft, medical devices) and worldwide functions (e-commerce).

### Cohesion and Coupling Diagram (Slide 26)
A visual comparison showing two arrangements of modules (represented as boxes):
- **High Coupling (left side):** Multiple modules with many connecting lines between them, representing heavy interdependencies. Each module communicates with and depends on several others, creating a tangled web of relationships that makes the system difficult to understand, modify, or maintain.
- **Low Coupling (right side):** Multiple modules with few connecting lines between them, representing minimal interdependencies. Each module operates more independently, with clean, limited interfaces to other modules.

```
  HIGH COUPLING                       LOW COUPLING

  +-----+   +-----+   +-----+        +-----+   +-----+   +-----+
  |  A  |---|  B  |---|  C  |        |  A  |   |  B  |   |  C  |
  +-----+   +-----+   +-----+        +-----+   +-----+   +-----+
    | \       / | \       |              |         |         |
    |  \     /  |  \      |              |         |         |
    |   \   /   |   \     |              |         |         |
  +-----+ X  +-----+ +-----+        +-----+   +-----+   +-----+
  |  D  |/ \ |  E  | |  F  |        |  D  |   |  E  |   |  F  |
  +-----+   \+-----+ +-----+        +-----+   +-----+   +-----+
    Many dependencies between          Minimal dependencies;
    modules = hard to maintain          modules are independent
```

The diagram effectively illustrates why low coupling is desirable — it reduces complexity and makes individual modules easier to develop, test, and replace.

### Top-down vs Bottom-up Decomposition Diagrams (Slide 28)
Two tree-structure diagrams illustrating complementary design approaches:

```
  TOP-DOWN DECOMPOSITION               BOTTOM-UP COMPOSITION

       [System]                              [System]
       /      \                              /          [Sub A]  [Sub B]                      [Sub A]  [Sub B]
    /    \      |                          /    \      |
  [M1]  [M2]  [M3]                     [M1]  [M2]  [M3]

  Direction: top -> down               Direction: bottom -> up
  Start with the whole system,         Start with individual modules,
  decompose into sub-modules           compose into larger subsystems
```

- **Top-down:** Shows a single root node (the complete system) at the top, with branches splitting downward into progressively smaller and more specific sub-modules. The design process starts with the overall system and decomposes it into components.
- **Bottom-up:** Shows individual leaf-node modules at the bottom being composed upward into larger subsystems, ultimately forming the complete system at the top.
Both diagrams use a hierarchical tree structure but emphasize opposite directions of the design process. The lecture notes that these are two complementary phases of the whole design process, not mutually exclusive alternatives.

### Software as Product and Process (Slide 5)
A simple conceptual diagram showing "Software" splitting into two dimensions: "Product" (What is built?) and "Process" (How is it built?), emphasizing the dual nature of software development.

## Code Examples

No explicit code examples are provided in this lecture. However, the abstraction case study references API-level operations:

```python
# Cloud Storage Abstraction Example (Conceptual)
# Users and developers interact with high-level commands
# without understanding the underlying distributed system

uploadFile("document.pdf")    # Hides: chunking, replication, server selection
getFile("document.pdf")       # Hides: retrieval, reconstruction, failover

# The complexity of distributed file systems, data synchronization,
# redundancy, and server communication is abstracted away
```

## Formulas & Algorithms

No mathematical formulas or algorithms are covered in this introductory lecture. Formal mathematical analysis of program correctness is mentioned as an example of formality in SE but is not elaborated upon here.

## Key Takeaways

- Software is fundamentally different from physical products: it is invisible, does not age, is not worn by use, is easy to modify, but expensive to develop.
- A successful software project must be within budget, on schedule, and meet user needs in scope and quality.
- Software engineering goes far beyond programming — it requires systematic, disciplined approaches encompassing requirements, design, testing, deployment, and maintenance.
- The **seven key SE principles** are: Rigor and Formality, Separation of Concerns, Modularity, Abstraction, Anticipation of Change, Generality, and Incrementality.
- **Modularity is the cornerstone principle** — aim for high cohesion within modules and low coupling between modules.
- Modularity enables four critical capabilities: decomposability, composability, understandability, and modifiability.
- **Abstraction** allows managing complexity by focusing on what matters and hiding unnecessary details (e.g., cloud storage APIs).
- **Anticipation of change** is essential because requirements always evolve — design software to absorb changes easily.
- **Generality** prevents reinventing the wheel — always consider if your solution can be generalized for reuse.
- **Incrementality** reduces risk — deliver in subsets, get early feedback, and refine iteratively rather than attempting a single monolithic delivery.
- Software engineering roles are projected to grow significantly through 2030, driven by increasing system complexity and society's dependence on software.

## Connections

This lecture establishes the theoretical foundation for the entire CSIT314 course. The seven SE principles introduced here directly inform the software development process models covered in **Week 2** (Rational Unified Process, Waterfall, Agile, Spiral, etc.) — each model represents a different way of organizing the development activities listed here. The principle of **incrementality** is the philosophical basis for iterative and agile methodologies. **Modularity** connects to object-oriented design, design patterns, and software architecture topics that appear in later weeks. **Separation of concerns** underpins architectural patterns like MVC and microservices. **Anticipation of change** ties directly to maintainability, refactoring practices, and configuration management. The emphasis on requirements, specification, and process foreshadows deeper dives into requirements engineering and project management in subsequent lectures. The distinction between Product and Process provides the framing for evaluating every methodology studied in this course.
