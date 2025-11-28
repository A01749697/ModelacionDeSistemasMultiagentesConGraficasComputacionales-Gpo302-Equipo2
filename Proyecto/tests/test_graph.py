from model import CityModel, TrafficLight
import networkx as nx

def test_graph_logic():
    print("Testing Graph Logic...")
    model = CityModel()
    
    # 1. Check Torus
    if not model.grid.torus:
        print("✅ Torus is False")
    else:
        print("❌ Torus is True (Should be False)")

    # 2. Check Traffic Lights
    lights = [a for a in model.schedule.agents if isinstance(a, TrafficLight)]
    green_lights = len([l for l in lights if l.state == "Green"])
    red_lights = len([l for l in lights if l.state == "Red"])
    
    print(f"Traffic Lights: {len(lights)} total. Green: {green_lights}, Red: {red_lights}")
    if green_lights > 0 and red_lights > 0:
        print("✅ Traffic Lights have mixed states (Phasing works)")
    else:
        print("❌ Traffic Lights are all same state")

    # 3. Check Graph Connectivity
    G = model.G
    
    # Helper to find a cell with specific char
    def find_cell(char):
        from model import city_map
        for r in range(len(city_map)):
            for c in range(len(city_map[r])):
                if city_map[r][c] == char:
                    return c, 23-r
        return None

    # Test specific connections based on map knowledge
    # Row 0: "v<<<<<<<<<<<S<<<<<<<<<<<" (y=23)
    # Col 1: '<' (1, 23)
    # Col 2: '<' (2, 23)
    
    # Test Forward: (2, 23) '<' should connect to (1, 23) '<'
    if G.has_edge((2, 23), (1, 23)):
        print("✅ Forward connection '<' -> '<' exists")
    else:
        print("❌ Forward connection '<' -> '<' MISSING")

    # Test Lane Change:
    # Row 14: "vvS<<<<<vv^^>>>>>>>>>>S^" (y=9)
    # Row 15: "vvS<<<<<vv^^>>>>>>>>>>S^" (y=8)
    # Col 4 is '<' in both.
    # (4, 9) is '<', (4, 8) is '<'.
    # Lane change lateral: '<' at (4, 9) connects to '<' at (4, 8) (Down, dy=-1)
    
    if G.has_edge((4, 9), (4, 8)):
        print("✅ Lane change connection (Side) exists")
    else:
        print("❌ Lane change connection (Side) MISSING")

    # Test Contraflow Prevention
    # Row 0, Col 0 is 'v'. Row 0, Col 1 is '<'.
    # (0, 23) 'v'. (1, 23) '<'.
    # 'v' points down (0, -1). Neighbor '<' is Right (1, 0).
    # Turn: 'v' to '<'.
    # Neighbor '<' direction is (-1, 0).
    # Movement is (1, 0).
    # Contraflow! Should NOT connect.
    
    if not G.has_edge((0, 23), (1, 23)):
        print("✅ Invalid Turn (Contraflow) blocked")
    else:
        print("❌ Invalid Turn (Contraflow) ALLOWED (Bad)")

    print("Graph verification complete.")

if __name__ == "__main__":
    test_graph_logic()
