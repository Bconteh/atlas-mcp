"""
Tests for Atlas MCP Server tools and API client.
"""
import asyncio
import pytest
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.atlas_client import AtlasApiClient
from src.llm_processor import _rule_based_extract_intent
from src.models import IntentType, ChangeRequestStatus
from src.config import DevSettings


@pytest.fixture
def settings():
    return DevSettings()


@pytest.fixture
def atlas(settings):
    return AtlasApiClient(settings)


class TestAtlasApiClient:
    def test_create_change_request(self, atlas):
        result = asyncio.run(atlas.create_change_request(
            title="Test Change",
            description="Test description",
            start_date="07/04/2026",
            end_date="07/06/2026",
            risk_level="medium",
            environment="dev",
        ))
        assert result.success is True
        assert result.data["title"] == "Test Change"
        assert result.data["id"].startswith("CHG")

    def test_get_existing_change_request(self, atlas):
        result = asyncio.run(atlas.get_change_request("CHG123456"))
        assert result.success is True
        assert result.data["id"] == "CHG123456"

    def test_get_nonexistent_change_request(self, atlas):
        result = asyncio.run(atlas.get_change_request("CHG999999"))
        assert result.success is False
        assert result.error == "NOT_FOUND"

    def test_add_task(self, atlas):
        result = asyncio.run(atlas.add_task(
            change_id="CHG123456",
            task_title="Deploy artifact",
            task_description="Deploy git-tools v2.0",
            assignee="dev@example.com",
        ))
        assert result.success is True
        assert "task" in result.data

    def test_close_change_request(self, atlas):
        # First create one to close
        cr = asyncio.run(atlas.create_change_request(
            title="To Close",
            description="Will be closed",
            start_date="07/01/2026",
            end_date="07/02/2026",
        ))
        change_id = cr.data["id"]
        result = asyncio.run(atlas.close_change_request(change_id, "Test close"))
        assert result.success is True
        assert result.data["status"] == ChangeRequestStatus.CLOSED.value

    def test_close_already_closed(self, atlas):
        result = asyncio.run(atlas.close_change_request("CHG123458"))
        assert result.success is False
        assert result.error == "ALREADY_CLOSED"

    def test_list_change_requests(self, atlas):
        result = asyncio.run(atlas.list_change_requests())
        assert result.success is True
        assert len(result.data["change_requests"]) > 0

    def test_list_filtered_by_status(self, atlas):
        result = asyncio.run(atlas.list_change_requests(status="open"))
        assert result.success is True
        for cr in result.data["change_requests"]:
            assert cr["status"] == "open"


class TestRuleBasedIntentExtraction:
    def test_create_intent(self):
        intent = _rule_based_extract_intent(
            "create a change request with date 07/04/2026 - 07/06/2026 with title Apollo server upgrade"
        )
        assert intent.intent == IntentType.CREATE_CHANGE_REQUEST
        assert not intent.clarification_needed
        assert intent.entities["start_date"] == "07/04/2026"
        assert intent.entities["end_date"] == "07/06/2026"

    def test_add_task_intent(self):
        intent = _rule_based_extract_intent(
            "Add a deployment task to CHG123456 for deploying artifact git-tools app"
        )
        assert intent.intent == IntentType.ADD_TASK
        assert intent.entities["change_id"] == "CHG123456"
        assert not intent.clarification_needed

    def test_close_intent(self):
        intent = _rule_based_extract_intent("Update the status of CHG123456 to close")
        assert intent.intent == IntentType.CLOSE_CHANGE_REQUEST
        assert intent.entities["change_id"] == "CHG123456"

    def test_status_check_intent(self):
        intent = _rule_based_extract_intent("what's the status of CHG12345")
        assert intent.intent == IntentType.CHECK_STATUS
        assert intent.entities["change_id"] == "CHG12345"

    def test_unclear_intent(self):
        intent = _rule_based_extract_intent("hello world")
        assert intent.intent == IntentType.UNCLEAR
        assert intent.clarification_needed

    def test_missing_chg_id_for_task(self):
        intent = _rule_based_extract_intent("add a deployment task for git-tools")
        assert intent.intent == IntentType.ADD_TASK
        assert intent.clarification_needed
        assert intent.entities["change_id"] is None

