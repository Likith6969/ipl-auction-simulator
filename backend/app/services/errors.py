class InvalidPhaseError(Exception):
    pass


class RetentionAlreadyConfirmedError(Exception):
    pass


class InvalidRetentionError(Exception):
    pass


class RetentionsIncompleteError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class AuctionAlreadyInitializedError(Exception):
    pass


class AuctionNotReadyError(Exception):
    """Raised when an operation requires phase=AUCTION but the session is not."""

    def __init__(self, session_id: str, actual_phase: str) -> None:
        self.session_id = session_id
        self.actual_phase = actual_phase
        super().__init__(
            f"Session {session_id} is in phase {actual_phase!r}; "
            "expected AUCTION phase."
        )


class InvalidAuctionStateError(Exception):
    """Raised when the requested state-machine transition is not permitted.

    Wraps ``auction_transitions.InvalidTransitionError`` with session context.
    """

    def __init__(self, session_id: str, from_state: str, event: str) -> None:
        self.session_id = session_id
        self.from_state = from_state
        self.event = event
        super().__init__(
            f"Session {session_id}: cannot apply event {event!r} "
            f"from state {from_state!r}."
        )
