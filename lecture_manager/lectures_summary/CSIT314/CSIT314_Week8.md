# CSIT314 — Week 8: Testing, Verification and Validation

> **Source files:** CSIT314_Week8.pptx
> **Date summarized:** 2026-02-24

## Overview

This lecture provides a comprehensive treatment of software testing, verification, and validation (V&V) as applied throughout the software development lifecycle. It begins by distinguishing verification ("Are we building the product right?") from validation ("Are we building the right product?"), then covers the V-model of development, static vs. dynamic verification techniques, and the full spectrum of testing approaches — from black-box techniques like equivalence partitioning and boundary value analysis, through white-box methods including software inspections, control flow graphs, def-use analysis, and structural coverage criteria (statement, branch, condition, and path coverage). Understanding these concepts is essential because testing consumes 30–80% of SDLC time and can account for up to 70% of lifecycle costs, making it the single most resource-intensive activity in software development.

## Key Concepts

### Verification vs. Validation
- **Validation** answers the question: "Are we building the right product?" — it confirms the software does what the user actually requires.
- **Verification** answers the question: "Are we building the product right?" — it confirms the software conforms to its specification.
- V&V is a **whole life-cycle process**, not a single phase. It must be applied at each stage of the software process.
- V&V has two principal objectives:
  1. The **discovery of defects** in a system
  2. The **assessment of whether the system is useful and usable** in an operational situation
- V&V should establish confidence that the software is "fit for purpose" — this does **not** mean completely free of defects, but rather good enough for its intended use.

### V&V Confidence Factors
The degree of confidence needed depends on three factors:
- **Software function (criticality):** The more critical the software is to an organisation, the higher the confidence level required.
- **User expectations:** Users may have low expectations for certain types of software (e.g., a free utility) or very high expectations (e.g., banking software).
- **Marketing environment:** Getting a product to market early may sometimes be more important than finding every defect.

### V&V Planning
- Careful planning is required to get the most out of testing and inspection processes.
- Planning should start **early** in the development process.
- The plan should identify the **balance between static verification and testing**.
- Test planning defines **standards for the testing process**, not specific product tests.

### The V-Model of Development
The V-model establishes a direct correspondence between development stages (left side) and testing stages (right side):
- Requirements Analysis corresponds to Acceptance Testing
- System Design corresponds to System Testing
- Architecture Design corresponds to Integration Testing
- Module Design corresponds to Unit Testing
- Each testing level validates the artifacts produced at its corresponding development level.

### Static vs. Dynamic Verification
- **Static verification (Software inspections):** Concerned with analysis of the static system representation to discover problems. Does not require execution. May be supported by tool-based document and code analysis.
- **Dynamic verification (Software testing):** Concerned with exercising and observing product behavior. The system is executed with test data and its operational behavior is observed.

### Testing Fundamentals
- **Program testing can reveal the presence of errors, NOT their absence** — this is a fundamental limitation.
- Testing should be used **in conjunction with** static verification to provide full V&V coverage.
- Cost statistics that illustrate the importance of testing:
  - $100,000 is the average cost of a single hour of downtime
  - 48% of users are less likely to use an app again after poor performance
  - 88% of Americans form negative opinions of brands with poorly performing apps
- Testing effort statistics:
  - Testing comprises about **30–80% of total SDLC time**
  - Testing is about **50% of total application development cost**
  - Testing can account for **70% of costs** during the application lifecycle

### The Testing Process
- **Component testing:** Testing of individual program components. Usually the responsibility of the component developer. Tests are derived from developer experience.
- **System testing:** Testing of groups of components integrated to create a system or sub-system. The responsibility of an **independent testing team**. Tests are based on the system specification.

### Testing Process Goals
- **Defect testing:** Discovering faults or defects where behavior is incorrect or does not conform to specification. A successful defect test is one that **makes the system perform incorrectly** and thus exposes a defect.
- **Validation testing:** Demonstrating to the developer and customer that the software meets its requirements. A successful validation test shows the system **operates as intended**.

### Testing Policies
- Only exhaustive testing can show a program is free from defects, but **exhaustive testing is impossible**.
- Testing policies define the approach for selecting system tests. Examples:
  - All functions accessed through menus should be tested
  - Combinations of functions accessed through the same menu should be tested
  - Where user input is required, all functions must be tested with both correct and incorrect inputs

