import sys
import os
import unittest
import networkx as nx
from mesa.space import MultiGrid
from mesa import Model
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agents import Car

class MockModel(Model):
    def __init__(self):
        self.G = nx.DiGraph()
        self.grid = MultiGrid(2, 2, torus=False)
        self.destinations = [] # Mock destinations list

class TestHighwayIntegrity(unittest.TestCase):
    def setUp(self):
        self.model = MockModel()
        # Create a simple one-way street: (0,0) -> (0,1)
        self.model.G.add_edge((0, 0), (0, 1))
        self.model.G.add_node((0, 0))
        self.model.G.add_node((0, 1))
        
    def test_cannot_move_against_traffic(self):
        # Place car at (0, 1) - End of the one-way street
        car = Car(1, self.model)
        self.model.grid.place_agent(car, (0, 1))
        
        # Try to move to (0, 0) - Against traffic
        can_move = car.can_move_to((0, 0))
        self.assertFalse(can_move, "Car should NOT be able to move against traffic flow")
        
        # Ensure wandering_step doesn't pick it either
        # Mock random choice to pick (0,0) if it were valid
        # But wandering_step filters neighbors first.
        # Let's check if (0,0) is in valid neighbors manually logic
        neighbors = self.model.grid.get_neighborhood(car.pos, moore=False, include_center=False)
        # (0,0) is a physical neighbor
        self.assertIn((0, 0), neighbors)
        
        # But should be filtered out by can_move_to AND has_edge check
        valid_neighbors = []
        for n in neighbors:
            if car.can_move_to(n) and self.model.G.has_edge(car.pos, n):
                valid_neighbors.append(n)
        
        self.assertNotIn((0, 0), valid_neighbors, "Wandering step should not consider upstream nodes")

    def test_can_move_with_traffic(self):
        # Place car at (0, 0) - Start of the one-way street
        car = Car(2, self.model)
        self.model.grid.place_agent(car, (0, 0))
        
        # Try to move to (0, 1) - With traffic
        can_move = car.can_move_to((0, 1))
        self.assertTrue(can_move, "Car SHOULD be able to move with traffic flow")

if __name__ == '__main__':
    unittest.main()
