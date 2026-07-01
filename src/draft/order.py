"""Snake-draft order generation.

The mid-season redraft uses a snake draft:
  Round 1 (forward):  1, 2, 3, 4
  Round 2 (reverse):  4, 3, 2, 1
  Round 3 (forward):  1, 2, 3, 4
  Round 4 (reverse):  4, 3, 2, 1
  Round 5 (forward):  1, 2, 3, 4

20 total picks for 4 players × 5 drivers each.
"""

from __future__ import annotations

import random


def generate_snake_order(
    player_names: list[str],
    total_picks: int = 20,
    randomize: bool = True,
) -> list[str]:
    """
    Generate a full snake-draft pick order.

    Args:
        player_names: The 4 player names.
        total_picks: Total picks to make (default 20 = 4 players × 5 drivers).
        randomize: If True, shuffle the base order randomly.

    Returns:
        List of player names in pick order, e.g.:
        ["Anup", "Rohit", "Abhinav", "Prateik",
         "Prateik", "Abhinav", "Rohit", "Anup",
         "Anup", "Rohit", "Abhinav", "Prateik", ...]
    """
    names = list(player_names)
    if randomize:
        random.shuffle(names)

    n = len(names)
    order = []
    pick = 0

    while pick < total_picks:
        round_num = pick // n  # 0-indexed round
        pos_in_round = pick % n

        if round_num % 2 == 0:
            # Forward round
            order.append(names[pos_in_round])
        else:
            # Reverse round
            order.append(names[n - 1 - pos_in_round])

        pick += 1

    return order


def generate_custom_snake_order(
    ordered_names: list[str],
    total_picks: int = 20,
) -> list[str]:
    """
    Generate snake-draft order from a manually-specified base order.
    No randomization — uses the exact order provided.
    """
    return generate_snake_order(ordered_names, total_picks, randomize=False)
