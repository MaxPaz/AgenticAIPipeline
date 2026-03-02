"""
Unit tests for get_available_kpis lambda_function.

Covers both direct JSON invocation (AgentCore) and the legacy
Bedrock action group envelope format.
"""

import json
import sys
import os
import unittest
from unittest.mock import patch

# Allow importing the lambda module from this directory
sys.path.insert(0, os.path.dirname(__file__))

from lambda_function import extract_parameters, lambda_handler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_KPIS = [
    {
        "kpi_id": 1,
        "kpi_name": "Revenue",
        "short_definition": "Total revenue",
        "unit": "$",
        "group_name": "Finance",
        "page_name": "Draft Customer A",
    }
]

ACTION_GROUP_EVENT = {
    "requestBody": {
        "content": {
            "application/json": {
                "properties": [{"name": "customer", "value": "Customer A"}]
            }
        }
    },
    "actionGroup": "GetAvailableKpisActionGroup",
    "apiPath": "/get_available_kpis",
    "httpMethod": "POST",
}

DIRECT_JSON_EVENT = {"customer": "Customer A"}


# ---------------------------------------------------------------------------
# extract_parameters tests
# ---------------------------------------------------------------------------

class TestExtractParameters(unittest.TestCase):

    def test_direct_json_returns_event_as_is(self):
        params = extract_parameters({"customer": "Customer A"})
        self.assertEqual(params, {"customer": "Customer A"})

    def test_action_group_envelope_parsed_correctly(self):
        params = extract_parameters(ACTION_GROUP_EVENT)
        self.assertEqual(params, {"customer": "Customer A"})

    def test_direct_json_empty_dict(self):
        params = extract_parameters({})
        self.assertEqual(params, {})

    def test_direct_json_multiple_keys(self):
        payload = {"customer": "Customer B", "extra": "value"}
        self.assertEqual(extract_parameters(payload), payload)


# ---------------------------------------------------------------------------
# lambda_handler tests
# ---------------------------------------------------------------------------

class TestLambdaHandler(unittest.TestCase):

    def _mock_load(self):
        return patch(
            "lambda_function.load_kpi_metadata",
            return_value=SAMPLE_KPIS,
        )

    def test_direct_json_returns_plain_dict(self):
        with self._mock_load():
            result = lambda_handler(DIRECT_JSON_EVENT, None)

        self.assertIsInstance(result, dict)
        # Must NOT contain the Bedrock envelope keys
        self.assertNotIn("messageVersion", result)
        self.assertIn("kpis", result)
        self.assertIn("customer", result)
        self.assertIn("kpi_count", result)

    def test_action_group_returns_envelope(self):
        with self._mock_load():
            result = lambda_handler(ACTION_GROUP_EVENT, None)

        self.assertIn("messageVersion", result)
        self.assertIn("response", result)
        self.assertEqual(result["response"]["httpStatusCode"], 200)

        body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
        self.assertIn("kpis", body)

    def test_direct_json_customer_filter_applied(self):
        with self._mock_load():
            result = lambda_handler({"customer": "Customer A"}, None)

        self.assertEqual(result["customer"], "Customer A")
        self.assertEqual(result["kpi_count"], 1)

    def test_direct_json_error_returns_plain_error_dict(self):
        with patch("lambda_function.load_kpi_metadata", side_effect=RuntimeError("boom")):
            result = lambda_handler(DIRECT_JSON_EVENT, None)

        self.assertNotIn("messageVersion", result)
        self.assertIn("error", result)

    def test_action_group_error_returns_envelope_500(self):
        with patch("lambda_function.load_kpi_metadata", side_effect=RuntimeError("boom")):
            result = lambda_handler(ACTION_GROUP_EVENT, None)

        self.assertIn("messageVersion", result)
        self.assertEqual(result["response"]["httpStatusCode"], 500)


if __name__ == "__main__":
    unittest.main()