### Types of Testing
- **White-box testing:** The tester has access to the source code. Tests are designed based on internal structure and logic.
- **Black-box testing (functional testing):** The tester interacts with the software only through inputs and outputs. No access to source code or internal structure.
- **Grey-box testing:** The tester has no access to the source code but **does** have knowledge of the software structure (e.g., architecture diagrams, database schemas).

### Testing and Debugging
- Defect testing and debugging are **distinct processes**.
- V&V is concerned with **establishing the existence** of defects in a program.
- Debugging is concerned with **locating and repairing** these errors.
- Debugging involves formulating a hypothesis about program behavior, then testing these hypotheses to find the system error.

### System Testing
System testing involves integrating components to create a system or sub-system. It has two major phases:

#### Integration Testing
- Building a system from its components and testing for problems arising from **component interactions**.
- Systems should be **incrementally integrated** to simplify error localisation.
- Incremental integration involves adding components one at a time and testing after each addition, rather than integrating everything at once ("big bang" integration).

#### Release Testing
- Testing a release of a system that will be distributed to customers.
- Primary goal: increase the supplier's confidence that the system meets its requirements.
- Release testing is usually **black-box** — based on the system specification only; testers do not have knowledge of implementation.

#### Performance Testing
- Part of release testing; tests emergent properties such as performance, reliability, and security.
- Involves planning a series of tests where the **load is steadily increased** until system performance becomes unacceptable.

### Test Cases from Use Cases
- Use cases can be a basis for deriving test cases for a system.
- They help identify **operations to be tested** and help design required test cases.
- From an associated **sequence diagram**, the inputs and outputs to be created for the tests can be identified.
- **Weather station example:** Issuing a request for a report results in the following method thread:
  `SatComms:request` -> `WeatherStation:reportWeather` -> `Commslink:Get(summary)` -> `WeatherData:summarize`

### Test Plan Structure
A software test plan typically has seven components:
1. **The testing process:** Description of the major phases of testing
2. **Requirements traceability:** Ensuring all requirements are individually tested
3. **Tested items:** Specifying the software process products to be tested
4. **Testing schedule:** Overall testing schedule and resource allocation
5. **Test recording procedures:** Systematic recording of test results for auditing
6. **Hardware and software requirements:** Tools required and estimated hardware utilisation
7. **Constraints:** Anticipated constraints such as staff shortages
### Equivalence Partitioning
- An **equivalence class** is a subset of data that is representative of a larger class.
- Equivalence partitioning tests representative values from equivalence classes rather than exhaustive testing.
- A group of tests forms an equivalence class if:
  - They all test the same thing
  - If one test catches a bug, the others probably will too
  - If one test does not catch a bug, the others probably will not either
- It is sufficient to pick **one test input from each equivalence class**.
- The goal is to **minimize the number of test cases** while covering all input conditions.

**Guidelines for creating equivalence classes:**

| Input Condition | Valid Classes | Invalid Classes |
|-----------------|--------------|-----------------|
| Range (e.g., a <= X <= b) | 1 valid: a <= X <= b | 2 invalid: X < a, X > b |
| Specific value | 1 valid: the value | 2 invalid: below and above |
| Boolean | 1 valid: true/false | 1 invalid: the other |
| Member of a set | 1 valid: in the set | 1 invalid: not in the set |

**Credit limit example ($10,000–$15,000):** Three equivalence classes:
1. Less than $10,000 (invalid)
2. Between $10,000 and $15,000 (valid)
3. Greater than $15,000 (invalid)

**Non-numeric data partitioning:** For a program taking character X and string Y:
- X: equivalence classes for lowercase characters (task T1) and uppercase characters (task T2)
- Y: equivalence classes for null string (task T3) and all other strings (task T4)

### Boundary Value Analysis (BVA)
- BVA generates test cases by looking for **boundary values** — the edges of equivalence classes.
- Inputs may lie **on the boundary**, **just inside**, or **just outside** the boundary.
- BVA is more targeted than arbitrary equivalence class sampling because errors tend to cluster at boundaries.

**Credit limit BVA example ($10,000–$15,000):**
- Low boundary: $9,999 (just below), $10,000 (on boundary), $10,001 (just above)
- Upper boundary: $14,999 (just below), $15,000 (on boundary), $15,001 (just above)

