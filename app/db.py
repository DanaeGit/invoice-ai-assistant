import os

import boto3
from dotenv import load_dotenv

load_dotenv()

def get_invoices_table():
    dynamodb = boto3.resource(
        "dynamodb",
        region_name = os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        endpoint_url = os.getenv("DYNAMODB_ENDPOINT_URL"),
    )
    return dynamodb.Table("Invoices")

if __name__ == "__main__":
    table = get_invoices_table()
    responce = table.scan()
    print(responce["Items"])
