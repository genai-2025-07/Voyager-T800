# **Developer Guide: AI-Assisted Development with Cursor Rules**

This document outlines the structure, purpose, and usage patterns of the Cursor rules implemented in the "Voyager-T800" project. These rules are a living part of our codebase, designed to encode our best practices, accelerate development, and maintain high code quality.

### **Philosophy: Why We Use Rules**

The `.cursor/rules` system acts as a **programmatic style guide and architectural expert** that is always available. Its purpose is to:

*   **Encode Expertise:** Capture our decisions about architecture, security, and coding standards.
*   **Reduce Cognitive Load:** Free you from having to remember every convention and boilerplate pattern.
*   **Ensure Consistency:** Apply the same patterns and standards across the entire codebase.
*   **Accelerate Onboarding:** Help new developers write high-quality code that aligns with project standards from day one.

---

### **The Rules Structure: Where to Find Things**

Our rules are organized in a nested structure that mirrors the project layout. This ensures that the AI's guidance is always relevant to the part of the codebase you are working on.

```
.
├── .cursor/rules/             # 1. Project-Wide Global Rules
│   ├── general-guidelines.mdc
│   ├── tech-stack-overview.mdc
│   └── security-and-privacy.mdc
│
├── app/
│   ├── .cursor/rules/         # 2. Core Application Rules
│   │   ├── api-best-practices.mdc
│   │   ├── langchain-patterns.mdc
│   │   └── ...
│   │
│   └── frontend/
│       └── .cursor/rules/     # 3. Specific Component Rules (Frontend)
│           ├── 1-general-frontend-principles.mdc
│           ├── 2-streamlit-guidelines.mdc
│           └── 3-react-guidelines.mdc
│
├── tests/
│   └── .cursor/rules/         # 3. Specific Component Rules (Tests)
│       └── testing-guidelines.mdc
│
└── docs/
    └── .cursor/rules/         # 3. Specific Component Rules (Docs)
        └── documentation-standards.mdc
```

1.  **Global Rules (`.cursor/rules/`):** These are the highest-level rules. They contain critical, non-negotiable standards like our security policy, general coding style (PEP 8), and an overview of the tech stack. Most of these are `alwaysApply: true`, meaning they are always in the AI's context.

2.  **Core Application Rules (`app/.cursor/rules/`):** This is where we define the core interaction patterns for our backend application. Rules for FastAPI, LangChain, Pydantic, and model integrations live here. They are generally `Auto Attached` with `globs` to activate when you are working with related files across the `app/` directory.

3.  **Specific Component Rules (e.g., `app/frontend/.cursor/rules/`):** These rules provide highly specific guidance for a particular part of the project. The frontend rules are only active when working on frontend code, and the testing rules are only active when writing tests. This keeps the AI's context focused and relevant.

---

### **Usage Patterns: How to Work with the Rules**

You will interact with these rules in three main ways, often without even realizing it.

#### **1. Automatic Context (The Magic)**

Most of the rules are configured as `Always` or `Auto Attached`. This means:

*   When you open any file, the global rules are automatically loaded.
*   When you start editing a file in `app/api/`, the `api-best-practices.mdc` rule is automatically attached to the AI's context.
*   When you ask the AI a question about your code (e.g., "how should I add an endpoint here?"), it already has the relevant guidelines and will provide an answer that aligns with our standards.

**Your Action:** Just code! The rules work in the background to help you.

#### **2. Manual Invocation (The Co-pilot)**

Sometimes you want to explicitly ask for guidance from a specific rule. You can do this by using the `@` symbol in the chat pane.

*   **Scenario:** You have a complex FastAPI endpoint and want to refactor it.
*   **Your Action:** In the chat, you can ask:
    > `@api-best-practices Can you review this endpoint and refactor it according to our standards?`

*   **Scenario:** You need to create a new LangChain chain and want to start with our preferred patterns.
*   **Your Action:**
    > `@langchain-patterns Please generate a boilerplate LangChain LCEL chain for retrieving data from a vector store and generating a response.`

#### **3. Creating and Maintaining Rules (The Gardener)**

These rules are a living part of the project. If you find yourself repeatedly giving the same instructions to the AI or writing the same boilerplate code, it's a sign that we need a new rule.

*   **Process:**
    1.  Create a new `.mdc` file in the appropriate `.cursor/rules/` directory.
    2.  Write the rule in clear, simple Markdown. Provide concrete examples.
    3.  Add the metadata (`description`, `type`, `globs`, etc.) at the top.
    4.  Commit the new rule with your code changes.