**Two-variable BVA (rectangle heuristic):**
For two integer inputs X and Y where x1 <= X <= x2 and y1 <= Y <= y2, select 14 test points:
- 4 corner points (1, 2, 3, 4)
- 4 points just outside each side (5, 6, 7, 8)
- 4 points just inside each side (10, 11, 12, 13)
- 1 point inside the bounded region (9)
- 1 point outside the bounded region (14)

**BVA applied to output variables:** Just as BVA applies to input data, it can be applied to output data to create equivalence classes for the output domain, then find test inputs that cover each output equivalence class.

### Error Guessing
- An **ad hoc** approach based on the **intuition and experience** of the test engineer.
- The idea is to make a list of possible errors or error-prone situations and develop tests based on the list.
- Examples:
  - If one input is a date, try February 29, 2000 or September 9, 1999
  - If there is a division operation A = B/C, test with C = 0

### Software Inspection (Static White-Box Verification)
- People examine the **source representation** to discover anomalies and defects.
- Does not require execution of the system — can be used **before implementation**.
- Can be applied to any representation: requirements, design, configuration data, test data.
- **Multiple defects** may be discovered in a single inspection (in testing, one defect may mask another).
- Inspections and testing are **complementary**, not opposing techniques.
- Inspections can check conformance with a specification but **cannot** check:
  - Conformance with customer's real requirements
  - Non-functional characteristics (performance, usability)

**Inspection pre-conditions, roles, and process:** Formalised approach with defined roles (author, reader, inspector, moderator) and a structured process including planning, overview, individual preparation, inspection meeting, rework, and follow-up.

**Inspection checklists:** Language-dependent checklists of common errors drive the inspection. The weaker the type checking in the language, the larger the checklist. Examples: initialization errors, constant naming, loop termination, array bounds.

**Inspection rate:**
- 500 statements/hour during overview
- 90–125 statements/hour during individual preparation
- Inspecting 500 lines costs approximately **40 man-hours** of effort

### Automated Static Analysis
- Automated analysis of source code **without executing** the application.
- Parses program text to discover potentially erroneous conditions.
- Very effective as an **aid to inspections** — a supplement to, but **not a replacement for**, inspections.

### Control Flow Graphs (CFGs)
- A CFG is a representation of the flow of execution within a program.
- Formally: **G = (N, A)** where N is the set of nodes and A is the set of arcs.
- There is a **unique entry node** (en) and a **unique exit node** (ex).
- A **node** represents a single statement or a **block** (single-entry-single-exit sequence of instructions always executed in sequence).
- Every statement in a block, except possibly the first, has exactly one predecessor; every statement except possibly the last has exactly one successor.
- An **arc** (n, m) represents transfer of control from node n to node m.
- A **path** of length k is an ordered sequence of arcs a1, a2, ..., ak where a1 starts at en and ak ends at ex.
- A path is **executable (feasible)** if there exists a test case that causes it to be traversed; otherwise it is **unexecutable (infeasible)**.

### def-use Analysis
- **def** = definition of a variable (assignment of a value)
- **c-use** (computational use) = the variable is used in a computation (e.g., `b = 3 + d` — variable d has a c-use)
- **p-use** (predicate use) = the variable is used in a decision/condition (e.g., `if (b > 6)` — variable b has a p-use)

**def-use analysis can reveal bugs:**
- A variable that is **defined but never used**
- A variable that is **used but never defined**
- A variable that is **defined twice before it is used**

**Staff discount program example:**
```
1  program Example()
2  var staffDiscount, totalPrice, finalPrice, discount, price
3  staffDiscount = 0.1
4  totalPrice = 0
5  input(price)
6  while(price \!= -1) do
7    totalPrice = totalPrice + price
8    input(price)
9  od
10 print("Total price: " + totalPrice)
11 if(totalPrice > 15.00) then
12   discount = (staffDiscount * totalPrice) + 0.50
13 else
14   discount = staffDiscount * totalPrice
15 fi
16 print("Discount: " + discount)
17 finalPrice = totalPrice - discount
```

def-use table for key variables:

| Variable | def (lines) | c-use (lines) | p-use (lines) |
|----------|-------------|----------------|----------------|
| staffDiscount | 3 | 12, 14 | — |
| totalPrice | 4, 7 | 7, 10, 12, 14, 17 | 6, 11 |
| price | 5, 8 | 7 | 6 |
| discount | 12, 14 | 16, 17 | — |
| finalPrice | 17 | — (potential bug: defined but never used after) | — |

