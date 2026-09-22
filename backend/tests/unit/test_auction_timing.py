"""
Unit tests for auction_timing.py

Verifies timing profiles, accelerated-mode scaling, fallback behaviour,
and the live_state structure produced by build_initial_live_state().

No database access — pure Python tests.
"""
from __future__ import annotations

import pytest

from app.domain.auction_timing import build_initial_live_state, get_timing_ms
from app.domain.enums import (
    LIVE_STATE_VERSION,
    InternalRunState,
    PublicRunState,
    SpeedProfile,
)
from app.domain.auction_transitions import PUBLIC_STATE_VALUES, INTERNAL_STATE_VALUES


# ---------------------------------------------------------------------------
# Expected timing values for each profile
# ---------------------------------------------------------------------------

_NORMAL_EXPECTED = {
    "countdown": 3000,
    "hammer_step": 2000,
    "inter_lot": 1500,
    "set_intro": 3000,
    "rtm_window": 4000,
    "nomination_timeout": 30000,
}

_FAST_EXPECTED = {
    "countdown": 2000,
    "hammer_step": 1500,
    "inter_lot": 1000,
    "set_intro": 2000,
    "rtm_window": 3000,
    "nomination_timeout": 20000,
}

_VERY_FAST_EXPECTED = {
    "countdown": 1000,
    "hammer_step": 800,
    "inter_lot": 500,
    "set_intro": 1000,
    "rtm_window": 2000,
    "nomination_timeout": 10000,
}


# ===========================================================================
# Timing profiles
# ===========================================================================

def test_normal_profile_returns_correct_values() -> None:
    timing = get_timing_ms(SpeedProfile.NORMAL)
    assert timing == _NORMAL_EXPECTED


def test_fast_profile_returns_correct_values() -> None:
    timing = get_timing_ms(SpeedProfile.FAST)
    assert timing == _FAST_EXPECTED


def test_very_fast_profile_returns_correct_values() -> None:
    timing = get_timing_ms(SpeedProfile.VERY_FAST)
    assert timing == _VERY_FAST_EXPECTED


def test_default_profile_is_normal() -> None:
    """Calling get_timing_ms() with no args should return normal-profile values."""
    assert get_timing_ms() == _NORMAL_EXPECTED


def test_unknown_profile_falls_back_to_normal() -> None:
    """An unrecognised profile string must not raise — it should fall back."""
    timing = get_timing_ms("turbo_mode_9000")  # not a real profile
    assert timing == _NORMAL_EXPECTED


# ===========================================================================
# Accelerated mode
# ===========================================================================

def test_accelerated_mode_halves_normal_timing() -> None:
    """Spec: accelerated flag halves every timing value."""
    normal = get_timing_ms(SpeedProfile.NORMAL, is_accelerated=False)
    accelerated = get_timing_ms(SpeedProfile.NORMAL, is_accelerated=True)
    for key, base_val in normal.items():
        expected = max(1, int(base_val * 0.5))
        assert accelerated[key] == expected, (
            f"{key}: expected {expected}, got {accelerated[key]}"
        )


def test_accelerated_mode_halves_fast_timing() -> None:
    fast = get_timing_ms(SpeedProfile.FAST, is_accelerated=False)
    accelerated = get_timing_ms(SpeedProfile.FAST, is_accelerated=True)
    for key, base_val in fast.items():
        assert accelerated[key] == max(1, int(base_val * 0.5))


def test_non_accelerated_flag_is_unchanged() -> None:
    """is_accelerated=False must not change timing values."""
    timing = get_timing_ms(SpeedProfile.NORMAL, is_accelerated=False)
    assert timing == _NORMAL_EXPECTED


def test_accelerated_minimum_is_1ms() -> None:
    """No timing value must be reduced below 1 ms, even with extreme scaling."""
    timing = get_timing_ms(SpeedProfile.VERY_FAST, is_accelerated=True)
    for key, val in timing.items():
        assert val >= 1, f"Timing {key} must be >= 1ms, got {val}"


