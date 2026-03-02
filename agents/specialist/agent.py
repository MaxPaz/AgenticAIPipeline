import json
import os

import boto3
from strands import Agent, tool
from strands.models import BedrockModel

from agents.specialist.prompts import SPECIALIST_SYSTEM_PROMPT

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")


def _invoke_lambda(function_name: str, payload: dict) -> dict:
    """Invoke a Lambda function and return the parsed response payload."""
    client = boto3.client("lambda", region_name=AWS_REGION)
    response = client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(payload).encode(),
    )
    result = json.loads(response["Payload"].read())
    if response.get("FunctionError") or (isinstance(result, dict) and result.get("error")):
        return result if isinstance(result, dict) else {"error": result}
    return result


@tool
def get_kpi_data(kpi_ids: str, date_range: str, frequency: str, org_id: str = "default") -> dict:
    """Retrieves pre-calculated KPI data from the reddyice_s3_commercial_money table.

    Args:
        kpi_ids: Comma-separated KPI IDs (e.g. '17870,17868')
        date_range: Date range in format 'YYYY-MM to YYYY-MM'
        frequency: One of 'monthly', 'weekly', 'daily'
        org_id: Organization ID for tenant isolation
    """
    return _invoke_lambda(
        "queen-get-kpi-data-lambda",
        {
            "kpi_ids": kpi_ids,
            "date_range": date_range,
            "frequency": frequency,
            "org_id": org_id,
        },
    )


@tool
def execute_sql_query(sql_query: str, org_id: str) -> dict:
    """Executes a SELECT SQL query against the MySQL database.
    Only SELECT queries are permitted. Always include org_id.

    Args:
        sql_query: A SELECT SQL query using only allowed tables and columns
        org_id: Organization ID for tenant isolation (required)
    """
    return _invoke_lambda(
        "queen-sql-executor-lambda",
        {
            "sql_query": sql_query,
            "org_id": org_id,
        },
    )


data_specialist_agent = Agent(
    model=BedrockModel("us.anthropic.claude-sonnet-4-5"),
    system_prompt=SPECIALIST_SYSTEM_PROMPT,
    tools=[get_kpi_data, execute_sql_query],
)
