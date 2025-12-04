import sys
import os

# Add parent directory to path to import model
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from model import CityModel, city_map

def full_audit():
    print("Initializing CityModel for Full Audit...")
    model = CityModel()
    print("Model initialized.\n")
    
    print("="*60)
    print("FULL GRAPH AUDIT REPORT")
    print("="*60)
    
    width = model.width
    height = model.height
    
    issues_found = 0
    
    # Iterate over all coordinates
    for x in range(width):
        for y in range(height):
            # Map coordinates: row is inverted relative to y
            row = 23 - y
            col = x
            
            # Boundary check for map access
            if not (0 <= row < len(city_map) and 0 <= col < len(city_map[0])):
                continue
                
            symbol = city_map[row][col]
            
            # Ignore obstacles
            if symbol == '#':
                continue
                
            # It's a traffic element (^, v, <, >, S, D)
            print(f"Coord: ({x}, {y}) | Tipo: {symbol}")
            
            # Check existence in graph
            if (x, y) not in model.G:
                print(f"  [ERROR CRÍTICO] Celda de calle desconectada del grafo.")
                issues_found += 1
                print("-" * 40)
                continue
            
            # Get outgoing connections
            successors = list(model.G.successors((x, y)))
            
            if not successors:
                print(f"  ⚠️ CALLE SIN SALIDA (0 conexiones salientes)")
                issues_found += 1
            
            connections = []
            for nx, ny in successors:
                # Get neighbor symbol
                nrow = 23 - ny
                ncol = nx
                nsymbol = '?'
                if 0 <= nrow < len(city_map) and 0 <= ncol < len(city_map[0]):
                    nsymbol = city_map[nrow][ncol]
                
                weight = model.G.edges[(x, y), (nx, ny)]['weight']
                connections.append(f"({nx}, {ny}) [{nsymbol} | w={weight}]")
            
            if connections:
                print(f"  Conexiones: {', '.join(connections)}")
            
            print("-" * 40)

    print("\n" + "="*60)
    print(f"AUDIT COMPLETE. Issues found: {issues_found}")
    print("="*60)

if __name__ == "__main__":
    full_audit()
