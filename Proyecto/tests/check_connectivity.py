import sys
import os
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from model import CityModel

class TestConnectivity(unittest.TestCase):
    def test_graph_connectivity(self):
        print("\n--- Testing Graph Connectivity ---")
        model = CityModel(num_cars=0, num_police=0, num_chaotic=0)
        
        # The setup_graph method prints the report. We just need to capture it or check internal state.
        # We can check model.G directly.
        
        print(f"Nodes: {model.G.number_of_nodes()}")
        print(f"Edges: {model.G.number_of_edges()}")
        
        unreachable = []
        for dest in model.destinations:
            if dest.pos not in model.G:
                unreachable.append(f"{dest.unique_id} (Not in Graph)")
            elif model.G.in_degree(dest.pos) == 0:
                unreachable.append(f"{dest.unique_id} (In-Degree 0)")
        
        if unreachable:
            print(f"❌ Unreachable Destinations: {unreachable}")
            self.fail(f"Found unreachable destinations: {unreachable}")
        else:
            print("✅ All destinations are reachable.")

if __name__ == '__main__':
    unittest.main()
