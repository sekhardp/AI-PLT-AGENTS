---
name: sales-products-analytics
description: Authoritative analytics, KPI reporting, and omnichannel synthesis guide for the BigQuery sales_products dataset in beam-suntory-gemini-llm-poc.
tools:
  - sales_products_server__get_executive_sales_summary
  - sales_products_server__get_dimension_catalog
  - sales_products_server__get_inventory_restock_alerts
  - sales_products_server__execute_sql_query
  - sales_products_server__get_dataset_metadata
---

# Sales & Products BigQuery Analytics Skill Guide

This skill governs all agent interactions with the `sales_products` BigQuery dataset hosted in Google Cloud project `beam-suntory-gemini-llm-poc`.

---

## MUST and Should Follow

* Always keep responses concise.
* Never expose SQL queries.


## 1. Golden Hybrid Tool Manifest

Use the following optimized tool suite to query and analyze sales, inventory, retail POS, and customer data:

### 1. `get_executive_sales_summary(date_from=None, date_to=None)`
- **When to Use**: Top-line enterprise sales KPIs across all channels: total omnichannel revenue ($1.56M), online vs retail revenue share %, total unit volumes (4,625 units), online store return rates (19.8%), and best-selling product revenue rankings.
- **Advantage**: Automatically resolves the multi-table union across e-commerce and retail transactions in 1 single turn.

### 2. `get_dimension_catalog(dimension=None)`
- **When to Use**: Instant categorical dimension lookups without writing SQL:
  - Physical store locations (`dimension="store_locations"`): `Store A`, `Store B`, `Store C`, `Store D`
  - Products (`dimension="products"`): `Chair`, `Desk`, `Laptop`, `Monitor`, `Phone`, `Printer`, `Tablet`
  - Sales regions (`dimension="regions"`): `Central`, `East`, `North`, `South`, `West`
  - Warehouses (`dimension="storage_locations"`): `WH-1` to `WH-5`
  - Suppliers (`dimension="suppliers"`): `DirectGoods`, `Global Parts`, `SupplyCo`, `WarePlus`
  - Order fulfillment statuses (`dimension="order_statuses"`): `Cancelled`, `Delivered`, `Pending`, `Returned`, `Shipped`
  - Payment methods (`dimension="payment_methods"`): `Cash`, `Credit Card`, `Debit Card`, `Online`, `Gift Card`
- **Zero Parameter Call**: Calling with no parameters immediately returns the complete catalog summary for all dimensions.

### 3. `get_inventory_restock_alerts(warehouse=None, supplier=None, product=None, limit=25)`
- **When to Use**: Supply chain and procurement stock emergencies: SKUs at or below reorder threshold (`QuantityInStock <= ReorderPoint`), deficit units, supplier contacts, lead times, and estimated restock costs.

### 4. `execute_sql_query(query: str)`
- **When to Use**: Universal SQL query engine for all custom analytical questions: shift breakdowns, cashier performance, customer lifetime spend, regional representative rankings, discounts, and custom groupings.
- **Server Guardrails**: Automatically wraps hyphenated table names in backticks, handles table aliases (`online_orders` -> `online-store-orders`), normalizes column typos, and restricts execution to safe, read-only `SELECT` queries.

---

## 2. Zero-Hallucination Ground Truth (5 Core Tables)

| Table Name | Key Columns & Data Types | Categorical Dimensions & Sample Values |
|---|---|---|
| **`customer-purchase-history`** | `CustomerID` (STRING), `CustomerName` (STRING), `Product` (STRING), `ProductCategory` (STRING), `PurchaseDate` (DATE), `Quantity` (INT64), `UnitPrice` (FLOAT64), `TotalPrice` (FLOAT64), `PaymentMethod` (STRING), `ReviewRating` (INT64) | **Categories**: `Electronics`, `Furniture`<br>**Payment**: `Cash`, `Credit Card`, `Debit Card`, `Online`<br>**Rating**: 1 to 5 stars |
| **`inventory-tracker`** | `ProductID` (STRING), `ProductName` (STRING), `QuantityInStock` (INT64), `ReorderPoint` (INT64), `Supplier` (STRING), `SupplierContact` (STRING), `LeadTime` (INT64), `StorageLocation` (STRING), `UnitCost` (FLOAT64) | **Products**: Chair, Desk, Laptop, Monitor, Phone, Printer, Tablet<br>**Storage**: WH-1 to WH-5<br>**Suppliers**: DirectGoods, Global Parts, SupplyCo, WarePlus |
| **`online-store-orders`** | `OrderID` (STRING), `Date` (DATE), `CustomerID` (STRING), `Product` (STRING), `Quantity` (INT64), `UnitPrice` (FLOAT64), `TotalPrice` (FLOAT64), `ItemsInCart` (INT64), `ShippingAddress` (STRING), `PaymentMethod` (STRING), `OrderStatus` (STRING), `TrackingNumber` (STRING), `CouponCode` (STRING), `ReferralSource` (STRING) | **Statuses**: Cancelled, Delivered, Pending, Returned, Shipped<br>**Coupons**: SAVE10, FREESHIP<br>**Referral**: Email, Social, Direct, Organic |
| **`product-sales-region`** | `OrderID` (STRING), `OrderDate` (DATE), `DeliveryDate` (DATE), `Date` (DATE), `Region` (STRING), `RegionManager` (STRING), `StoreLocation` (STRING), `Salesperson` (STRING), `Product` (STRING), `Quantity` (INT64), `UnitPrice` (FLOAT64), `Discount` (FLOAT64), `ShippingCost` (FLOAT64), `TotalPrice` (FLOAT64), `CustomerType` (STRING), `CustomerName` (STRING), `PaymentMethod` (STRING), `Promotion` (STRING), `Returned` (INT64) | **Regions**: Central, East, North, South, West<br>**CustomerType**: Retail, Wholesale<br>**Promotions**: WINTER15, FREESHIP, Promo A, Promo B<br>**Returned**: 0 or 1 |
| **`retail-store-transactions`** | `TransactionID` (STRING), `Date` (DATE), `Time` (STRING), `TimeOfDay` (STRING), `DayOfWeek` (STRING), `StoreID` (STRING), `Location` (STRING), `StoreManager` (STRING), `Cashier` (STRING), `Product` (STRING), `Quantity` (INT64), `UnitPrice` (FLOAT64), `TotalPrice` (FLOAT64), `PaymentType` (STRING) | **Locations**: Store A, Store B, Store C, Store D<br>**Shifts**: Morning, Afternoon, Evening<br>**Cashiers**: C1 to C4<br>**Days**: Monday through Sunday |

