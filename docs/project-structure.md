# Voyager T800 - Project Structure Guide

This document outlines project structure for the Voyager T800 AI Travel Assistant.

## Project Structure

```
.
├── app/                         # Core application logic
│   ├── agents/                  # Autonomous agents
│   ├── api/                     # FastAPI route handlers
│   ├── chains/                  # LangChain / LangGraph orchestration logic
│   ├── config/                  # Environment and settings configuration
│   ├── frontend/                # Frontend logic
│   ├── models/                  # Wrappers for LLMs and Vision APIs
│   │   ├── llms/                # LLM client integrations
│   │   └── image_analysis/      # Image Analysis client integrations
│   ├── prompts/                 # Prompt templates and utilities
│   ├── retrieval/               # Embedding-based search and vector DB logic
│   ├── services/                # Business logic
│   └── utils/                   # Shared utility functions
├── tests/                       # Unit and integration tests
└── docs/                        # Developer and project documentation
```