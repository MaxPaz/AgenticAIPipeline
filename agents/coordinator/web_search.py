"""
Web search via Amazon Nova 2 Lite with nova_grounding.

Replaces the old Nova Act browser automation — dramatically faster (1-2s vs 60s).
"""

import os
import boto3

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
_NOVA_MODEL_ID = "us.amazon.nova-2-lite-v1:0"
_TOOL_CONFIG = {"tools": [{"systemTool": {"name": "nova_grounding"}}]}


def nova_grounding_search(query: str, region: str = AWS_REGION) -> dict:
    """
    Perform a web search using Nova 2 Lite with nova_grounding.

    Args:
        query: The search query string.
        region: AWS region for the bedrock-runtime client.

    Returns:
        {
            "content": "extracted text from the response",
            "citations": [{"url": "...", "domain": "..."}, ...]  # up to 5
        }
        On failure returns {"content": "", "citations": [], "error": "..."}.
    """
    try:
        bedrock = boto3.client("bedrock-runtime", region_name=region)
        response = bedrock.converse(
            modelId=_NOVA_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": query}]}],
            toolConfig=_TOOL_CONFIG,
            inferenceConfig={"maxTokens": 1000, "temperature": 0},
        )

        content_list = response["output"]["message"]["content"]
        text_parts = []
        citations = []

        for item in content_list:
            if "text" in item:
                text_parts.append(item["text"])
            elif "citationsContent" in item:
                for c in item["citationsContent"].get("citations", []):
                    url = c.get("location", {}).get("web", {}).get("url", "")
                    domain = c.get("location", {}).get("web", {}).get("domain", "")
                    if url:
                        citations.append({"url": url, "domain": domain})

        return {
            "content": "\n".join(text_parts),
            "citations": citations[:5],
        }

    except Exception as e:
        return {"content": "", "citations": [], "error": str(e)}
