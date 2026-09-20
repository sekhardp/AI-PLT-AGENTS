---
name: sales-products-analytics
description: Authoritative analytics, KPI reporting, and omnichannel synthesis guide for the BigQuery sales_products dataset in beam-suntory-gemini-llm-poc.
tools:
  - sales_products_server__get_dimension_catalog
  - sales_products_server__get_dataset_metadata
  - sales_products_server__get_executive_sales_summary
  - sales_products_server__get_omnichannel_comparison
  - sales_products_server__get_inventory_restock_alerts
  - sales_products_server__get_inventory_status
  - sales_products_server__get_online_orders
  - sales_products_server__get_retail_transactions
  - sales_products_server__get_regional_sales
  - sales_products_server__get_customer_purchases
  - sales_products_server__execute_custom_analytics_query
---

# Sales & Products BigQuery Analytics Skill

Use this skill whenever the user asks questions about **sales revenue, omnichannel channel mix (online e-commerce vs physical retail POS), product sales, inventory levels, stock deficits/reorder alerts, customer reviews, regional territories, cashiers, shifts, or suppliers** across the `beam-suntory-gemini-llm-poc.sales_products` BigQuery dataset.

---

## 1. Available Tools & Capabilities

### Dimension & Metadata Discovery
1. **`get_dimension_catalog(dimension=None)`**
   - **Purpose**: Authoritative distinct values for categorical dimensions without writing custom SQL.
   - **Dimensions**: `'store_locations'` (physical stores: Store A–D), `'products'` (Chair, Desk, Laptop, Monitor, Phone, Printer, Tablet), `'regions'` (Central, East, North, South, West), `'storage_locations'` (WH-1 to WH-5), `'suppliers'` (DirectGoods, Global Parts, SupplyCo, WarePlus), `'order_statuses'` (Cancelled, Delivered, Pending, Returned, Shipped), `'payment_methods'`, `'customer_types'` (Retail, Wholesale), `'promotions'`.
   - **Empty / None Call**: Automatically returns complete catalog summary for all dimensions in 1 step.

2. **`get_dataset_metadata(table_name=None)`**
   - **Purpose**: Inspect table schemas, column data types, row counts, and cross-table join keys.

### Executive & Omnichannel Synthesis
3. **`get_executive_sales_summary(date_from=None, date_to=None)`**
   - **Purpose**: Top-line enterprise KPIs: total revenue ($1.56M), total units sold (4,625), total orders/transactions, online return rate (19.8%), and ranking of top products by revenue.

4. **`get_omnichannel_comparison(product=None, date_from=None, date_to=None)`**
   - **Purpose**: Side-by-side comparison of Online E-Commerce vs Physical Retail Store POS revenue, volume, and percentage market share.

### Supply Chain & Inventory Operations
5. **`get_inventory_restock_alerts(warehouse=None, supplier=None, product=None, limit=50)`**
   - **Purpose**: Immediate restock priority list for SKUs at or below reorder points (`QuantityInStock <= ReorderPoint`), deficit units, supplier contacts, lead time days, and estimated restock costs.

6. **`get_inventory_status(product=None, warehouse=None, supplier=None, status='all', limit=50)`**
   - **Purpose**: General warehouse stock levels, unit costs, storage locations, and health status filtering (`'all'`, `'low_stock'`, `'out_of_stock'`, `'healthy'`).

### Channel-Specific Query Engines
7. **`get_online_orders(order_id=None, customer_id=None, product=None, status=None, coupon_code=None, referral_source=None, date_from=None, date_to=None, limit=50)`**
   - **Purpose**: Digital e-commerce orders, fulfillment statuses, tracking numbers, coupon performance (`SAVE10`, `FREESHIP`), and acquisition channels (`Email`, `Social`, `Direct`, `Organic`).

8. **`get_retail_transactions(transaction_id=None, store_id=None, location=None, product=None, shift=None, day_of_week=None, cashier=None, payment_type=None, date_from=None, date_to=None, limit=50)`**
   - **Purpose**: Physical store POS transactions, store locations (`Store A` to `Store D`), shifts (`Morning`, `Afternoon`, `Evening`), cashiers (`C1` to `C4`), and payment methods.

9. **`get_regional_sales(order_id=None, region=None, product=None, customer_type=None, salesperson=None, promotion=None, date_from=None, date_to=None, limit=50)`**
   - **Purpose**: Regional sales territories (`Central`, `East`, `North`, `South`, `West`), representative performance, customer channel mix (`Retail` vs `Wholesale`), discounts, and promo campaigns.

10. **`get_customer_purchases(customer_id=None, product=None, category=None, payment_method=None, rating=None, date_from=None, date_to=None, limit=50)`**
    - **Purpose**: Customer purchase history, product categories (`Electronics`, `Furniture`), payment methods (`Cash`, `Credit Card`, `Debit Card`, `Online`), and review satisfaction ratings (1 to 5 stars).

### Fallback SQL Query Tool
11. **`execute_custom_analytics_query(query)`**
    - **Purpose**: Execute read-only SQL for complex multi-table joins or bespoke aggregations. Hyphenated table names and aliases are resolved automatically.

