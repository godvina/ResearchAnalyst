"""Rate limiter for AI summary Bedrock invocations.

Enforces a maximum of 60 Bedrock invocations per fixed clock-hour window,
resetting at minute :00. Uses module-level state for Lambda container reuse.
"""

from datetime import datetime, timedelta, timezone


class SummaryRateLimiter:
    """Limits Bedrock invocations to MAX_INVOCATIONS_PER_HOUR per clock-hour.

    The counter resets when the current time crosses a clock-hour boundary
    (i.e., when the minute reaches :00). On Lambda cold starts the counter
    resets to zero, which is safe — it under-counts, never over-invokes.
    """

    MAX_INVOCATIONS_PER_HOUR = 60

    def __init__(self):
        self._counter: int = 0
        self._window_start: datetime = self._current_hour_start()

    def check_and_increment(self) -> tuple[bool, int]:
        """Check if under the hourly limit.

        Returns:
            (True, remaining_invocations) if the request is allowed.
            (False, seconds_until_next_hour) if the rate limit is exhausted.
        """
        now = datetime.now(timezone.utc)
        current_window = self._current_hour_start()

        # Reset counter if we've crossed into a new clock-hour
        if current_window > self._window_start:
            self._counter = 0
            self._window_start = current_window

        if self._counter < self.MAX_INVOCATIONS_PER_HOUR:
            self._counter += 1
            remaining = self.MAX_INVOCATIONS_PER_HOUR - self._counter
            return (True, remaining)

        # Rate limited — compute seconds until next hour boundary
        next_hour = self._window_start + timedelta(hours=1)
        seconds_remaining = max(1, int((next_hour - now).total_seconds()))
        return (False, seconds_remaining)

    def _current_hour_start(self) -> datetime:
        """Return the start of the current clock-hour (minute :00, second :00)."""
        now = datetime.now(timezone.utc)
        return now.replace(minute=0, second=0, microsecond=0)
