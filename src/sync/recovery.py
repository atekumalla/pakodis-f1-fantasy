"""Recovery module — handles resuming after crashes or restarts."""

from __future__ import annotations

import logging
from datetime import date

from src.models.session import Session, SessionStatus
from src.sync.state_manager import StateManager

logger = logging.getLogger(__name__)


def get_sessions_needing_update(
    sessions: list[Session], state: StateManager
) -> list[Session]:
    """
    Determine which sessions need score updates.

    A session needs updating if:
      - It's scheduled for today or earlier
      - It's not already marked as scored in state
      - It's not already finished with results
    """
    today = date.today()
    needs_update = []

    for session in sessions:
        if session.date > today:
            continue

        if state.is_session_scored(session.session_key):
            continue

        if session.status == SessionStatus.FINISHED and session.results:
            state.mark_session_scored(session.session_key)
            continue

        needs_update.append(session)

    logger.info(
        f"Recovery check: {len(needs_update)} sessions need updates "
        f"(out of {len(sessions)} total)"
    )
    return needs_update


def reconcile_sessions(
    existing: list[Session], from_api: list[Session]
) -> list[Session]:
    """
    Merge API data with existing data, preferring API for finished sessions.
    """
    api_index: dict[int, Session] = {s.session_key: s for s in from_api}

    reconciled = []
    for session in existing:
        if session.session_key in api_index:
            api_session = api_index[session.session_key]
            if api_session.status in (SessionStatus.FINISHED, SessionStatus.IN_PROGRESS):
                reconciled.append(api_session)
            else:
                reconciled.append(session)
        else:
            reconciled.append(session)

    # Add any API sessions not in existing
    existing_keys = {s.session_key for s in existing}
    for key, api_session in api_index.items():
        if key not in existing_keys:
            reconciled.append(api_session)

    return sorted(reconciled, key=lambda s: (s.session_date, s.session_type.value))