---

## 2. Zero-Hallucination Ground Truth (5 Core Tables)

The dataset `beam-suntory-gemini-llm-poc.sales_products` consists of 5 governed tables:

| Table Name | Key Columns | Categorical Dimensions & Sample Values | Primary Use Case |
|---|---|---|---|
| **`customer-purchase-history`** | `CustomerID`, `CustomerName`, `Product`, `ProductCategory`, `PurchaseDate`, `Quantity`, `UnitPrice`, `TotalPrice`, `PaymentMethod`, `ReviewRating` | **Category**: `Electronics`, `Furniture`<br>**Payment**: `Cash`, `Credit Card`, `Debit Card`, `Online`<br>**Rating**: 1 to 5 | Customer LTV, satisfaction ratings, payment preferences. |
| **`inventory-tracker`** | `ProductID`, `ProductName`, `QuantityInStock`, `ReorderPoint`, `Supplier`, `SupplierContact`, `LeadTime`, `StorageLocation`, `UnitCost` | **Products**: Chair, Desk, Laptop, Monitor, Phone, Printer, Tablet<br>**Storage**: WH-1 to WH-5<br>**Suppliers**: DirectGoods, Global Parts, SupplyCo, WarePlus | Stock levels, deficit alerts, supplier contacts, restock planning. |
| **`online-store-orders`** | `OrderID`, `Date`, `CustomerID`, `Product`, `Quantity`, `UnitPrice`, `TotalPrice`, `ItemsInCart`, `ShippingAddress`, `PaymentMethod`, `OrderStatus`, `TrackingNumber`, `CouponCode`, `ReferralSource` | **Status**: Cancelled, Delivered, Pending, Returned, Shipped<br>**Coupons**: SAVE10, FREESHIP<br>**Referral**: Email, Social, Direct, Organic | E-commerce funnel, returns, coupon effectiveness, digital marketing. |
| **`product-sales-region`** | `OrderID`, `OrderDate`, `DeliveryDate`, `Date`, `Region`, `RegionManager`, `StoreLocation`, `Salesperson`, `Product`, `Quantity`, `UnitPrice`, `Discount`, `ShippingCost`, `TotalPrice`, `CustomerType`, `CustomerName`, `PaymentMethod`, `Promotion`, `Returned` | **Regions**: Central, East, North, South, West<br>**CustomerType**: Retail, Wholesale<br>**Promotions**: WINTER15, FREESHIP, Promo A, Promo B | Territorial performance, sales rep benchmarking, wholesale mix. |
| **`retail-store-transactions`** | `TransactionID`, `Date`, `Time`, `TimeOfDay`, `DayOfWeek`, `StoreID`, `Location`, `StoreManager`, `Cashier`, `Product`, `Quantity`, `UnitPrice`, `TotalPrice`, `PaymentType` | **Locations**: Store A, Store B, Store C, Store D<br>**Shifts**: Morning, Afternoon, Evening<br>**Cashiers**: C1 to C4<br>**Payment**: Cash, Credit Card, Gift Card | Physical POS store revenue, shift analysis, cashier throughput. |

---

## 3. Step-by-Step Workflow & Decision Tree

### Step 1: Prompt Intent & Tool Selection
- **Catalog & Dimension Values**: Use `get_dimension_catalog` (e.g. `dimension="store_locations"`, `dimension="products"`, `dimension="suppliers"`).
- **Top-Line Enterprise KPIs**: Use `get_executive_sales_summary` or `get_omnichannel_comparison`.
- **Low Stock & Supply Deficits**: Use `get_inventory_restock_alerts`.
- **Channel Deep Dives**: Use the corresponding specialized tool (`get_online_orders`, `get_retail_transactions`, `get_regional_sales`, `get_customer_purchases`).
- **Bespoke Joins**: Use `execute_custom_analytics_query`.

### Step 2: Direct Parameter Binding
Pass clean canonical arguments without redundant parameter synonyms:
- `product`: e.g. `"Laptop"`, `"Phone"`, `"Monitor"`
- `warehouse`: e.g. `"WH-1"`, `"WH-2"`
- `location`: e.g. `"Store A"`, `"Store B"`
- `region`: e.g. `"Central"`, `"West"`
- `status`: e.g. `"Delivered"`, `"low_stock"`, `"out_of_stock"`

### Step 3: Synthesis & Grounding
- Extract verified numbers from the tool's structured summary and records.
- Format all financial figures in USD (`$XX,XXX.XX`).
- Never hallucinate unqueried fields or assume external data.

---

## 4. Executive 4-Part Response Standard

When responding to analytical questions, format all responses according to the standard executive 4-part structure:

1. **Governed Source Attribution**: Explicitly state the underlying BigQuery table(s) and filter criteria queried.
2. **KPI Summary Table**: Clean Markdown table of top-line figures ($USD, Units, % Share).
3. **Distribution Breakdown**: Structured breakdown by dimension (Product, Region, Store, Channel, Shift).
4. **Analytical Insights & Recommended Actions**: 2–3 actionable operational conclusions.
