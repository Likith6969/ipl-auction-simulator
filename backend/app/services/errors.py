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
