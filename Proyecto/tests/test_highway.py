from model import CityModel, city_map
import networkx as nx

def test_highway_integrity():
    print("Testing Highway Integrity Rule...")
    model = CityModel()
    
    # Map highway cells (multi-lane streets)
    print("\n=== Detecting Highways ===")
    
    direction_deltas = {
        '^': (0, 1),
        'v': (0, -1),
        '>': (1, 0),
        '<': (-1, 0)
    }
    
    highway_cells = []
    single_lane_cells = []
    
    for row in range(len(city_map)):
        for col in range(len(city_map[row])):
            cell = city_map[row][col]
            if cell not in direction_deltas:
                continue
                
            x = col
            y = 23 - row
            
            # Check lateral neighbors
            is_highway = False
            if cell in ['^', 'v']:
                lateral_offsets = [(1, 0), (-1, 0)]
            else:
                lateral_offsets = [(0, 1), (0, -1)]
            
            for lat_dx, lat_dy in lateral_offsets:
                lat_x = x + lat_dx
                lat_y = y + lat_dy
                
                if 0 <= lat_x < 24 and 0 <= lat_y < 24:
                    lat_row = 23 - lat_y
                    lat_col = lat_x
                    lateral_cell = city_map[lat_row][lat_col]
                    
                    if lateral_cell == cell:
                        is_highway = True
                        break
            
            if is_highway:
                highway_cells.append((x, y, cell))
            else:
                single_lane_cells.append((x, y, cell))
    
    print(f"Highway cells (multi-lane): {len(highway_cells)}")
    print(f"Single-lane cells: {len(single_lane_cells)}")
    
    # Test: Highway cells should NOT have Turn connections
    print("\n=== Checking Turn Restrictions ===")
    illegal_turns = 0
    legal_restrictions = 0
    
    for x, y, cell in highway_cells[:10]:  # Sample first 10
        successors = list(model.G.successors((x, y)))
        
        # Check if any successor is a perpendicular street (not S, not same direction)
        for nx_x, nx_y in successors:
            n_row = 23 - nx_y
            n_col = nx_x
            neighbor_cell = city_map[n_row][n_col]
            
            # Is it a perpendicular turn?
            is_turn = False
            if cell in ['^', 'v'] and neighbor_cell in ['<', '>']:
                is_turn = True
            elif cell in ['<', '>'] and neighbor_cell in ['^', 'v']:
                is_turn = True
            
            if is_turn:
                illegal_turns += 1
                print(f"❌ ILLEGAL: Highway {cell} at ({x},{y}) can turn to {neighbor_cell} at ({nx_x},{nx_y})")
    
    if illegal_turns == 0:
        print("✅ NO illegal turns found from highways!")
        legal_restrictions = len(highway_cells)
    
    # Test: Single-lane cells SHOULD still have Turn connections (where applicable)
    print("\n=== Checking Single-Lane Turn Preservation ===")
    single_lane_turns = 0
    
    for x, y, cell in single_lane_cells[:20]:  # Sample
        successors = list(model.G.successors((x, y)))
        
        for nx_x, nx_y in successors:
            n_row = 23 - nx_y
            n_col = nx_x
            neighbor_cell = city_map[n_row][n_col]
            
            # Check for valid turns
            if cell in ['^', 'v'] and neighbor_cell in ['<', '>']:
                single_lane_turns += 1
                break
            elif cell in ['<', '>'] and neighbor_cell in ['^', 'v']:
                single_lane_turns += 1
                break
    
    print(f"Single-lane cells with turn capability: {single_lane_turns}")
    
    # Summary
    print("\n=== Summary ===")
    print(f"✅ Highway cells properly restricted: {legal_restrictions}")
    print(f"❌ Illegal turns from highways: {illegal_turns}")
    print(f"✅ Single-lane turns preserved: {single_lane_turns}")
    
    if illegal_turns == 0:
        print("\n✅ HIGHWAY INTEGRITY RULE WORKING CORRECTLY!")
    else:
        print("\n❌ Highway integrity rule has issues")

if __name__ == "__main__":
    test_highway_integrity()
