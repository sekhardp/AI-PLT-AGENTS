---
name: rag-knowledge-base
description: Standard operating procedure for searching, retrieving, and synthesizing grounded information from uploaded user documents using the RAG MCP server tools (search_knowledge_base, list_user_documents, get_document_snippet).
tools:
  - search_knowledge_base
  - list_user_documents
  - get_document_snippet
---

# RAG Knowledge Base Retrieval Skill

Use this skill whenever the user asks questions referencing uploaded files, domain policies, corporate reports, financial statistics, or indexed document knowledge.

## Capabilities & Tools

1. **`search_knowledge_base(query, user_id, document_ids=None, top_k=5, mode='hybrid')`**:
   - Executes Hybrid Search (pgvector cosine similarity + BM25 keyword matching with Reciprocal Rank Fusion).
   - Scoped strictly to the authenticated `user_id` to maintain multi-tenant data isolation.
   - Modes: `hybrid` (recommended), `vector` (semantic search), `bm25` (exact keyword lookup).

2. **`list_user_documents(user_id)`**:
   - Discovers all ready, indexed documents available to the user.
   - Returns document UUIDs, filenames, file sizes, and timestamps.

3. **`get_document_snippet(chunk_id, user_id)`**:
   - Retrieves the full text, token count, and metadata for a specific document chunk.

---

## Step-by-Step SOP (Standard Operating Procedure)

### Step 1: Resolve Target Documents & Scope
- If the user's request explicitly includes `document_ids` in request metadata, restrict the search to those IDs.
- If no specific documents were attached or if the user asks *"what documents do I have?"*, call `list_user_documents(user_id=...)` first to inspect available documents.

### Step 2: Query Formulation Heuristic (Critical)
Do **NOT** pass conversational or verbose questions directly to `search_knowledge_base`.
Extract 2–4 dense semantic/keyword terms from the user query:

* **User Prompt:** *"Can you check the Q3 financial report and tell me what the total operating profit was in North America?"*
* **Optimized Search Query:** `Q3 financial report North America operating profit revenue`

### Step 3: Search Execution
Invoke `search_knowledge_base` with `mode='hybrid'`:
```json
{
  "query": "North America Q3 operating profit revenue",
  "user_id": "<authenticated_user_id>",
  "document_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
  "top_k": 5,
  "mode": "hybrid"
}
```

### Step 4: Multi-Hop Search & Refinement
- If the initial search yields low-confidence chunks or does not fully answer the question:
  1. Identify missing keywords or specific section headings from the first result.
  2. Perform **one refined secondary search** (e.g., using `mode='bm25'` for exact numbers, codes, or error strings).

### Step 5: Grounded Answer Synthesis & Citations
- **Strict Grounding:** Only make statements that are factually supported by the returned chunk text. Do not hallucinate external figures.
- **Citation Requirement:** Every factual assertion must cite its source using standard document tags:
  `North American operating profit reached $412M in Q3 [Document: Q3_Financials.pdf, Chunk #4].`
- Never expose raw database UUIDs or internal cosine similarity scores to the user.
