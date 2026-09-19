---
name: sales-products-analytics
description: Authoritative analytics, KPI reporting, and omnichannel synthesis guide for the BigQuery sales_products dataset in beam-suntory-gemini-llm-poc.
tools:
  - sales_products_server__get_dataset_metadata
  - sales_products_server__get_dimension_catalog
  - sales_products_server__get_customer_purchases
  - sales_products_server__get_inventory_status
  - sales_products_server__get_online_orders
  - sales_products_server__get_regional_sales
  - sales_products_server__get_retail_transactions
  - sales_products_server__get_executive_sales_summary
  - sales_products_server__get_omnichannel_comparison
  - sales_products_server__get_inventory_restock_alerts
  - sales_products_server__execute_custom_analytics_query
---

# Sales & Products BigQuery Analytics Skill Guide

This skill governs all agent interactions with the `sales_products` BigQuery dataset hosted in project `beam-suntory-gemini-llm-poc`.

---

## 1. Available Tools Reference

1. **`get_dimension_catalog(dimension="products")`**:
   - **Purpose**: Returns exact distinct values for any categorical dimension.
   - **Valid Dimensions**: `'products'`, `'regions'`, `'store_locations'`, `'store_ids'`, `'order_statuses'`, `'payment_methods'`, `'storage_locations'`, `'customer_types'`, `'promotions'`.
   - **Aliases Supported**: `'dim'`, `'category'`, `'type'`, `'name'`, singular/plural names (e.g. `'warehouse'`, `'store'`).

2. **`get_dataset_metadata(table_name=None)`**:
   - **Purpose**: Returns authoritative schemas, primary keys, record counts, and cross-table join relationships.
   - **Parameters**: `table_name` (optional filter for a specific table).

3. **`get_executive_sales_summary(product=None)`**:
   - **Purpose**: Top-line enterprise KPIs across all channels: total omnichannel revenue, online return rate %, retail revenue, regional revenue, top product revenue ranking, inventory health.

4. **`get_omnichannel_comparison(product=None, limit=50)`**:
   - **Purpose**: Side-by-side product performance breakdown comparing Online E-Commerce vs Physical Retail Stores (order counts, units sold, gross revenue, avg unit price, online revenue share %).

5. **`get_inventory_restock_alerts(storage_location=None, supplier=None, product=None, limit=100)`**:
   - **Purpose**: Supply chain deficit alerts for SKUs where `QuantityInStock <= ReorderPoint`. Returns deficit units, lead time days, estimated restock costs, and priority alert level (`CRITICAL_OUT_OF_STOCK`, `HIGH_PRIORITY`, `REORDER_POINT_REACHED`).

6. **`get_inventory_status(product_name=None, storage_location=None, supplier=None, stock_status="all", limit=50)`**:
   - **Purpose**: Warehouse stock levels, unit costs, lead times, storage locations (`WH-1` to `WH-5`), and stock health (`'all'`, `'low_stock'`, `'out_of_stock'`, `'healthy'`).

7. **`get_customer_purchases(customer_id=None, product=None, product_category=None, payment_method=None, min_review_rating=None, purchase_date_from=None, purchase_date_to=None, limit=50)`**:
   - **Purpose**: Customer purchase transactions with review satisfaction ratings (1–5), payment methods, and category classifications. Automatically returns `total_quantity_sum` and `total_revenue_usd`.

8. **`get_online_orders(order_id=None, customer_id=None, product=None, order_status=None, coupon_code=None, referral_source=None, order_date_from=None, order_date_to=None, limit=50)`**:
   - **Purpose**: E-commerce orders with fulfillment statuses (`Delivered`, `Shipped`, `Pending`, `Returned`, `Cancelled`), discount coupons (`SAVE10`, `FREESHIP`), tracking numbers, and marketing referral sources. Returns `total_revenue_usd` and `total_quantity_sum`.

9. **`get_regional_sales(region=None, product=None, customer_type=None, salesperson=None, region_manager=None, store_location=None, promotion=None, returned_only=False, order_date_from=None, order_date_to=None, limit=50)`**:
   - **Purpose**: Territory sales across `Central`, `East`, `North`, `South`, `West`, wholesale vs retail customer types, sales rep performance, and return flags (`Returned=1`). Returns `total_revenue_usd` and `total_quantity_sum`.

10. **`get_retail_transactions(store_id=None, location=None, product=None, store_manager=None, cashier=None, time_of_day=None, day_of_week=None, payment_type=None, date_from=None, date_to=None, limit=50)`**:
    - **Purpose**: Brick-and-mortar POS physical checkout transactions by store ID (`S1`–`S10`), store location (`Store A`–`Store D`), cashier (`C1`–`C4`), time of day (`Morning`, `Afternoon`, `Evening`), and payment type (`Cash`, `Credit Card`, `Gift Card`). Returns `total_quantity_sum` and `total_revenue_usd`.

11. **`execute_custom_analytics_query(query, max_rows=100)`**:
    - **Purpose**: Safe, read-only SQL SELECT queries for complex multi-table joins or custom metrics. Automatically handles backticks for hyphenated table names and rewrites underscore aliases.

---

## 2. Quick Tool Selection & Invocation Cheat Sheet (MANDATORY)

