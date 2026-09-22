"""
Unit tests for auction_transitions.py

Tests every entry in VALID_TRANSITIONS, the guard predicates, and the
critical invariant that InternalRunState values are NOT in PublicRunState.

No database access — these are pure Python tests.
"""
from __future__ import annotations

import pytest

from app.domain.auction_transitions import (
    INTERNAL_STATE_VALUES,
    PUBLIC_STATE_VALUES,
    VALID_TRANSITIONS,
    InvalidTransitionError,
    assert_not_internal,
    can_pause,
    can_transition,
    get_next_state,
    is_terminal_state,
)
from app.domain.enums import AuctionEvent, InternalRunState, PublicRunState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trans(from_state: PublicRunState, event: AuctionEvent) -> PublicRunState:
    """Convenience shorthand for get_next_state."""
    return get_next_state(from_state, event)


# ===========================================================================
# Spec-required transitions 1-12
# ===========================================================================

def test_1_ready_to_set_intro() -> None:
    """Spec #1: READY → SET_INTRO on start_auction."""
    assert _trans(PublicRunState.READY, AuctionEvent.START_AUCTION) == PublicRunState.SET_INTRO


def test_2_set_intro_to_lot_open() -> None:
    """Spec #2: SET_INTRO → LOT_OPEN on open_lot."""
    assert _trans(PublicRunState.SET_INTRO, AuctionEvent.OPEN_LOT) == PublicRunState.LOT_OPEN


def test_3_lot_open_to_bidding_active() -> None:
    """Spec #3: LOT_OPEN → BIDDING_ACTIVE on first_bid."""
    assert _trans(PublicRunState.LOT_OPEN, AuctionEvent.FIRST_BID) == PublicRunState.BIDDING_ACTIVE


def test_4_countdown_to_bidding_active_on_new_bid() -> None:
    """Spec #4: COUNTDOWN → BIDDING_ACTIVE on new_bid."""
    assert _trans(PublicRunState.COUNTDOWN, AuctionEvent.NEW_BID) == PublicRunState.BIDDING_ACTIVE


def test_5_countdown_to_going_once_on_timer() -> None:
    """Spec #5: COUNTDOWN → GOING_ONCE on timer_expired."""
    assert _trans(PublicRunState.COUNTDOWN, AuctionEvent.TIMER_EXPIRED) == PublicRunState.GOING_ONCE


def test_6_going_once_to_going_twice() -> None:
    """Spec #6: GOING_ONCE → GOING_TWICE on timer_expired."""
    assert _trans(PublicRunState.GOING_ONCE, AuctionEvent.TIMER_EXPIRED) == PublicRunState.GOING_TWICE


def test_7_going_twice_to_final_call() -> None:
    """Spec #7: GOING_TWICE → FINAL_CALL on timer_expired."""
    assert _trans(PublicRunState.GOING_TWICE, AuctionEvent.TIMER_EXPIRED) == PublicRunState.FINAL_CALL


def test_8_final_call_to_rtm_pending_when_eligible() -> None:
    """Spec #8: FINAL_CALL → RTM_PENDING on hammer_and_rtm_eligible."""
    assert (
        _trans(PublicRunState.FINAL_CALL, AuctionEvent.HAMMER_AND_RTM_ELIGIBLE)
        == PublicRunState.RTM_PENDING
    )


def test_9_final_call_to_lot_open_no_rtm() -> None:
    """Spec #9: FINAL_CALL → LOT_OPEN on hammer_sold (no RTM)."""
    assert _trans(PublicRunState.FINAL_CALL, AuctionEvent.HAMMER_SOLD) == PublicRunState.LOT_OPEN


def test_10_rtm_pending_to_lot_open() -> None:
    """Spec #10: RTM_PENDING → LOT_OPEN on rtm_resolved."""
    assert _trans(PublicRunState.RTM_PENDING, AuctionEvent.RTM_RESOLVED) == PublicRunState.LOT_OPEN


def test_11_lot_open_to_set_intro_at_set_boundary() -> None:
    """Spec #11: LOT_OPEN → SET_INTRO on next_set (moving to a new auction set)."""
    assert _trans(PublicRunState.LOT_OPEN, AuctionEvent.NEXT_SET) == PublicRunState.SET_INTRO


def test_12_lot_open_to_auction_complete_when_pool_exhausted() -> None:
    """Spec #12: LOT_OPEN → AUCTION_COMPLETE on pool_exhausted."""
    assert (
        _trans(PublicRunState.LOT_OPEN, AuctionEvent.POOL_EXHAUSTED)
        == PublicRunState.AUCTION_COMPLETE
    )


# ===========================================================================
# Additional valid transitions (non-spec, but present in table)
# ===========================================================================

def test_bidding_active_to_countdown_on_bid_or_tick() -> None:
    assert _trans(PublicRunState.BIDDING_ACTIVE, AuctionEvent.BID_OR_TICK) == PublicRunState.COUNTDOWN


def test_going_once_to_bidding_active_on_new_bid() -> None:
    assert _trans(PublicRunState.GOING_ONCE, AuctionEvent.NEW_BID) == PublicRunState.BIDDING_ACTIVE


