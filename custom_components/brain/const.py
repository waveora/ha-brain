"""Constants for the Brain integration (Septic Brain, local API)."""

from datetime import timedelta

DOMAIN = "brain"
MANUFACTURER = "Septic Brain"

# Status JSON format major version this integration reads.
STATUS_FORMAT_VERSION = 1

# Transport (`fw-status-api`): keep-alive comments every 15 s, so twice that
# plus slack means the stream is dead; poll while the stream is refused.
STREAM_IDLE_TIMEOUT = 35.0
POLL_INTERVAL = timedelta(seconds=10)
STREAM_RETRY = timedelta(seconds=60)
RECONNECT_MIN = 2.0
RECONNECT_MAX = 60.0
REQUEST_TIMEOUT = 10.0

# A power value is current when it came within this of its partner (`current_with`).
SAME_REPORT_S = 2.0
# Energy is not integrated across a gap longer than this (AC reports come at
# least every 60 s; the catalog marks them stale after 3 min).
ENERGY_MAX_GAP_S = 180.0
