# Indovix --- System Overview

**Prepared by: ChatGPT**

------------------------------------------------------------------------

## 1. What Indovix Is

Indovix is a model-agnostic operational memory and execution layer for
AI systems.

It is not an AI model.

It sits between AI models (Claude, ChatGPT, etc.) and real-world
systems, providing:

-   Persistent memory
-   Structured context
-   Controlled tool execution
-   Role-based access control

Core principle:

The model is not the memory.\
Indovix provides the memory, structure, and system context.

------------------------------------------------------------------------

## 2. High-Level Architecture

AI Model (Claude / ChatGPT / etc.) ↓ Indovix MCP Layer (tools, auth,
routing) ↓ Connectors + Knowledge Base + System State ↓ External systems
(M365, Xero, filesystem, infrastructure)

------------------------------------------------------------------------

## 3. Core Capabilities

### 3.1 Externalised Memory

All knowledge is stored outside the AI model:

-   Files stored in /data/...
-   Documents ingested and embedded
-   Metadata structured (type, date, schema, etc.)
-   Retrieved via semantic search (Indovix_search)

Result: - No reliance on chat history - Same context available to any
model - Persistent, queryable knowledge base

------------------------------------------------------------------------

### 3.2 Model-Agnostic Design

Indovix works with multiple AI frontends:

-   Claude
-   ChatGPT
-   Gemini
-   Local models

Implication: - No vendor lock-in - Models can be swapped without
changing the system - All models operate against the same memory and
tools

------------------------------------------------------------------------

### 3.3 MCP Tool Layer (Execution Engine)

Indovix exposes functionality through tools:

-   Knowledge retrieval (Indovix_search)
-   System actions (project creation, file ops)
-   External connectors (M365, Xero, etc.)

AI models do not act directly --- they call tools.

Result: - Controlled execution - Deterministic behavior - Full
auditability

------------------------------------------------------------------------

### 3.4 Role-Based Access Control

Access is enforced at the tool level, not via prompts.

-   Each user has a token
-   Token maps to a role
-   Role determines available connectors/tools
-   Tool list is built per session

Critical rule:

If a tool is not present, it cannot be used.

------------------------------------------------------------------------

### 3.5 Unified Ingest Pipeline

All documents become searchable:

-   Supported formats: .md, .txt, .docx, .pdf, .html, .csv
-   Central drop zone: /data/incoming/
-   Automatic ingestion (\~5 minutes)
-   Post-ingest routing to correct directories

------------------------------------------------------------------------

### 3.6 Structured Knowledge Schema

Each document includes metadata:

-   doc_type
-   doc_date
-   schema
-   chunk_index
-   device_tags

------------------------------------------------------------------------

### 3.7 Multi-User Architecture

Each user: - Uses their own AI account - Connects to the same Indovix
backend - Sees only what their role allows

------------------------------------------------------------------------

### 3.8 Authentication Model

Current: - Per-user bearer tokens

Future: - OAuth 2.0 (PKCE)

------------------------------------------------------------------------

### 3.9 Autonomous Operations

-   Daily agent execution
-   Approved action queue
-   Infrastructure monitoring

Constraint: No autonomous access to business data without approval

------------------------------------------------------------------------

## 4. Key Advantages

-   Model independence
-   Persistent memory
-   Real security (tool-level)
-   Unified system access
-   Multi-user simplicity
-   Full auditability
-   Rapid deployment
-   Scalable architecture
-   Enables AI as an operator

------------------------------------------------------------------------

## 5. Positioning

Indovix is:

An AI operating layer for real-world systems

------------------------------------------------------------------------

## 6. Bottom Line

Indovix turns AI into a stateful, controlled, and auditable system
operator.
