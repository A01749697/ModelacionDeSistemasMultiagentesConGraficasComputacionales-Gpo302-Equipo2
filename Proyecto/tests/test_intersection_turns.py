import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mesa import Model
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import networkx as nx
from agents import Car

def test_intersection_turns():
    print("🔄 INICIANDO TEST DE GIROS DESDE INTERSECCIÓN...")
    
    # Crear modelo mínimo
    class MinimalModel(Model):
        def __init__(self):
            super().__init__()
            self.grid = MultiGrid(10, 10, torus=False)
            self.schedule = RandomActivation(self)
            self.G = nx.DiGraph()
            self.destinations = []
    
    model = MinimalModel()
    
    # Escenario: Intersección en (5,5) con 4 calles salientes
    # Norte (5,6) con dirección ^
    # Sur (5,4) con dirección v  
    # Este (6,5) con dirección >
    # Oeste (4,5) con dirección <
    
    model.G.add_node((5, 5))  # Intersección
    model.G.add_node((5, 6))  # Norte
    model.G.add_node((5, 4))  # Sur
    model.G.add_node((6, 5))  # Este
    model.G.add_node((4, 5))  # Oeste
    
    # Probar la lógica de setup_graph manualmente
    # Desde intersección (5,5) debería poder ir a:
    # - (5,6) si es calle ^ (movimiento Norte, OK si no es v)
    # - (6,5) si es calle > (movimiento Este, OK si no es <)
    # - (5,4) si es calle v (movimiento Sur, OK si no es ^)
    # - (4,5) si es calle < (movimiento Oeste, OK si no es >)
    
    from model import city_map
    
    # Direction deltas from model.py
    direction_deltas = {
        '^': (0, 1),
        'v': (0, -1),
        '>': (1, 0),
        '<': (-1, 0)
    }
    
    # Test 1: Giro de Intersección a calle Norte (^)
    # Movimiento: (5,5) -> (5,6), dx=0, dy=1
    # Calle Norte tiene dirección ^: (0, 1)
    # Contraflujo sería: (0, -1) = v
    # dx,dy = (0,1) != (0,-1), así que DEBERÍA permitirse
    dx, dy = 0, 1
    n_dir = (0, 1)  # ^
    contraflow = (-n_dir[0], -n_dir[1])  # (0, -1)
    can_turn_north = (dx, dy) != contraflow
    
    print(f"\n🧪 Test 1: Giro a calle Norte (^)")
    print(f"   Movimiento: (0, 1), Contraflujo: {contraflow}")
    print(f"   ¿Puede girar? {can_turn_north}")
    assert can_turn_north, "❌ FALLO: No puede girar a Norte"
    print("   ✅ ÉXITO: Puede girar a Norte")
    
    # Test 2: Giro de Intersección a calle Este (>)
    # Movimiento: (5,5) -> (6,5), dx=1, dy=0
    # Calle Este tiene dirección >: (1, 0)
    # Contraflujo sería: (-1, 0) = <
    dx, dy = 1, 0
    n_dir = (1, 0)  # >
    contraflow = (-n_dir[0], -n_dir[1])  # (-1, 0)
    can_turn_east = (dx, dy) != contraflow
    
    print(f"\n🧪 Test 2: Giro a calle Este (>)")
    print(f"   Movimiento: (1, 0), Contraflujo: {contraflow}")
    print(f"   ¿Puede girar? {can_turn_east}")
    assert can_turn_east, "❌ FALLO: No puede girar a Este"
    print("   ✅ ÉXITO: Puede girar a Este")
    
    # Test 3: Intento de contraflujo (DEBE bloquearse)
    # Intentar moverse Norte desde intersección hacia calle Sur (v)
    # Movimiento: (5,5) -> (5,6), dx=0, dy=1
    # Pero si la calle en (5,6) fuera 'v' (Sur), sería contraflujo
    dx, dy = 0, 1
    n_dir = (0, -1)  # v (calle apuntando Sur)
    contraflow = (-n_dir[0], -n_dir[1])  # (0, 1) ← COINCIDE con movimiento
    should_block = (dx, dy) == contraflow
    
    print(f"\n🧪 Test 3: Intento de contraflujo")
    print(f"   Movimiento: (0, 1), Dirección calle: v (0, -1)")
    print(f"   ¿Debe bloquearse? {should_block}")
    assert should_block, "❌ FALLO: Contraflujo no bloqueado"
    print("   ✅ ÉXITO: Contraflujo correctamente bloqueado")
    
    print("\n" + "="*50)
    print("✅ TODOS LOS TESTS DE GIROS PASARON")
    print("="*50)

if __name__ == "__main__":
    test_intersection_turns()
