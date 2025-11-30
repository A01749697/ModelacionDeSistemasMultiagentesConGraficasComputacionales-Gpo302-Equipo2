import sys
import os
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from model import CityModel
from agents import Car, TrafficLight

class TestIntersectionClearance(unittest.TestCase):
    def test_clear_intersection(self):
        print("\n--- Testing Intersection Clearance ---")
        model = CityModel(num_cars=0, num_police=0, num_chaotic=0)
        
        # Setup: Car INSIDE intersection at (1,1)
        # Traffic Light at (1,1) is RED
        # Target is (1,2)
        
        pos_intersection = (1, 1)
        pos_target = (1, 2)
        
        model.G.add_node(pos_intersection)
        model.G.add_node(pos_target)
        model.G.add_edge(pos_intersection, pos_target, weight=1)
        
        tl = TrafficLight(model.next_id(), model, direction="NS", state="Red")
        model.grid.place_agent(tl, pos_intersection)
        
        car = Car(model.next_id(), model, destination=None)
        model.grid.place_agent(car, pos_intersection)
        
        print(f"Initial: Car at {car.pos}, TL at {tl.pos} (State={tl.state})")
        
        # Check if car can move to target
        # Should be True because car is ON the TL
        can_pass = car.can_pass_traffic_light(pos_target)
        print(f"Can Pass Traffic Light? {can_pass}")
        
        self.assertTrue(can_pass, "Car should be allowed to exit intersection even if light is Red")
        
        # Now test entering: Car at (1,0) trying to enter (1,1) Red
        pos_start = (1, 0)
        model.G.add_node(pos_start)
        model.G.add_edge(pos_start, pos_intersection, weight=1)
        
        car_entering = Car(model.next_id(), model, destination=None)
        model.grid.place_agent(car_entering, pos_start)
        
        can_enter = car_entering.can_pass_traffic_light(pos_intersection)
        print(f"Can Enter Red Light? {can_enter}")
        
        # Should be False (assuming strict direction check blocks it, or just Red light blocks it)
        # In this case, Red NS blocks vertical movement?
        # TL direction is NS. Car moving (1,0)->(1,1) is vertical (dy=1).
        # Wait, Red NS blocks vertical? 
        # Logic: if agent.direction == "NS" and dy != 0: return False
        # So Red NS blocks vertical. Correct.
        
        self.assertFalse(can_enter, "Car should NOT be allowed to enter Red light")

if __name__ == '__main__':
    unittest.main()
