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

# Suntory BigQuery Procurement Analytics Skill (`sgs_bq_server`)

## Overview

This skill documents the FastMCP tools for querying gold-layer BigQuery datasets that support enterprise procurement, vendor intelligence, cost center benchmarking, financial attribution, invoice analytics, material categorization, and executive reporting.

## Usage

Invoke the relevant tool by name from the MCP client. Each tool accepts a `limit` parameter for the maximum number of rows returned.

### Common Parameters

| Name | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `limit` | integer | Maximum number of rows to return. | No | `10` |

---

## Available Tools

### 1. `sgs_bq_server__Gold_Account_Assignment_Fact`
- **Business Purpose**: Provides detailed procurement account assignment information linking spend to cost centers, internal orders, WBS elements, and financial ownership.
- **Primary Business Questions Answered**:
  - How is spend allocated?
  - Which cost centers receive the cost?
  - Which projects or WBS elements consume procurement spend?
- **Filters**:
  - `company_code` (string, optional)
  - `purchasing_org` (string, optional)
  - `purchasing_group` (string, optional)
  - `material_group` (string, optional)
  - `cost_center` (string, optional)
  - `gl_account` (string, optional)

### 2. `sgs_bq_server__Gold_Content_Brand_Investment`
- **Business Purpose**: Identifies marketing, content, branding, agency, and media-related spend across the enterprise. Supports marketing investment optimization.
- **Primary Business Questions Answered**:
  - How much is spent on Content?
  - How much on Brand Investment?
  - Which agencies perform similar work?
  - Which brands spend the most on agencies?
- **Filters**:
  - `company_code` (string, optional)
  - `purchasing_org` (string, optional)
  - `vendor_name_full` (string, optional)
  - `material_group` (string, optional)

### 3. `sgs_bq_server__Gold_Cost_Center_Intelligence`
- **Business Purpose**: Provides benchmarking and intelligence for cost center spending patterns, peer comparisons, and purchasing behaviour.
- **Primary Business Questions Answered**:
  - Which cost centers overspend?
  - Which cost centers have the greatest savings potential?
  - Which departments buy the same services from different suppliers?
- **Filters**:
  - None (no additional filters beyond `limit`)

### 4. `sgs_bq_server__Gold_Enterprise_Spend_Fact`
- **Business Purpose**: Central enterprise spend fact table at spend-line level. Provides the canonical source for procurement, invoice, vendor, cost center, company, category, and time analysis. This is the primary analytical dataset used by all downstream intelligence layers.
- **Primary Business Questions Answered**:
  - What is the total spend?
  - Which vendors have the highest spend?
  - How much do we spend by company, business unit, cost center, category, market, or period?
  - How has spend evolved over time?
- **Filters**:
  - `company_code` (string, optional)
  - `purchasing_org` (string, optional)
  - `vendor_name_full` (string, optional)

### 5. `sgs_bq_server__Gold_Executive_Dashboard`
- **Business Purpose**: Executive-ready aggregated dataset optimized for dashboards and high-level business reporting. Provides curated KPIs and summary metrics for leadership.
- **Primary Business Questions Answered**:
  - What are the key procurement KPIs?
  - What is total enterprise spend?
  - What are the highest savings opportunities?
  - How is spend distributed across the enterprise?
- **Filters**:
  - `min_total_spend_usd` (float, optional)
  - `min_spend_line_count` (int, optional)
  - `min_vendor_count` (int, optional)
  - `first_po_date_from` (string, optional)
  - `first_po_date_to` (string, optional)
  - `last_po_date_from` (string, optional)
  - `last_po_date_to` (string, optional)

### 6. `sgs_bq_server__Gold_Financial_Attribution`
- **Business Purpose**: Explains financial ownership after FI/CO reallocations and internal repostings, providing the final business owner of each expense.
- **Primary Business Questions Answered**:
  - Where was spend finally allocated?
  - Which reclassifications occurred?
  - Who is the final owner of the expense?
- **Filters**:
  - `company_code` (string, optional)
  - `cost_center` (string, optional)
  - `profit_center` (string, optional)
  - `gl_account` (string, optional)

### 7. `sgs_bq_server__Gold_GL_Account_Intelligence`
- **Business Purpose**: Enriches spend using General Ledger account classifications and financial reporting structures.
- **Primary Business Questions Answered**:
  - Which GL accounts generate the highest spend?
  - Which expense types are increasing?
  - Which financial categories should be optimized?
- **Filters**:
  - `gl_account` (string, optional)
  - `company_code` (string, optional)

### 8. `sgs_bq_server__Gold_Invoice_Fact`
- **Business Purpose**: Canonical invoice-level analytical dataset linking invoices with purchase orders, vendors, and accounting information.
- **Primary Business Questions Answered**:
  - Which invoices belong to a PO?
  - Which invoices are duplicated?
  - Which invoices are blocked?
  - Which vendors generated the highest invoice volume?
- **Filters**:
  - `invoice_number` (string, optional)
  - `company_code` (string, optional)
  - `vendor_id` (string, optional)