Note: `finalPrice` is defined on line 17 but never used afterward — this is a potential bug that def-use analysis reveals.

### Structure-Based Test Adequacy (Coverage Criteria)

#### Statement Coverage
- The coverage domain consists of **all statements** (all nodes in the CFG).
- A test set T satisfies statement coverage if every statement in the program is executed at least once.

**Weakness example — buggy abs function:**
```c
int abs(int x) {
    if (x >= 0) x = 0 - x;
    return x;
}
```
This function is **incorrect** — when x >= 0, it negates x (returning a negative value instead of the original positive value). The correct code should be `if (x < 0) x = 0 - x;`. A test case T = {x = 1} achieves 100% statement coverage (both the if-body and the return execute), yet the bug is exposed only if we check expected vs. actual output. This illustrates that **statement coverage alone is insufficient** to guarantee correctness.

#### Branch/Edge Coverage
- Each **condition node** in the CFG must evaluate to both **true** and **false** during some execution.
- Branch coverage is stronger than statement coverage — satisfying branch coverage implies statement coverage.
- Example: For the abs function, we need at least two test cases: one where x >= 0 (true branch) and one where x < 0 (false branch).

**Weakness example — buggy check function:**
```c
int check(int x) {
    if ((x >= 0) && (x <= 10))    // BUG: x <= 10 should be x <= 100
        return true;
    else
        return false;
}
```
This program is supposed to check if x is in the range 0 to 100 (inclusive), but the code says `x <= 10` instead of `x <= 100`. Branch coverage with T = {x = 5, x = -1} covers both true and false branches but does **not** reveal the error because neither test case falls in the range 11–100 where the bug manifests. This shows that **branch coverage can miss errors in compound conditions**.

#### Condition Coverage
- Condition nodes may have **compound conditions** (e.g., `(x >= 0) && (x <= 10)`).
- Condition coverage requires that all **elementary conditions** within a compound condition evaluate to both true and false.
- For the check function, the elementary conditions are `x >= 0` and `x <= 10`. Condition coverage requires test cases that make each of these individually true and false.
- Condition coverage is stronger than branch coverage for compound conditions.

#### Path Coverage
- A path is a sequence of statements from the **entry node** to the **exit node** of the CFG.
- A test set T satisfies path coverage if **all paths** from entry to exit are executed at least once.
- Path coverage is the **strongest** of the four criteria but often impractical — programs with loops can have an **enormous or infinite number** of paths.
- Example: A function with three sequential if-statements (no else) has 2^3 = 8 possible paths.
## Definitions

| Term | Definition |
|------|------------|
| Validation | Confirming that the software meets the user's actual requirements — "Are we building the right product?" |
| Verification | Confirming that the software conforms to its specification — "Are we building the product right?" |
| V&V (Verification and Validation) | A whole life-cycle process for discovering defects and assessing system usefulness and usability |
| Static Verification | Analysis of the static system representation (source code, documents) without executing the system |
| Dynamic Verification | Testing the system by executing it with test data and observing its operational behavior |
| Software Inspection | A formalised review process where people examine source representations to discover anomalies and defects |
| Defect Testing | Testing aimed at discovering faults where behavior is incorrect or non-conformant with specification |
| Validation Testing | Testing aimed at demonstrating the software meets its requirements; a successful test shows correct operation |
| Component Testing | Testing of individual program components, usually by the developer |
| System Testing | Testing of integrated groups of components, usually by an independent testing team |
| Integration Testing | Building a system from components and testing for problems arising from component interactions |
| Release Testing | Black-box testing of a system release intended for distribution to customers |
| Performance Testing | Testing where load is steadily increased to determine when system performance becomes unacceptable |
| White-Box Testing | Testing where the tester has access to the source code and designs tests based on internal logic |
| Black-Box Testing | Testing where the tester has no access to source code or structure; tests based on inputs and outputs only |
| Grey-Box Testing | Testing where the tester has no source code access but has knowledge of the software's structure |
| Equivalence Partitioning | A technique that divides the input domain into equivalence classes, testing one representative from each |
| Equivalence Class | A subset of data that is representative of a larger class; all members expected to produce equivalent behavior |
| Boundary Value Analysis (BVA) | A testing technique that generates test cases at and near the boundaries of equivalence classes |
| Error Guessing | An ad hoc testing approach based on tester intuition and experience to identify likely error conditions |
| Control Flow Graph (CFG) | A directed graph G = (N, A) representing the flow of execution, with nodes for statements and arcs for control transfers |
| Block (in CFG) | A single-entry-single-exit sequence of instructions always executed in sequence without path diversion |
| Feasible Path | A path through the CFG for which a test case exists that causes the path to be traversed |
| Infeasible Path | A path through the CFG that cannot be traversed by any test case |
| def (definition) | An occurrence of a variable on the left side of an assignment; the variable receives a value |
| c-use (computational use) | A use of a variable in a computation (e.g., in an arithmetic expression) |
| p-use (predicate use) | A use of a variable in a decision or condition (e.g., in an if-statement predicate) |
| Statement Coverage | Test adequacy criterion requiring every statement (node) in the program to be executed at least once |
| Branch Coverage (Edge Coverage) | Test adequacy criterion requiring every condition node to evaluate to both true and false |
| Condition Coverage | Test adequacy criterion requiring every elementary condition in compound conditions to evaluate to both true and false |
| Path Coverage | Test adequacy criterion requiring every path from entry to exit in the CFG to be traversed at least once |
| Debugging | The process of locating and repairing errors after defects have been discovered through testing |
| Test Plan | A document defining testing standards, requirements traceability, tested items, schedule, recording procedures, and constraints |
| Automated Static Analysis | Automated parsing of source code without execution to discover potentially erroneous conditions |
| Exhaustive Testing | Testing all possible input combinations; theoretically the only way to prove absence of defects, but practically impossible |
## Diagrams & Visual Descriptions

