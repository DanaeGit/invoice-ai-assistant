"""Seed the local (LocalStack) Invoices table with sample data for demos and testing."""

from app.db import get_invoices_table

SAMPLE_INVOICES = [
    {
        "invoice_id": "inv-001",
        "vendor": "Acme Corp",
        "invoice_date": "2026-08-01",
        "currency": "USD",
        "total_amount": 1250,
        "po_number": "po-100",
        "status": "extracted",
        "line_items": [
            {"item_name": "Widget A", "quantity": 10, "unit_price": 100, "amount": 1000},
            {"item_name": "Widget B", "quantity": 5, "unit_price": 50, "amount": 250},
        ],
    },
    {
        "invoice_id": "inv-002",
        "vendor": "Acme Corp",
        "invoice_date": "2026-08-05",
        "currency": "USD",
        "total_amount": 480,
        "po_number": "po-101",
        "status": "extracted",
        "line_items": [
            {"item_name": "Widget A", "quantity": 4, "unit_price": 100, "amount": 400},
            {"item_name": "Shipping", "quantity": 1, "unit_price": 80, "amount": 80},
        ],
    },
    {
        "invoice_id": "inv-003",
        "vendor": "Globex Supplies",
        "invoice_date": "2026-07-20",
        "currency": "USD",
        "total_amount": 3200,
        "po_number": "po-200",
        "status": "extracted",
        "line_items": [
            {"item_name": "Office Chairs", "quantity": 8, "unit_price": 400, "amount": 3200},
        ],
    },
    {
        "invoice_id": "inv-004",
        "vendor": "Globex Supplies",
        "invoice_date": "2026-08-10",
        "currency": "USD",
        "total_amount": 150,
        "po_number": "po-201",
        "status": "pending",
        "line_items": [
            {"item_name": "Printer Paper", "quantity": 15, "unit_price": 10, "amount": 150},
        ],
    },
    {
        "invoice_id": "inv-005",
        "vendor": "Initech Consulting",
        "invoice_date": "2026-08-12",
        "currency": "USD",
        "total_amount": 7500,
        "po_number": "po-300",
        "status": "extracted",
        "line_items": [
            {"item_name": "Consulting Hours", "quantity": 50, "unit_price": 150, "amount": 7500},
        ],
    },
]


def seed() -> None:
    table = get_invoices_table()
    for invoice in SAMPLE_INVOICES:
        table.put_item(Item=invoice)
        print(f"Seeded {invoice['invoice_id']} ({invoice['vendor']})")


if __name__ == "__main__":
    seed()
