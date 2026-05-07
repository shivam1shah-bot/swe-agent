"""
Unit tests for GoogleDocsClient utility.

Tests for src.utils.google_docs module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.utils.google_docs import GoogleDocsClient, _extract_plain_text


class TestExtractFileId:
    """Tests for URL parsing."""

    def test_extracts_file_id_from_edit_url(self):
        client = GoogleDocsClient()
        file_id = client._extract_file_id(
            "https://docs.google.com/document/d/1h4mn43oGQaJxrbqO3vswvoNG/edit"
        )
        assert file_id == "1h4mn43oGQaJxrbqO3vswvoNG"

    def test_extracts_file_id_with_query_params(self):
        client = GoogleDocsClient()
        file_id = client._extract_file_id(
            "https://docs.google.com/document/d/ABC123xyz/edit?usp=sharing"
        )
        assert file_id == "ABC123xyz"

    def test_returns_none_for_non_google_doc_url(self):
        client = GoogleDocsClient()
        assert client._extract_file_id("https://docs.google.com/spreadsheets/d/XYZ") is None
        assert client._extract_file_id("https://github.com/razorpay/swe-agent") is None
        assert client._extract_file_id("not a url") is None

    def test_returns_none_for_empty_string(self):
        client = GoogleDocsClient()
        assert client._extract_file_id("") is None


class TestFetchByUrl:
    """Tests for fetch_by_url public method."""

    @pytest.mark.asyncio
    @patch.object(GoogleDocsClient, 'fetch_document', new_callable=AsyncMock)
    async def test_delegates_to_fetch_document(self, mock_fetch):
        mock_fetch.return_value = "doc content"
        client = GoogleDocsClient()
        result = await client.fetch_by_url(
            "https://docs.google.com/document/d/FILE123/edit"
        )
        assert result == "doc content"
        mock_fetch.assert_called_once_with("FILE123")

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_url(self):
        client = GoogleDocsClient()
        result = await client.fetch_by_url("https://github.com/razorpay")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_url(self):
        client = GoogleDocsClient()
        result = await client.fetch_by_url("")
        assert result is None


class TestFetchDocument:
    """Tests for fetch_document public method."""

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_file_id(self):
        client = GoogleDocsClient()
        assert await client.fetch_document("") is None
        assert await client.fetch_document("   ") is None

    @pytest.mark.asyncio
    @patch('src.utils.google_docs.is_google_cloud_auth_configured', return_value=False)
    async def test_returns_none_when_auth_not_configured(self, mock_auth):
        client = GoogleDocsClient()
        result = await client.fetch_document("FILE123")
        assert result is None

    @pytest.mark.asyncio
    @patch('src.utils.google_docs.is_google_cloud_auth_configured', return_value=True)
    @patch('asyncio.to_thread')
    async def test_returns_content_on_success(self, mock_thread, mock_auth):
        mock_thread.return_value = "fetched document text"
        client = GoogleDocsClient()
        result = await client.fetch_document("FILE123")
        assert result == "fetched document text"

    @pytest.mark.asyncio
    @patch('src.utils.google_docs.is_google_cloud_auth_configured', return_value=True)
    @patch('asyncio.to_thread', side_effect=Exception("403 Permission denied"))
    async def test_returns_none_on_fetch_error(self, mock_thread, mock_auth):
        client = GoogleDocsClient()
        result = await client.fetch_document("FILE123")
        assert result is None

    @pytest.mark.asyncio
    @patch('src.utils.google_docs.is_google_cloud_auth_configured', return_value=True)
    @patch('asyncio.to_thread', return_value="")
    async def test_returns_none_for_empty_content(self, mock_thread, mock_auth):
        client = GoogleDocsClient()
        result = await client.fetch_document("FILE123")
        assert result is None


class TestLoadOAuthCredentials:
    """Tests for credential loading."""

    @patch('src.utils.google_docs.GoogleDocsClient._load_oauth_credentials')
    def test_returns_none_when_config_key_missing(self, mock_load):
        mock_load.return_value = None
        client = GoogleDocsClient()
        assert client._load_oauth_credentials() is None

    @patch('src.providers.config_loader.get_config')
    def test_returns_none_when_creds_json_empty(self, mock_config):
        mock_config.return_value = {"gcp": {"google_docs_credentials_json": ""}}
        client = GoogleDocsClient()
        result = client._load_oauth_credentials()
        assert result is None

    @patch('src.providers.config_loader.get_config')
    def test_returns_none_for_invalid_json(self, mock_config):
        mock_config.return_value = {
            "gcp": {"google_docs_credentials_json": "not valid json {{{"}
        }
        client = GoogleDocsClient()
        result = client._load_oauth_credentials()
        assert result is None

    @patch('src.providers.config_loader.get_config')
    def test_returns_credentials_for_valid_json(self, mock_config):
        mock_config.return_value = {
            "gcp": {
                "google_docs_credentials_json": '{"client_id":"cid","client_secret":"csec","refresh_token":"rtoken","type":"authorized_user"}'
            }
        }
        client = GoogleDocsClient()
        result = client._load_oauth_credentials()
        assert result is not None


class TestExtractPlainText:
    """Tests for plain text extraction from Google Docs API response."""

    def test_extracts_text_from_paragraphs(self):
        document = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Hello World\n"}}
                            ]
                        }
                    },
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Second paragraph\n"}}
                            ]
                        }
                    },
                ]
            }
        }
        result = _extract_plain_text(document)
        assert "Hello World" in result
        assert "Second paragraph" in result

    def test_skips_empty_paragraphs(self):
        document = {
            "body": {
                "content": [
                    {"paragraph": {"elements": [{"textRun": {"content": "\n"}}]}},
                    {"paragraph": {"elements": [{"textRun": {"content": "Real content\n"}}]}},
                ]
            }
        }
        result = _extract_plain_text(document)
        assert result == "Real content"

    def test_skips_non_paragraph_blocks(self):
        document = {
            "body": {
                "content": [
                    {"sectionBreak": {}},
                    {"paragraph": {"elements": [{"textRun": {"content": "Text\n"}}]}},
                ]
            }
        }
        result = _extract_plain_text(document)
        assert result == "Text"

    def test_returns_empty_string_for_empty_document(self):
        assert _extract_plain_text({}) == ""
        assert _extract_plain_text({"body": {}}) == ""
        assert _extract_plain_text({"body": {"content": []}}) == ""

    def test_concatenates_multiple_text_runs_in_paragraph(self):
        document = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Hello "}},
                                {"textRun": {"content": "World\n"}},
                            ]
                        }
                    }
                ]
            }
        }
        result = _extract_plain_text(document)
        assert result == "Hello World"