### The V-Model of Development (Slide 10)
The V-model is a diagram shaped like the letter "V" showing the correspondence between development phases and testing phases:

```
Requirements Analysis                        Acceptance Testing
         \                                      /
    System Design                      System Testing
              \                          /
        Architecture Design      Integration Testing
                   \              /
              Module Design   Unit Testing
                        \    /
                     Coding/Implementation
```

The left side descends from high-level requirements through increasingly detailed design. The right side ascends from low-level unit testing through increasingly integrated testing. Each testing level on the right directly validates the corresponding development artifact on the left. The bottom of the V is the coding/implementation phase. This model emphasizes that testing activities should be planned in parallel with development activities, not as an afterthought.

### Incremental Integration Testing (Slide 31)
A diagram showing the incremental integration approach in three stages:
1. **Stage 1:** Component A is tested individually, then Component B is tested individually.
2. **Stage 2:** Components A and B are integrated and tested together (A+B). Component C is tested individually.
3. **Stage 3:** A+B is integrated with C and tested as a complete system (A+B+C).

```
Stage 1:  [A] tested    [B] tested    [C] tested

Stage 2:  [A+B] tested together       [C] tested

Stage 3:  [A+B+C] tested as complete system
```

This contrasts with "big bang" integration where all components are combined at once, making error localization difficult.

### Equivalence Partitioning Diagram (Slide 43)
A number line divided into three regions for the credit limit example:

```
  Invalid            Valid              Invalid
  (< $10,000)    ($10,000-$15,000)    (> $15,000)
  |______________|____________________|_____________|
              $10,000              $15,000
```

One test case is selected from each partition. The diagram illustrates that testing any single value within a partition is representative of all values in that partition.

### Two-Variable BVA Rectangle (Slides 59–61)
A rectangle in the X-Y plane with 14 numbered test points:

```
              x1                    x2
        y2  +--2----6---------3--+
            | 13         12      |
            |                    |
            5 10      9     11   8
            |                    |
        y1  +--1----5---------4--+
            |  7              14 |
           y1-1              x2+1
           x1-1

  Legend:
  1-4:   Corner points (x1,y1), (x1,y2), (x2,y1), (x2,y2)
  5-8:   Points just outside each of the four sides
  9:     Point inside the bounded region
  10-13: Points just inside each of the four sides
  14:    Point outside the bounded region
```

This heuristic ensures thorough testing of boundary conditions for two-variable input domains.

### Control Flow Graph Example (Slides 86–87)
A CFG for a simple program with an if-else structure:

```
    [Entry: int m = n * n]
             |
        [if (n < 0)]
         /         \
  [return 0]   [return m]
         \         /
        [Exit node]
    (printf unreachable)
```

Note: The `printf("Good bye.")` statement after the return statements is **unreachable code** — a defect that CFG analysis can reveal.

