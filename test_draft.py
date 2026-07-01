#!/usr/bin/env python3
"""
Test script for mid-season draft functionality.
Creates a mock draft scenario without touching real data.

Usage:
    python test_draft.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from src.draft.manager import DraftManager, DraftStatus
from src.seed_data import DRIVERS_2026, get_all_driver_names, PLAYER_NAMES

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def test_draft_workflow():
    """Test the complete draft workflow."""
    
    # Use a test state file so we don't affect real data
    test_state_file = Path("state/test_draft_state.json")
    test_state_file.parent.mkdir(exist_ok=True)
    
    # Clean up any existing test state
    if test_state_file.exists():
        test_state_file.unlink()
        logger.info("Cleaned up previous test state")
    
    # Get all driver names
    all_drivers = get_all_driver_names()
    logger.info(f"Available drivers: {len(all_drivers)}")
    
    # Create draft manager
    draft = DraftManager(state_file=str(test_state_file), all_drivers=all_drivers)
    logger.info(f"Initial draft status: {draft.state.status}")
    
    # Test 1: Start the draft
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Starting the draft")
    logger.info("="*80)
    
    # Custom order based on H1 standings (reverse order - worst goes first)
    custom_order = ["Prateik", "Abhinav", "Rohit", "Anup"]  # Example order
    
    state = draft.start_draft(
        player_names=PLAYER_NAMES, 
        all_drivers=all_drivers,
        randomize=False,
        custom_order=custom_order
    )
    success = state.status != DraftStatus.NOT_STARTED
    if success:
        logger.info(f"✅ Draft started successfully!")
        logger.info(f"   Status: {draft.state.status}")
        logger.info(f"   Players: {draft.state.player_names}")
        logger.info(f"   Base order: {draft.state.base_order}")
        logger.info(f"   Total picks: {draft.state.total_picks}")
        logger.info(f"   Pick order (first 10): {draft.state.pick_order[:10]}")
        logger.info(f"   Current picker: {draft.state.current_picker}")
    else:
        logger.error("❌ Failed to start draft")
        return
    
    # Test 2: Make some picks
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Making picks")
    logger.info("="*80)
    
    # Simulate making picks for the first round (4 picks)
    test_picks = [
        ("Max Verstappen", "Prateik picks the reigning champion"),
        ("Kimi Antonelli", "Abhinav goes for the young Mercedes star"),
        ("Lewis Hamilton", "Rohit picks the Ferrari legend"),
        ("Lando Norris", "Anup chooses the McLaren ace"),
    ]
    
    for driver_name, comment in test_picks:
        current_picker = draft.state.current_picker
        pick_number = draft.state.current_pick_index + 1
        
        logger.info(f"\nPick #{pick_number}: {current_picker}'s turn")
        logger.info(f"   Available drivers: {len(draft.state.available_drivers)}")
        
        draft.state = draft.make_pick(player_name=current_picker, driver_name=driver_name)
        logger.info(f"   ✅ {comment}")
        logger.info(f"   Pick recorded: {current_picker} → {driver_name}")
    
    # Test 3: Check current state
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Current draft state")
    logger.info("="*80)
    
    state_dict = draft.get_status()
    logger.info(f"Status: {state_dict['status']}")
    logger.info(f"Current picker: {state_dict['current_picker']}")
    logger.info(f"Pick #{state_dict['current_pick_number']} of {state_dict['total_picks']}")
    logger.info(f"Current round: {state_dict['current_round']}")
    logger.info(f"Pick in round: {state_dict['pick_in_round']}")
    logger.info(f"\nPicks made so far:")
    for pick in state_dict['picks']:
        logger.info(f"  Pick #{pick['pick_number']}: {pick['player_name']} → {pick['driver_name']}")
    
    logger.info(f"\nDrivers by player:")
    for player, drivers in state_dict['picks_by_player'].items():
        logger.info(f"  {player}: {', '.join(drivers) if drivers else '(none yet)'}")
    
    # Test 4: Undo last pick
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Testing undo functionality")
    logger.info("="*80)
    
    last_pick = draft.state.picks[-1] if draft.state.picks else None
    if last_pick:
        logger.info(f"Last pick: {last_pick.player_name} → {last_pick.driver_name}")
        
        draft.state = draft.undo_last_pick()
        logger.info(f"✅ Undid last pick")
        logger.info(f"   Current picker now: {draft.state.current_picker}")
    
    # Test 5: Complete a full snake draft simulation
    logger.info("\n" + "="*80)
    logger.info("TEST 5: Simulating full draft (auto-pick remaining)")
    logger.info("="*80)
    
    # Auto-complete the rest of the draft
    import random
    while not draft.state.is_complete:
        available = draft.state.available_drivers
        if not available:
            logger.error("No drivers available!")
            break
        
        # Pick a random driver
        driver = random.choice(available)
        picker = draft.state.current_picker
        pick_num = draft.state.current_pick_index + 1
        
        draft.state = draft.make_pick(player_name=picker, driver_name=driver)
        logger.info(f"Pick #{pick_num}: {picker} → {driver}")
    
    # Test 6: Final state
    logger.info("\n" + "="*80)
    logger.info("TEST 6: Final draft results")
    logger.info("="*80)
    
    if draft.state.status == DraftStatus.COMPLETED:
        logger.info("✅ Draft completed successfully!")
        logger.info(f"\nFinal rosters (5 drivers each):")
        for player, drivers in draft.state.picks_by_player.items():
            logger.info(f"\n{player}:")
            for i, driver in enumerate(drivers, 1):
                logger.info(f"  {i}. {driver}")
        
        # Show pick order for reference
        logger.info(f"\nSnake draft order (picks 1-20):")
        for i, picker in enumerate(draft.state.pick_order, 1):
            driver = draft.state.picks[i-1].driver_name if i <= len(draft.state.picks) else "TBD"
            logger.info(f"  Pick {i:2d}: {picker:10s} → {driver}")
    else:
        logger.warning(f"Draft not completed. Status: {draft.state.status}")
    
    # Test 7: Check state persistence
    logger.info("\n" + "="*80)
    logger.info("TEST 7: Testing state persistence")
    logger.info("="*80)
    
    # Create a new manager instance and verify state is loaded
    draft2 = DraftManager(state_file=str(test_state_file), all_drivers=all_drivers)
    logger.info(f"Loaded draft status: {draft2.state.status}")
    logger.info(f"Loaded picks: {len(draft2.state.picks)}")
    logger.info(f"State matches: {draft2.state.status == draft.state.status}")
    
    # Cleanup
    logger.info("\n" + "="*80)
    logger.info("Test completed! Check the test state file at:")
    logger.info(f"  {test_state_file.absolute()}")
    logger.info("="*80)


if __name__ == "__main__":
    try:
        test_draft_workflow()
    except Exception as e:
        logger.exception(f"Test failed with error: {e}")