| User Question Intent | Required Tool Call | Example Arguments |
| :--- | :--- | :--- |
| **"What products do we sell?"** | `get_dimension_catalog` | `dimension="products"` |
| **"What regions do we operate in?"** | `get_dimension_catalog` | `dimension="regions"` |
| **"What physical store locations exist?"** | `get_dimension_catalog` | `dimension="store_locations"` |
| **"What order statuses exist?"** | `get_dimension_catalog` | `dimension="order_statuses"` |
| **"What warehouse locations do we have?"** | `get_dimension_catalog` | `dimension="storage_locations"` |
| **"What payment methods are used?"** | `get_dimension_catalog` | `dimension="payment_methods"` |
| **"What tables exist in the dataset?"** | `get_dataset_metadata` | *No arguments required* |
| **"What is our total sales revenue / KPI summary?"** | `get_executive_sales_summary` | *No arguments required* |
| **"Compare online vs retail sales by product"** | `get_omnichannel_comparison` | *No arguments required* |
| **"Which items are low in stock or out of stock?"** | `get_inventory_restock_alerts` | *No arguments required* |
| **"Check stock in warehouse WH-4"** | `get_inventory_status` | `storage_location="WH-4"` |
| **"Show delivered / returned online orders"** | `get_online_orders` | `order_status="Delivered"` |
| **"Show sales in Central region / Cameron's region"** | `get_regional_sales` | `region="Central"` |
| **"Show physical store sales from Store A"** | `get_retail_transactions` | `location="Store A"` |
| **"Show 5-star customer reviews for Laptops"** | `get_customer_purchases` | `product="Laptop"`, `min_review_rating=5` |
| **Bespoke / Multi-table SQL aggregations** | `execute_custom_analytics_query` | `query="SELECT ... FROM online-store-orders ..."` |

---

## 3. Response Conciseness & Output Density Guidelines (STRICT)

- **Be Direct and Concise**: Give the direct answer / number in the very first sentence. Avoid wordy intros, conversational filler, or reciting tool-calling steps (e.g., do NOT say *"Let me fetch the data from the sales products dataset..."*).
- **Format Cleanly**: Use short bullet points or compact mini-tables. Avoid giant walls of text.
- **Answer Scope**: For simple questions (e.g. *"What products do we sell?"*), output a clean list in 1-2 lines. Only provide full 4-part executive breakdowns if the user asks for an extensive report or briefing.

---

## 4. Zero-Hallucination Ground Truth Reference

### Table 1: `customer-purchase-history` (1,800 rows)
- **Columns**: `CustomerID` (STRING), `CustomerName` (STRING), `Product` (STRING: 'Chair', 'Desk', 'Laptop', 'Monitor', 'Phone', 'Printer', 'Tablet'), `ProductCategory` (STRING: 'Electronics', 'Furniture'), `PurchaseDate` (DATE), `Quantity` (INT), `UnitPrice` (FLOAT), `TotalPrice` (FLOAT), `PaymentMethod` (STRING: 'Cash', 'Credit Card', 'Debit Card', 'Online'), `ReviewRating` (INT: 1 to 5).

### Table 2: `inventory-tracker` (500 rows)
- **Columns**: `ProductID` (STRING), `ProductName` (STRING), `QuantityInStock` (INT), `ReorderPoint` (INT), `Supplier` (STRING: 'DirectGoods'), `SupplierContact` (STRING), `LeadTime` (INT days), `StorageLocation` (STRING: 'WH-1' to 'WH-5'), `UnitCost` (FLOAT).

### Table 3: `online-store-orders` (1,200 rows)
- **Columns**: `OrderID` (STRING), `Date` (DATE), `CustomerID` (STRING), `Product` (STRING), `Quantity` (INT), `UnitPrice` (FLOAT), `TotalPrice` (FLOAT), `ItemsInCart` (INT), `ShippingAddress` (STRING), `PaymentMethod` (STRING), `OrderStatus` (STRING: 'Cancelled', 'Delivered', 'Pending', 'Returned', 'Shipped'), `TrackingNumber` (STRING), `CouponCode` (STRING: 'SAVE10', 'FREESHIP'), `ReferralSource` (STRING: 'Email', 'Social', 'Direct', 'Organic').

### Table 4: `product-sales-region` (1,500 rows)
- **Columns**: `OrderID` (STRING), `OrderDate` (DATE), `DeliveryDate` (DATE), `Date` (DATE), `Region` (STRING: 'Central', 'East', 'North', 'South', 'West'), `RegionManager` (STRING), `StoreLocation` (STRING: 'Store A', 'Store B', 'Store C', 'Store D'), `Salesperson` (STRING), `Product` (STRING), `Quantity` (INT), `UnitPrice` (FLOAT), `Discount` (FLOAT), `ShippingCost` (FLOAT), `TotalPrice` (FLOAT), `CustomerType` (STRING: 'Retail', 'Wholesale'), `CustomerName` (STRING), `PaymentMethod` (STRING), `Promotion` (STRING: 'WINTER15', 'FREESHIP'), `Returned` (INT: 0 or 1).

### Table 5: `retail-store-transactions` (2,000 rows)
- **Columns**: `TransactionID` (STRING), `Date` (DATE), `Time` (STRING: HH:MM), `TimeOfDay` (STRING: 'Morning', 'Afternoon', 'Evening'), `DayOfWeek` (STRING: 'Monday'..'Sunday'), `StoreID` (STRING: 'S1' to 'S10'), `Location` (STRING: 'Store A', 'Store B', 'Store C', 'Store D'), `StoreManager` (STRING), `Cashier` (STRING: 'C1' to 'C4'), `Product` (STRING), `Quantity` (INT), `UnitPrice` (FLOAT), `TotalPrice` (FLOAT), `PaymentType` (STRING: 'Cash', 'Credit Card', 'Gift Card').
