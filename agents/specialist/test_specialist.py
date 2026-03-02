"""
Unit tests for the Data Specialist Agent.
Requirements: 2.4, 2.5, 11.1
"""
import ast
import pathlib


# ---------------------------------------------------------------------------
# Prompt tests (import only the prompt string — no boto3/strands init)
# ---------------------------------------------------------------------------

from agents.specialist.prompts import SPECIALIST_SYSTEM_PROMPT


class TestSpecialistSystemPrompt:
    def test_prompt_contains_schema_section(self):
        """SPECIALIST_SYSTEM_PROMPT must document the database schema."""
        assert "Database Schema" in SPECIALIST_SYSTEM_PROMPT or "reddyice_s3_commercial_money" in SPECIALIST_SYSTEM_PROMPT

    def test_prompt_contains_both_table_names(self):
        """Schema section must reference both tables."""
        assert "reddyice_s3_commercial_money" in SPECIALIST_SYSTEM_PROMPT
        assert "reddyice_s3_order_details" in SPECIALIST_SYSTEM_PROMPT

    def test_prompt_contains_sql_rules_section(self):
        """SPECIALIST_SYSTEM_PROMPT must include SQL generation rules."""
        assert "SQL" in SPECIALIST_SYSTEM_PROMPT
        # Must mention SELECT-only restriction
        assert "SELECT" in SPECIALIST_SYSTEM_PROMPT

    def test_prompt_contains_retry_guidance(self):
        """SPECIALIST_SYSTEM_PROMPT must include retry guidance."""
        lower = SPECIALIST_SYSTEM_PROMPT.lower()
        assert "retry" in lower or "attempt" in lower

    def test_prompt_contains_max_retry_count(self):
        """Retry guidance must specify a maximum of 3 attempts."""
        assert "3" in SPECIALIST_SYSTEM_PROMPT
        lower = SPECIALIST_SYSTEM_PROMPT.lower()
        assert "attempt" in lower or "retry" in lower

    def test_prompt_contains_org_id_requirement(self):
        """SQL rules must mention org_id for tenant isolation (Req 11.1)."""
        assert "org_id" in SPECIALIST_SYSTEM_PROMPT

    def test_prompt_contains_output_format(self):
        """SPECIALIST_SYSTEM_PROMPT must describe the output format."""
        assert "Output Format" in SPECIALIST_SYSTEM_PROMPT or "output" in SPECIALIST_SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# Tool registration tests — parse agent.py with AST to avoid boto3 init
# ---------------------------------------------------------------------------

import pathlib

_AGENT_FILE = pathlib.Path(__file__).parent / "agent.py"


def _load_agent_source() -> str:
    return _AGENT_FILE.read_text()


def _get_agent_tools_list() -> list[str]:
    """
    Parse agents/specialist/agent.py and extract the list of tool names
    passed to Agent(..., tools=[...]) without executing the module.
    """
    source = _load_agent_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        # Look for: data_specialist_agent = Agent(..., tools=[...])
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "data_specialist_agent":
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


class TestSpecialistToolRegistration:
    def test_get_kpi_data_tool_registered(self):
        """get_kpi_data must be in the tools list passed to Agent(...)."""
        tools = _get_agent_tools_list()
        assert "get_kpi_data" in tools, f"get_kpi_data not found in tools: {tools}"

    def test_execute_sql_query_tool_registered(self):
        """execute_sql_query must be in the tools list passed to Agent(...)."""
        tools = _get_agent_tools_list()
        assert "execute_sql_query" in tools, f"execute_sql_query not found in tools: {tools}"

    def test_exactly_two_tools_registered(self):
        """Data Specialist Agent should have exactly 2 tools."""
        tools = _get_agent_tools_list()
        assert len(tools) == 2, f"Expected 2 tools, got {len(tools)}: {tools}"


# ---------------------------------------------------------------------------
# execute_sql_query docstring / signature tests
# ---------------------------------------------------------------------------

def _get_function_source(func_name: str) -> str:
    source = _load_agent_source()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return ast.get_source_segment(source, node) or ""
    return ""


class TestExecuteSqlQueryTool:
    def test_execute_sql_query_docstring_mentions_org_id(self):
        """execute_sql_query docstring must mention org_id (Req 11.1)."""
        source = _load_agent_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "execute_sql_query":
                docstring = ast.get_docstring(node) or ""
                assert "org_id" in docstring, "execute_sql_query docstring must mention org_id"
                return
        raise AssertionError("execute_sql_query function not found in agent.py")

    def test_execute_sql_query_has_org_id_parameter(self):
        """execute_sql_query must declare org_id as a parameter."""
        source = _load_agent_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "execute_sql_query":
                param_names = [arg.arg for arg in node.args.args]
                assert "org_id" in param_names, f"org_id not in params: {param_names}"
                return
        raise AssertionError("execute_sql_query function not found in agent.py")

    def test_execute_sql_query_passes_org_id_to_lambda(self):
        """execute_sql_query must include org_id in the Lambda payload."""
        source = _load_agent_source()
        # The payload dict literal in _invoke_lambda call should contain "org_id"
        assert '"org_id"' in source or "'org_id'" in source
