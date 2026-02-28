# CSIT314 — Week 6: Advanced UML Part 2 — State Diagrams, Class Identification, Sequence Diagrams, and B-C-E Design

> **Source files:** CSIT314_Week6.pptx
> **Date summarized:** 2026-02-24

## Overview
This lecture extends UML modeling into advanced behavioral and structural diagrams. It covers state diagrams for modeling object lifecycle behavior, class identification through noun/verb extraction, sequence diagrams for modeling object interactions over time, and the Boundary-Control-Entity (B-C-E) design pattern (also known as MVC). The lecture ties together the 4+1 architectural view model introduced in Week 5 by populating the Logical View (state and class diagrams), Process View (sequence, communication, and interaction overview diagrams), Development View (component diagrams), and Physical View (deployment diagrams). This is a pivotal lecture that bridges requirements analysis (use cases from Week 4) with concrete object-oriented design.

## Key Concepts

### Design and Implementation — The Big Picture
- Software design and implementation is the stage where an executable software system is developed
- Design and implementation activities are invariably **interleaved** — they are not strictly sequential
- **Software design** is a creative activity: identifying software components and their relationships based on customer requirements
- **Implementation** is the process of realizing the design as a program
- For large systems developed by different groups, design models serve as an important **communication mechanism**
- For small systems, the overhead of maintaining detailed models may not be cost-effective

### Object-Oriented Design
- Structured OOD processes involve developing multiple system models
- Common activities depend on the organization using the process
- **System context** = a structural model (e.g., class diagram) showing other systems in the environment of the system being developed
- **Interaction model** = a dynamic model (e.g., use case diagram + structured natural language) showing how the system interacts with its environment
- Understanding context helps establish **system boundaries** — deciding what features belong inside vs outside the system
- **Design models** show objects, object classes, and relationships:
  - **Static models** describe structure (class diagrams)
  - **Dynamic models** describe interactions (sequence diagrams, state diagrams)

### State Diagrams (Logic View)

#### What is a State?
- A state is a **set of values of attributes** that describe an object at a specific point in its life
- Example: A Student object's state is determined by name, ID, program, semester, etc.
- Some objects are quite dynamic, passing through a variety of states over their existence
- A student can change from "new" to "current" to "former"
- A state **abstracts** from the detailed attribute values and associations of an object
- Represents the internal condition of an object during a period of time
- **The response to events may depend on the current state** of the object
- Object creation comes with an **initial state**; object deletion may be related to a **final state**

#### Events
- An event is **something worth noticing at a point in time**
- Types of events:
  - **Signal** from other objects
  - **Message** received by an object
  - **Time-based** — a certain date/time is reached
- Events may take arguments
- An event changes value(s) that describe an object (changes the state)
- Example: "The student graduates" is an event that changes state from "current" to "former"
- **Concurrent events:** two events related only by coincidence with no effect on each other (e.g., two planes taking off simultaneously)

#### Transitions
- A transition represents a **change of internal state** of an object
- Usually triggered (fired) by an event
- Transitions **fire instantly** and are **not interruptible**
- Can go from one state to another or back to the same state (self-transition)
- Five components of a transition:
  1. **Source State** — the state the object is in when it receives the event
  2. **Event Trigger** — the event whose reception makes the transition eligible to fire
  3. **Guard Condition** (optional) — a boolean expression; transition fires only if true
  4. **Action** (optional) — an executable atomic computation performed during the transition
  5. **Target State** — the state that is active after the transition completes
- Example: "When you go out in the morning (event), if the temperature is below freezing (guard), then put on your gloves (action)" and move to the next state

#### Activities
- Activities are **long-running processes** that last as long as an object is in a certain state
- Unlike transitions (which are instantaneous), activities **can take longer**
- Activities are **interruptible** — an event causing a state transition may abort an ongoing activity

#### Guards
- A guard is a **logical condition** that evaluates to true or false
- A guarded transition fires **only if the guard resolves to true**
- Since only one transition can fire from a given state, guards should be **mutually exclusive** for any event

