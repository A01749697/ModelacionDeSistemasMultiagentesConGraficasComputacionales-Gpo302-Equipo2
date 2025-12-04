import sys
import os

# Add parent directory to path to import model
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from model import CityModel

def print_connections(model, x, y):
    """Imprime conexiones para una celda dada."""
    # Validar límites
    if not (0 <= x < model.width and 0 <= y < model.height):
        return

    # Obtener símbolo del mapa
    # city_map[row][col] -> row = 23 - y
    row = 23 - y
    col = x
    
    # Acceso directo a city_map desde el modelo si es posible, o importarlo
    # model.city_map no existe como atributo público directo en __init__ pero está en el módulo
    # Vamos a usar el grid para ver qué hay, o importar city_map del modulo model
    from model import city_map
    symbol = city_map[row][col]
    
    node = (x, y)
    if node in model.G:
        neighbors = list(model.G.successors(node))
        neighbor_info = []
        for nx, ny in neighbors:
            nrow = 23 - ny
            ncol = nx
            nsymbol = city_map[nrow][ncol]
            # Peso
            weight = model.G.edges[node, (nx, ny)]['weight']
            neighbor_info.append(f"({nx},{ny})[{nsymbol}|w={weight}]")
            
        print(f"Celda ({x}, {y}) [Tipo: {symbol}] conecta hacia -> {', '.join(neighbor_info)}")
    else:
        print(f"Celda ({x}, {y}) [Tipo: {symbol}] NO está en el grafo (posible obstáculo o error)")

def main():
    print("Inicializando CityModel...")
    model = CityModel()
    print("Modelo inicializado.\n")
    
    # Rangos solicitados por el usuario
    # (3-4,5-6)
    # (7-8,5-6)
    # (5-6,13-22)
    # (17-18, 3-8)
    # (16-17,13-16)
    # (13,17-18)
    # (22,17-18)
    
    ranges = [
        ({'x': [3, 4], 'y': [5, 6]}),
        ({'x': [7, 8], 'y': [5, 6]}),
        ({'x': [5, 6], 'y': range(13, 23)}), # 13-22 inclusive
        ({'x': [17, 18], 'y': range(3, 9)}), # 3-8 inclusive
        ({'x': [16, 17], 'y': range(13, 17)}), # 13-16 inclusive
        ({'x': [13], 'y': [17, 18]}),
        ({'x': [22], 'y': [17, 18]})
    ]
    
    print("--- AUDITORÍA DE CONEXIONES ---")
    
    visited = set()
    
    for r in ranges:
        xs = r['x']
        ys = r['y']
        
        for x in xs:
            for y in ys:
                if (x, y) not in visited:
                    print_connections(model, x, y)
                    visited.add((x, y))

if __name__ == "__main__":
    main()
