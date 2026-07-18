"""Mid-season draft manager — handles the state machine for the H2 redraft.

States:
  NOT_STARTED  → Draft hasn't been initiated yet.
  ORDER_SET    → Player order is decided; waiting for first pick.
  IN_PROGRESS  → Picks are being made turn-by-turn.
  COMPLETED    → All 20 picks done; H2 ownership finalized.

The draft state is persisted to disk so it survives server restarts.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from src.config import Config
from src.draft.order import generate_snake_order, generate_custom_snake_order

logger = logging.getLogger(__name__)


class DraftStatus(str, Enum):
    NOT_STARTED = "not_started"
    ORDER_SET = "order_set"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class DraftPick(BaseModel):
    """A single pick in the draft."""
    pick_number: int           # 1-based pick index
    player_name: str           # Who is picking
    driver_name: str           # Which driver they picked
    timestamp: str = ""        # When the pick was made


class DraftState(BaseModel):
    """Full state of the mid-season draft."""
    status: DraftStatus = DraftStatus.NOT_STARTED
    player_names: list[str] = Field(default_factory=list)
    base_order: list[str] = Field(default_factory=list)      # The initial 1-4 order
    pick_order: list[str] = Field(default_factory=list)       # Full 20-pick snake order
    picks: list[DraftPick] = Field(default_factory=list)      # Completed picks
    available_drivers: list[str] = Field(default_factory=list)  # Remaining drivers
    current_pick_index: int = 0                                # Index into pick_order
    total_picks: int = 20
    created_at: str = ""
    completed_at: str = ""
    revision: int = 0                                          # Bumped on every save; used for polling

    @property
    def current_picker(self) -> Optional[str]:
        """Who is currently picking."""
        if self.current_pick_index < len(self.pick_order):
            return self.pick_order[self.current_pick_index]
        return None

    @property
    def is_complete(self) -> bool:
        return self.current_pick_index >= self.total_picks

    @property
    def picks_by_player(self) -> dict[str, list[str]]:
        """Map of player_name -> list of driver names they picked."""
        result: dict[str, list[str]] = {name: [] for name in self.player_names}
        for pick in self.picks:
            result[pick.player_name].append(pick.driver_name)
        return result

    @property
    def current_round(self) -> int:
        """Current round number (1-based)."""
        n = len(self.player_names)
        if n == 0:
            return 0
        return (self.current_pick_index // n) + 1

    @property
    def pick_in_round(self) -> int:
        """Pick position within the current round (1-based)."""
        n = len(self.player_names)
        if n == 0:
            return 0
        return (self.current_pick_index % n) + 1


class DraftManager:
    """Manages the mid-season redraft process."""

    def __init__(
        self,
        state_file: str | None = None,
        all_drivers: list[str] | None = None,
        sheets_backend=None,
    ):
        self.state_file = Path(state_file or Config.DRAFT_STATE_FILE)
        self.all_drivers = all_drivers or []
        # Optional durable backend (Google Sheets). Must expose
        # load_state() -> dict | None and save_state(dict) -> None.
        self.sheets_backend = sheets_backend
        # Guards all state mutations so simultaneous picks from different
        # browsers can't corrupt the draft or double-write the state file.
        self._lock = threading.RLock()
        self.state = self._load()

    def _load(self) -> DraftState:
        """Load draft state, preferring the durable sheets backend."""
        # 1) Try the durable backend (survives redeploys / ephemeral disk).
        if self.sheets_backend is not None:
            try:
                data = self.sheets_backend.load_state()
                if data:
                    logger.info("Loaded draft state from Google Sheets")
                    return DraftState(**data)
            except Exception as e:
                logger.warning(f"Failed to load draft state from sheets: {e}")

        # 2) Fall back to the local disk cache.
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                return DraftState(**data)
            except Exception as e:
                logger.warning(f"Failed to load draft state: {e}")
        return DraftState()

    def _save(self):
        """Persist draft state to disk and (if configured) to Google Sheets."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state.revision += 1
        payload = self.state.model_dump()
        with open(self.state_file, "w") as f:
            json.dump(payload, f, indent=2)
        logger.debug(f"Draft state saved to {self.state_file}")

        if self.sheets_backend is not None:
            try:
                self.sheets_backend.save_state(payload)
            except Exception as e:
                # Sheets is the durable store, but a write failure shouldn't
                # crash a pick — the local cache still has the latest state.
                logger.warning(f"Failed to persist draft state to sheets: {e}")

    def start_draft(
        self,
        player_names: list[str],
        all_drivers: list[str],
        randomize: bool = True,
        custom_order: list[str] | None = None,
    ) -> DraftState:
        """
        Initialize a new draft.

        Args:
            player_names: The 4 player names.
            all_drivers: All 20 F1 driver names available for picking.
            randomize: If True, randomly determine draft order.
            custom_order: If provided, use this exact order (overrides randomize).
        """
        # Each player picks exactly DRAFT_PICKS_PER_PLAYER drivers (default 5),
        # so with 4 players that's 20 picks — NOT every available driver.
        num_players = len(player_names)
        total_picks = num_players * Config.DRAFT_PICKS_PER_PLAYER

        if custom_order:
            base_order = list(custom_order)
            pick_order = generate_custom_snake_order(base_order, total_picks=total_picks)
        elif randomize:
            pick_order = generate_snake_order(player_names, total_picks=total_picks, randomize=True)
            # Extract the base order from the first N picks
            base_order = pick_order[:len(player_names)]
        else:
            base_order = list(player_names)
            pick_order = generate_custom_snake_order(base_order, total_picks=total_picks)

        with self._lock:
            self.state = DraftState(
                status=DraftStatus.ORDER_SET,
                player_names=list(player_names),
                base_order=base_order,
                pick_order=pick_order,
                picks=[],
                available_drivers=sorted(all_drivers),
                current_pick_index=0,
                total_picks=total_picks,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._save()
        logger.info(f"Draft started! Order: {base_order} ({total_picks} picks)")
        return self.state

    def make_pick(self, player_name: str, driver_name: str) -> DraftState:
        """
        Record a draft pick.

        Args:
            player_name: Who is making the pick.
            driver_name: Which driver they're picking.

        Raises:
            ValueError: If it's not this player's turn, or driver is unavailable.
        """
        with self._lock:
            if self.state.status == DraftStatus.COMPLETED:
                raise ValueError("Draft is already completed")

            if self.state.status == DraftStatus.NOT_STARTED:
                raise ValueError("Draft hasn't started yet")

            expected = self.state.current_picker
            if player_name != expected:
                raise ValueError(
                    f"It's {expected}'s turn to pick, not {player_name}'s"
                )

            if driver_name not in self.state.available_drivers:
                raise ValueError(
                    f"{driver_name} is not available. "
                    f"Available: {self.state.available_drivers}"
                )

            # Record the pick
            pick = DraftPick(
                pick_number=self.state.current_pick_index + 1,
                player_name=player_name,
                driver_name=driver_name,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            self.state.picks.append(pick)
            self.state.available_drivers.remove(driver_name)
            self.state.current_pick_index += 1

            # Update status
            if self.state.status == DraftStatus.ORDER_SET:
                self.state.status = DraftStatus.IN_PROGRESS

            if self.state.is_complete:
                self.state.status = DraftStatus.COMPLETED
                self.state.completed_at = datetime.now(timezone.utc).isoformat()
                logger.info("🏁 Draft completed!")

            self._save()
            logger.info(
                f"Pick #{pick.pick_number}: {player_name} → {driver_name} "
                f"({len(self.state.available_drivers)} remaining)"
            )
            return self.state

    def undo_last_pick(self) -> DraftState:
        """Undo the most recent pick (admin function)."""
        with self._lock:
            if not self.state.picks:
                raise ValueError("No picks to undo")

            last_pick = self.state.picks.pop()
            self.state.available_drivers.append(last_pick.driver_name)
            self.state.available_drivers.sort()
            self.state.current_pick_index -= 1

            if self.state.status == DraftStatus.COMPLETED:
                self.state.status = DraftStatus.IN_PROGRESS
            if not self.state.picks and self.state.status == DraftStatus.IN_PROGRESS:
                self.state.status = DraftStatus.ORDER_SET

            self._save()
            logger.info(f"Undid pick: {last_pick.player_name} → {last_pick.driver_name}")
            return self.state

    def reset_draft(self) -> DraftState:
        """Reset the draft back to NOT_STARTED."""
        with self._lock:
            self.state = DraftState()
            self._save()
        logger.info("Draft reset to NOT_STARTED")
        return self.state

    def get_status(self) -> dict:
        """Get a JSON-serializable status summary."""
        return {
            "status": self.state.status.value,
            "player_names": self.state.player_names,
            "base_order": self.state.base_order,
            "current_picker": self.state.current_picker,
            "current_pick_number": self.state.current_pick_index + 1,
            "total_picks": self.state.total_picks,
            "current_round": self.state.current_round,
            "pick_in_round": self.state.pick_in_round,
            "available_drivers": self.state.available_drivers,
            "picks": [
                {
                    "pick_number": p.pick_number,
                    "player_name": p.player_name,
                    "driver_name": p.driver_name,
                }
                for p in self.state.picks
            ],
            "picks_by_player": self.state.picks_by_player,
            "is_complete": self.state.is_complete,
            "pick_order": self.state.pick_order,
            "revision": self.state.revision,
        }
