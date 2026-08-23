"""Driver substitution system — temporary driver replacements for specific rounds."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.scoring.calculator import normalize_driver_name


@dataclass
class DriverSubstitution:
    original_driver: str
    substitute_driver: str
    rounds: list[int] = field(default_factory=list)
    reason: str = ""
    active: bool = True


# Code-side defaults (sheet tab is the source of truth; these are fallback)
ACTIVE_SUBSTITUTIONS: list[DriverSubstitution] = [
    DriverSubstitution(
        original_driver="Isack Hadjar",
        substitute_driver="Yuki Tsunoda",
        rounds=[12],
        reason="Driver replacement for Dutch GP",
        active=True,
    ),
]


def get_substitute_for_round(
    driver_name: str,
    round_number: int,
    substitutions: list[DriverSubstitution] | None = None,
) -> str | None:
    """If this driver has a substitute for this round, return the sub's name."""
    subs = substitutions or ACTIVE_SUBSTITUTIONS
    norm = normalize_driver_name(driver_name)
    for s in subs:
        if not s.active:
            continue
        if normalize_driver_name(s.original_driver) == norm and round_number in s.rounds:
            return s.substitute_driver
    return None


def get_original_for_substitute(
    substitute_name: str,
    round_number: int,
    substitutions: list[DriverSubstitution] | None = None,
) -> str | None:
    """Reverse lookup: given a sub driver name and round, return the original."""
    subs = substitutions or ACTIVE_SUBSTITUTIONS
    norm = normalize_driver_name(substitute_name)
    for s in subs:
        if not s.active:
            continue
        if normalize_driver_name(s.substitute_driver) == norm and round_number in s.rounds:
            return s.original_driver
    return None


def get_effective_drivers(
    player_drivers: list[str],
    round_number: int,
    substitutions: list[DriverSubstitution] | None = None,
) -> list[str]:
    """Return driver list with active substitutions applied for this round."""
    result = []
    for d in player_drivers:
        sub = get_substitute_for_round(d, round_number, substitutions)
        result.append(sub if sub else d)
    return result


def is_substitute_round(
    driver_name: str,
    round_number: int,
    substitutions: list[DriverSubstitution] | None = None,
) -> bool:
    return get_substitute_for_round(driver_name, round_number, substitutions) is not None


def get_all_substitution_info(
    substitutions: list[DriverSubstitution] | None = None,
) -> list[dict]:
    """Serializable list of active substitutions for API responses."""
    subs = substitutions or ACTIVE_SUBSTITUTIONS
    return [
        {
            "original_driver": s.original_driver,
            "substitute_driver": s.substitute_driver,
            "rounds": s.rounds,
            "reason": s.reason,
        }
        for s in subs
        if s.active
    ]
