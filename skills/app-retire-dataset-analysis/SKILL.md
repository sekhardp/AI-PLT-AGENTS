---
name: app-retire-dataset-analysis
description: Retrieve app-retirement metadata from the BigQuery `app_retire_tables.app_retire_coda****` table when a request mentions Coda or asks about application-retirement table status, row counts, schemas, or hashes.
---

# Bigquery App Retirement

Use this skill for read-only requests about Coda application-retirement data. In particular, when the user's prompt contains "coda" (case-insensitive), query the specified table for the requested fields and filters.

## Data source

- GCP project: `beam-suntory-gemini-llm-poc`
- Dataset: `app_retire_tables`
- Table pattern: `app_retire_coda****`
- Available columns: `id`, `schema_name`, `table_name`, `md5_hash`, `row_count`, `status`

The four asterisks are a placeholder. Resolve the actual Coda table name from the BigQuery catalog or the user's request before querying; do not place literal `****` in SQL. If multiple matching tables exist and the request does not identify one, list the candidates or ask the user which table to use.

## Querying rules

- Use fully qualified, backticked BigQuery identifiers: `` `beam-suntory-gemini-llm-poc.app_retire_tables.<resolved_table>` ``.
- Select only columns needed to answer the request. Do not use `SELECT *` unless the user explicitly asks for every available column.
- Treat requests as read-only. Do not run DDL, DML, or job-changing statements.
- Apply a `LIMIT` for listings unless the user requests a complete extract. State the applied limit.
- Translate natural-language status conditions into explicit SQL filters; use case-insensitive matching only when status capitalization is unknown.

## SQL examples

Assume the resolved table is `app_retire_coda` and it has `id`, `schema_name`, `table_name`,`md5_hash`, `row_count` and `status` columns.

```sql
-- Return a specific record.
SELECT id, status
FROM `beam-suntory-gemini-llm-poc.app_retire_tables.app_retire_coda`;
```

```sql
-- List records with a requested status.
SELECT id, schema_name, table_name, status
FROM `beam-suntory-gemini-llm-poc.app_retire_tables.app_retire_coda`;
```

```sql
-- Summarize records by status.
SELECT id, schema_name, table_name, status
FROM `beam-suntory-gemini-llm-poc.app_retire_tables.app_retire_coda`
WHERE status = 'Active'
ORDER BY id
```
