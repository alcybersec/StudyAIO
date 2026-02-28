# CSIT314 — Week 5: Program Design and Architecture

> **Source files:** CSIT314_Week5.pptx
> **Date summarized:** 2026-02-24

## Overview
This lecture covers system architecture types, program design principles, and UML architectural modeling. It introduces key architectural patterns (peer-to-peer, client/server, multitier, microservices), revisits cohesion and coupling at the class level, and explores UML package diagrams, component diagrams, and deployment diagrams within the "4+1" architectural view model. This bridges requirements engineering (Week 4) with detailed UML modeling (Week 6).

## Key Concepts

### System Architecture
- **IEEE definition:** "The process of defining a collection of hardware and software components and their interfaces to establish the framework for the development of a computer system"
- **Architectural design** = description of system in terms of subsystems/modules (layered organization, process assignment, reuse)
- **Detailed design** = internal workings of each module (algorithms, data structures, collaboration models)

### Architecture Types

#### Peer-to-Peer Architecture
- Distributed processing system where any node may be both client and server
- Key consideration: minimization of network traffic while maximizing throughput
- Supports distributed database systems — single request can combine data from multiple servers

#### Client/Server Architecture
- Client = computing process making requests; Server = process serving requests
- Centralized model
- Weakness: single point of failure (if not scaled)

#### Multitier / Layered / Three-tier / N-tier Architecture
- Separates views, domain logic, and data from one another
- Can still be a monolith
- Middle tier can itself be multitiered
- Easier to modify and test than monolithic designs

#### Microservices Architecture
- Each component responsible for one clear aim within the system
- Components only interact with essential elements on a need-to-know basis
- Independent services communicating via APIs

### Complexity Management
- Unrestricted communication between objects grows exponentially with new objects
- **Hierarchies reduce complexity from exponential to polynomial**
- In typical hierarchy, only objects in adjacent layers communicate directly

### Program Design Overview
- System design → Architectural design (framework) → Detailed design (front-end/back-end) → Program design (one application at a time)
- Program execution logic splits between client and server processes

### Class Cohesion and Coupling
- **Class cohesion** = degree of inner self-determination; measures class independence; **stronger is better**
- **Class coupling** = degree of connections between classes; measures interdependence; **weaker is better** (but classes must be coupled to cooperate)

#### Cohesion and Coupling Heuristics
1. Two classes should either be independent or one depends only on public interface(s) of another
2. Attributes and related methods should be kept in one class
3. A class should capture one and only one abstraction
4. System intelligence should be distributed uniformly across classes

#### Kinds of Class Coupling
- X contains Y or has attribute referencing Y
- X has method referencing an instance of Y (parameter, local variable, return type)
- X calls services of (sends messages to) Y
- X is a direct or indirect subclass of Y
- X has method with input argument of class Y
- Y is an interface and X implements that interface

### Reuse Strategy
- **Reuse granularity:** class, component, solution idea
- **Reuse strategies:** Toolkits (class libraries), Frameworks, Analysis and design patterns
- **Toolkit reuse:** Foundation toolkits (e.g., Set, List, Index collections) and Architecture toolkits (e.g., object database system)

### Architecture Modelling — "4+1" View Model

#### Logical View
- Concerned with system functionality
- Uses **class diagrams** and **package diagrams**
- Optional: Object, State Machine, Composite Structure diagrams

#### Process View
- Models dynamic aspects, communication, runtime behavior
- Uses **sequence diagrams** or **communication diagrams**
- Optional: Activity, Timing, Interaction Overview diagrams

#### Development View
- **Component diagrams** showing modules, subsystems, relationships
- Components represent independent systems/subsystems with interface capability

#### Physical View
- **Deployment diagrams** showing where things run
- Models hardware configuration and software mapping onto nodes

### UML Package Diagrams
- Groups related classes into a namespace
- Typically shows public classes only
- Simplifies UML by grouping related elements into higher-level elements
- Class can only be owned by one package (but can "appear" in others if justified)
- Can be nested; related with generalization and dependency

#### Package Diagram Notations
| Notation | Description |
|----------|-------------|
| **Package** | Rectangle with tab; name inside or on tab |
| **Sub-packages** | Nested rectangles inside parent |
| **Dependency** | Dashed arrow from dependent to depended-on |
| **Import** (`<<import>>`) | Only publicly visible elements available |
| **Merge** (`<<merge>>`) | Contents combined; model refinement |
| **Access** (`<<access>>`) | Public/protected elements with qualified name |
| **Visibility** | `+` public, `-` private, `#` protected |
| **Stereotypes** | Written in `<< >>` above package name |

#### Abstract vs Concrete Packages
- **Abstract package:** conceptual, provides generic structure, cannot be instantiated directly (name in italics)
- **Concrete package:** contains actual implementable elements, can be used directly