### Weather Station Sequence Diagram (Slides 36–37)
A sequence diagram showing the method thread for requesting a weather report:

```
  SatComms    WeatherStation    Commslink    WeatherData
     |              |              |              |
     |--request---->|              |              |
     |              |--Get(summary)-------->      |
     |              |              |--summarize-->|
     |              |              |<--summary----|
     |              |<--summary----|              |
     |<--report-----|              |              |
     |<--acknowledge|              |              |
```

This diagram shows how test cases can be derived from sequence diagrams: each method call represents a testable operation, and the inputs/outputs at each interaction point define test data requirements.
## Code Examples

### Buggy abs Function (Statement Coverage Weakness)
```c
int abs(int x) {
    if (x >= 0) x = 0 - x;  // BUG: should be if (x < 0)
    return x;
}
```
**Bug explanation:** When x is positive (e.g., x = 5), the condition `x >= 0` is true, so the function executes `x = 0 - 5 = -5` and returns -5. The absolute value of 5 should be 5, not -5. The correct implementation should negate x only when x is negative. This example demonstrates that 100% statement coverage with T = {x = 1} executes all statements but the test **reveals** the bug only if we check expected vs. actual output carefully.

### Buggy check Function (Branch Coverage Weakness)
```c
int check(int x) {
    if ((x >= 0) && (x <= 10))    // BUG: x <= 10 should be x <= 100
        return true;
    else
        return false;
}
```
**Bug explanation:** The specification says the function should check if x is in the range 0 to 100, but the code says `x <= 10` instead of `x <= 100` due to a typo. Branch coverage with T = {x = 5, x = -1} achieves both true and false branches but misses the error. A value like x = 50 (which should return true but returns false) would expose the bug but is not required by branch coverage alone.

### Staff Discount Program (def-use Analysis)
```
 1  program Example()
 2  var staffDiscount, totalPrice, finalPrice, discount, price
 3  staffDiscount = 0.1           // def: staffDiscount
 4  totalPrice = 0                // def: totalPrice
 5  input(price)                  // def: price
 6  while(price \!= -1) do         // p-use: price
 7    totalPrice = totalPrice + price  // def: totalPrice; c-use: totalPrice, price
 8    input(price)                // def: price
 9  od
10  print("Total price: " + totalPrice)  // c-use: totalPrice
11  if(totalPrice > 15.00) then   // p-use: totalPrice
12    discount = (staffDiscount * totalPrice) + 0.50  // def: discount; c-use: staffDiscount, totalPrice
13  else
14    discount = staffDiscount * totalPrice  // def: discount; c-use: staffDiscount, totalPrice
15  fi
16  print("Discount: " + discount)  // c-use: discount
17  finalPrice = totalPrice - discount  // def: finalPrice; c-use: totalPrice, discount
```
**Potential bug detected by def-use analysis:** `finalPrice` is defined on line 17 but never used afterward — the program never prints or returns `finalPrice`, suggesting either a missing output statement or dead code.

### CFG Exercise Code
```c
int f(int n) {
    int m = n * n;
    if (n < 0)
        return 0;
    else
        return m;
    printf("Good bye.");  // Unreachable code\!
}
```
**Analysis:** The `printf` statement on the last line is unreachable because both branches of the if-else contain return statements. This is a defect that CFG analysis and static analysis tools can detect — the node for `printf` has no incoming arcs from any reachable node.

### def-use Exercise Code
```
sum = 0        // def: sum
i = 1          // def: i
while (i < N) do    // p-use: i, N
{
    sum = sum + 1;  // def: sum; c-use: sum (NOTE: likely bug — should be sum = sum + i)
    i = i + 1;      // def: i; c-use: i
}
```
**Potential bug:** The statement `sum = sum + 1` likely should be `sum = sum + i` to compute the sum of integers from 1 to N-1. The variable `i` has a c-use only in `i = i + 1` for incrementing, but is never used in the computation of `sum`, which is suspicious.
## Formulas & Algorithms

### Test Case Count for Equivalence Partitioning
For an input condition specifying a range [a, b]:
- Number of equivalence classes = 3 (one valid: a <= X <= b, two invalid: X < a and X > b)
- Minimum test cases = 3 (one from each class)

### BVA Test Points for Single Variable
For a range [a, b], BVA generates 6 test points:

```
{a-1, a, a+1, b-1, b, b+1}
```

