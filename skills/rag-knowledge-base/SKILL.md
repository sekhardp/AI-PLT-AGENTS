---
name: rag-knowledge-base
description: Standard operating procedure for searching documents, checking vector status, and retrieving knowledge using RAG MCP server tools.
tools:
  - rag_server__search_knowledge_base
  - rag_server__check_document_vector_status
  - rag_server__list_available_documents
---

# RAG Knowledge Base Retrieval Skill

Use this skill whenever the user asks questions referencing uploaded documents, domain policies, corporate reports, or knowledge base files.

## Available Tools

1. **`rag_server__search_knowledge_base(query, document_id=None, top_k=10)`**:
   - **Primary Retrieval Tool**: Directly retrieves the most relevant raw text passages (10–15 chunks) using cosine similarity.
   - If a specific `document_id` is provided, restricts search scope to that document.
   - If `document_id` is omitted, searches across all ready documents in the knowledge base.

2. **`rag_server__check_document_vector_status(document_id)`**:
   - Checks whether a document has been vectorized and is ready for retrieval.
   - Returns `{ is_vectorized: true/false, status: "ready", total_chunks: N, filename: "..." }`.

3. **`rag_server__list_available_documents(limit=50)`**:
   - Lists all available documents in the knowledge base with their `document_id`, `filename`, and `status`.

---

## Step-by-Step Workflow

### Step 1: Identify Target Documents
* **Single Document:** Pass the given `document_id` to `rag_server__search_knowledge_base`.
* **Multiple Documents (Parallel Tool Calls):** If the user references multiple files or provides multiple `document_id`s, **call `rag_server__search_knowledge_base` in parallel for each document ID** in a single turn.
* **Document Discovery:** If the user asks *"what documents do I have?"*, call `rag_server__list_available_documents()`.
* **Status Check:** If verifying upload readiness, call `rag_server__check_document_vector_status(document_id=...)`.

### Step 2: Multi-Document Parallel Execution
When comparing or answering across multiple documents (e.g. `doc_A` and `doc_B`), execute parallel tool calls:
- Tool Call 1: `rag_server__search_knowledge_base(query="...", document_id="doc_A_uuid", top_k=10)`
- Tool Call 2: `rag_server__search_knowledge_base(query="...", document_id="doc_B_uuid", top_k=10)`

### Step 3: Synthesis, Grounding & Citations
* Inspect the returned chunks from **all** queried documents.
* Synthesize a unified, grounded answer comparing or combining the information from each document.
* **Grounding:** Synthesize your answer accurately using only facts supported by the returned text passages. Do not hallucinate external details.
* **Citations:** Clearly attribute facts to their source document and chunk (e.g., `[Doc A, Chunk #2]` vs `[Doc B, Chunk #5]`).
