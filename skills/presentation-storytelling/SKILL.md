---
name: presentation-storytelling
description: Standard operating procedure for synthesizing BigQuery quantitative metrics and RAG qualitative document insights into structured executive presentation decks (SlideDeck schema).
tools:
  - sgs_bq_server__Gold_Executive_Dashboard
  - sgs_bq_server__Gold_Procurement_KPI
  - sgs_bq_server__Gold_Monthly_Spend_Trend
  - sgs_bq_server__Gold_Enterprise_Spend_Fact
  - sgs_bq_server__Gold_Supplier_Risk
  - sgs_bq_server__Gold_Savings_Opportunity
  - rag_server__search_knowledge_base
  - ppt_server__compile_deck_to_pptx_base64
  - ppt_server__validate_presentation_schema
---

# Executive Presentation & Data Storytelling Skill

Use this skill whenever the user asks to **create, generate, design, or summarize a presentation, pitch deck, slide deck, executive briefing, PowerPoint, or QBR (Quarterly Business Review)** using BigQuery procurement/spend metrics and RAG document insights.

---

## 1. Core Principles of Data Storytelling

1. **Dual-Sourced Grounding**:
   - **Quantitative Backbone (BigQuery)**: Query BigQuery tools to retrieve exact spend totals, KPI deltas, supplier concentration risks, and time-series monthly trends.
   - **Qualitative Context (RAG)**: Query RAG document search to extract strategic drivers, root-cause explanations, vendor interview notes, and domain policies.
2. **Actionable Narrative Structure**:
   - Move logically from **Executive Overview** $\rightarrow$ **Key Benchmarks** $\rightarrow$ **Data Trends** $\rightarrow$ **Root-Cause Analysis** $\rightarrow$ **Strategic Recommendations**.
3. **Structured Slide Output**:
   - Structure each slide using one of the standardized layouts (`title_slide`, `kpi_grid`, `chart_and_bullets`, `two_column_comparison`, `table_slide`, `bullet_cards`).

---

## 2. Standard 5-Slide Executive Deck Blueprint

When asked to generate a presentation deck, plan the sequence according to this proven executive narrative:

| Slide # | Layout | Purpose & Content | Tools to Call |
|---|---|---|---|
| **Slide 1** | `title_slide` | **Executive Briefing Title**: Main topic, subtitle, date/author. | None |
| **Slide 2** | `kpi_grid` | **Executive Scorecard**: 3–4 high-impact KPI cards (Total Spend, Savings Target, Vendor Count, Risk Index) with % YoY/QoQ deltas. | `sgs_bq_server__Gold_Executive_Dashboard`<br>`sgs_bq_server__Gold_Procurement_KPI` |
| **Slide 3** | `chart_and_bullets` | **Trend Deep Dive**: Native Column/Bar/Line chart (categories, series data) alongside 2–3 key takeaway bullets. | `sgs_bq_server__Gold_Monthly_Spend_Trend` |
| **Slide 4** | `two_column_comparison` | **Quant vs. Qual Synthesis**: Left column has BigQuery telemetry/numbers; right column has qualitative context/explanations from RAG docs. | `sgs_bq_server__Gold_Supplier_Risk`<br>`rag_server__search_knowledge_base` |
| **Slide 5** | `bullet_cards` | **Strategic Action Pillars**: 3 numbered strategic recommendations and next steps for leadership. | `sgs_bq_server__Gold_Savings_Opportunity`<br>`rag_server__search_knowledge_base` |

---

## 3. Step-by-Step Execution Workflow

### Step 1: Decompose Prompt & Execute Parallel Data Queries
Identify what data is needed and execute parallel tool calls in a single turn:
- **BigQuery metrics**: e.g., `sgs_bq_server__Gold_Executive_Dashboard()` and `sgs_bq_server__Gold_Monthly_Spend_Trend()`.
- **RAG context**: e.g., `rag_server__search_knowledge_base(query="strategic savings initiatives vendor risk")`.

### Step 2: Validate Numerical Alignment
- Format all currency in USD with commas and abbreviations (e.g. `$4.2M`, `$850K`, `$12.5B`).
- Ensure every chart data point in `chart.series.values` matches the exact order of `chart.categories`.

### Step 3: Populate SlideDeck Schema
Ensure each slide has:
- `slide_number` (1, 2, 3...)
- `layout` (one of `title_slide`, `kpi_grid`, `chart_and_bullets`, `two_column_comparison`, `table_slide`, `bullet_cards`)
- `title` & optional `subtitle`
- `sources` list (e.g. `["BigQuery: Gold_Executive_Dashboard", "RAG: procurement_policy_2024.pdf"]`)
- Complete content blocks matching the layout (`kpi_cards`, `chart`, `bullet_points`, `table`, etc.).
