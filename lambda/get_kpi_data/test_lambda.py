"""
Unit tests for get_kpi_data lambda_function.

Covers both direct JSON invocation (AgentCore) and the legacy
Bedrock action group envelope format.
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Allow importing the lambda module from this directory
sys.path.insert(0, os.path.dirname(__file__))

from lambda_function import extract_parameters, lambda_handler

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

ACTION_GROUP_EVENT = {
    "requestBody": {
        "content": {
            "application/json": {
                "properties": [
                    {"name": "kpi_ids", "value": "17870,17868"},
                    {"name": "date_range", "value": "2024-01 to 2024-03"},
                    {"name": "frequency", "value": "monthly"},
                    {"name": "org_id", "value": "org123"},
                ]
            }
        }
    },
    "actionGroup": "GetKpiDataActionGroup",
    "apiPath": "/get_kpi_data",
    "httpMethod": "POST",
}

DIRECT_JSON_EVENT = {
    "kpi_ids": "17870,17868",
    "date_range": "2024-01 to 2024-03",
    "frequency": "monthly",
    "org_id": "org123",
}


# ---------------------------------------------------------------------------
# extract_parameters tests
# ---------------------------------------------------------------------------

class TestExtractParameters(unittest.TestCase):

    def test_direct_json_returns_event_as_is(self):
        params = extract_parameters(DIRECT_JSON_EVENT)
        self.assertEqual(params, DIRECT_JSON_EVENT)

    def test_action_group_envelope_parsed_correctly(self):
        params = extract_parameters(ACTION_GROUP_EVENT)
        self.assertEqual(params["kpi_ids"], "17870,17868")
        self.assertEqual(params["date_range"], "2024-01 to 2024-03")
        self.assertEqual(params["frequency"], "monthly")
        self.assertEqual(params["org_id"], "org123")

    def test_direct_json_empty_dict(self):
        self.assertEqual(extract_parameters({}), {})

    def test_direct_json_multiple_keys(self):
        payload = {"kpi_ids": "1,2", "date_range": "2024-01 to 2024-02", "extra": "val"}
        self.assertEqual(extract_parameters(payload), payload)


# ---------------------------------------------------------------------------
# lambda_handler tests — direct JSON invocation
# ---------------------------------------------------------------------------

def _make_mock_conn(rows):
    """Return a mock pymysql connection that yields `rows` from fetchall()."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


class TestLambdaHandlerDirect(unittest.TestCase):

    def _patch_db(self, rows=None):
        return patch(
            "lambda_function.get_db_connection",
            return_value=_make_mock_conn(rows or []),
        )

    def _patch_kpi_mapping(self):
        return patch("lambda_function.get_cached_kpi_mapping", return_value={})

    def test_direct_returns_plain_dict(self):
        with self._patch_db(), self._patch_kpi_mapping():
            result = lambda_handler(DIRECT_JSON_EVENT, None)

        self.assertIsInstance(result, dict)
        self.assertNotIn("messageVersion", result)
        self.assertIn("kpi_data", result)
        self.assertIn("kpi_ids", result)

    def test_direct_empty_kpi_ids_returns_error_dict(self):
        result = lambda_handler({"kpi_ids": "", "date_range": "2024-01 to 2024-03"}, None)
        self.assertNotIn("messageVersion", result)
        self.assertIn("error", result)

    def test_direct_error_returns_plain_error_dict(self):
        with patch("lambda_function.get_db_connection", side_effect=RuntimeError("db down")):
            with self._patch_kpi_mapping():
                result = lambda_handler(DIRECT_JSON_EVENT, None)

        self.assertNotIn("messageVersion", result)
        self.assertIn("error", result)
        self.assertIn("kpi_data", result)


# ---------------------------------------------------------------------------
# lambda_handler tests — action group invocation
# ---------------------------------------------------------------------------

class TestLambdaHandlerActionGroup(unittest.TestCase):

    def _patch_db(self, rows=None):
        return patch(
            "lambda_function.get_db_connection",
            return_value=_make_mock_conn(rows or []),
        )

    def _patch_kpi_mapping(self):
        return patch("lambda_function.get_cached_kpi_mapping", return_value={})

    def test_action_group_returns_envelope(self):
        with self._patch_db(), self._patch_kpi_mapping():
            result = lambda_handler(ACTION_GROUP_EVENT, None)

        self.assertIn("messageVersion", result)
        self.assertIn("response", result)
        self.assertEqual(result["response"]["httpStatusCode"], 200)

        body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
        self.assertIn("kpi_data", body)

    def test_action_group_empty_kpi_ids_returns_400_envelope(self):
        event = {
            "requestBody": {
                "content": {
                    "application/json": {
                        "properties": [
                            {"name": "kpi_ids", "value": ""},
                            {"name": "date_range", "value": "2024-01 to 2024-03"},
                        ]
                    }
                }
            },
            "actionGroup": "GetKpiDataActionGroup",
            "apiPath": "/get_kpi_data",
            "httpMethod": "POST",
        }
        result = lambda_handler(event, None)
        self.assertIn("messageVersion", result)
        self.assertEqual(result["response"]["httpStatusCode"], 400)

    def test_action_group_error_returns_500_envelope(self):
        with patch("lambda_function.get_db_connection", side_effect=RuntimeError("boom")):
            with self._patch_kpi_mapping():
                result = lambda_handler(ACTION_GROUP_EVENT, None)

        self.assertIn("messageVersion", result)
        self.assertEqual(result["response"]["httpStatusCode"], 500)


if __name__ == "__main__":
    unittest.main()
