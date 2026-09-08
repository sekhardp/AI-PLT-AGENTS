---
name: sgs-bq-server
description: Standard operating procedure for querying Suntory GCP BigQuery gold procurement, spend analytics, vendor intelligence, cost center benchmarking, and savings opportunity tools.
tools:
  - sgs_bq_server__Gold_Account_Assignment_Fact
  - sgs_bq_server__Gold_Content_Brand_Investment
  - sgs_bq_server__Gold_Cost_Center_Intelligence
  - sgs_bq_server__Gold_Enterprise_Spend_Fact
  - sgs_bq_server__Gold_Executive_Dashboard
  - sgs_bq_server__Gold_Financial_Attribution
  - sgs_bq_server__Gold_GL_Account_Intelligence
  - sgs_bq_server__Gold_Invoice_Fact
  - sgs_bq_server__Gold_Material_Intelligence
  - sgs_bq_server__Gold_Monthly_Spend_Trend
  - sgs_bq_server__Gold_Procurement_KPI
  - sgs_bq_server__Gold_Savings_Opportunity
  - sgs_bq_server__Gold_Shadow_IT
  - sgs_bq_server__Gold_Supplier_Risk
  - sgs_bq_server__Gold_Supply_Chain_Intelligence
  - sgs_bq_server__Gold_Vendor_Intelligence
  - sgs_bq_server__Gold_Vendor_Similarity
  - sgs_bq_server__Gold_Vendor_Spend_Classification
---

# Suntory BigQuery Procurement Analytics Skill

Use this skill whenever the user asks questions referencing procurement spend, purchase orders, invoices, vendor intelligence, supplier risk, cost centers, savings opportunities, shadow IT, or supply chain logistics from BigQuery gold datasets (`bsi-sftphub-dev.DNT_MCP_PILOT`).

## Available Tools

### 1. Executive KPIs & Spend Trends
1. **`sgs_bq_server__Gold_Executive_Dashboard(limit=10, min_total_spend_usd=None, min_spend_line_count=None, min_vendor_count=None, first_po_date_from=None, first_po_date_to=None, last_po_date_from=None, last_po_date_to=None)`**:
   - **Executive Overview Tool**: Returns leadership metrics including total enterprise spend, total PO/invoice values, strategic vendor counts, and estimated savings.
2. **`sgs_bq_server__Gold_Procurement_KPI(limit=10, first_po_date_from=None, first_po_date_to=None, last_po_date_from=None, last_po_date_to=None)`**:
   - Returns procurement operational performance indicators, active supplier counts, and average spend per vendor.
3. **`sgs_bq_server__Gold_Monthly_Spend_Trend(limit=10, fiscal_year=None, company_code=None, purchasing_org=None)`**:
   - Time-series monthly spend aggregates across categories (technology, consulting, content, supply chain, HR).

### 2. Spend Fact & Invoices
4. **`sgs_bq_server__Gold_Enterprise_Spend_Fact(limit=10, company_code=None, purchasing_org=None, vendor_name_full=None)`**:
   - **Primary Spend Line Tool**: Granular spend-line fact table linking POs, line items, vendors, net price, and document currencies.
5. **`sgs_bq_server__Gold_Invoice_Fact(limit=10, invoice_number=None, company_code=None, vendor_id=None)`**:
   - Canonical invoice-level records linking invoices to purchase orders, tax codes, payment terms, and status.

### 3. Vendor Intelligence & Risk
6. **`sgs_bq_server__Gold_Vendor_Intelligence(limit=10, vendor_name=None, vendor_activity_class=None, vendor_family=None)`**:
   - Classifies suppliers across business categories (technology, consulting, marketing, brand, supply chain, HR).
7. **`sgs_bq_server__Gold_Vendor_Similarity(limit=10)`**:
   - Pairwise supplier comparison identifying overlapping functionality, shared capabilities, and consolidation potential.
8. **`sgs_bq_server__Gold_Vendor_Spend_Classification(limit=10, vendor_id=None, vendor_name_full=None)`**:
   - Machine learning business capability classifications and confidence percentages per supplier.
9. **`sgs_bq_server__Gold_Supplier_Risk(limit=10, vendor_name=None, vendor_family=None, vendor_tier=None)`**:
   - Quantifies supplier concentration risk, critical single-source dependencies, and risk tiers.