#### Package Diagram Benefits
- Represent division of work among teams in large projects
- Useful for high-level system overview models

### UML Component Diagrams
- Represent high-level architecture showing components, relationships, dependencies
- **Provided interface** = lollipop symbol (complete circle)
- **Required interface** = half circle (socket symbol)
- **Subsystems** = specialized component with `<<subsystem>>` keyword
- **Ports** = square along edge, exposing required/provided interfaces
- **Component vs Package:** Components are vertical groups with behavioral proximity; packages are typically larger architectural units

### Deployment Diagrams
- **Node** = computational resource with memory and computing capability
- Connection relationships link nodes
- Components deployed on nodes; node + components = **distribution unit**
- **Artifacts:** source files, executables, design docs, test reports, etc. (rectangle with `<<artifact>>`)
- **Associations** = communication paths between nodes
- **Node as Container:** can contain other elements (components or artifacts)

## Definitions
| Term | Definition |
|------|------------|
| Architectural Design | Description of a system in terms of its subsystems and/or modules |
| Detailed Design | Description of the internal workings of each module |
| Cohesion | Degree to which elements within a module are related to each other |
| Coupling | Degree of interdependence between modules/classes |
| Peer-to-Peer | Architecture where any node acts as both client and server |
| Client/Server | Architecture with centralized server handling client requests |
| Multitier | Architecture separating presentation, logic, and data layers |
| Microservices | Architecture of independent services each handling one responsibility |
| Package Diagram | UML diagram grouping related classes into namespaces |
| Component Diagram | UML diagram showing system components and their interfaces |
| Deployment Diagram | UML diagram modeling runtime architecture on hardware nodes |
| Toolkit | Class library that emphasizes code reuse at the class level |
| Framework | Reusable software structure providing main body of program |
| Node | Computational resource in a deployment diagram |
| Artifact | Any product of software development |

## Diagrams & Visual Descriptions

### Three-Tier Architecture
```
+-------------------------+
|   Presentation Layer    |  (UI / Views)
+-------------------------+
|  Business Logic Layer   |  (Domain Logic)
+-------------------------+
|   Data Access Layer     |  (Database)
+-------------------------+
```
Separates concerns; each layer can be modified independently.

### Peer-to-Peer Architecture
```
    [C/S] <-------> [C/S]
      |   Communication   |
      |     Network       |
    [C/S] <-------> [C/S]
```
Each node acts as both Client (C) and Server (S).

### Client/Server Architecture
```
         [Server]
        /   |    \
    [Client] [Client] [Client]
```
Centralized; single point of failure without scaling.

### Package Diagram Example
```
+------------+     +------------+
| <<import>> |     |            |
|  UI Layer  |---->| Domain     |
|            |     | Layer      |
+------------+     +-----+------+
                         |
                         v
                   +------------+
                   | Data       |
                   | Layer      |
                   +------------+
```

### Component Diagram Notation
```
+--------------------+
| <<component>>      |
|   OrderService     |--O IOrderService  (provided interface - lollipop)
|                    |--C IPayment       (required interface - socket)
+--------------------+
```

### Low vs High Cohesion Example
- **Low cohesion (bad):** `OrderManager` class handles creating orders, processing payments, sending emails, updating DB, generating reports
- **High cohesion (good):** Separate classes: `OrderCreator`, `PaymentProcessor`, `EmailNotifier`, `DBUpdater`, `ReportGenerator`

## Code Examples
No explicit code examples in this lecture.

## Formulas & Algorithms
- **Complexity growth:** Unrestricted object communication: O(2^n) paths; Hierarchical: O(n^k) paths

## Key Takeaways
- Choose architecture based on requirements: peer-to-peer for distributed equality, client/server for centralized control, multitier for separation of concerns, microservices for independent scalability
- **High cohesion + low coupling** is the golden rule of program design
- Hierarchies tame complexity — only adjacent layers should communicate
- The "4+1" view model provides comprehensive architectural perspective: Logical + Process + Development + Physical + Use Cases
- Package diagrams organize large systems for team-based development
- Component diagrams show provided/required interfaces between modules
- Deployment diagrams map software onto hardware infrastructure
- Reuse at appropriate granularity (class, component, pattern) reduces cost and increases reliability
- Abstract packages provide generic structure; concrete packages contain implementable elements

## Connections
- **Week 1:** Builds on SE principles of modularity, separation of concerns, and abstraction
- **Week 4:** Use cases from requirements engineering drive architectural decisions
- **Week 6:** Class diagrams, sequence diagrams, state diagrams from logical/process views are detailed further
- **Week 7:** CI/CD pipelines depend on well-structured, modular architectures
- **Week 9:** DevOps benefits from microservices and well-separated deployment units
