"""Tests for _resolve_subagent_model — dynamic subagent model selection.

Pins the contract:
- User picks opus → opus-tier gets user model, sonnet-tier gets default sonnet
- User picks sonnet → ALL tiers get user model (cost-conscious)
- User picks legacy opus → opus-tier gets legacy, sonnet-tier gets default sonnet
"""

from db.constants import LEGACY_OPUS, SUPPORTED_OPUS, SUPPORTED_SONNET
from prompts.subagent import _resolve_subagent_model
from utils.constants import TIER_OPUS, TIER_SONNET


class TestResolveSubagentModel:
    """_resolve_subagent_model maps tier + user selection to concrete model."""

    # ── User picks supported opus ──

    def test_opus_run_opus_tier_gets_user_model(self) -> None:
        assert _resolve_subagent_model(TIER_OPUS, SUPPORTED_OPUS) == SUPPORTED_OPUS

    def test_opus_run_sonnet_tier_gets_default_sonnet(self) -> None:
        assert _resolve_subagent_model(TIER_SONNET, SUPPORTED_OPUS) == SUPPORTED_SONNET

    # ── User picks sonnet (cost-conscious) ──

    def test_sonnet_run_opus_tier_becomes_sonnet(self) -> None:
        assert _resolve_subagent_model(TIER_OPUS, SUPPORTED_SONNET) == SUPPORTED_SONNET

    def test_sonnet_run_sonnet_tier_stays_sonnet(self) -> None:
        assert _resolve_subagent_model(TIER_SONNET, SUPPORTED_SONNET) == SUPPORTED_SONNET

    # ── User picks legacy opus ──

    def test_legacy_run_opus_tier_gets_legacy(self) -> None:
        assert _resolve_subagent_model(TIER_OPUS, LEGACY_OPUS) == LEGACY_OPUS

    def test_legacy_run_sonnet_tier_gets_default_sonnet(self) -> None:
        assert _resolve_subagent_model(TIER_SONNET, LEGACY_OPUS) == SUPPORTED_SONNET