def test_going_twice_to_bidding_active_on_new_bid() -> None:
    assert _trans(PublicRunState.GOING_TWICE, AuctionEvent.NEW_BID) == PublicRunState.BIDDING_ACTIVE


def test_final_call_to_bidding_active_on_new_bid() -> None:
    assert _trans(PublicRunState.FINAL_CALL, AuctionEvent.NEW_BID) == PublicRunState.BIDDING_ACTIVE


def test_lot_open_to_lot_open_on_skip_unsold() -> None:
    """LOT_OPEN stays LOT_OPEN on skip_unsold (skipping a player with no bids)."""
    assert _trans(PublicRunState.LOT_OPEN, AuctionEvent.SKIP_UNSOLD) == PublicRunState.LOT_OPEN


# ===========================================================================
# Spec #13 — Invalid transitions are rejected
# ===========================================================================

def test_13a_ready_rejects_open_lot() -> None:
    """Cannot open a lot before starting the auction."""
    with pytest.raises(InvalidTransitionError):
        _trans(PublicRunState.READY, AuctionEvent.OPEN_LOT)


def test_13b_ready_rejects_first_bid() -> None:
    with pytest.raises(InvalidTransitionError):
        _trans(PublicRunState.READY, AuctionEvent.FIRST_BID)


def test_13c_auction_complete_rejects_all_events() -> None:
    """Terminal state AUCTION_COMPLETE must reject every further event."""
    for event in AuctionEvent:
        with pytest.raises(InvalidTransitionError):
            _trans(PublicRunState.AUCTION_COMPLETE, event)


def test_13d_set_intro_rejects_bid() -> None:
    """Cannot bid while in set intro (no lot open yet)."""
    with pytest.raises(InvalidTransitionError):
        _trans(PublicRunState.SET_INTRO, AuctionEvent.FIRST_BID)


def test_13e_can_transition_returns_false_for_invalid() -> None:
    assert can_transition(PublicRunState.READY, AuctionEvent.POOL_EXHAUSTED) is False


def test_13f_can_transition_returns_true_for_valid() -> None:
    assert can_transition(PublicRunState.READY, AuctionEvent.START_AUCTION) is True


def test_13g_invalid_transition_error_carries_state_info() -> None:
    exc = InvalidTransitionError("LOT_OPEN", "start_auction")
    assert exc.from_state == "LOT_OPEN"
    assert exc.event == "start_auction"
    assert "LOT_OPEN" in str(exc)
    assert "start_auction" in str(exc)


# ===========================================================================
# Spec #14 — Internal states are NOT public states
# ===========================================================================

def test_14a_internal_states_disjoint_from_public_states() -> None:
    """InternalRunState values must not appear in PublicRunState values."""
    overlap = INTERNAL_STATE_VALUES & PUBLIC_STATE_VALUES
    assert overlap == set(), (
        f"Internal states {overlap!r} should not be public states"
    )


def test_14b_assert_not_internal_raises_for_internal_value() -> None:
    for internal in InternalRunState:
        with pytest.raises(ValueError, match="must not be exposed"):
            assert_not_internal(internal.value)


def test_14c_assert_not_internal_passes_for_public_values() -> None:
    for public in PublicRunState:
        assert_not_internal(public.value)   # must not raise


def test_14d_lot_resolving_not_in_valid_transitions_targets() -> None:
    """No transition in the table should produce an internal state."""
    target_values = {v.value for v in VALID_TRANSITIONS.values()}
    for internal in InternalRunState:
        assert internal.value not in target_values, (
            f"Internal state {internal.value!r} must not be a transition target"
        )


# ===========================================================================
# Guard predicates
# ===========================================================================

def test_can_pause_allows_active_states() -> None:
    pausable = [
        PublicRunState.LOT_OPEN,
        PublicRunState.BIDDING_ACTIVE,
        PublicRunState.COUNTDOWN,
        PublicRunState.GOING_ONCE,
        PublicRunState.GOING_TWICE,
        PublicRunState.FINAL_CALL,
        PublicRunState.RTM_PENDING,
    ]
    for state in pausable:
        assert can_pause(state) is True, f"Expected can_pause({state!r}) = True"


def test_can_pause_rejects_non_active_states() -> None:
    non_pausable = [
        PublicRunState.READY,
        PublicRunState.SET_INTRO,
        PublicRunState.AUCTION_COMPLETE,
    ]
    for state in non_pausable:
        assert can_pause(state) is False, f"Expected can_pause({state!r}) = False"


def test_is_terminal_state() -> None:
    assert is_terminal_state(PublicRunState.AUCTION_COMPLETE) is True
    for state in PublicRunState:
        if state != PublicRunState.AUCTION_COMPLETE:
            assert is_terminal_state(state) is False


# ===========================================================================
# Coverage: all entries in VALID_TRANSITIONS are exercised at least once
# ===========================================================================

def test_all_transitions_covered() -> None:
    """Sanity check: the transition table has the expected number of entries."""
    # 1 + 1 + 4 + 1 + 2 + 2 + 2 + 3 + 1 = 17
    assert len(VALID_TRANSITIONS) == 17, (
        f"Expected 17 entries in VALID_TRANSITIONS, got {len(VALID_TRANSITIONS)}"
    )
