"""
Tests for SQL Executor Lambda function.

Covers:
- extract_parameters: both direct JSON and Bedrock action group envelope
- validate_sql_security: forbidden operations, multi-statement, non-SELECT
- lambda_handler: direct JSON invocation and action group invocation
"""

import json
import pytest

from lambda_function import (
    extract_parameters,
    validate_sql_security,
    lambda_handler,
    FORBIDDEN_OPERATIONS,
)


# ---------------------------------------------------------------------------
# extract_parameters
# ---------------------------------------------------------------------------

class TestExtractParameters:
    def test_direct_json_returned_as_is(self):
        payload = {"sql_query": "SELECT 1", "org_id": "org_123"}
        assert extract_parameters(payload) == payload

    def test_direct_json_empty_dict(self):
        assert extract_parameters({}) == {}

    def test_bedrock_envelope_extracts_properties(self):
        event = {
            "requestBody": {
                "content": {
                    "application/json": {
                        "properties": [
                            {"name": "sql_query", "value": "SELECT 1"},
                            {"name": "org_id", "value": "org_abc"},
                        ]
                    }
                }
            }
        }
        result = extract_parameters(event)
        assert result == {"sql_query": "SELECT 1", "org_id": "org_abc"}

    def test_bedrock_envelope_multiple_properties(self):
        event = {
            "requestBody": {
                "content": {
                    "application/json": {
                        "properties": [
                            {"name": "sql_query", "value": "SELECT * FROM t"},
                            {"name": "org_id", "value": "org_1"},
                            {"name": "timeout", "value": "60"},
                        ]
                    }
                }
            }
        }
        result = extract_parameters(event)
        assert result["timeout"] == "60"
        assert result["sql_query"] == "SELECT * FROM t"


# ---------------------------------------------------------------------------
# validate_sql_security
# ---------------------------------------------------------------------------

class TestValidateSqlSecurity:
    def test_valid_select_passes(self):
        result = validate_sql_security("SELECT * FROM users WHERE org_id = 'x'")
        assert result["valid"] is True

    def test_select_with_where_and_limit(self):
        result = validate_sql_security(
            "SELECT id, name FROM orders WHERE org_id = 'o1' LIMIT 100"
        )
        assert result["valid"] is True

    @pytest.mark.parametrize("op", FORBIDDEN_OPERATIONS)
    def test_forbidden_operation_rejected(self, op):
        query = f"{op} INTO users VALUES (1)"
        result = validate_sql_security(query)
        assert result["valid"] is False
        assert "error" in result

    def test_forbidden_op_case_insensitive(self):
        result = validate_sql_security("insert into users values (1)")
        assert result["valid"] is False

    def test_forbidden_op_not_triggered_by_substring(self):
        # "INSERTED" should not trigger the INSERT rule
        result = validate_sql_security("SELECT inserted_at FROM logs")
        assert result["valid"] is True

    def test_multi_statement_rejected(self):
        result = validate_sql_security("SELECT 1; DROP TABLE users")
        assert result["valid"] is False

    def test_two_selects_rejected(self):
        result = validate_sql_security("SELECT 1; SELECT 2")
        assert result["valid"] is False

    def test_trailing_semicolon_allowed(self):
        # A single statement with a trailing semicolon is fine
        result = validate_sql_security("SELECT 1;")
        assert result["valid"] is True

    def test_non_select_rejected(self):
        result = validate_sql_security("SHOW TABLES")
        assert result["valid"] is False

    def test_error_message_does_not_expose_schema(self):
        result = validate_sql_security("DROP TABLE secret_table")
        assert "secret_table" not in result.get("error", "")


# ---------------------------------------------------------------------------
# lambda_handler — direct JSON invocation
# ---------------------------------------------------------------------------

class TestLambdaHandlerDirect:
    """Tests that don't require a real DB connection (validation paths only)."""

    def test_missing_sql_query_returns_error(self):
        event = {"org_id": "org_1"}
        response = lambda_handler(event, None)
        assert response["success"] is False
        assert "sql_query" in response["error"]

    def test_missing_org_id_returns_error(self):
        event = {"sql_query": "SELECT 1"}
        response = lambda_handler(event, None)
        assert response["success"] is False
        assert "org_id" in response["error"]

    def test_forbidden_operation_returns_error(self):
        event = {"sql_query": "DELETE FROM users WHERE id = 1", "org_id": "org_1"}
        response = lambda_handler(event, None)
        assert response["success"] is False
        assert "Forbidden" in response["error"] or "forbidden" in response["error"].lower()

    def test_multi_statement_returns_error(self):
        event = {"sql_query": "SELECT 1; DROP TABLE users", "org_id": "org_1"}
        response = lambda_handler(event, None)
        assert response["success"] is False

    def test_non_select_returns_error(self):
        event = {"sql_query": "SHOW TABLES", "org_id": "org_1"}
        response = lambda_handler(event, None)
        assert response["success"] is False

    def test_direct_response_is_plain_dict(self):
        """Direct invocation must NOT return a statusCode/body wrapper."""
        event = {"sql_query": "DELETE FROM t", "org_id": "org_1"}
        response = lambda_handler(event, None)
        assert "statusCode" not in response
        assert "messageVersion" not in response


# ---------------------------------------------------------------------------
# lambda_handler — Bedrock action group invocation
# ---------------------------------------------------------------------------

class TestLambdaHandlerActionGroup:
    def _make_event(self, sql_query: str, org_id: str) -> dict:
        return {
            "actionGroup": "ExecuteSqlQueryActionGroup",
            "apiPath": "/execute_sql_query",
            "httpMethod": "POST",
            "requestBody": {
                "content": {
                    "application/json": {
                        "properties": [
                            {"name": "sql_query", "value": sql_query},
                            {"name": "org_id", "value": org_id},
                        ]
                    }
                }
            }
        }

    def test_action_group_response_has_envelope(self):
        event = self._make_event("DELETE FROM t", "org_1")
        response = lambda_handler(event, None)
        assert "messageVersion" in response
        assert "response" in response

    def test_action_group_forbidden_op_returns_403(self):
        event = self._make_event("DROP TABLE users", "org_1")
        response = lambda_handler(event, None)
        assert response["response"]["httpStatusCode"] == 403

    def test_action_group_missing_query_returns_400(self):
        event = {
            "actionGroup": "ExecuteSqlQueryActionGroup",
            "apiPath": "/execute_sql_query",
            "httpMethod": "POST",
            "requestBody": {
                "content": {
                    "application/json": {
                        "properties": [
                            {"name": "org_id", "value": "org_1"},
                        ]
                    }
                }
            }
        }
        response = lambda_handler(event, None)
        assert response["response"]["httpStatusCode"] == 400

    def test_action_group_missing_org_id_returns_400(self):
        event = {
            "actionGroup": "ExecuteSqlQueryActionGroup",
            "apiPath": "/execute_sql_query",
            "httpMethod": "POST",
            "requestBody": {
                "content": {
                    "application/json": {
                        "properties": [
                            {"name": "sql_query", "value": "SELECT 1"},
                        ]
                    }
                }
            }
        }
        response = lambda_handler(event, None)
        assert response["response"]["httpStatusCode"] == 400

    def test_action_group_body_is_json_string(self):
        event = self._make_event("INSERT INTO t VALUES (1)", "org_1")
        response = lambda_handler(event, None)
        body_str = response["response"]["responseBody"]["application/json"]["body"]
        body = json.loads(body_str)
        assert "success" in body
        assert body["success"] is False
