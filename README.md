# OrderFlow

A Python order management project with product inventory, payment and delivery strategies, and JSON catalog persistence.

## Features

- Validated products with stock management.
- Orders with `NEW`, `PAID`, and `CANCELLED` states.
- Abstract payment and delivery interfaces with interchangeable implementations.
- Fixed order line prices and stored payment totals, delivery costs, and receipts.
- Decimal arithmetic for monetary values.
- JSON catalog loading and atomic file replacement on save.
- Automated tests with pytest.

## Requirements

- Python 3.10 or later
- pip

The application uses only the Python standard library. pytest is required for development.

## Installation

From the project directory, create a virtual environment:

```bash
python -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Or on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the package and development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Use `python3` instead of `python` if required by your system. For application use without development dependencies, run `python -m pip install .`.

## Quick start

Run the example:

```bash
python -m orderflow
```

Output:

```text
Paid 1004500.00 KZT via Kaspi
Status: PAID; remaining stock: 8
```

The example runs in memory and does not modify files.

## Usage

```python
from orderflow import Product, Order, CardPayment, StandardDelivery

product = Product(id=1, name="Keyboard", price="25000.00", stock=5)
order = Order(order_id=101)
order.add_product(product, quantity=2)

receipt = order.pay(CardPayment(), StandardDelivery(), distance=10)

print(receipt)             # Paid 52000.00 KZT via Card
print(order.status)        # PAID
print(order.paid_amount)   # 52000.00
print(order.delivery_cost) # 2000.00
print(product.stock)       # 3
```

### Product catalog

```python
from orderflow import Product, load_products, save_products

products = [Product(1, "Keyboard", "25000.00", 5)]
save_products(products, "products.json")
loaded_products = load_products("products.json")
```

The catalog is a JSON array with unique positive integer product IDs:

```json
[
  {
    "id": 1,
    "name": "Keyboard",
    "price": "25000.00",
    "stock": 5
  }
]
```

Prices are stored as strings to preserve decimal values. The destination directory must exist. Invalid catalog entries raise `ValueError`; missing files and malformed JSON raise `FileNotFoundError` and `json.JSONDecodeError`, respectively.

### Order snapshots

```python
import json

with open("order-101.json", "w", encoding="utf-8") as file:
    json.dump(order.to_dict(), file, ensure_ascii=False, indent=2)
```

The snapshot contains product IDs, names, quantities, fixed unit prices, subtotal, delivery cost, paid amount, and receipt. Payment fields are `None` before payment and become `null` in JSON. Order snapshots can be exported; restoring an order from a snapshot is not implemented.

## Order behavior

An order starts as `NEW` and can transition to `PAID` or `CANCELLED`. Paid and cancelled orders cannot be modified or paid again.

The unit price is captured when a product is first added. Adding the same product object again increases its quantity at that original price. A different product object with the same ID is rejected. Order items are exposed as an immutable tuple of frozen `OrderItem` records.

Stock is checked when adding products and again before payment. Adding an item does not reserve stock. Stock is reduced after the payment method returns a valid receipt. If payment raises an exception or returns an invalid receipt, the order and stock remain unchanged under the payment interface contract.

After payment, `paid_amount`, `delivery_cost`, and `receipt` remain available. `calculate_total()` returns the item subtotal; `calculate_final_total(delivery_method, distance)` returns the stored paid amount for a paid order, regardless of the supplied delivery arguments.

## Payments and delivery

`PaymentMethod` defines `pay(amount)`. An implementation must return a non-empty receipt string on success or raise an exception on failure. It must not modify the order or product inventory.

`KaspiPayment` and `CardPayment` simulate payments locally. They do not connect to a bank or transfer money.

`DeliveryMethod` defines `calculate_cost(distance)`.

| Method | Cost |
| --- | --- |
| `StandardDelivery` | 200 KZT per kilometer |
| `ExpressDelivery` | 350 KZT per kilometer + 1,000 KZT |

Distances must be finite and greater than zero. Custom delivery methods must return a finite, non-negative cost.

## Validation and money

- Product and order IDs must be positive integers.
- Product names must be non-empty strings.
- Stock must be a non-negative integer; quantities must be positive integers.
- Booleans are rejected for numeric fields.
- Money uses `Decimal` and is rounded to two decimal places with `ROUND_HALF_UP`.
- Prices must be positive after rounding. NaN and infinite values are rejected.
- Numbers and decimal strings are accepted for money and distances. Use strings such as `"10.25"` for exact decimal input.

## Tests

```bash
python -m pytest -q
```

The suite covers input validation, inventory changes, delivery rates, fixed order prices, saved payment totals, failed and repeated payments, order state restrictions, and JSON persistence.

## Project structure

```text
OrderFlow/
├── orderflow/
│   ├── __init__.py
│   ├── __main__.py
│   ├── catalog.py
│   └── core.py
├── tests/
│   └── test_orderflow.py
├── products.json
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
├── LICENSE
└── README.md
```

## Scope

OrderFlow is intended for sequential execution in a single process. Production payment processing and concurrent inventory updates require transactional storage, stock reservation, and idempotent payment handling.

## Author

[proxejDias](https://github.com/proxejDias)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
