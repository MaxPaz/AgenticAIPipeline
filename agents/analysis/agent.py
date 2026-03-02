import os

from strands import Agent
from strands.models import BedrockModel

from agents.analysis.prompts import ANALYSIS_SYSTEM_PROMPT

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")

analysis_agent = Agent(
    model=BedrockModel(
        model_id="us.anthropic.claude-haiku-4-5",
        region_name=AWS_REGION,
    ),
    system_prompt=ANALYSIS_SYSTEM_PROMPT,
    tools=[],  # Pure formatting — no tools
)
