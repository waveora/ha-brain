"""Constants for the Brain integration (Septic Brain / Water Aware, local API)."""

from datetime import timedelta

DOMAIN = "brain"
MANUFACTURER = "Septic Brain"

CONF_TOKEN = "token"

# Options.
OPT_RELAY_CONTROL = "relay_control"
OPT_WATER_UNIT = "water_unit"
OPT_WATER_MULTIPLIER = "water_multiplier"
WATER_UNITS = ["gal", "ft³", "CCF", "m³", "L"]
DEFAULT_WATER_UNIT = "gal"
DEFAULT_WATER_MULTIPLIER = 1.0

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

# Action whose name no product handles: authorised → 404, else 401. Used to
# check a token without changing anything.
VERIFY_ACTION = "brain-verify"
