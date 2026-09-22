"""
auction_timing.py
=================
Timing-policy module for the IPL Auction Engine.

Responsibilities
----------------
- Define timing_ms values for each speed profile (normal / fast / very_fast).
- Apply the accelerated-mode scale factor when ``is_accelerated=True``.
- Provide ``build_initial_live_state()`` so every call-site gets a consistent,
  correctly-versioned live_state structure.

NOT responsible for
-------------------
- Executing timers (that belongs to CountdownService, not yet built).
- Database access.
- State transitions.
- Bid placement.
- RTM resolution.

Accelerated mode
----------------
Accelerated auction is represented by two live_state fields:

    speed_profile  : "normal" | "fast" | "very_fast"
    is_accelerated : bool

It is NOT a public_run_state value — there is no "ACCELERATED_ACTIVE" state.
"""
from __future__ import annotations

from app.domain.enums import LIVE_STATE_VERSION, PublicRunState, SpeedProfile

# ---------------------------------------------------------------------------
# Timing profiles (milliseconds)
# ---------------------------------------------------------------------------
#
# All timings are defined per speed_profile.  Accelerated mode applies an
# additional 0.5× scale factor on top of the selected profile.
#
_TIMING_PROFILES: dict[str, dict[str, int]] = {
    SpeedProfile.NORMAL: {
        "countdown": 3000,      # 3-second hammer countdown per bid
        "hammer_step": 2000,    # going-once / going-twice / final-call step
        "inter_lot": 1500,      # pause between lot close and next lot open
        "set_intro": 3000,      # set-intro display duration
        "rtm_window": 4000,     # RTM decision window (spec: 4 seconds)
        "nomination_timeout": 30000,  # auctioneer nomination timeout
    },
    SpeedProfile.FAST: {
        "countdown": 2000,
        "hammer_step": 1500,
        "inter_lot": 1000,
        "set_intro": 2000,
        "rtm_window": 3000,
        "nomination_timeout": 20000,
    },
    SpeedProfile.VERY_FAST: {
        "countdown": 1000,
        "hammer_step": 800,
        "inter_lot": 500,
        "set_intro": 1000,
        "rtm_window": 2000,
        "nomination_timeout": 10000,
    },
}

# Accelerated mode halves all timing values relative to the selected profile.
_ACCELERATED_SCALE: float = 0.5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_timing_ms(
    speed_profile: str = SpeedProfile.NORMAL,
    *,
    is_accelerated: bool = False,
) -> dict[str, int]:
    """Return the timing_ms dict for *speed_profile* and *is_accelerated*.

    Parameters
    ----------
    speed_profile:
        One of "normal", "fast", "very_fast".  Falls back to "normal" if the
        value is unrecognised (e.g. after a future enum rename).
    is_accelerated:
        When True, every timing value is multiplied by 0.5 (minimum 1 ms).

    Returns
    -------
    dict[str, int]
        A flat dict of ``{timing_key: milliseconds}`` suitable for embedding
        directly in live_state["timing_ms"].
    """
    base = dict(_TIMING_PROFILES.get(speed_profile, _TIMING_PROFILES[SpeedProfile.NORMAL]))
    if is_accelerated:
        return {k: max(1, int(v * _ACCELERATED_SCALE)) for k, v in base.items()}
    return base


def build_initial_live_state(
    speed_profile: str = SpeedProfile.NORMAL,
    *,
    is_accelerated: bool = False,
) -> dict:
    """Return a freshly constructed, correctly-versioned live_state dict.

    This is the canonical factory function for live_state.  All code that
    creates or resets live_state must use this function — never construct the
    dict inline — so that version bumps propagate automatically.

    The resulting structure is **lightweight**: it contains only runtime state,
    NOT persistent auction data (current player, purse, bids, squad counts).
    Those fields live in auction_pool / team_states.

    Parameters
    ----------
    speed_profile:
        Initial speed profile ("normal" by default).
    is_accelerated:
        Initial accelerated-mode flag (False by default).
    """
    return {
        "version": LIVE_STATE_VERSION,
        "public_run_state": PublicRunState.READY.value,
        "speed_profile": speed_profile,
        "is_accelerated": is_accelerated,

        # Pause sub-object
        "pause": {
            "active": False,
            "paused_from": None,   # PublicRunState value or None
        },

        # Countdown sub-object (CountdownService will populate expires_at)
        "countdown": {
            "phase": None,          # "countdown" | "going_once" | … | None
            "expires_at": None,     # ISO-8601 UTC timestamp or None
            "generation": 0,        # increments on every reset to allow cancellation
        },

        # RTM window sub-object
        "rtm_window": {
            "active": False,
            "expires_at": None,     # ISO-8601 UTC timestamp or None
        },

        # When the engine is in an internal transition this holds the
        # InternalRunState value; otherwise None.
        "internal_phase": None,

        # Derived from speed_profile + is_accelerated; stored so the frontend
        # can display correct countdown lengths without a round-trip.
        "timing_ms": get_timing_ms(speed_profile, is_accelerated=is_accelerated),
    }
