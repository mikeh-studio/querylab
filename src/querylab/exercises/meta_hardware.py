"""Fictional hardware sales practice; all quantities and prices are synthetic."""

from querylab.models import ExerciseSet


def get_meta_hardware_exercise_set() -> ExerciseSet:
    """Return three progressively deeper questions over a shared sales cohort."""
    date_filter = "s.sale_date >= DATE '2025-01-01' AND s.sale_date < DATE '2025-02-01'"
    returns_cte = """WITH returned AS (
        SELECT sale_id, SUM(quantity) AS returned_units,
               SUM(refund_amount) AS refunds
        FROM returns WHERE return_date < DATE '2025-03-01'
        GROUP BY sale_id
    )"""
    questions = [
        {
            "id": "hardware_sales",
            "difficulty": "medium",
            "concepts": ["joins", "aggregation", "date boundaries"],
            "task_summary": "Compare January hardware sales across products and channels. Which combinations generated the most revenue?",
            "question": "Report January 2025 hardware sales by product and channel. Return product_name, channel, units_sold, and gross_revenue. Include completed sales only, before subtracting returns. Order by gross_revenue descending, then product_name and channel ascending.",
            "requirements": [
                "Return product_name, channel, units_sold, and gross_revenue.",
                "Include completed sales from Jan 1 inclusive to Feb 1 exclusive, 2025.",
                "Revenue = quantity × unit_price; prices are synthetic USD amounts before tax.",
                "Include only product/channel pairs with qualifying sales. Do not subtract returns yet.",
                "Order by gross_revenue descending, then product_name and channel ascending.",
            ],
            "reference_sql": f"""SELECT p.product_name, s.channel,
    SUM(s.quantity) AS units_sold,
    SUM(s.quantity * s.unit_price) AS gross_revenue
FROM sales AS s
JOIN products AS p ON p.product_id = s.product_id
WHERE s.status = 'completed'
  AND {date_filter}
GROUP BY p.product_name, s.channel
ORDER BY gross_revenue DESC, p.product_name, s.channel;""",
            "explanation": "Aggregate at product and channel grain. Filter completed sales using a half-open date interval; returns are a separate metric.",
            "hints": [
                "Join sales to products for the product name.",
                "Sum quantity, not the number of sales rows.",
                "Multiply quantity by the actual unit price on each sale.",
            ],
        },
        {
            "id": "hardware_returns",
            "difficulty": "medium",
            "concepts": ["CTEs", "left joins", "weighted rates"],
            "task_summary": "Check how much of January's hardware volume was returned by the end of February. Compare unit return rates by product.",
            "question": "For each product with completed January 2025 sales, return product_name, units_sold, returned_units, and return_rate. Include returns recorded before March 1, 2025 for those sales. Round returned_units / units_sold to three decimals; use zero for products with no returns. Order by product_name.",
            "requirements": [
                "Use completed January sales as the cohort; count returns recorded before March 1, 2025.",
                "Return product_name, units_sold, returned_units, and return_rate (a fraction rounded to 3 decimals).",
                "A sale can have multiple partial returns. Avoid multiplying sold units when joining.",
                "Keep products with sales but no returns; order by product_name.",
            ],
            "reference_sql": f"""{returns_cte}
SELECT p.product_name, SUM(s.quantity) AS units_sold,
    SUM(COALESCE(r.returned_units, 0)) AS returned_units,
    ROUND(SUM(COALESCE(r.returned_units, 0)) * 1.0 / SUM(s.quantity), 3) AS return_rate
FROM sales s JOIN products p ON p.product_id = s.product_id
LEFT JOIN returned r ON r.sale_id = s.sale_id
WHERE s.status = 'completed' AND {date_filter}
GROUP BY p.product_name ORDER BY p.product_name;""",
            "explanation": "Aggregate partial returns per sale before joining. Divide total returned units by total sold units rather than averaging row-level rates.",
            "hints": [
                "Reduce returns to one row per sale first.",
                "Use a LEFT JOIN to retain sales with no returns.",
            ],
        },
        {
            "id": "hardware_net_revenue",
            "difficulty": "medium",
            "concepts": ["CTEs", "joins", "NULL handling"],
            "task_summary": "Reconcile January sales with refunds through February to see which product and channel combinations retained the most revenue.",
            "question": "For completed January 2025 sales, return product_name, channel, gross_revenue, refunds, and net_revenue. Subtract refund_amount for returns recorded before March 1, 2025 for those sales. Use zero when no refund exists. Order by net_revenue descending, then product_name and channel ascending.",
            "requirements": [
                "Return product_name, channel, gross_revenue, refunds, and net_revenue.",
                "Use completed January 2025 sales and their returns recorded before March 1, 2025.",
                "Sum refund_amount rather than inferring refunds from product prices.",
                "Retain sales with no returns and avoid duplicating revenue across partial returns.",
                "Order by net_revenue descending, then product_name and channel ascending.",
            ],
            "reference_sql": f"""{returns_cte}
SELECT p.product_name, s.channel,
    SUM(s.quantity * s.unit_price) AS gross_revenue,
    SUM(COALESCE(r.refunds, 0)) AS refunds,
    SUM(s.quantity * s.unit_price) - SUM(COALESCE(r.refunds, 0)) AS net_revenue
FROM sales s JOIN products p ON p.product_id = s.product_id
LEFT JOIN returned r ON r.sale_id = s.sale_id
WHERE s.status = 'completed' AND {date_filter}
GROUP BY p.product_name, s.channel
ORDER BY net_revenue DESC, p.product_name, s.channel;""",
            "explanation": "Use recorded refunds, aggregate them per sale, then subtract them from gross revenue at product/channel grain.",
            "hints": [
                "Reuse the per-sale returns aggregation from Question 2.",
                "COALESCE missing refunds to zero before summing.",
            ],
        },
    ]
    for question in questions:
        question["grading"] = {"order_matters": True, "numeric_tolerance": 0.000001}
    products = """INSERT INTO products VALUES
        (1, 'Quest 3', 'Headset'), (2, 'Quest 3S', 'Headset'),
        (3, 'Ray-Ban Meta', 'Smart glasses'), (4, 'Quest accessory', 'Accessory');"""
    return ExerciseSet.model_validate(
        {
            "id": "meta_hardware_sales_001",
            "company": "Meta",
            "dialect": "duckdb",
            "business_context": "A fictional Meta hardware team reviews Quest headsets and Ray-Ban Meta glasses sales. All schemas, prices, quantities, and transactions are synthetic practice data, not actual Meta sales or interview materials.",
            "tables": [
                {
                    "name": "products",
                    "description": "One row per product in the fictional catalog.",
                    "ddl": "CREATE TABLE products (product_id INTEGER PRIMARY KEY, product_name VARCHAR NOT NULL, category VARCHAR NOT NULL);",
                },
                {
                    "name": "sales",
                    "description": "One row per product sale; quantity can exceed one. Synthetic USD unit prices exclude tax. Only completed sales count.",
                    "ddl": "CREATE TABLE sales (sale_id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, sale_date DATE NOT NULL, channel VARCHAR NOT NULL, quantity INTEGER NOT NULL, unit_price DECIMAL(12,2) NOT NULL, status VARCHAR NOT NULL);",
                },
                {
                    "name": "returns",
                    "description": "One row per partial return. A sale can have multiple returns; refund_amount is the total USD refund for that row.",
                    "ddl": "CREATE TABLE returns (return_id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL, return_date DATE NOT NULL, quantity INTEGER NOT NULL, refund_amount DECIMAL(12,2) NOT NULL);",
                },
            ],
            "seed_sql": products
            + """
        INSERT INTO sales VALUES
        (101,1,'2025-01-03','Online',4,500,'completed'),
        (102,1,'2025-01-12','Retail',3,480,'completed'),
        (103,2,'2025-01-08','Online',6,300,'completed'),
        (104,2,'2025-01-31','Retail',5,290,'completed'),
        (105,3,'2025-01-15','Online',8,300,'completed'),
        (106,3,'2025-01-22','Retail',10,280,'completed'),
        (107,1,'2025-02-01','Online',20,500,'completed'),
        (108,3,'2025-01-18','Retail',12,280,'cancelled');
        INSERT INTO returns VALUES
        (1,101,'2025-01-20',1,500),(2,101,'2025-02-05',1,500),
        (3,104,'2025-02-15',1,290),(4,106,'2025-02-20',2,560),
        (5,105,'2025-03-01',1,300);
        """,
            "hidden_datasets": [
                {
                    "name": "boundaries_and_partial_returns",
                    "hidden": True,
                    "seed_sql": products
                    + """
            INSERT INTO sales VALUES
            (201,1,'2025-01-01','Online',3,450,'completed'),
            (202,1,'2025-01-31','Online',2,500,'completed'),
            (203,2,'2025-01-10','Retail',4,250,'completed'),
            (204,3,'2024-12-31','Online',99,300,'completed'),
            (205,3,'2025-02-01','Online',99,300,'completed'),
            (206,3,'2025-01-15','Retail',99,300,'cancelled'),
            (207,4,'2025-01-21','Retail',2,50,'completed'),
            (208,2,'2025-01-11','Online',2,500,'completed');
            INSERT INTO returns VALUES
            (11,201,'2025-01-15',1,425),(12,201,'2025-02-28',1,450),
            (13,202,'2025-03-01',1,500),(14,204,'2025-01-20',1,300),
            (15,207,'2025-02-01',2,100);
            """,
                }
            ],
            "questions": questions,
        }
    )