def test_accelerated_fast_is_less_than_non_accelerated_normal() -> None:
    """An accelerated-fast profile should be faster than a plain normal profile."""
    accel_fast = get_timing_ms(SpeedProfile.FAST, is_accelerated=True)
    normal = get_timing_ms(SpeedProfile.NORMAL)
    for key in normal:
        assert accel_fast[key] < normal[key], (
            f"Expected accelerated-fast {key} < normal {key}"
        )


# ===========================================================================
# build_initial_live_state
# ===========================================================================

def test_initial_live_state_has_correct_version() -> None:
    state = build_initial_live_state()
    assert state["version"] == LIVE_STATE_VERSION


def test_initial_live_state_starts_at_ready() -> None:
    """Spec #15: live_state starts with public_run_state = READY."""
    state = build_initial_live_state()
    assert state["public_run_state"] == PublicRunState.READY.value


def test_initial_live_state_is_not_accelerated() -> None:
    state = build_initial_live_state()
    assert state["is_accelerated"] is False


def test_initial_live_state_default_profile_is_normal() -> None:
    state = build_initial_live_state()
    assert state["speed_profile"] == SpeedProfile.NORMAL.value


def test_initial_live_state_pause_is_inactive() -> None:
    state = build_initial_live_state()
    assert state["pause"]["active"] is False
    assert state["pause"]["paused_from"] is None


def test_initial_live_state_countdown_is_empty() -> None:
    state = build_initial_live_state()
    assert state["countdown"]["phase"] is None
    assert state["countdown"]["expires_at"] is None
    assert state["countdown"]["generation"] == 0


def test_initial_live_state_rtm_window_inactive() -> None:
    state = build_initial_live_state()
    assert state["rtm_window"]["active"] is False
    assert state["rtm_window"]["expires_at"] is None


def test_initial_live_state_internal_phase_is_none() -> None:
    """Spec #15: live_state must not expose internal state on creation."""
    state = build_initial_live_state()
    assert state["internal_phase"] is None


def test_initial_live_state_timing_ms_matches_normal_profile() -> None:
    """Default initial live_state must embed the normal timing profile."""
    state = build_initial_live_state()
    assert state["timing_ms"] == _NORMAL_EXPECTED


def test_initial_live_state_with_fast_profile() -> None:
    state = build_initial_live_state(SpeedProfile.FAST)
    assert state["speed_profile"] == SpeedProfile.FAST.value
    assert state["timing_ms"] == _FAST_EXPECTED


def test_initial_live_state_with_accelerated_flag() -> None:
    state = build_initial_live_state(SpeedProfile.NORMAL, is_accelerated=True)
    assert state["is_accelerated"] is True
    expected_timing = get_timing_ms(SpeedProfile.NORMAL, is_accelerated=True)
    assert state["timing_ms"] == expected_timing


# ===========================================================================
# Spec #15 — live_state remains lightweight
# ===========================================================================

def test_live_state_does_not_contain_player_data() -> None:
    """live_state must NOT contain player identity or bid data."""
    state = build_initial_live_state()
    forbidden_keys = {
        "player_id", "player_name", "current_bid_cr", "leading_team_id",
        "bid_count", "purse_remaining_cr", "squad_count", "overseas_count",
        "current_player_id", "current_auction_set",
    }
    state_keys = set(state.keys())
    leaking_keys = forbidden_keys & state_keys
    assert leaking_keys == set(), (
        f"live_state must not contain persistent auction data: {leaking_keys!r}"
    )


def test_live_state_public_run_state_is_a_public_state() -> None:
    """The initial public_run_state value must be in PublicRunState, not internal."""
    state = build_initial_live_state()
    prs_value = state["public_run_state"]
    assert prs_value in PUBLIC_STATE_VALUES
    assert prs_value not in INTERNAL_STATE_VALUES
