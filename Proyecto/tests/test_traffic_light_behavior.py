import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mesa import Model
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import networkx as nx
from agents import Car, TrafficLight

def test_traffic_light_crossing():
    print("🚦 INICIANDO TEST DE SEMÁFORO...")
    
    # 1. Crear modelo mínimo SIN llamar a CityModel (para evitar setup_map)
    class MinimalModel(Model):
        def __init__(self):
            super().__init__()
            self.grid = MultiGrid(10, 10, torus=False)
            self.schedule = RandomActivation(self)
            self.G = nx.DiGraph()
            self.destinations = []
    
    model = MinimalModel()
    
    # 2. Construir Escenario: Calle Vertical (Norte-Sur) en Columna 5
    # Coche en (5, 4) -> Semáforo en (5, 5) -> Destino en (5, 6)
    
    # Definir Grafo Manualmente (Aristas con peso 1)
    model.G.add_node((5, 4))
    model.G.add_node((5, 5)) # Intersección
    model.G.add_node((5, 6))
    
    model.G.add_edge((5, 4), (5, 5), weight=1) # Entrada a intersección
    model.G.add_edge((5, 5), (5, 6), weight=1) # Salida de intersección
    
    # 3. Colocar Agentes
    # Semáforo NS en (5, 5) - Estado Inicial ROJO
    tl = TrafficLight(999, model, direction="NS", state="Red")
    model.grid.place_agent(tl, (5, 5))
    model.schedule.add(tl)
    
    # Coche en (5, 4) mirando al norte
    car = Car(1, model)
    car.debug = True # ¡Forzar Debug!
    car.path = [(5, 5), (5, 6)] # Ruta forzada para evitar cálculo A*
    car.state = "DRIVING"  # Forzar estado
    model.grid.place_agent(car, (5, 4))
    model.schedule.add(car)
    
    print(f"Estado Inicial: Coche en {car.pos}, Semáforo en {tl.pos} estado={tl.state}")
    
    # --- PRUEBA 1: SEMÁFORO ROJO ---
    print("\n🛑 STEP 1: Intentar cruzar en ROJO")
    car.step()
    
    if car.pos == (5, 4):
        print("✅ ÉXITO: El coche se detuvo correctamente en Rojo.")
    else:
        print(f"❌ FALLO: El coche se movió a {car.pos} en Rojo.")

    # --- PRUEBA 2: CAMBIO A VERDE ---
    print("\n🟢 STEP 2: Cambiar Semáforo a VERDE y reintentar")
    tl.state = "Green"
    # Reiniciar paciencia del coche por si acaso
    car.patience = 3 
    
    # Verificar lógica can_move_to directamente
    can_move = car.can_move_to((5, 5))
    print(f"DEBUG: car.can_move_to((5,5)) retornó -> {can_move}")
    
    car.step()
    
    if car.pos == (5, 5):
        print("✅ ÉXITO: El coche avanzó a la intersección en Verde.")
    elif car.pos == (5, 4):
        print("❌ FALLO CRÍTICO: El coche sigue atorado en (5,4) aunque hay luz Verde.")
        # Diagnóstico profundo
        if not model.G.has_edge((5,4), (5,5)):
            print("   -> CAUSA: No hay arista en el grafo.")
        else:
            print("   -> CAUSA: Algo en can_move_to bloqueó el paso.")
    
    print("\n" + "="*50)
    print("FIN DEL TEST")

if __name__ == "__main__":
    test_traffic_light_crossing()

