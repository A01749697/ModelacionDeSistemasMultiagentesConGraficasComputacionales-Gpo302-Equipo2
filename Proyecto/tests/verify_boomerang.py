import sys
import os
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from model import CityModel
from agents import Car, Destination

class TestBoomerang(unittest.TestCase):
    def test_boomerang_avoidance(self):
        print("\n--- Testing Boomerang Bug Avoidance ---")
        model = CityModel(num_cars=0, num_police=0, num_chaotic=0)
        
        # Setup: 
        # Dest A at (5,5)
        # Dest B at (5,6) (very close)
        
        pos_a = (5, 5)
        pos_b = (5, 6)
        
        dest_a = Destination(model.next_id(), model)
        model.grid.place_agent(dest_a, pos_a)
        model.destinations.append(dest_a)
        
        dest_b = Destination(model.next_id(), model)
        model.grid.place_agent(dest_b, pos_b)
        model.destinations.append(dest_b)
        
        # Car at Dest A, PARKED, about to leave
        car = Car(model.next_id(), model, destination=dest_a)
        model.grid.place_agent(car, pos_a)
        car.state = "PARKED"
        car.parking_timer = 1
        dest_a.occupant = car
        
        print(f"Initial: Car at {car.pos}, State={car.state}, Dest={car.destination.unique_id}")
        
        # Step 1: Timer expires. Should release A and become WANDERING.
        # Should set do_not_park_here = dest_a
        car.step()
        print(f"Step 1: Car State={car.state}, DoNotPark={car.do_not_park_here.unique_id if car.do_not_park_here else 'None'}")
        
        self.assertEqual(car.state, "WANDERING")
        self.assertEqual(car.do_not_park_here, dest_a)
        self.assertIsNone(dest_a.occupant)
        
        # Step 2: Wandering step. Should call broadcast_request.
        # Should NOT pick dest_a (dist 0). Should pick dest_b (dist 1).
        car.step()
        print(f"Step 2: Car State={car.state}, Dest={car.destination.unique_id if car.destination else 'None'}")
        
        if car.destination == dest_a:
            self.fail("Boomerang! Car re-picked the spot it just left.")
        
        self.assertIsNotNone(car.destination, "Car should pick a new destination")
        self.assertNotEqual(car.destination, dest_a, "Car should NOT pick Dest A")
        self.assertEqual(car.state, "DRIVING")
        self.assertIsNone(car.do_not_park_here, "Should have cleared do_not_park_here after finding new dest")

if __name__ == '__main__':
    unittest.main()
