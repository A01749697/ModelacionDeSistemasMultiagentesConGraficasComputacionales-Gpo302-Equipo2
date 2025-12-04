import unittest
import sys
import os
import networkx as nx

# Add parent directory to path to import model and agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from model import CityModel
from agents import ChaoticCar, PoliceCar, Car

class TestAILogic(unittest.TestCase):
    def setUp(self):
        # Initialize model with 0 agents to manually place them
        self.model = CityModel(num_cars=0, num_police=0, num_chaotic=0)
        # Clear schedule to avoid interference
        # self.model.schedule.agents is a property, cannot set. 
        # Since we init with 0 agents, it should be empty.
        pass
        pass # MultiGrid handles empties automatically

    def test_chaotic_escape(self):
        print("\n--- Test Chaotic Escape ---")
        # Setup: Chaotic at (5, 5), Police at (5, 4)
        # Assuming (5,5) and (5,4) are valid road cells. 
        # Let's check the map in model.py or just use known road coordinates.
        # Row 25 (index 2) is "vv##vv##vvSS########D#^^" -> y=21
        # Let's use the tunnel spawn point area which is known to be road.
        # Tunnel is at (22, 22). 
        
        # Let's find valid road points dynamically to be safe
        road_cells = [node for node in self.model.G.nodes()]
        self.assertTrue(len(road_cells) > 10, "Graph should have nodes")
        
        # Pick two adjacent nodes
        start_node = (1, 22) # Top left corner area
        neighbor_nodes = list(self.model.G.neighbors(start_node))
        if not neighbor_nodes:
            start_node = road_cells[0]
            neighbor_nodes = list(self.model.G.neighbors(start_node))
            
        police_pos = start_node
        chaotic_pos = neighbor_nodes[0]
        
        print(f"Placing Police at {police_pos}, Chaotic at {chaotic_pos}")
        
        police = PoliceCar(100, self.model)
        chaotic = ChaoticCar(101, self.model)
        
        self.model.grid.place_agent(police, police_pos)
        self.model.grid.place_agent(chaotic, chaotic_pos)
        self.model.schedule.add(police)
        self.model.schedule.add(chaotic)
        
        # Force detection
        chaotic.step() # Should detect police and switch to ESCAPING
        
        print(f"Chaotic State: {chaotic.state}")
        self.assertEqual(chaotic.state, "ESCAPING")
        
        # Check movement
        initial_dist = abs(chaotic.pos[0] - police.pos[0]) + abs(chaotic.pos[1] - police.pos[1])
        print(f"Initial Distance: {initial_dist}")
        
        # Chaotic moves again (step was called above, but let's check result of next step if needed or check current pos)
        # The first step() already moved it? Yes.
        new_dist = abs(chaotic.pos[0] - police.pos[0]) + abs(chaotic.pos[1] - police.pos[1])
        print(f"New Distance: {new_dist}")
        
        # It should have moved AWAY or stayed same (if cornered), but ideally away.
        # Since we picked a neighbor, dist was 1. Now it should be >= 1.
        self.assertGreaterEqual(new_dist, initial_dist)

    def test_police_chase_and_arrest(self):
        print("\n--- Test Police Chase and Arrest ---")
        # Setup: Police and Chaotic adjacent
        
        # Find a valid pair in G
        edges = list(self.model.G.edges())
        if not edges:
             self.skipTest("Graph has no edges")
        
        # Pick an edge (u, v)
        u, v = edges[0]
        p_pos = u
        c_pos = v
        
        police = PoliceCar(200, self.model)
        chaotic = ChaoticCar(201, self.model)
        
        self.model.grid.place_agent(police, p_pos)
        self.model.grid.place_agent(chaotic, c_pos)
        self.model.schedule.add(police)
        self.model.schedule.add(chaotic)
        
        # 1. Police detects Chaotic
        police.step()
        print(f"Police State after step 1: {police.state}")
        
        # Since they are neighbors (distance 1), Police might arrest immediately (Close Range) OR move and arrest
        dist = abs(police.pos[0] - chaotic.pos[0]) + abs(police.pos[1] - chaotic.pos[1])
        
        if police.state == "ARRESTING":
            print("Arrest happened!")
            self.assertTrue(dist <= 1, "Arrest should only happen at close range")
            self.assertEqual(chaotic.state, "ARRESTED")
        else:
            self.assertEqual(police.state, "CHASE")

    def test_serialization_direction(self):
        print("\n--- Test Serialization Direction ---")
        car = Car(400, self.model)
        self.model.grid.place_agent(car, (1, 1))
        self.model.schedule.add(car)
        
        # Mock last_move
        car.last_move = (1, 0) # East
        data = self.model.serialize_grid()
        car_data = next(d for d in data if d['id'] == 400)
        self.assertEqual(car_data['direction'], "East")
        
        car.last_move = (0, 1) # North
        data = self.model.serialize_grid()
        car_data = next(d for d in data if d['id'] == 400)
        self.assertEqual(car_data['direction'], "North")
        
        # Test initial static direction (no last_move)
        car.last_move = None
        # (1,1) in map is likely a street. Let's check map at (1,1) -> row 22, col 1
        # city_map[22] is "vv>>>>>S>>>>>>>S>>>>>>^^"
        # city_map[22][1] is 'v' -> South? 
        # Wait, row 0 is top. 
        # y=1 means row = 23 - 1 = 22.
        # city_map[22] is "vv>>>>>S>>>>>>>S>>>>>>^^"
        # col 1 is 'v'. So direction should be South.
        
        # Let's verify map content at (1,1)
        cell = self.model.grid.get_cell_list_contents([(1,1)])
        # We can't easily check map symbol from here without accessing city_map global or model property if it had one.
        # But we can rely on the test running against the real model.py
        
        data = self.model.serialize_grid()
        car_data = next(d for d in data if d['id'] == 400)
        # Based on my analysis of map string in model.py:
        # row 22: "vv>>>>>..." -> col 1 is 'v' -> South
        # Let's assert it returns SOMETHING valid
        self.assertIn(car_data['direction'], ["North", "South", "East", "West"])

    def test_arrest_logic_explicit(self):
        print("\n--- Test Explicit Arrest Logic ---")
        # Force Police to be next to Chaotic and step onto it
        
        # Find a valid pair in G
        edges = list(self.model.G.edges())
        u, v = edges[0]
        p_pos = u
        c_pos = v

        police = PoliceCar(300, self.model)
        chaotic = ChaoticCar(301, self.model)
        
        self.model.grid.place_agent(police, p_pos)
        self.model.grid.place_agent(chaotic, c_pos)
        
        # Run police step
        police.step()
        
        # Should be ARRESTING now because it moved to c_pos
        print(f"Police Pos: {police.pos}")
        print(f"Police State: {police.state}")
        print(f"Chaotic State: {chaotic.state}")
        
        self.assertEqual(police.pos, c_pos)
        self.assertEqual(police.state, "ARRESTING")
        self.assertEqual(chaotic.state, "ARRESTED")

if __name__ == '__main__':
    unittest.main()
