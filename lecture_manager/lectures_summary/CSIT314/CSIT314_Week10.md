# CSIT314 — Week 10: Ethics and Professional Practice / Future Trends

> **Source files:** CSIT314_Week10.pptx, CSIT314_Week10_v2.pptx
> **Date summarized:** 2026-02-24

## Overview

This two-part lecture addresses the ethical responsibilities of software engineers and surveys emerging trends shaping the software development industry. Part A examines what it means to be a professional, the relationship between society, morality, and ethics, the IEEE/ACM Software Engineering Code of Ethics, virtue ethics, and the ethical challenges posed by AI development. Part B explores five key industry trends: low-code/no-code platforms, cloud computing growth, rising cybersecurity threats, accelerating AI adoption, and the Rust programming language. Together, these topics prepare students to think critically about their professional obligations and the evolving landscape they will enter upon graduation.

---

## Key Concepts

### Professions and Professionalism

A **profession** is characterized by three core attributes:
- **High level of education** — formal academic training is required.
- **Practical experience** — hands-on application of knowledge in real-world settings.
- **Decisions have impact** — professional decisions affect other people, organizations, or society.

Society pays professionals well (e.g., doctors, lawyers) because we expect them to **act for the public good**. Software engineering increasingly fits this definition as software systems become critical infrastructure.

**Characteristics of Professionals** follow a developmental pathway:
1. **Initial professional education** — foundational academic degree
2. **Accreditation** — program or institution meets quality standards
3. **Skills development** — building competence through practice
4. **Certification** — formal recognition of knowledge/skills
5. **Licensing** — legal authorization to practice
6. **Professional development** — ongoing learning throughout career
7. **Code of ethics** — adherence to a shared moral framework
8. **Professional society** — membership in a body that upholds standards

### Ethics and Morality

Three nested concepts are distinguished through an illustrative metaphor:

- **Society** — an association of people organized under a system of rules designed to enhance the overall good. (Metaphor: a town full of people driving cars — everyone participates in a shared system.)
- **Morality** — the rules of conduct describing what people ought and ought not to do in various situations. (Metaphor: the road networks — they constrain and guide behavior.)
- **Ethics** — the philosophical study of morality; a rational examination of people's moral beliefs and behaviour. (Metaphor: those who study ethics float in balloons above the town — they observe and analyze the rules from a higher vantage point.)

### Case Study: The Startup Dilemma

A senior software engineer at a startup faces a critical decision:
- The company has developed a smartphone app for generating and emailing sales quotes and invoices.
- A major corporation expects the product next week.
- The testing team reports only minor known bugs but needs **another month** to confirm no catastrophic errors.
- A well-established competitor will release a similar product in a few weeks — if they launch first, the startup will likely go out of business.

**Ethical questions raised:**
1. Should you recommend releasing the product next week?
2. Who will **benefit** if the company follows your recommendation?
3. Who will be **harmed** if the company follows your recommendation?
4. Do you have an **obligation** to any group of people affected by your decision?
5. What **additional information** would help you answer the previous questions?

This case study illustrates the tension between business survival, professional responsibility, and user safety — a recurring theme in software ethics.

### Software Engineers Code of Ethics (IEEE/ACM)

The Code contains **8 principles** that software engineers should adhere to:

| Principle | Description |
|-----------|-------------|
| **1. Public** | Act consistently with the public interest |
| **2. Client and employer** | Act in a manner that is in the best interests of client and employer, consistent with the public interest |
| **3. Product** | Ensure products meet the highest professional standards possible |
| **4. Judgment** | Maintain integrity and independence in professional judgment |
| **5. Management** | Promote an ethical approach to the management of software development and maintenance |
| **6. Profession** | Advance the integrity and reputation of the profession |
| **7. Colleagues** | Be fair to and supportive of colleagues |
| **8. Self** | Participate in lifelong learning and promote an ethical approach to practice |

**Key points about interpreting the Code:**
- There is **no mechanical process** for determining if an action is right or wrong.
- One should **not take an overly legalistic view** of the Code.
- If the Code does not explicitly forbid something, that does **not** mean it is morally acceptable.
- **Judgment is required** — the Code is a guide, not a rulebook.
- The Code reflects principles drawn from **multiple ethical theories**.

### Virtue Ethics

Virtue ethics focuses on the character of the moral agent rather than on rules or consequences.

**Key virtues:** benevolence, courage, fairness, generosity, honesty, loyalty, patience, tolerance.

A person of **strong moral character**:
- Possesses many virtues
- Knows the right thing to do in each situation

| Strengths | Weaknesses |
|-----------|------------|
| Provides a **motivation** for good behavior | Offers **no methodology** for answering specific moral problems |
| Provides a solution to the **problem of impartiality** — some virtues are partial (e.g., generosity toward specific people) while others must be impartial (e.g., honesty toward everyone) | Given a problem, **which virtues apply?** |
| | How to **resolve a conflict** between more than one virtue? |

