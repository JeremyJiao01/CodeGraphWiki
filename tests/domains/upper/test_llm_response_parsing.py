"""Regression tests for robust LLM API response parsing.

Covers:
- 063594b: Guard against malformed API responses — error key, empty choices,
  null message, null content
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from code_graph_builder.domains.upper.rag.client import ChatResponse, LLMClient


@pytest.fixture
def client():
    """Create an LLMClient with a dummy API key."""
    return LLMClient(api_key="sk-test-key-12345")


def _mock_response(json_data, status_code=200):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestLLMResponseParsing:
    """LLMClient.chat must raise RuntimeError with descriptive messages
    for each class of malformed API response."""

    @patch("code_graph_builder.domains.upper.rag.client.requests.post")
    def test_normal_response(self, mock_post, client):
        """A well-formed response returns a ChatResponse."""
        mock_post.return_value = _mock_response({
            "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 10},
            "model": "test-model",
        })
        result = client.chat("test query")
        assert isinstance(result, ChatResponse)
        assert result.content == "Hello"
        assert result.finish_reason == "stop"

    @patch("code_graph_builder.domains.upper.rag.client.requests.post")
    def test_error_key_in_response(self, mock_post, client):
        """API returns 200 but with an 'error' key -> RuntimeError."""
        mock_post.return_value = _mock_response({
            "error": {"message": "rate limit exceeded", "type": "rate_limit"}
        })
        with pytest.raises(RuntimeError, match="API error.*rate limit"):
            client.chat("test")

    @patch("code_graph_builder.domains.upper.rag.client.requests.post")
    def test_error_key_string(self, mock_post, client):
        """API returns error as a plain string."""
        mock_post.return_value = _mock_response({
            "error": "internal server error"
        })
        with pytest.raises(RuntimeError, match="API error"):
            client.chat("test")

    @patch("code_graph_builder.domains.upper.rag.client.requests.post")
    def test_empty_choices(self, mock_post, client):
        """API returns empty choices array -> RuntimeError."""
        mock_post.return_value = _mock_response({
            "choices": [],
        })
        with pytest.raises(RuntimeError, match="no choices"):
            client.chat("test")

    @patch("code_graph_builder.domains.upper.rag.client.requests.post")
    def test_missing_choices_key(self, mock_post, client):
        """API returns response without choices key -> RuntimeError."""
        mock_post.return_value = _mock_response({
            "model": "test-model",
        })
        with pytest.raises(RuntimeError, match="no choices"):
            client.chat("test")

    @patch("code_graph_builder.domains.upper.rag.client.requests.post")
    def test_null_message(self, mock_post, client):
        """API returns null message in first choice -> RuntimeError."""
        mock_post.return_value = _mock_response({
            "choices": [{"message": None, "finish_reason": "length"}],
        })
        with pytest.raises(RuntimeError, match="null message"):
            client.chat("test")

    @patch("code_graph_builder.domains.upper.rag.client.requests.post")
    def test_null_content(self, mock_post, client):
        """API returns message with null content -> RuntimeError."""
        mock_post.return_value = _mock_response({
            "choices": [{"message": {"content": None}, "finish_reason": "stop"}],
        })
        with pytest.raises(RuntimeError, match="null content"):
            client.chat("test")

    @patch("code_graph_builder.domains.upper.rag.client.requests.post")
    def test_non_dict_response(self, mock_post, client):
        """API returns a non-dict (e.g. string) -> RuntimeError."""
        mock_post.return_value = _mock_response("unexpected string response")
        with pytest.raises(RuntimeError, match="Unexpected response format"):
            client.chat("test")

    @patch("code_graph_builder.domains.upper.rag.client.requests.post")
    def test_missing_message_key(self, mock_post, client):
        """Choice dict has no 'message' key -> RuntimeError (null message)."""
        mock_post.return_value = _mock_response({
            "choices": [{"finish_reason": "stop"}],
        })
        with pytest.raises(RuntimeError, match="null message"):
            client.chat("test")
