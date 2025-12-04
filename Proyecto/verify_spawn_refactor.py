#!/usr/bin/env python3
"""
Verification script for chaotic agent spawn refactoring.
Tests the finite pool system and spawn validation logic.
"""

from model import CityModel
from agents import ChaoticCar, PoliceCar

def test_finite_pool():
    """Test that chaotic agents have a finite pool."""
    print("=" * 60)
    print("TEST 1: Finite Pool System")
    print("=" * 60)
    
    # Create model with 3 chaotic agents max
    model = CityModel(num_chaotic=3, num_police=2, num_cars=0)
    
    print(f"✓ Model initialized with max_chaotic_total = {model.max_chaotic_total}")
    print(f"✓ Initial chaotic_spawned_count = {model.chaotic_spawned_count}")
    
    # Count initial chaotic cars
    initial_count = sum(1 for a in model.schedule.agents if isinstance(a, ChaoticCar))
    print(f"✓ Initial chaotic cars spawned: {initial_count}")
    
    # Simulate arrests by manually removing all chaotic cars
    chaotic_agents = [a for a in model.schedule.agents if isinstance(a, ChaoticCar)]
    for agent in chaotic_agents:
        model.grid.remove_agent(agent)
        model.schedule.remove(agent)
    
    print(f"✓ Removed all chaotic cars (simulating arrests)")
    
    # Try to spawn more - should fail if pool is exhausted
    for i in range(5):
        result = model.spawn_chaotic_from_tunnel()
        current_count = model.chaotic_spawned_count
        print(f"  Spawn attempt {i+1}: {'Success' if result else 'Blocked'} (total spawned: {current_count}/{model.max_chaotic_total})")
    
    final_count = model.chaotic_spawned_count
    if final_count == model.max_chaotic_total:
        print(f"✅ PASS: Pool limit respected ({final_count}/{model.max_chaotic_total})")
    else:
        print(f"❌ FAIL: Pool limit not respected ({final_count}/{model.max_chaotic_total})")
    
    print()

def test_spawn_locations():
    """Test that spawn locations are valid."""
    print("=" * 60)
    print("TEST 2: Spawn Location Validation")
    print("=" * 60)
    
    model = CityModel(num_chaotic=0, num_police=0, num_cars=0)
    
    valid_corners = [(1, 1), (22, 1), (1, 22), (22, 22)]
    print(f"✓ Valid spawn corners: {valid_corners}")
    
    # Try spawning multiple times
    spawn_positions = []
    for i in range(10):
        agent = model.spawn_chaotic_from_tunnel()
        if agent:
            spawn_positions.append(agent.pos)
            # Remove to allow more spawns
            model.grid.remove_agent(agent)
            model.schedule.remove(agent)
            model.chaotic_spawned_count -= 1  # Reset counter for testing
    
    print(f"✓ Spawned {len(spawn_positions)} agents")
    print(f"✓ Spawn positions: {set(spawn_positions)}")
    
    # Check all spawns are at valid corners
    all_valid = all(pos in valid_corners for pos in spawn_positions)
    
    if all_valid:
        print(f"✅ PASS: All spawns at valid corners")
    else:
        invalid = [pos for pos in spawn_positions if pos not in valid_corners]
        print(f"❌ FAIL: Invalid spawn positions found: {invalid}")
    
    print()

def test_police_proximity():
    """Test that spawning is blocked when police are too close."""
    print("=" * 60)
    print("TEST 3: Police Proximity Check")
    print("=" * 60)
    
    model = CityModel(num_chaotic=0, num_police=0, num_cars=0)
    
    # Manually place police at all corners
    corners = [(1, 1), (22, 1), (1, 22), (22, 22)]
    for i, corner in enumerate(corners):
        police = PoliceCar(model.next_id(), model, patrol_id=i, checkpoints=[])
        model.grid.place_agent(police, corner)
        model.schedule.add(police)
    
    print(f"✓ Placed police at all corners: {corners}")
    
    # Try to spawn - should fail
    result = model.spawn_chaotic_from_tunnel()
    
    if result is None:
        print(f"✅ PASS: Spawn blocked when all corners guarded")
    else:
        print(f"❌ FAIL: Spawn succeeded at {result.pos} despite police presence")
    
    print()

if __name__ == "__main__":
    print("\n🔍 CHAOTIC AGENT SPAWN REFACTORING - VERIFICATION\n")
    
    try:
        test_finite_pool()
        test_spawn_locations()
        test_police_proximity()
        
        print("=" * 60)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 60)
        print("\nNote: Manual testing via visualization server recommended")
        print("to verify real-time behavior and visual correctness.")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