#### State Diagram Examples
- **Student states:** new -> current -> former (triggered by enrollment and graduation events)
- **Tape recorder:** States include Stopped, Playing, Recording, Paused with transitions triggered by button-press events (Play, Stop, Record, Pause, Eject)
- **Weather Station activity:** In-class exercise drawing a state diagram for a weather station system (states like Idle, Collecting Data, Processing, Transmitting)

### Class Diagrams and Class Identification

#### Object Concepts
- Every object has three characteristic concepts:
  1. **Identity** — unique distinguishability from other objects
  2. **State** — current values of its attributes
  3. **Behavior** — operations it can perform

#### Class Diagram Perspectives
- Class diagrams operate at three distinct levels:
  1. **Conceptual** — represents domain concepts independent of software
  2. **Specification** — focuses on interfaces (what classes do, not how)
  3. **Implementation** — shows actual software classes with full detail

#### Identifying Classes: Noun Extraction
- Identifying object classes is often the **most difficult part** of OOD
- There is **no magic formula** — it relies on skill, experience, and domain knowledge
- Object identification is **iterative** — unlikely to be correct on the first attempt
- **Rule of thumb: Look for nouns** in the problem description
- Focus on **concepts, not implementation** (e.g., "MessageQueue stores messages" — don't worry yet about queue implementation)

##### Three-Stage Noun Extraction Process
1. **Stage 1 — Concise Problem Definition:** Define the product in a single sentence
2. **Stage 2 — Informal Strategy:** Incorporate constraints, express the result in a single paragraph
3. **Stage 3 — Formalize the Strategy:**
   - Identify **nouns** in the informal strategy -> candidate classes
   - Identify **verbs** in the informal strategy -> candidate responsibilities

#### Identifying Responsibilities: Verb Extraction
- **Rule of thumb: Look for verbs** in the problem description
- Verbs map to class methods/responsibilities
- Example for MessageQueue behavior: "Add message to tail", "Remove message from head", "Test whether queue is empty"

#### Scenarios as Analysis Technique
- Each scenario focuses on a specific task/execution
- Scenario = sequence of actions
- Action = interaction between actor and computer system
- Each action yields a result; each result has value to one of the actors
- Use **variations** for exceptional situations

#### VoiceMail System Example — Full Noun/Verb Extraction Walkthrough
- **Concise definition:** "A system that manages voice mails for users"
- **Informal strategy:** "When a caller dials user's number and the user is not able to take the call, the system asks the caller if s/he wants to leave a message. If yes, the system speaks a prompt after which the caller will speak the message. If no, the caller disconnects. The message is then recorded then stored in the user's mailbox. The user can play the mailbox after authentication. The user can also delete the message or archive it for future use. If the mailbox is full, the caller cannot leave a message. If the mailbox is empty, the user cannot play a message."
- **Nouns (candidate classes):** caller, user's number, user, call, system, message, prompt, mailbox, authentication, full, empty, future
- **Verbs (candidate responsibilities):** dials, take, ask, want, leave, speak, disconnects, record, store, play, delete, archive
- **Scenario — Leave a Message:**
  1. Caller dials main number of voice mail system
  2. System speaks prompt: "Enter mailbox number followed by #"
  3. User types extension number
  4. System speaks: "You have reached mailbox xxxx. Please leave a message now"
  5. Caller speaks message
  6. Caller hangs up
  7. System places message in mailbox
- **Variation #1:** User enters invalid extension -> system speaks error -> return to step 2
- **Variation #2:** Caller hangs up instead of speaking message -> system discards empty message

#### Weather Station Object Classes
- Identification based on tangible hardware and data:
  - **Ground thermometer, Anemometer, Barometer** — application domain 'hardware' objects related to instruments
  - **Weather station** — basic interface to environment, reflects use-case interactions
  - **Weather data** — encapsulates summarized data from instruments

### Class Relationships

#### Aggregation
- An **"is-a-part-of"** (assembly-component) relationship
- The assembly object is made up of component objects
- **Components can exist independently** of the assembly
- Notation: **hollow diamond** on the assembly end
- Examples: "A car HAS A driver and HAS passengers", "A department IS PART OF a university", "MessageQueue aggregates Messages", "Mailbox aggregates MessageQueue"
- Implemented through instance fields

#### Composition
- A stronger form of aggregation where parts **cannot exist independently**
- If the whole is destroyed, its parts are also destroyed
- Notation: **filled (solid) diamond** on the whole end
- Example: "A house is composed of a floor, roof, and 4 walls" — if the house is destroyed, so are its parts

#### Inheritance (Generalization/Specialization)
- An **"is-a"** relationship
- Subclasses describe properties that are specializations of a superclass
- All properties of the superclass are inherited by the subclass (attributes, operations, associations)
- More general class = **superclass**; more specialized class = **subclass**
- Subclass supports all method interfaces of superclass (implementations may differ)
- Subclass may have added methods and added states
- Examples: "ForwardedMessage inherits from Message", "Greeting does NOT inherit from Message"

#### Association
- The **most generic** type of relationship — the default option
- Any relationship that does not fit aggregation, composition, or inheritance
- Typically of types: **"has-a"**, **"uses"**, **"communicates with"**, **"makes requests of"**

#### Dependency ("uses")
- A method of class C manipulates objects of class D
- If C does not use D, then C can be developed without knowing about D
- Example: Mailbox depends on Message

#### Multiplicities
- **\*** — any number (zero or more)
- **1..\*** — one or more
- **0..1** — zero or one (optional)
- **1** — exactly one

### Sequence Diagrams (Process View)

#### Core Elements
- **Objects:** Shown as rectangles with instance name and/or class name using syntax `[instanceName][:className]`
- **Lifeline:** Dashed vertical line showing the life of an object; X (cross) marks deletion
- **Focus of Control (Activation Box):** Long, hollow, narrow rectangle placed over a lifeline; shows the object has control (sending or receiving messages)
- **Time** runs down the page — an arrow above comes before an arrow below

#### Messages
- Shown by a line with a **filled arrowhead**
- Message name corresponds to the class method being invoked
- An interaction between two objects requires some link (dependency, association) between them
- Private methods can also be shown as self-messages

#### Return Values
- Shown by a **dashed arrow** with a label indicating the return value
- Do not model a return value when it is obvious (e.g., `getTotal()`)
- Model return values when needed as parameters in other messages (e.g., `ok = isValid()`)

#### Self Calls
- An object sends a message to itself — shown as an arrow looping back to the same lifeline

#### Object Creation and Destruction
- **Creation:** `<<create>>` message arrow pointing to the newly created object
- **Destruction:** `<<destroy>>` message; an object may destroy another or itself
- Avoid modeling destruction unless memory management is critical

#### Synchronous Messages
- Nested flow of control, typically implemented as an operation call
- The routine handling the message completes before the caller resumes execution
- The **caller is blocked** until the receiver returns

#### Control Information
- **Conditions:** `[expression] message-label` — message sent only if condition is true
  - Example: `[ok] borrow(member)`
- **Iteration:** `*[expression] message-label` — message sent many times, possibly to multiple receivers
  - Examples: `*draw()`, `*[until full] insert()`
- For complex scenarios, consider drawing **separate diagrams** rather than overloading one
- Sequence diagrams are not ideal for detailed algorithm modeling — prefer activity diagrams or pseudocode

#### Library Member/Book Example
```
member:LibraryMember        book:Book        :BookCopy
        |                      |                 |
        |--- borrow(book) ---->|                 |
        |                      |-- ok=mayBorrow() (self call)
        |                      |                 |
        |                      |--[ok] borrow(member)-->|
        |                      |                 |-- setTaken(member) (self call)
        |                      |                 |
```
- member sends `borrow(book)` to book
- book checks `ok = mayBorrow()` (self call)
- If ok, book sends `borrow(member)` to BookCopy
- BookCopy calls `setTaken(member)` on itself

#### ATM Example
- Classes involved: ATM (InsertCard, EnterPIN, ValidatePIN, CheckAvailableCash, WithdrawCash, DispenseCash), ATMCard (ReadCard), BankAccount (GetBalance)
- Demonstrates how use cases drive sequence diagram creation
- Links use case + class diagram -> sequence diagram -> coding work

### B-C-E Design (MVC Pattern)

#### The Three Layers
1. **Entity Layer (Model)**
   - Represents core **business domain concepts**
   - Holds and manages system data
   - Responsible for **data persistence** — maps directly to database tables
   - Implemented as classes with attributes and methods
   - Some entity classes may be **transient** (not stored in DB, only temporary)
   - Identified from the domain class diagram

2. **Control Layer (Controller)**
   - Coordinates the **execution of a use case**
   - Contains application-specific logic: combining information, controlling interaction flow
   - Acts as central coordinator between Boundary and Entity
   - Implements the logic shown in sequence diagrams
   - The "glue" between boundary and entity classes
   - Contains **application-specific business rules** (e.g., "A student should enroll in 4 subjects per semester", "A customer cannot withdraw more than  per day")
   - **One control class per use case** (some use cases may not need one)
   - Created when the system performs the use case; usually dies when the use case completes

3. **Boundary Layer (View)**
   - Manages interaction between the **user (actor)** and the system
   - Presents information to the user and receives user input
   - Represents the user interface: screens, forms, menus, mobile/web interfaces
   - Does NOT provide actual use case behavior — typically represents the GUI (dialog, menu, screen)
   - **Actors interact only with boundary classes**

#### Interaction Rules
- **Actor -> Boundary -> Control -> Entity** (strict flow)
- The user interacts with the View
- The Controller responds to user actions and coordinates logic
- The Model is updated based on controller decisions
- The View refreshes using updated model data

#### Forbidden Shortcuts
- **Boundary must NOT directly manipulate Entity**
- Entity must NOT depend on Boundary
- Entity must NOT control the flow of a use case
- Actors NEVER talk directly to Control or Entity
- Violating these rules is wrong in both robustness and B-C-E thinking

#### Two Representations
1. **Circle notation** — circle icon for class, line for association between classes
2. **Prefix notation** — standard class rectangles with B/C/E prefix labels

#### ATM B-C-E Example
- Use case: **Withdraw Cash** (sub-scenario: Validate PIN)
- **Boundary:** ATM GUI — receives input from user, displays responses
- **Control:** Withdraw Cash Controller — coordinates the use case logic
- **Entities:** ATM Card, PIN List, ATM, Bank Account — represent data and domain behavior
- The sequence diagram follows B-C-E responsibilities: Actor -> ATM GUI -> Withdraw Cash Controller -> Entity classes
- B-C-E is used as a **guiding principle** when drawing sequence diagrams, not as a replacement for them

### Communication Diagrams
- Convey the **same information** as sequence diagrams — just a different visual style
- Sequence diagrams focus on messages over a **timeline**
- Communication diagrams focus on **links between participating objects**
- Sequence ordering is less clear in communication diagrams
- Relationships between objects are more clearly visible

### Interaction Overview Diagrams
- A form of **activity diagram** where nodes represent interaction diagrams
- Nodes can contain sequence diagrams, communication diagrams, or other interaction overviews
- New elements: **interaction occurrences** and **interaction elements**
- Shows the flow between multiple interaction diagrams, analogous to how activity diagrams show flow between actions

### Component Diagrams (Development View)
- Illustrate pieces of software, embedded controllers, etc. that make up a system
- Show relationships between different parts and organize the system into subsystems
- A **component** = a module of classes representing independent systems or subsystems with the ability to interface with the rest of the system
- Usually implemented by one or more classes at runtime
- **Provided interface** = complete circle (lollipop) — interface the component offers
- **Required interface** = half circle (socket) — interface the component needs
- **Assembly connector** links provided and required interfaces
- **Package vs Component:** Package = physical location of code; Component = functionality

### Deployment Diagrams (Physical View)
- Model the **run-time architecture** of a system
- Show configuration of hardware elements (**nodes**) and how software elements/artifacts are mapped onto them
- **Node** = hardware or software element, shown as a 3D box shape
- **Node Instance** shows name and base node type
- **Standard stereotypes:** `<<computer>>`, `<<pc>>`, `<<server>>`, `<<pc client>>`, `<<pc server>>`, `<<unix server>>`, `<<storage>>`, `<<disk array>>`, etc.
- **Artifact** = any product of software development (source files, executables, design docs, test reports, prototypes, user manuals); denoted by rectangle with `<<artifact>>` keyword and document icon
- **Association** = communication path between nodes
- **Node as Container** = a node can contain other elements such as components or artifacts

## Definitions
| Term | Definition |
|------|------------|
| State | A set of attribute values that describe an object at a specific point in its life |
| Event | Something worth noticing that occurs at a point in time and may trigger a state change |
| Transition | An instantaneous, non-interruptible change from one state to another, triggered by an event |
| Guard | A logical condition (true/false) that must be true for a guarded transition to fire |
| Activity | A long-running, interruptible process that occurs while an object remains in a certain state |
| Action | An executable atomic computation performed during a transition |
| Concurrent Events | Two events related only by coincidence with no effect on each other |
| Source State | The state an object is in when it receives an event that may trigger a transition |
| Target State | The state that becomes active after a transition completes |
| Class Diagram | UML diagram partitioning a system into areas of responsibility (classes) and showing associations between them |
| Noun Extraction | Technique for identifying candidate classes by finding nouns in a problem description |
| Verb Extraction | Technique for identifying candidate responsibilities/methods by finding verbs in a problem description |
| Scenario | An analysis technique describing a specific sequence of actions between actors and the system |
| Aggregation | "Is-a-part-of" relationship where components can exist independently (hollow diamond) |
| Composition | Stronger aggregation where parts cannot exist independently of the whole (filled diamond) |
| Inheritance | "Is-a" relationship where a subclass inherits all properties of a superclass |
| Association | The most generic relationship type between classes (has-a, uses, communicates-with) |
| Dependency | Relationship where a method of one class manipulates objects of another class |
| Multiplicity | Constraint on the number of objects that participate in a relationship (e.g., *, 1..*, 0..1, 1) |
| Sequence Diagram | UML diagram showing object interactions arranged in time sequence |
| Lifeline | Dashed vertical line representing an object's existence over time in a sequence diagram |
| Focus of Control | Narrow rectangle on a lifeline indicating the object is actively sending or receiving messages |
| Synchronous Message | A message where the caller is blocked until the receiver completes processing |
| Self Call | A message an object sends to itself, shown as a looping arrow on the same lifeline |
| Boundary (View) | B-C-E layer managing user interaction; the GUI layer that actors interact with |
| Control (Controller) | B-C-E layer coordinating use case execution and containing business rules |
| Entity (Model) | B-C-E layer representing business domain concepts and handling data persistence |
| Communication Diagram | UML diagram conveying the same information as sequence diagrams but focusing on links between objects |
| Interaction Overview Diagram | A form of activity diagram where nodes represent interaction diagrams |
| Component Diagram | UML diagram showing software components, their interfaces, and relationships |
| Deployment Diagram | UML diagram modeling run-time architecture showing hardware nodes and software artifact mapping |
| Artifact | Any product of software development (source files, executables, design documents, test reports) |
| Node | A hardware or software computational resource shown as a 3D box in deployment diagrams |
| Assembly Connector | Links a provided interface (lollipop) to a required interface (socket) in component diagrams |

## Diagrams & Visual Descriptions

### State Diagram — Student Lifecycle
```
    [*] (initial)
     |
     v
  +-------+   enroll    +---------+   graduate   +--------+
  |  New  |------------>| Current |------------->| Former |
  +-------+             +---------+              +--------+
                             |                       |
                             +--- drop out ----------+
```
A student object transitions from New (upon creation) to Current (upon enrollment) to Former (upon graduation or dropping out). Each transition is triggered by a specific event.

### State Diagram — Tape Recorder
```
                 +----------+
     play        |          |   stop
  +----------->  | Playing  | ----------+
  |              |          |           |
  |              +----+-----+           v
  |                   |            +---------+
  |              pause|            | Stopped |<--[*]
  |                   v            +---------+
  |              +---------+           ^
  |              | Paused  |           |
  |              +---------+      stop |
  |                   |                |
  |              resume               |
  |                   |           +-----------+
  |                   +---------->| Recording |
  |                               +-----------+
  |                                    ^
  +------------------------------------+
              record
```
Demonstrates multiple states with event-driven transitions. The Stop event can fire from Playing or Recording to return to Stopped.

### Transition Anatomy
```
+----------------+    event [guard] / action    +----------------+
|  Source State  |----------------------------->|  Target State  |
+----------------+                              +----------------+
```
A transition consists of: source state, event trigger, optional guard condition in square brackets, optional action after slash, and target state.

### Class Diagram Notation — Relationships
```
Aggregation (hollow diamond):
    [Department] <>-------- [University]
    "Department is part of University; department can exist independently"

Composition (filled diamond):
    [Floor] <filled>-------- [House]
    "Floor cannot exist without House; destroyed together"

Inheritance (triangle arrow):
    [ForwardedMessage] -------|> [Message]
    "ForwardedMessage is-a Message"

Association (plain line):
    [Student] --------------- [Course]
    "Student takes Course"

Dependency (dashed arrow):
    [Mailbox] - - - - - - -> [Message]
    "Mailbox uses Message"
```

### Multiplicities on Associations
```
  [Student] 1..* --------  * [Course]
  "One or more students enrolled in zero or more courses"

  [Order] 1 -------- 0..1 [Invoice]
  "Exactly one order has zero or one invoice"
```

### Sequence Diagram — Library Borrow Book
```
member:LibraryMember     book:Book        :BookCopy
     |                      |                 |
     |--- borrow(book) ---->|                 |
     |                      |                 |
     |                  ok = mayBorrow()       |
     |                      |----+            |
     |                      |    | (self)     |
     |                      |<---+            |
     |                      |                 |
     |                      |--[ok] borrow(member)-->|
     |                      |                 |
     |                      |            setTaken(member)
     |                      |                 |----+
     |                      |                 |    | (self)
     |                      |                 |<---+
     |                      |                 |
```
Shows member requesting to borrow, book checking eligibility via self-call, and conditionally delegating to BookCopy.

### Sequence Diagram — Synchronous Message
```
     :A                :B
      |                 |
      |--doYouUnderstand()-->|
      |   (blocked)     |    |  (processing)
      |                 |    |
      |<--yes (return)--|    |
      |                 |
```
Caller A is blocked until receiver B completes processing and returns.

### Sequence Diagram Elements Reference
```
  X-Axis: Objects (instances)
  Y-Axis: Time (flows downward)

  [instanceName:ClassName]     -- Object
       |                       -- Lifeline (dashed vertical line)
      +-+                      -- Activation box (focus of control)
      | |
      +-+
  --->                         -- Message (filled arrowhead)
  <---                         -- Return (dashed arrow, open arrowhead)
  [condition] msg()            -- Conditional message
  *[expr] msg()                -- Iterated message
  <<create>>                   -- Object creation
  X                            -- Object destruction
```

### B-C-E / MVC Architecture
```
  +--------+      +-----------+      +---------+      +--------+
  | Actor  |----->| Boundary  |----->| Control |----->| Entity |
  | (User) |      | (View/GUI)|      | (Logic) |      | (Data) |
  +--------+      +-----------+      +---------+      +--------+
                       ^                                   |
                       |       (View refreshes from        |
                       +------------- Model) --------------+

  FORBIDDEN:
    Actor ---X---> Control    (actors must go through Boundary)
    Actor ---X---> Entity     (actors must go through Boundary)
    Boundary -X--> Entity     (Boundary must go through Control)
```

### ATM B-C-E Sequence Diagram (Validate PIN)
```
Actor    :ATM GUI     :WithdrawCash    :ATMCard   :PINList   :ATM   :BankAccount
  |      (Boundary)    Controller       (Entity)   (Entity)  (Entity)  (Entity)
  |          |         (Control)           |          |         |          |
  |--insertCard->|          |              |          |         |          |
  |          |--insertCard->|              |          |         |          |
  |          |              |--readCard()->|          |         |          |
  |          |              |<-cardData----|          |         |          |
  |<-enterPIN|              |              |          |         |          |
  |---PIN--->|              |              |          |         |          |
  |          |--validatePIN(PIN)->|        |          |         |          |
  |          |              |--checkPIN(PIN)------->|          |         |
  |          |              |<-valid/invalid--------|          |         |
  |          |              |              |          |         |          |
```
Demonstrates strict B-C-E flow: Actor interacts only with Boundary (ATM GUI), Boundary delegates to Control (Withdraw Cash Controller), Control queries Entities.

### Component Diagram Notation
```
+--------------------+           +--------------------+
| <<component>>      |           | <<component>>      |
|   OrderService     |--O      C--|   PaymentService   |
|                    |  (provided) (required)          |
+--------------------+           +--------------------+

O = Provided interface (lollipop / complete circle)
C = Required interface (socket / half circle)
Assembly connector joins provided to required
```

### Deployment Diagram Structure
```
+========================+         +========================+
||    <<pc client>>     ||         ||    <<server>>        ||
||   Client Machine     || ------> ||   Application Server ||
||                      ||  HTTP   ||                      ||
|| [<<artifact>>       ]||         || [<<artifact>>       ]||
|| [  WebApp.html      ]||         || [  AppServer.jar    ]||
+========================+         +========================+
                                            |
                                            | JDBC
                                            v
                                   +========================+
                                   ||   <<server>>         ||
                                   ||   Database Server    ||
                                   ||                      ||
                                   || [<<artifact>>       ]||
                                   || [  schema.sql       ]||
                                   +========================+

Node = 3D box (hardware/software resource)
Artifact = rectangle with <<artifact>> keyword
Association = communication path between nodes
```

## Code Examples
No explicit code examples were provided in this lecture. The lecture focuses on UML modeling concepts rather than implementation code. However, the class identification process maps directly to code:

```java
// From VoiceMail noun/verb extraction:
public class Mailbox {
    private String number;
    private List<Message> messages;
    private boolean full;

    public void store(Message msg) { /* verb: store */ }
    public Message play() { /* verb: play */ }
    public void delete(Message msg) { /* verb: delete */ }
    public void archive(Message msg) { /* verb: archive */ }
}

public class Message {
    private String content;
    private Date timestamp;

    public void record() { /* verb: record */ }
}

public class Caller {
    public void dial(String number) { /* verb: dials */ }
    public void speak(Message msg) { /* verb: speak */ }
    public void disconnect() { /* verb: disconnects */ }
}
```
This illustrates how nouns become classes and verbs become methods during the class identification process.

## Formulas & Algorithms

### Noun/Verb Extraction Algorithm
```
1. Write a concise problem definition (one sentence)
2. Write an informal strategy (one paragraph with constraints)
3. Extract all NOUNS from the informal strategy
   -> These become candidate CLASSES
4. Filter nouns:
   - Remove duplicates
   - Remove nouns that are attributes, not classes
   - Remove nouns outside scope (e.g., "future")
   - Remove abstract/vague nouns (e.g., "full", "empty" -> attributes)
5. Extract all VERBS from the informal strategy
   -> These become candidate RESPONSIBILITIES (methods)
6. Assign each verb to the most appropriate noun/class
7. Iterate: refine classes and responsibilities through scenarios
```

### B-C-E Layer Assignment Algorithm
```
For each class in the domain model:
  IF class handles user interaction (GUI, forms, screens):
    -> Assign to BOUNDARY layer
  ELSE IF class coordinates use case logic or business rules:
    -> Assign to CONTROL layer
  ELSE IF class represents domain data or persistent storage:
    -> Assign to ENTITY layer

Verify constraints:
  - Actors interact ONLY with Boundary classes
  - Boundary communicates with Control (never directly with Entity)
  - Control coordinates between Boundary and Entity
  - Entity manages data and domain behavior
  - One Control class per use case (typically)
```

## Key Takeaways
- Software design is a **creative, iterative activity** that is interleaved with implementation — not a separate sequential phase
- A **state** is defined by an object's attribute values at a point in time; **state diagrams** model how events drive objects through different states
- Transitions are **instantaneous and non-interruptible**; activities within states are **long-running and interruptible** — this is a critical distinction
- **Guards must be mutually exclusive** for a given state to ensure deterministic behavior
- **Noun extraction** (nouns -> classes) and **verb extraction** (verbs -> methods) provide a systematic approach to class identification, but require iterative refinement
- The **three-stage process** (concise definition -> informal strategy -> formalization) structures the class identification effort
- **Sequence diagrams** model object interactions over time; key elements are objects, lifelines, activation boxes, messages (filled arrowheads), and returns (dashed arrows)
- Understand the difference between the five class relationship types: **aggregation** (hollow diamond, independent parts), **composition** (filled diamond, dependent parts), **inheritance** (is-a), **association** (generic), and **dependency** (uses)
- **B-C-E (Boundary-Control-Entity)** enforces separation of concerns: actors talk only to Boundary, Boundary delegates to Control, Control manipulates Entity — **no shortcuts allowed**
- B-C-E is a **design principle for structuring sequence diagrams**, not a replacement for them
- **Communication diagrams** show the same information as sequence diagrams but emphasize links over timeline ordering
- **Component diagrams** model the Development View with provided/required interfaces and assembly connectors
- **Deployment diagrams** model the Physical View, mapping software artifacts onto hardware nodes
- The 4+1 view model is now populated: Logical (class + state diagrams), Process (sequence + communication diagrams), Development (component diagrams), Physical (deployment diagrams), and Use Cases tying them all together

## Connections
- **Week 4 (Use Cases):** Use cases identified in Week 4 directly drive the sequence diagrams and B-C-E design in this lecture. Each use case maps to one Control class and one or more sequence diagrams. Scenarios from use case analysis feed directly into noun/verb extraction for class identification
- **Week 5 (Architecture and 4+1 View):** This lecture populates the views introduced in the 4+1 model — state and class diagrams fill the Logical View, sequence and communication diagrams fill the Process View, component diagrams fill the Development View, and deployment diagrams fill the Physical View
- **Week 5 (Cohesion/Coupling):** B-C-E design enforces high cohesion (each layer has a single responsibility) and low coupling (strict interaction rules prevent ad-hoc dependencies)
- **Week 7 (CI/CD):** Well-structured B-C-E designs with clear component boundaries make systems easier to integrate and deploy continuously
- **Week 8 (Testing):** Use cases from Week 4 become test cases; sequence diagrams define expected interaction flows that can be verified during integration testing; state diagrams define state-based test scenarios
- **Broader CS Context:** The MVC/B-C-E pattern is foundational in web frameworks (Spring MVC, Django MTV, ASP.NET MVC, React+Redux). Understanding the separation of Boundary, Control, and Entity translates directly to modern full-stack development
