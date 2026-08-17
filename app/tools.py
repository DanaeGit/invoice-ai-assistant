from boto3.dynamodb.conditions import Attr
from strands import tool

from app.db import get_invoices_table



@tool
def get_invoice_by_id(invoice_id: str) -> dict | None:
    """Look up a single invoice by its exact invoice ID.

    Args:
        invoice_id: The invoice's unique ID, e.g. "inv-001".
    """
    table = get_invoices_table()
    response = table.get_item(Key={"invoice_id": invoice_id})
    return response.get("Item")


@tool
def search_invoices_by_vendor(vendor: str) -> list[dict]:
    """Find all invoices from a given vendor.

    Args:
        vendor: The vendor/supplier name to search for, e.g. "Acme Corp".
    """
    table = get_invoices_table()
    response = table.scan(FilterExpression=Attr("vendor").eq(vendor))
    return response.get("Items",[])

if __name__ == "__main__":
    print(get_invoice_by_id("inv-001"))
    print(search_invoices_by_vendor("Acme Corp"))