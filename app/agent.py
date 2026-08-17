import os

import boto3
from dotenv import load_dotenv
from strands import Agent
from strands.models import BedrockModel

from app.tools import get_invoice_by_id, search_invoices_by_vendor

load_dotenv()


def build_agent() -> Agent:
    session = boto3.Session(profile_name=os.getenv("BEDROCK_AWS_PROFILE"))
    model = BedrockModel(
        model_id=os.getenv("BEDROCK_MODEL_ID"),
        boto_session=session,
    )
    return Agent(
        model=model,
        tools = [get_invoice_by_id, search_invoices_by_vendor],
        system_prompt="You are an invoice assistant. Use the tools to answer questions about invoices stored in the database."
    )


if __name__ == "__main__":
    agent = build_agent()
    agent("What is the vendor for invoice inv-001?")