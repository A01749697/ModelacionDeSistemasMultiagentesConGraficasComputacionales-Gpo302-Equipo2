import sys
import os
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from model import CityModel
from agents import Car, TrafficLight, Destination

class TestRefactor(unittest.TestCase):
    def test_wandering_wait_at_red(self):
        print("\n--- Testing Wandering Car Waits at Red Light ---")
        model = CityModel(num_cars=0, num_police=0, num_chaotic=0)
        
        # Setup: Car -> (1,1) -> Light(Red) at (1,2) -> (1,3)
        # Also add a "Lane Change" option: (1,1) -> (2,1)
        
        test_pos_car = (1, 1)
        test_pos_light = (1, 2)
        test_pos_lane_change = (2, 1)
        
        model.G.add_node(test_pos_car)
        model.G.add_node(test_pos_light)
        model.G.add_node(test_pos_lane_change)
        
        # Edge to Light (Weight 1)
        model.G.add_edge(test_pos_car, test_pos_light, weight=1)
        # Edge for Lane Change (Weight 10)
        model.G.add_edge(test_pos_car, test_pos_lane_change, weight=10)
        
        # Place Agents
        tl = TrafficLight(model.next_id(), model, direction="NS", state="Red")
        tl.timer = 10
        model.grid.place_agent(tl, test_pos_light)
        
        car = Car(model.next_id(), model, destination=None) # Wandering
        car.debug = True
        model.grid.place_agent(car, test_pos_car)
        
        # Step
        print("Stepping Car...")
        car.step()
        
        # Assertions
        # 1. Car should NOT move to Lane Change (weight 10 vs 1)
        # 2. Car should NOT move to Light (Red)
        # 3. Car should stay at (1,1)
        
        print(f"Car Pos: {car.pos}")
        self.assertEqual(car.pos, test_pos_car, "Car should wait at Red Light, not change lane or pass.")
        
    def test_parking_release(self):
        print("\n--- Testing Parking Release ---")
        model = CityModel(num_cars=0, num_police=0, num_chaotic=0)
        
        dest_pos = (5, 5)
        dest = Destination(model.next_id(), model)
        model.grid.place_agent(dest, dest_pos)
        
        car = Car(model.next_id(), model, destination=dest)
        model.grid.place_agent(car, dest_pos)
        
        # Manually set car to PARKED
        car.state = "PARKED"
        car.parking_timer = 1
        dest.occupant = car
        
        print(f"Initial: Car State={car.state}, Dest Occupant={dest.occupant}")
        
        # Step 1: Timer becomes 0, should release
        car.step()
        
        print(f"After Step: Car State={car.state}, Dest Occupant={dest.occupant}")
        
        self.assertEqual(car.state, "WANDERING", "Car should be WANDERING after parking")
        self.assertIsNone(dest.occupant, "Destination should be released")
        self.assertIsNone(car.destination, "Car should have no destination")

if __name__ == '__main__':
    unittest.main()