### Alternative 9 Fundamental Principles

The lecture references an alternative set of 9 fundamental principles as a complementary ethical framework. These provide additional guidance beyond the 8-principle IEEE/ACM code and are used alongside the ACM principles in the in-class activity on AI ethics.

### Ethics in AI Software Development

An **in-class activity (ICA)** asks student groups to:
1. Use an allocated **ACM principle** and the Alternative Fundamental Principles.
2. Research a real **software development scandal involving Artificial Intelligence**.
3. Develop a set of **guidelines for AI developers** with justification.
4. Present findings as a poster to the class.

This activity highlights that AI systems pose unique ethical challenges — bias in training data, lack of transparency in decision-making, potential for harm at scale — and that existing codes of ethics must be actively applied to emerging technologies.

### Trend 1: Low-Code / No-Code Development

- Does not require advanced IT knowledge or coding skills.
- **No-code platforms** allow users to drag-and-drop blocks of pre-made code in a visual interface.
- **Low-code platforms** are more technically involved but provide shortcuts to accelerate development.
- Translates into **easier, faster development** cycles.
- **100% of enterprises** that adopted a low-code platform reported a **positive ROI**.

### Trend 2: Cloud Computing Increase (Driven by Remote Work)

- The pandemic forced businesses to expand remote work capabilities, causing a massive shift in IT needs.
- Cloud infrastructure was the primary enabler of this transition.
- **More than 90%** of survey respondents reported that cloud usage increased due to the pandemic.
- Cloud computing is equally useful for businesses that need to **scale down** — elasticity works in both directions.

### Trend 3: Malicious Software Development

- Cybersecurity remains a **major concern** for the foreseeable future.
- **Ransomware increased 435%** over 2019 levels (measured in 2020).
- Businesses need to invest in the right tools and practices to keep assets protected.
- This trend creates demand for security-focused software engineers.

### Trend 4: AI Adoption Accelerates

- The global AI market was valued at **$327.5 billion in 2021**.
- Projected to reach **$500 billion by 2024**.
- Growth exceeding 16% annually signals that AI integration will become a standard expectation across industries.

### Trend 5: Rust Gains Momentum

- Voted the **"most beloved language"** for four consecutive years in developer surveys.
- The **second-most used** programming language (at the time of the lecture).
- Key appeal: Rust is a **memory-safe language**, eliminating the risk of memory-related bugs.
- Also praised for **speed, security, and performance**.
- Relevant to the cybersecurity trend — memory safety addresses an entire class of vulnerabilities.

---

## Definitions

| Term | Definition |
|------|------------|
| **Profession** | An occupation requiring high-level education, practical experience, and whose practitioners make decisions that have significant impact on others |
| **Society** | An association of people organized under a system of rules designed to enhance the overall good |
| **Morality** | Rules of conduct within a society describing what people ought and ought not to do in various situations |
| **Ethics** | The philosophical study of morality; a rational examination of people's moral beliefs and behaviour |
| **Virtue Ethics** | An ethical theory that focuses on the moral character of the individual, emphasizing virtues such as honesty, courage, and fairness |
| **Code of Ethics** | A formal set of principles guiding the professional conduct of practitioners in a field |
| **Low-code Platform** | A development environment that provides shortcuts and visual tools to reduce the amount of hand-coding required, aimed at developers |
| **No-code Platform** | A development environment using drag-and-drop visual interfaces with pre-made code blocks, requiring no programming knowledge |
| **Ransomware** | Malicious software that encrypts a victim's data and demands payment for the decryption key |
| **Memory Safety** | A property of a programming language that prevents programs from accessing memory in invalid ways (e.g., buffer overflows, use-after-free) |
| **ROI** | Return on Investment — a measure of the profitability of an investment relative to its cost |
| **Accreditation** | A quality assurance process ensuring that an educational program or institution meets established standards |
| **Certification** | Formal recognition that a professional has demonstrated competence in a specific area |

---

## Diagrams & Visual Descriptions

### Society / Morality / Ethics Metaphor Illustration
The slide presents a layered visual metaphor:
- **Bottom layer (Society):** A town populated with people driving cars, representing the organized association of people living under shared rules for the common good.
- **Middle layer (Morality):** Road networks running through the town, representing the rules of conduct that guide behavior — the "ought" and "ought not" of daily life.
- **Top layer (Ethics):** People floating in balloons above the town, representing the philosophical study of morality — observing, questioning, and rationally examining the moral rules from a higher vantage point.

This metaphor effectively communicates the hierarchical relationship: society is the context, morality is the set of rules within that context, and ethics is the discipline that studies those rules.

### Software Engineers Code of Ethics Principles Diagram
A circular or segmented diagram showing the **8 principles** as distinct segments arranged around a central concept:
- **Public** | **Client and employer** | **Product** | **Judgment** | **Management** | **Profession** | **Colleagues** | **Self**

