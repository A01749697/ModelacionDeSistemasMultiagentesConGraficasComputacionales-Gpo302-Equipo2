import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mesa import Model
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import networkx as nx
from agents import Car, Destination

def test_cnp_negotiation():
    print("📢 INICIANDO DIAGNÓSTICO DE PROTOCOLO CONTRACT NET...")
    
    # 1. Crear modelo mínimo
    class MinimalModel(Model):
        def __init__(self):
            super().__init__()
            self.grid = MultiGrid(10, 10, torus=False)
            self.schedule = RandomActivation(self)
            self.G = nx.DiGraph()
            self.destinations = []
    
    model = MinimalModel()
    
    # 2. Configurar Escenario: Coche en (0,0) y Destino en (0,5)
    # Grafo simple lineal: (0,0) -> (0,1) -> ... -> (0,5)
    for y in range(5):
        model.G.add_edge((0, y), (0, y+1), weight=1)
    
    # Destino en (0,5)
    dest = Destination(999, model)
    model.grid.place_agent(dest, (0, 5))
    model.destinations.append(dest)
    
    # Coche en (0,0)
    car = Car(1, model)
    model.grid.place_agent(car, (0, 0))
    
    print(f"Estado Inicial: Coche en {car.pos}, Destino en {dest.pos}")
    print(f"Grafo tiene camino: {nx.has_path(model.G, car.pos, dest.pos)}")
    
    # 3. Ejecutar broadcast_request manualmente y ver logs
    print("\n📡 Ejecutando broadcast_request()...")
    
    # Monkey patch para ver logs internos si no están habilitados
    original_debug = car.debug
    car.debug = True
    
    # Simular lógica de broadcast
    best_bid = float('inf')
    best_dest = None
    
    print(f"   Destinos disponibles: {len(model.destinations)}")
    
    for d in model.destinations:
        bid = d.calculate_bid(car.pos)
        print(f"   📝 Oferta de Destino {d.unique_id} en {d.pos}: {bid}")
        
        if bid < best_bid:
            has_path = nx.has_path(model.G, car.pos, d.pos)
            print(f"      ¿Existe camino en grafo? {has_path}")
            
            if has_path:
                best_bid = bid
                best_dest = d
            else:
                print("      ❌ Descartado: No hay camino")
    
    if best_dest:
        print(f"✅ GANADOR: Destino {best_dest.unique_id} con oferta {best_bid}")
        best_dest.book(car)
        car.destination = best_dest
        car.state = "DRIVING"
        car.calculate_path()
        print(f"   Ruta calculada: {car.path}")
    else:
        print("❌ FALLO: No se encontró destino válido.")

if __name__ == "__main__":
    test_cnp_negotiation()
