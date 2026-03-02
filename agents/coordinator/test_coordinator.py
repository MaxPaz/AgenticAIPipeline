"""
Unit tests for the Coordinator Agent.
Requirements: 1.3, 2.1, 2.2, 2.3, 10.3
"""
import ast
import inspect
import pathlib


# ---------------------------------------------------------------------------
# Prompt tests (import only the prompt string — no boto3/strands init)
# ---------------------------------------------------------------------------

from agents.coordinator.prompts import COORDINATOR_SYSTEM_PROMPT


class TestCoordinatorSystemPrompt:
    def test_prompt_contains_data_retrieval_strategy(self):
        """COORDINATOR_SYSTEM_PROMPT must describe the data retrieval strategy (Req 1.3)."""
        assert "Data Retrieval Strategy" in COORDINATOR_SYSTEM_PROMPT or "data retrieval" in COORDINATOR_SYSTEM_PROMPT.lower()

    def test_prompt_contains_response_format(self):
        """COORDINATOR_SYSTEM_PROMPT must specify the JSON response format (Req 6.5)."""
        assert "response" in COORDINATOR_SYSTEM_PROMPT
        assert "suggested_questions" in COORDINATOR_SYSTEM_PROMPT

    def test_prompt_contains_context_resolution(self):
        """COORDINATOR_SYSTEM_PROMPT must include context resolution guidance (Req 4.2)."""
        lower = COORDINATOR_SYSTEM_PROMPT.lower()
        assert "context" in lower

    def test_prompt_mentions_all_four_tools(self):
        """COORDINATOR_SYSTEM_PROMPT must reference all four tools."""
        assert "get_available_kpis" in COORDINATOR_SYSTEM_PROMPT
        assert "web_search" in COORDINATOR_SYSTEM_PROMPT
        assert "data_specialist" in COORDINATOR_SYSTEM_PROMPT
        assert "analysis" in COORDINATOR_SYSTEM_PROMPT

    def test_prompt_contains_org_id_security_guidance(self):
        """COORDINATOR_SYSTEM_PROMPT must mention org_id for security (Req 11.1)."""
        assert "org_id" in COORDINATOR_SYSTEM_PROMPT

    def test_prompt_contains_json_response_structure(self):
        """Response format must specify JSON with response and suggested_questions keys."""
        assert '"response"' in COORDINATOR_SYSTEM_PROMPT or "'response'" in COORDINATOR_SYSTEM_PROMPT
        assert "suggested_questions" in COORDINATOR_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Tool registration tests — parse agent.py with AST to avoid boto3/strands init
# ---------------------------------------------------------------------------

_AGENT_FILE = pathlib.Path(__file__).parent / "agent.py"


def _load_coordinator_source() -> str:
    return _AGENT_FILE.read_text()


def _get_coordinator_tools_list() -> list[str]:
    """
    Parse agents/coordinator/agent.py and extract the list of tool names
    passed to Agent(..., tools=[...]) without executing the module.
    """
    source = _load_coordinator_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "coordinator_agent":
                call = node.value
                if not isinstance(call, ast.Call):
                    continue
                for kw in call.keywords:
                    if kw.arg == "tools" and isinstance(kw.value, ast.List):
                        return [
                            elt.id
                            for elt in kw.value.elts
                            if isinstance(elt, ast.Name)
                        ]
    return []


class TestCoordinatorToolRegistration:
    def test_get_available_kpis_registered(self):
        """get_available_kpis must be registered on the coordinator (Req 2.1)."""
        tools = _get_coordinator_tools_list()
        assert "get_available_kpis" in tools, f"get_available_kpis not in tools: {tools}"

    def test_web_search_registered(self):
        """web_search must be registered on the coordinator (Req 2.2)."""
        tools = _get_coordinator_tools_list()
        assert "web_search" in tools, f"web_search not in tools: {tools}"

    def test_data_specialist_registered(self):
        """data_specialist must be registered on the coordinator (Req 2.3)."""
        tools = _get_coordinator_tools_list()
        assert "data_specialist" in tools, f"data_specialist not in tools: {tools}"

    def test_analysis_registered(self):
        """analysis must be registered on the coordinator."""
        tools = _get_coordinator_tools_list()
        assert "analysis" in tools, f"analysis not in tools: {tools}"

    def test_exactly_four_tools_registered(self):
        """Coordinator Agent should have exactly 4 tools."""
        tools = _get_coordinator_tools_list()
        assert len(tools) == 4, f"Expected 4 tools, got {len(tools)}: {tools}"


# ---------------------------------------------------------------------------
# web_search.py — model ID and toolConfig tests (Req 10.3)
# ---------------------------------------------------------------------------

from agents.coordinator.web_search import _NOVA_MODEL_ID, _TOOL_CONFIG


class TestWebSearchConfiguration:
    def test_nova_model_id_is_correct(self):
        """web_search must use us.amazon.nova-2-lite-v1:0 (Req 10.3)."""
        assert _NOVA_MODEL_ID == "us.amazon.nova-2-lite-v1:0"

    def test_tool_config_contains_nova_grounding(self):
        """toolConfig must include the nova_grounding system tool (Req 10.3)."""
        tools = _TOOL_CONFIG.get("tools", [])
        assert len(tools) == 1
        system_tool = tools[0].get("systemTool", {})
        assert system_tool.get("name") == "nova_grounding"

    def test_tool_config_structure(self):
        """toolConfig must have the correct nested structure."""
        assert "tools" in _TOOL_CONFIG
        assert isinstance(_TOOL_CONFIG["tools"], list)
        assert "systemTool" in _TOOL_CONFIG["tools"][0]

    def test_nova_grounding_search_function_exists(self):
        """nova_grounding_search must be importable from web_search module."""
        from agents.coordinator.web_search import nova_grounding_search
        assert callable(nova_grounding_search)

    def test_nova_grounding_search_accepts_query_param(self):
        """nova_grounding_search must accept a query parameter."""
        from agents.coordinator.web_search import nova_grounding_search
        sig = inspect.signature(nova_grounding_search)
        assert "query" in sig.parameters
