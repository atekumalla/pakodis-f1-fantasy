"""Automatic substitution detection from OpenF1 entry lists.

For each scored session we know who actually took part (``/drivers``, which
sync already fetches). Comparing that to the regular 2026 roster gives:

  * absent regulars — roster drivers missing from the entry list
  * newcomers       — entrants who aren't on the roster (reserves, rookies)

Each newcomer is paired with the absent regular whose seat they ended up in
by following the chain of displaced drivers from the newcomer's team:
e.g. Tsunoda at Racing Bulls displaced Lawson, Lawson is at Red Bull where
he displaced Hadjar, Hadjar is absent → Hadjar → Tsunoda.

Detections are applied to the Substitutions list per round. Rows whose
``source`` is "manual" are never edited, and a manual row (active or not)
for an original driver + round stops detection touching that round.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from src.models.driver import Driver
from src.scoring.calculator import normalize_driver_name
from src.substitutions import DriverSubstitution

logger = logging.getLogger(__name__)

# Below this many entrants the entry list is probably partial — don't infer
# anything from who's "missing".
MIN_ENTRANTS = 18

FALLBACK_HEADSHOT = "https://media.formula1.com/d_driver_fallback_image.png"

_TEAM_NOISE = re.compile(r"\b(f1 team|formula 1 team|formula one team|scuderia|team)\b")


@dataclass
class Detection:
    original_driver: str        # roster name, e.g. "Esteban Ocon"
    substitute: Driver          # OpenF1 entrant, e.g. Rafael CAMARA
    team: str                   # roster team of the original, e.g. "Haas"


def _team_key(name: str | None) -> str:
    return " ".join(_TEAM_NOISE.sub(" ", (name or "").lower()).split())


def same_team(a: str | None, b: str | None) -> bool:
    """Loose team match: "Haas" == "Haas F1 Team", but "Red Bull Racing" != "Racing Bulls"."""
    ka, kb = _team_key(a), _team_key(b)
    if not ka or not kb:
        return False
    return ka == kb or ka in kb or kb in ka


def detect_session(
    entrants: list[Driver], regulars: list[dict]
) -> tuple[list[Detection], list[str]]:
    """Pair absent regulars with newcomers for one session.

    Returns ``(detections, issues)``; ``issues`` describes newcomers or
    absences that couldn't be resolved and need a human.
    """
    if len(entrants) < MIN_ENTRANTS:
        return [], []

    present = {normalize_driver_name(e.full_name): e for e in entrants}
    by_norm = {normalize_driver_name(r["name"]): r for r in regulars}
    absent = {n for n in by_norm if n not in present}
    newcomers = [e for n, e in present.items() if n not in by_norm]
    if not newcomers:
        return [], []

    def in_own_seat(norm: str, team: str) -> bool:
        e = present.get(norm)
        return e is not None and same_team(e.team_name, team)

    detections: list[Detection] = []
    unresolved: list[Driver] = []
    claimed: set[str] = set()

    for nc in newcomers:
        team, seen, original = nc.team_name, set(), None
        for _ in range(len(regulars)):
            displaced = [
                n for n, r in by_norm.items()
                if same_team(r["team"], team) and not in_own_seat(n, team)
                and n not in seen and n not in claimed
            ]
            if len(displaced) != 1:
                break
            n = displaced[0]
            seen.add(n)
            if n in absent:
                original = n
                break
            team = present[n].team_name  # displaced driver moved; follow him
        if original:
            claimed.add(original)
            detections.append(Detection(by_norm[original]["name"], nc, by_norm[original]["team"]))
        else:
            unresolved.append(nc)

    # Fallback (e.g. OpenF1 sent team_name=null): one newcomer left, one
    # regular left — they must be each other.
    remaining = sorted(absent - claimed)
    if len(unresolved) == 1 and len(remaining) == 1:
        r = by_norm[remaining[0]]
        detections.append(Detection(r["name"], unresolved[0], r["team"]))
        unresolved = []

    issues = [
        f"{nc.full_name} ({nc.team_name or 'unknown team'}) — couldn't tell whose seat they took"
        for nc in unresolved
    ]
    return detections, issues


def display_name(openf1_name: str) -> str:
    """'Rafael CAMARA' → 'Rafael Camara' (roster style)."""
    return " ".join(
        w.capitalize() if w.isupper() and len(w) > 1 else w for w in openf1_name.split()
    )


def make_profile(d: Detection) -> dict:
    """Driver profile for a newcomer, in the shape of seed_data.DRIVERS_2026."""
    s = d.substitute
    return {
        "number": s.driver_number,
        "name": display_name(s.full_name),
        "team": d.team,
        "acronym": s.name_acronym or display_name(s.full_name).split()[-1][:3].upper(),
        "country": s.country_code or "",
        "headshot_url": s.headshot_url or FALLBACK_HEADSHOT,
    }


def apply_round(
    substitutions: list[DriverSubstitution],
    round_number: int,
    detections: list[Detection],
    grand_prix: str,
) -> tuple[list[DriverSubstitution], list[str]]:
    """Make the auto rows for ``round_number`` match ``detections``.

    Returns the new substitution list and human-readable changes. Only this
    round is touched; manual rows are left alone and shield their original
    driver for any round they list.
    """
    norm = normalize_driver_name
    protected = {
        norm(s.original_driver)
        for s in substitutions
        if s.source == "manual" and round_number in s.rounds
    }
    wanted = {
        (norm(d.original_driver), norm(display_name(d.substitute.full_name))): d
        for d in detections
        if norm(d.original_driver) not in protected
    }

    subs = [
        DriverSubstitution(s.original_driver, s.substitute_driver, list(s.rounds),
                           s.reason, s.active, s.source)
        for s in substitutions
    ]
    changes: list[str] = []

    # Remove this round from auto rows the data contradicts.
    for s in subs:
        if s.source == "manual" or not s.active or round_number not in s.rounds:
            continue
        if norm(s.original_driver) in protected:
            continue
        if (norm(s.original_driver), norm(s.substitute_driver)) not in wanted:
            changes.append(
                f"Round {round_number}: removed {s.original_driver} → {s.substitute_driver}"
            )
            s.rounds.remove(round_number)

    # Add detected pairs.
    for key, d in wanted.items():
        row = next(
            (s for s in subs if s.source != "manual" and s.active
             and (norm(s.original_driver), norm(s.substitute_driver)) == key),
            None,
        )
        sub_name = display_name(d.substitute.full_name)
        if row is None:
            row = DriverSubstitution(
                original_driver=d.original_driver,
                substitute_driver=sub_name,
                rounds=[],
                reason=f"Auto-detected from OpenF1 entry list ({grand_prix})",
                active=True,
                source="auto",
            )
            subs.append(row)
        if round_number not in row.rounds:
            row.rounds = sorted(row.rounds + [round_number])
            changes.append(f"Round {round_number}: {d.original_driver} → {sub_name}")

    subs = [s for s in subs if s.rounds or s.source == "manual"]
    return subs, changes
