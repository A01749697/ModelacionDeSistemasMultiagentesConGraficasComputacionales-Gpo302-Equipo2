import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from model import CityModel
from agents import Car, Destination

def test_negotiation():
    print("--- INICIANDO TEST DE NEGOCIACIÓN (CONTRACT NET) ---")
    
    # 1. Crear modelo con tamaño correcto (24x24) para evitar crash en setup_map
    # Hackeamos los defaults para el test
    model = CityModel(num_cars=0, width=24, height=24) 
    
    # Limpiamos mapa generado y ponemos el nuestro para control total
    for agent in list(model.schedule.agents):
        model.grid.remove_agent(agent)
        model.schedule.remove(agent)
    
    model.destinations = []
    
    # 3. Configurar Escenario
    # Coche en (0,0)
    car = Car(1, model)
    model.grid.place_agent(car, (0, 0))
    model.schedule.add(car)
    
    # Destino A (Lejos) en (10, 0)
    dest_a = Destination(100, model)
    model.grid.place_agent(dest_a, (10, 0))
    model.destinations.append(dest_a)
    
    # Destino B (Cerca) en (2, 0)
    dest_b = Destination(200, model)
    model.grid.place_agent(dest_b, (2, 0))
    model.destinations.append(dest_b)
    
    # CONECTAR GRAFO MANUALMENTE PARA EL TEST
    # (0,0) -> (1,0) -> (2,0) -> ... -> (10,0)
    for x in range(10):
        model.G.add_edge((x, 0), (x+1, 0), weight=1)
    
    print(f"Estado Inicial: Coche en {car.pos}, Destino A{dest_a.pos}, Destino B{dest_b.pos}")
    
    # FORZAR DEBUG
    car.debug = True
    
    # 2. Ejecutar un paso para detonar broadcast_request()
    print("\n>>> Ejecutando Step 1 (Subasta)...")
    car.step()
    
    # VERIFICACIÓN 1: ¿Eligió el destino más cercano (B)?
    if car.destination == dest_b:
        print("✅ ÉXITO: El coche eligió el destino más cercano (B).")
    else:
        print(f"❌ FALLO: El coche eligió {car.destination.unique_id if car.destination else 'Ninguno'} en lugar de B.")

    # VERIFICACIÓN 2: ¿El destino está reservado?
    if dest_b.reserved_by == car:
        print("✅ ÉXITO: El destino B marcó correctamente la reserva.")
    else:
        print("❌ FALLO: El destino B no registró la reserva.")

    # 3. Simular llegada al destino
    print("\n>>> Teletransportando coche al destino y ejecutando Step 2...")
    model.grid.move_agent(car, (2, 0)) # Forzar llegada
    car.step()
    
    # VERIFICACIÓN 3: ¿Cambió a estado PARKED?
    if car.state == "PARKED" and dest_b.occupant == car:
         print("✅ ÉXITO: El coche se estacionó y ocupó el lugar.")
    else:
         print(f"❌ FALLO: Estado coche={car.state}, Ocupante Destino={dest_b.occupant}")

if __name__ == "__main__":
    try:
        test_negotiation()
    except Exception as e:
        print(f"❌ ERROR CRÍTICO EN EL TEST: {e}")