Each segment represents a stakeholder group or domain of responsibility. The visual emphasizes that a software engineer's ethical obligations extend in multiple directions simultaneously — not only to the employer but also to the public, the profession, colleagues, and oneself.

### Characteristics of Professionals Pathway
A sequential pathway or flowchart showing the progression of professionalism:

```
Initial Professional Education
        |
        v
   Accreditation
        |
        v
  Skills Development
        |
        v
   Certification
        |
        v
     Licensing
        |
        v
Professional Development
        |
        v
  Code of Ethics
        |
        v
Professional Society
```

This represents the journey from education to full professional standing, emphasizing that professionalism is not a single achievement but a continuous developmental process.

### Global Trends Statistic
A prominent display of the statistic **"29%"** — only 29% of software projects are successfully delivered on functionality, deadline, and budget. This stark number sets the stage for the trends discussion by highlighting that the software industry still faces fundamental challenges in project delivery.

### Low-Code/No-Code Development Trend
A growth chart or infographic showing the rise of low-code/no-code platforms, accompanied by the key statistic: **100% of enterprises with low-code platforms reported positive ROI**. Visual elements include representations of drag-and-drop interfaces and visual development environments.

### AI Market Growth
A visualization showing AI market trajectory:
- **2021:** $327.5 billion (global AI market value)
- **2024:** $500 billion (projected)
- **Growth rate:** 16%+ annually

This illustrates the rapid acceleration of AI adoption across industries.

---

## Code Examples

No code examples were presented in this lecture. The content is focused on ethics, professional practice, and industry trends rather than technical implementation. However, the discussion of **Rust** (Trend 5) is directly relevant to programming practice — Rust's memory safety model eliminates common bugs like buffer overflows and use-after-free errors at compile time through its ownership and borrowing system.

---

## Formulas & Algorithms

No mathematical formulas or algorithms were covered in this lecture. The content is conceptual and discussion-based, focusing on ethical frameworks and industry analysis.

---

## Key Takeaways

### Ethics and Professional Practice (Part A)
- Software engineering is a **profession** — practitioners have a responsibility to the public, not just to employers or clients.
- **Ethics, morality, and society** are distinct but related concepts: society provides the context, morality provides the rules, and ethics provides the analytical framework.
- The **IEEE/ACM Code of Ethics** has 8 principles covering obligations to the public, clients, product quality, judgment, management, the profession, colleagues, and self-development.
- The Code is a **guide, not a rulebook** — it requires judgment and cannot be applied mechanically. Silence on an issue does not imply permission.
- **Virtue ethics** provides motivation for good behavior but lacks a clear methodology for resolving specific dilemmas or conflicts between virtues.
- Ethical considerations in **AI development** are especially urgent — existing codes of ethics must be actively applied to new technologies, not assumed to cover them by default.
- Real-world ethical dilemmas (like the startup case study) rarely have clear-cut answers — they involve **trade-offs** between competing interests and obligations.

### Future Trends (Part B)
- Only **29% of software projects** are delivered successfully on functionality, deadline, and budget — the industry has significant room for improvement.
- **Low-code/no-code** platforms democratize software development and deliver measurable ROI.
- **Cloud computing** has become essential infrastructure, accelerated by the pandemic and remote work.
- **Cybersecurity threats** (especially ransomware, up 435%) are growing faster than defenses — security expertise is in high demand.
- **AI adoption** is accelerating rapidly ($327.5B to $500B market in three years), making AI literacy essential for all software engineers.
- **Rust** is gaining momentum as a memory-safe, high-performance language — relevant for security-critical and systems-level development.

---

## Connections

### Within CSIT314
- This lecture builds on the **software development methodologies** covered throughout the course by adding the ethical dimension — no methodology is complete without considering the moral implications of what is being built and how it is delivered.
- The case study connects to earlier discussions of **project management** — the tension between deadlines, quality, and stakeholder expectations is a recurring theme in Agile, Waterfall, and other methodologies.
- The future trends discussion contextualizes the methodologies learned in the course within the **current industry landscape** — understanding where the industry is heading helps students choose which skills and practices to prioritize.

### Broader CS Connections
- **CSIT321 (Graduation Project):** The lecture explicitly connects to CSIT321, encouraging students to consider these trends and ethical frameworks when planning their graduation projects.
- **Software Quality Assurance:** The startup case study directly relates to testing and quality assurance — releasing untested software raises both ethical and practical concerns.
- **Cybersecurity:** Trend 3 (malicious software) and Trend 5 (Rust's memory safety) connect to security courses and the growing importance of secure development practices.
- **Cloud Computing and Distributed Systems:** Trend 2 connects to infrastructure and architecture topics covered in networking and systems courses.
- **Artificial Intelligence:** Trend 4 and the AI ethics activity connect to AI/ML courses, emphasizing that technical competence in AI must be paired with ethical awareness.
- **Programming Languages:** The discussion of Rust connects to programming language theory — memory safety through ownership models represents a different paradigm from garbage collection (Java, Python) or manual management (C, C++).
