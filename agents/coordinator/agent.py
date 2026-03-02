import json
import os

import boto3
from strands import Agent, tool
from strands.models import BedrockModel

from agents.analysis.agent import analysis_agent
from agents.coordinator.prompts import COORDINATOR_SYSTEM_PROMPT
from agents.coordinator.web_search import nova_grounding_search
from agents.specialist.agent import data_specialist_agent

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
def get_available_kpis(customer: str) -> dict:
    """Returns available KPI IDs and definitions for a given customer.
    Call this first to identify which KPI IDs to pass to the data_specialist.

    Args:
        customer: Customer/chain name (e.g. 'Customer A') or 'all' for all customers
    """
    return _invoke_lambda("queen-get-available-kpis-lambda", {"customer": customer})


@tool
def web_search(query: str) -> dict:
    """Searches the web for external information about companies, market trends, or news.
    Use when the question requires information not available in the internal database.

    Args:
        query: A concise search query
    """
    return nova_grounding_search(query)


@tool
def data_specialist(question: str, context: str, kpi_ids: str = "") -> str:
    """Delegates complex data retrieval and analysis to the Data Specialist Agent.
    Use for any question requiring KPI data retrieval or SQL query execution.

    Args:
        question: The user's data question (be specific — include customer, date range, metric)
        context: Relevant conversation context (customer name, date range, prior results, org_id)
        kpi_ids: Optional comma-separated KPI IDs from get_available_kpis
    """
    prompt = f"Context: {context}\n\nQuestion: {question}"
    if kpi_ids:
        prompt += f"\n\nAvailable KPI IDs: {kpi_ids}"
    return str(data_specialist_agent(prompt))


@tool
def analysis(raw_data: str, question: str) -> str:
    """Formats raw data into a user-facing response with markdown tables, insights,
    and follow-up question suggestions. Always call this last before responding to the user.

    Args:
        raw_data: JSON string or text of retrieved KPI or SQL data
        question: The original user question for context
    """
    prompt = f"Question: {question}\n\nRaw data:\n{raw_data}\n\nFormat this into a response."
    return str(analysis_agent(prompt))


coordinator_agent = Agent(
    model=BedrockModel(
        model_id="us.anthropic.claude-haiku-4-5",
        region_name=AWS_REGION,
    ),
    system_prompt=COORDINATOR_SYSTEM_PROMPT,
    tools=[get_available_kpis, web_search, data_specialist, analysis],
)
