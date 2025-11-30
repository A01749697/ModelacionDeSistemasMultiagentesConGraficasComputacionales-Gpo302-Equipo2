import sys
import os
import unittest
import networkx as nx
from mesa.space import MultiGrid
from mesa import Model
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agents import Car, Destination

class MockModel(Model):
    def __init__(self):
        self.G = nx.DiGraph()
        self.grid = MultiGrid(5, 5, torus=False)
        self.destinations = []

class TestWeightedNavigation(unittest.TestCase):
    def setUp(self):
        self.model = MockModel()
        
    def test_weighted_pathfinding_prefers_straight_over_lane_change(self):
        """Verify that A* with weights prefers straight path over lane-changing path"""
        # Create two paths:
        # Path 1: (0,0) -> (1,0) -> (2,0) (2 edges, weight=1 each, total=2)
        # Path 2: (0,0) -> (0,1) -> (1,1) -> (2,1) -> (2,0) (4 edges with lane change, higher total weight)
        
        self.model.G.add_edge((0, 0), (1, 0), weight=1)  # Forward
        self.model.G.add_edge((1, 0), (2, 0), weight=1)  # Forward
        
        self.model.G.add_edge((0, 0), (0, 1), weight=5)  # Lane change
        self.model.G.add_edge((0, 1), (1, 1), weight=1)  # Forward
        self.model.G.add_edge((1, 1), (2, 1), weight=1)  # Forward
        self.model.G.add_edge((2, 1), (2, 0), weight=5)  # Lane change back
        
        # Create dest
        dest = Destination(999, self.model)
        self.model.grid.place_agent(dest, (2, 0))
        
        # Create car at start
        car = Car(1, self.model, destination=dest)
        self.model.grid.place_agent(car, (0, 0))
        
        # Calculate path with weights
        car.calculate_path()
        
        # Should pick the straight path (0,0) -> (1,0) -> (2,0)
        # Note: calculate_path removes first element, so we expect path to have (1,0) and (2,0)
        # But since we're at (0,0), after popping we have only the remaining steps
        self.assertGreater(len(car.path), 0)
        # First step should be toward (1,0) - the straight path
        self.assertEqual(car.path[0], (1, 0))
    
    def test_destination_protection(self):
        """Verify that cars can't enter destinations that aren't theirs"""
        # Place two destinations
        dest1 = Destination (100, self.model)
        dest2 = Destination(200, self.model)
        self.model.grid.place_agent(dest1, (1, 0))
        self.model.grid.place_agent(dest2, (2, 0))
        
        # Create car with dest1 as destination
        car = Car(1, self.model, destination=dest1)
        self.model.grid.place_agent(car, (0, 0))
        
        # Add edges
        self.model.G.add_edge((0, 0), (1, 0), weight=1)
        self.model.G.add_edge((0, 0), (2, 0), weight=1)
        
        # Car should be able to move to dest1
        self.assertTrue(car.can_move_to((1, 0)))
        
        # Car should NOT be able to move to dest2
        self.assertFalse(car.can_move_to((2, 0)))
    
    def test_smart_wandering_prefers_low_weight(self):
        """Verify that wandering prefers neighbors with lower edge weights"""
        # Create graph with one low-weight edge and one high-weight edge
        self.model.G.add_edge((1, 1), (2, 1), weight=1)   # Low weight
        self.model.G.add_edge((1, 1), (1, 2), weight=100) # High weight (parking)
        
        car = Car(1, self.model)
        self.model.grid.place_agent(car, (1, 1))
        car.state = "WANDERING"
        
        # Run wandering step multiple times (should pick low-weight neighbor most of the time)
        low_weight_picks = 0
        num_trials = 100
        
        for _ in range(num_trials):
            initial_pos = car.pos
            car.wandering_step()
            if car.pos == (2, 1):
                low_weight_picks += 1
            # Reset position
            self.model.grid.move_agent(car, initial_pos)
        
        # Should pick low-weight option >70% of the time (90% expected with randomness)
        self.assertGreater(low_weight_picks, 70)

if __name__ == '__main__':
    unittest.main()