---

## 3. Golden SQL Rules & Recipes for Local LLM

Follow these strict rules when generating SQL queries with `execute_sql_query` to prevent errors and hallucinations:

### Rule 1: Product Names are Singular Title-Case
- Products are stored as `'Chair'`, `'Desk'`, `'Laptop'`, `'Monitor'`, `'Phone'`, `'Printer'`, `'Tablet'`.
- When filtering on product, use `lower(Product) LIKE '%laptop%'` or the singular title `'Laptop'`. Never write `WHERE Product = 'Laptops'`.

### Rule 2: Store Locations vs. Store IDs
- Physical retail stores are named `'Store A'`, `'Store B'`, `'Store C'`, `'Store D'` in the column `Location` (in `retail-store-transactions`) and `StoreLocation` (in `product-sales-region`).
- Do **not** filter `StoreID = 'Store A'` or `StoreID = 'C'`. Always use `WHERE Location = 'Store C'`.

### Rule 3: Shifts & Time of Day
- Shift filtering is on the column `TimeOfDay` with values `'Morning'`, `'Afternoon'`, `'Evening'`.
- Example: `SELECT AVG(TotalPrice) FROM \`retail-store-transactions\` WHERE Location = 'Store C' AND TimeOfDay = 'Afternoon'`

### Rule 4: Return Rates & Orders
- In `online-store-orders`, returns are identified by `OrderStatus = 'Returned'`.
- In `product-sales-region`, returns are identified by `Returned = 1`.
- Never write `WHERE Returned = 1` on `online-store-orders`.

### Rule 5: Cross-Table Omnichannel Unions
- To compute total sales revenue across both online and retail channels, use `get_executive_sales_summary()` OR execute a `UNION ALL`:
```sql
SELECT SUM(TotalPrice) AS total_revenue
FROM (
  SELECT TotalPrice FROM `online-store-orders`
  UNION ALL
  SELECT TotalPrice FROM `retail-store-transactions`
)
```

---

## 4. Step-by-Step Workflow & Decision Tree

```
                                  USER QUERY
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
   [Executive Omnichannel]     [Catalog/Dimension]     [Custom Analytics/Filters]
            │                          │                          │
  get_executive_sales_summary  get_dimension_catalog      execute_sql_query
  - Top-line revenue           - Store lists              - Shift averages
  - Online vs Retail mix       - Products                 - Cashier throughput
  - Total return rates         - Warehouses               - Sales rep rankings
  - Best sellers ranking       - Suppliers                - Customer lifetime spend
```

1. **Step 1: Intent Routing**: Check if the question is an executive omnichannel total (`get_executive_sales_summary`), dimension lookup (`get_dimension_catalog`), restock alert (`get_inventory_restock_alerts`), or analytical query (`execute_sql_query`).
2. **Step 2: Single-Turn Query Execution**: Execute the appropriate tool call. If writing SQL, apply the Golden Rules (singular products, `Location = 'Store X'`, `TimeOfDay = 'Shift'`).
3. **Step 3: Grounded Synthesis**: Formulate the response using the exact returned metrics and numbers.

---

## 5. Executive 4-Part Response Standard

All responses must strictly adhere to the executive 4-part structure. Give the core answer and key numbers in the first sentence:

```markdown
### 1. Governed Source Attribution
- **Source Table(s)**: `beam-suntory-gemini-llm-poc.sales_products.retail-store-transactions`
- **Filter Parameters**: Location = 'Store C', TimeOfDay = 'Afternoon'

### 2. KPI Summary
| Metric | Value |
| :--- | :--- |
| **Average Transaction Total** | **$237.05** |
| **Total Afternoon Transactions** | **148** |
| **Total Afternoon Revenue** | **$35,083.40** |

### 3. Distribution Breakdown
- **Highest Volume Category**: Electronics represented 62% of Afternoon checkout revenue.
- **Peak Hour**: 2:00 PM – 3:30 PM generated the highest basket sizes.

### 4. Analytical Insights & Recommended Actions
1. **High Basket Value**: Afternoon shifts in Store C average 18% higher basket values than Morning shifts.
2. **Staffing Allocation**: Ensure Cashier C1 and C2 are staffed during 2:00 PM – 4:00 PM peak periods.
```
