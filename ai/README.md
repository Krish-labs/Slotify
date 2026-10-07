# AI Module

This module handles natural language processing for timetable constraints.

## Architecture

```
Natural Language Input
         │
         ▼
┌─────────────────────┐
│  Constraint Parser  │  (converts NL → structured constraints)
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Requirement        │  (interprets scheduling requirements)
│  Interpreter        │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Conflict Explainer │  (explains conflicts in natural language)
└─────────────────────┘
         │
         ▼
   Structured Constraints
         │
         ▼
   Constraint Engine (OR-Tools CP-SAT)
```

## Important

The AI layer MUST NOT directly generate timetable entries.

Correct flow:
```
Natural Language → AI → Structured Constraints → Constraint Engine → OR-Tools CP-SAT → Timetable
```

## Components

- **prompts/** - Prompt templates for LLM interactions
- **schemas/** - JSON schemas for structured output validation
- **services/** - Python services calling LLM APIs
- **classifiers/** - Intent/entity classification
- **explainers/** - Natural language explanations for conflicts