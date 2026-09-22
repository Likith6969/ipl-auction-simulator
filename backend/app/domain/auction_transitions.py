"""
auction_transitions.py
======================
Pure state-machine transition table for the IPL Auction Engine.

Responsibilities
----------------
- Define every valid (from_state, event) → to_state mapping.
- Expose guard predicates (can_transition, can_pause, is_terminal_state).
- Raise ``InvalidTransitionError`` for any disallowed transition attempt.

NOT responsible for
-------------------
- Database access.
- Timer execution.
- Bid validation.
- RTM resolution.
- Any side-effects whatsoever.
"""
from __future__ import annotations

from app.domain.enums import AuctionEvent, InternalRunState, PublicRunState

# ---------------------------------------------------------------------------
# Transition table  (from_state, event) → to_state
# ---------------------------------------------------------------------------
#
# Source-of-truth for every permitted state change.  If a (state, event) pair
# is not in this dict it is an invalid / disallowed transition.
#
VALID_TRANSITIONS: dict[tuple[PublicRunState, AuctionEvent], PublicRunState] = {
    # ── Auction start ────────────────────────────────────────────────────────
    (PublicRunState.READY, AuctionEvent.START_AUCTION): PublicRunState.SET_INTRO,

    # ── Set intro → open first lot of the set ────────────────────────────────
    (PublicRunState.SET_INTRO, AuctionEvent.OPEN_LOT): PublicRunState.LOT_OPEN,

    # ── Lot open variants ────────────────────────────────────────────────────
    # First bid received → activate bidding panel
    (PublicRunState.LOT_OPEN, AuctionEvent.FIRST_BID): PublicRunState.BIDDING_ACTIVE,
    # Skipping this lot with no bid → next lot in same set
    (PublicRunState.LOT_OPEN, AuctionEvent.SKIP_UNSOLD): PublicRunState.LOT_OPEN,
    # All lots in this set exhausted → intro for next set
    (PublicRunState.LOT_OPEN, AuctionEvent.NEXT_SET): PublicRunState.SET_INTRO,
    # Entire pool exhausted → auction complete
    (PublicRunState.LOT_OPEN, AuctionEvent.POOL_EXHAUSTED): PublicRunState.AUCTION_COMPLETE,

    # ── Bidding active → countdown ───────────────────────────────────────────
    # A bid was placed (or a tick fired) → start the 3-second hammer countdown
    (PublicRunState.BIDDING_ACTIVE, AuctionEvent.BID_OR_TICK): PublicRunState.COUNTDOWN,

    # ── Countdown ────────────────────────────────────────────────────────────
    (PublicRunState.COUNTDOWN, AuctionEvent.NEW_BID): PublicRunState.BIDDING_ACTIVE,
    (PublicRunState.COUNTDOWN, AuctionEvent.TIMER_EXPIRED): PublicRunState.GOING_ONCE,

    # ── Going once ───────────────────────────────────────────────────────────
    (PublicRunState.GOING_ONCE, AuctionEvent.NEW_BID): PublicRunState.BIDDING_ACTIVE,
    (PublicRunState.GOING_ONCE, AuctionEvent.TIMER_EXPIRED): PublicRunState.GOING_TWICE,

    # ── Going twice ──────────────────────────────────────────────────────────
    (PublicRunState.GOING_TWICE, AuctionEvent.NEW_BID): PublicRunState.BIDDING_ACTIVE,
    (PublicRunState.GOING_TWICE, AuctionEvent.TIMER_EXPIRED): PublicRunState.FINAL_CALL,

    # ── Final call ───────────────────────────────────────────────────────────
    (PublicRunState.FINAL_CALL, AuctionEvent.NEW_BID): PublicRunState.BIDDING_ACTIVE,
    # Hammer falls AND previous team has an RTM right for this player
    (PublicRunState.FINAL_CALL, AuctionEvent.HAMMER_AND_RTM_ELIGIBLE): PublicRunState.RTM_PENDING,
    # Hammer falls with no RTM entitlement → lot closed, next lot opens
    (PublicRunState.FINAL_CALL, AuctionEvent.HAMMER_SOLD): PublicRunState.LOT_OPEN,

    # ── RTM window ───────────────────────────────────────────────────────────
    # RTM accepted or declined (or timed out) → next lot
    (PublicRunState.RTM_PENDING, AuctionEvent.RTM_RESOLVED): PublicRunState.LOT_OPEN,
}

# ---------------------------------------------------------------------------
# Derived sets for guard checks
# ---------------------------------------------------------------------------

#: States from which a PAUSE event is accepted.
PAUSE_RESUMABLE_STATES: frozenset[PublicRunState] = frozenset({
    PublicRunState.LOT_OPEN,
    PublicRunState.BIDDING_ACTIVE,
    PublicRunState.COUNTDOWN,
    PublicRunState.GOING_ONCE,
    PublicRunState.GOING_TWICE,
    PublicRunState.FINAL_CALL,
    PublicRunState.RTM_PENDING,
})

#: String values of internal (engine-only) states — must never reach the UI.
INTERNAL_STATE_VALUES: frozenset[str] = frozenset(s.value for s in InternalRunState)

#: All valid public state string values — used for boundary checking.
PUBLIC_STATE_VALUES: frozenset[str] = frozenset(s.value for s in PublicRunState)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class InvalidTransitionError(ValueError):
    """Raised when an event cannot be applied from the current public run state."""

    def __init__(self, from_state: str, event: str) -> None:
        self.from_state = from_state
        self.event = event
        super().__init__(
            f"Invalid transition: cannot apply event {event!r} "
            f"from state {from_state!r}."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def can_transition(from_state: PublicRunState, event: AuctionEvent) -> bool:
    """Return True if *event* is a valid trigger from *from_state*."""
    return (from_state, event) in VALID_TRANSITIONS


def get_next_state(from_state: PublicRunState, event: AuctionEvent) -> PublicRunState:
    """Return the next state for (from_state, event).

    Raises
    ------
    InvalidTransitionError
        If the (from_state, event) pair has no entry in VALID_TRANSITIONS.
    """
    key = (from_state, event)
    if key not in VALID_TRANSITIONS:
        raise InvalidTransitionError(from_state.value, event.value)
    return VALID_TRANSITIONS[key]


def can_pause(current_state: PublicRunState) -> bool:
    """Return True if the auction can be paused from *current_state*."""
    return current_state in PAUSE_RESUMABLE_STATES


def is_terminal_state(state: PublicRunState) -> bool:
    """Return True if *state* is the final state (AUCTION_COMPLETE)."""
    return state is PublicRunState.AUCTION_COMPLETE


def assert_not_internal(state_value: str) -> None:
    """Raise ValueError if *state_value* is an internal-only state.

    Used as a safety guard before writing public_run_state to any response.
    """
    if state_value in INTERNAL_STATE_VALUES:
        raise ValueError(
            f"Internal state {state_value!r} must not be exposed as a "
            "public_run_state value."
        )