### 9. `sgs_bq_server__Gold_Material_Intelligence`
- **Business Purpose**: Material-centric analytical dataset used to analyse procurement by materials, commodities, and procurement categories.
- **Primary Business Questions Answered**:
  - Which materials generate the highest spend?
  - Which commodities could be consolidated?
  - Which products are purchased from multiple suppliers?
- **Filters**:
  - `material_id` (string, optional)
  - `material_group` (string, optional)

### 10. `sgs_bq_server__Gold_Monthly_Spend_Trend`
- **Business Purpose**: Pre-aggregated monthly spend trends optimized for executive reporting and time-series analysis.
- **Primary Business Questions Answered**:
  - How has enterprise spend evolved month by month?
  - Which categories show increasing trends?
  - Which vendors have growing spend?
- **Filters**:
  - `fiscal_year` (string, optional)
  - `company_code` (string, optional)
  - `purchasing_org` (string, optional)

### 11. `sgs_bq_server__Gold_Procurement_KPI`
- **Business Purpose**: Central repository of procurement KPIs including purchasing performance, supplier counts, savings indicators, and operational procurement metrics.
- **Primary Business Questions Answered**:
  - What are the procurement KPIs?
  - How many active suppliers exist?
  - What is the average spend per supplier?
  - How is procurement performance evolving?
- **Filters**:
  - `first_po_date_from` (string, optional)
  - `first_po_date_to` (string, optional)
  - `last_po_date_from` (string, optional)
  - `last_po_date_to` (string, optional)

### 12. `sgs_bq_server__Gold_Savings_Opportunity`
- **Business Purpose**: Identifies cost-saving opportunities through vendor comparison, consolidation potential, and competitive analysis.
- **Primary Business Questions Answered**:
  - Which vendors offer savings potential?
  - Where can we consolidate suppliers?
  - What is the estimated savings potential?
- **Filters**:
  - `company_code` (string, optional)
  - `cost_center` (string, optional)
  - `gl_account` (string, optional)

### 13. `sgs_bq_server__Gold_Shadow_IT`
- **Business Purpose**: Detects technology-related purchases performed outside central IT governance using vendor classification, cost center ownership, and technology indicators.
- **Primary Business Questions Answered**:
  - Where does Shadow IT exist?
  - Which non-IT departments purchase software?
  - Which technology vendors bypass central IT?
- **Filters**:
  - `vendor_name_full` (string, optional)
  - `company_code` (string, optional)
  - `purchasing_org` (string, optional)
  - `purchasing_group` (string, optional)

### 14. `sgs_bq_server__Gold_Supplier_Risk`
- **Business Purpose**: Measures supplier dependency, concentration, and procurement risk across the enterprise using spend concentration and organizational distribution.
- **Primary Business Questions Answered**:
  - Which vendors represent concentration risk?
  - Which suppliers are critical?
  - Which vendors are used across the largest number of cost centers?
- **Filters**:
  - `vendor_name` (string, optional)
  - `vendor_family` (string, optional)
  - `vendor_tier` (string, optional)

### 15. `sgs_bq_server__Gold_Supply_Chain_Intelligence`
- **Business Purpose**: Consolidates logistics, warehousing, packaging, manufacturing, and operational procurement intelligence.
- **Primary Business Questions Answered**:
  - Which logistics providers are most expensive?
  - Which suppliers could be consolidated?
  - Which supply chain categories generate the highest spend?
- **Filters**:
  - `company_code` (string, optional)
  - `purchasing_org` (string, optional)
  - `purchasing_group` (string, optional)

### 16. `sgs_bq_server__Gold_Vendor_Intelligence`
- **Business Purpose**: Provides a business classification of suppliers, including activity type, vendor family, technology indicators, and business capability. Used to enrich spend with supplier intelligence.
- **Primary Business Questions Answered**:
  - Which vendors are technology providers?
  - Which vendors provide consulting?
  - Which agencies provide marketing services?
  - Which suppliers belong to the same business capability?
- **Filters**:
  - `vendor_name` (string, optional)
  - `vendor_activity_class` (string, optional)
  - `vendor_family` (string, optional)

### 17. `sgs_bq_server__Gold_Vendor_Similarity`
- **Business Purpose**: Identifies vendors providing similar or overlapping products or services by comparing classifications, purchasing patterns, and business capabilities. Supports supplier rationalization initiatives.
- **Primary Business Questions Answered**:
  - Which vendors provide similar services?
  - Which suppliers could be consolidated?
  - Which vendors overlap in functionality?
- **Filters**:
  - None (no additional filters beyond `limit`)

### 18. `sgs_bq_server__Gold_Vendor_Spend_Classification`
- **Business Purpose**: Classifies vendor spending by primary and secondary business capabilities to support procurement strategy and category management.
- **Primary Business Questions Answered**:
  - What are the vendor business capabilities?
  - How is vendor spend classified?
  - Which vendors require capability review?
- **Filters**:
  - `vendor_id` (string, optional)
  - `vendor_name_full` (string, optional)

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