### BVA Test Points for Two Variables
For x1 <= X <= x2 and y1 <= Y <= y2, BVA generates **14 test points**:
- 4 corner points
- 4 outside boundary points
- 4 inside boundary points
- 1 interior point
- 1 exterior point

### Coverage Criterion Strength Hierarchy

```
Path Coverage > Condition Coverage > Branch Coverage > Statement Coverage
```

Path coverage subsumes condition coverage, which subsumes branch coverage, which subsumes statement coverage. Each successive criterion is strictly stronger (more demanding) than the previous.

### Path Count with Independent If-Statements
For a program with n independent sequential if-statements (each with two branches):

```
Number of paths = 2^n
```

Example: 3 sequential if-statements = 2^3 = 8 paths.

### Inspection Effort Estimation
- Overview rate: 500 statements/hour
- Individual preparation rate: 90–125 statements/hour
- For 500 lines of code: approximately **40 man-hours** total effort

### CFG Formal Definition
A control flow graph is defined as:

```
G = (N, A)
```

where:
- N = set of nodes (statements or blocks)
- A = set of arcs (control transfer edges)
- There exists a unique entry node (en) in N
- There exists a unique exit node (ex) in N
- A path of length k: a1, a2, ..., ak where for adjacent arcs ai = (n, m), aj = (p, q): m = p

## Key Takeaways

- **Verification checks conformance to specification; validation checks conformance to user needs** — both are essential and neither alone is sufficient.
- **V&V is a whole life-cycle process**, not a phase — it must be applied at every stage of software development.
- **Testing can reveal the presence of errors but NOT their absence** — this is a fundamental theoretical limitation.
- **Testing is enormously expensive**: 30–80% of SDLC time, 50% of development cost, and up to 70% of lifecycle cost. Efficient test design is critical.
- **Exhaustive testing is impossible** — testing policies and systematic techniques (equivalence partitioning, BVA) are needed to select effective test cases.
- **Static verification (inspections) and dynamic verification (testing) are complementary**, not opposing — use both for full V&V coverage.
- **Equivalence partitioning** reduces the test space by grouping inputs into classes where all members are expected to behave equivalently; test one from each class.
- **Boundary value analysis** focuses on boundaries where errors tend to cluster — test at, just inside, and just outside each boundary.
- **Software inspections can find multiple defects in a single session** (unlike testing where one defect can mask others) and are cost-effective at approximately 40 man-hours per 500 lines.
- **Coverage criteria form a hierarchy**: statement < branch < condition < path, with each level providing stronger assurance but requiring more test cases.
- **Statement coverage alone is weak** — it can miss bugs in conditional logic; branch and condition coverage provide stronger guarantees.
- **def-use analysis** reveals subtle bugs: variables defined but never used, used but never defined, or defined twice before use.
- **Control flow graphs** provide the formal foundation for all structural (white-box) coverage criteria and enable systematic path analysis.
- **Use cases and sequence diagrams directly drive test case design** — the inputs and outputs visible in sequence diagrams define test data requirements.
- **Automated static analysis supplements but does not replace** human inspection — both are needed for thorough static verification.
- **Debugging is distinct from testing** — testing finds that defects exist; debugging locates and repairs them through hypothesis formulation and testing.

## Connections

This lecture builds directly on the **V-model introduced in Week 2**, which established the correspondence between development stages and testing levels — Week 8 now explains what actually happens at each testing level and how test cases are designed. The use of **use cases (Week 4) and sequence diagrams (Week 6)** as sources for deriving test cases demonstrates how analysis and design artifacts feed directly into V&V activities — the weather station example shows exactly how a sequence diagram's method calls become testable operations with defined inputs and outputs. The **CI/CD pipeline concepts from Week 7** depend heavily on automated testing — the coverage criteria (statement, branch, condition, path) studied here define what "adequate" automated test suites look like in continuous integration environments. Looking ahead to **Week 9 (DevOps and Continuous Testing)**, the testing foundations established here — particularly automated static analysis and structural coverage metrics — become the quality gates in deployment pipelines. The emphasis on software inspections connects to the **quality assurance principles from Week 2**, while the cost statistics (30–80% of SDLC time) reinforce why process models like Agile emphasize test-driven development. The def-use analysis and CFG techniques bridge software engineering methodology with the formal methods hinted at in Week 1's discussion of rigor and formality as SE principles.