### 4. Financial Ownership & Cost Centers
10. **`sgs_bq_server__Gold_Account_Assignment_Fact(limit=10, company_code=None, purchasing_org=None, purchasing_group=None, material_group=None, cost_center=None, gl_account=None)`**:
    - Links spend to cost centers, internal orders, WBS elements, profit centers, and GL accounts.
11. **`sgs_bq_server__Gold_Cost_Center_Intelligence(limit=10)`**:
    - Departmental cost-center benchmarks, peer comparisons, fragmentation flags, and spending patterns.
12. **`sgs_bq_server__Gold_Financial_Attribution(limit=10, company_code=None, cost_center=None, profit_center=None, gl_account=None)`**:
    - Final financial expense ownership after FI/CO repostings and reallocations.
13. **`sgs_bq_server__Gold_GL_Account_Intelligence(limit=10, gl_account=None, company_code=None)`**:
    - General Ledger account classifications and cumulative accounting spend.

### 5. Domain Analytics & Optimization
14. **`sgs_bq_server__Gold_Savings_Opportunity(limit=10, company_code=None, cost_center=None, gl_account=None)`**:
    - Algorithmic savings recommendations, vendor rationalization targets, and estimated cost reductions.
15. **`sgs_bq_server__Gold_Shadow_IT(limit=10, vendor_name_full=None, company_code=None, purchasing_org=None, purchasing_group=None)`**:
    - Identifies technology software/hardware purchases executed outside central IT governance.
16. **`sgs_bq_server__Gold_Content_Brand_Investment(limit=10, company_code=None, purchasing_org=None, vendor_name_full=None, material_group=None)`**:
    - Creative agency, marketing, media, and branding investments across purchasing orgs.
17. **`sgs_bq_server__Gold_Supply_Chain_Intelligence(limit=10, company_code=None, purchasing_org=None, purchasing_group=None)`**:
    - Logistics, freight, warehousing, packaging, and manufacturing spend intelligence.
18. **`sgs_bq_server__Gold_Material_Intelligence(limit=10, material_id=None, material_group=None)`**:
    - Commodity-level spend, material groups, and single-source material risks.

---

## Step-by-Step Workflow

### Step 1: Identify Question Intent & Target Filters
* **High-Level KPIs:** For executive summaries or overall spend, call `sgs_bq_server__Gold_Executive_Dashboard()` or `sgs_bq_server__Gold_Procurement_KPI()`.
* **Vendor & Risk Analysis:** Extract vendor names or category flags and query `sgs_bq_server__Gold_Vendor_Intelligence` or `sgs_bq_server__Gold_Supplier_Risk`.
* **Accounting & Cost Center:** Extract `company_code`, `cost_center`, or `gl_account` and query `sgs_bq_server__Gold_Account_Assignment_Fact`.
* **Parameter Filtering:** Always pass specific filter parameters (`company_code="AU60"`, `purchasing_org="AU01"`, `vendor_name="FUEL..."`) to narrow results.

### Step 2: Multi-Tool Parallel Execution
When answering multi-dimensional questions (e.g. evaluating a vendor's spend, risk, and savings opportunities), execute parallel tool calls in a single turn:
- Tool Call 1: `sgs_bq_server__Gold_Enterprise_Spend_Fact(vendor_name_full="MICROSOFT", limit=5)`
- Tool Call 2: `sgs_bq_server__Gold_Supplier_Risk(vendor_name="MICROSOFT", limit=5)`
- Tool Call 3: `sgs_bq_server__Gold_Savings_Opportunity(limit=5)`

### Step 3: Synthesis, Grounding & Citations
* **Grounding:** Synthesize answers using only facts, numbers, and dates returned in the BigQuery tool JSON payloads. Do not assume or extrapolate figures.
* **Currency & Financial Formatting:** Format monetary amounts clearly in USD with comma separators (e.g., `$1,250,000.00` or `$45.2M`).
* **Source Attribution:** Clearly state the originating gold dataset when presenting conclusions (e.g., `[Dataset: Gold_Enterprise_Spend_Fact]`, `[Dataset: Gold_Supplier_Risk]`).
