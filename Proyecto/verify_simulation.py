from model import CityModel, Car
import time

def verify_simulation():
    print("Iniciando verificación de simulación...")
    model = CityModel()
    
    initial_cars = len([a for a in model.schedule.agents if isinstance(a, Car)])
    print(f"Carros iniciales: {initial_cars}")
    
    cars_arrived = 0
    cars_removed = 0
    
    # Ejecutar 100 pasos
    for i in range(100):
        model.step()
        
        current_cars = [a for a in model.schedule.agents if isinstance(a, Car)]
        
        # Verificar si algún carro llegó (parking_time > 0)
        for car in current_cars:
            if car.parking_time > 0:
                # print(f"Paso {i}: Carro {car.unique_id} esperando en destino (tiempo: {car.parking_time})")
                pass
                
        # Verificar población
        if i % 10 == 0:
            print(f"Paso {i}: {len(current_cars)} carros activos.")
            
    final_cars = len([a for a in model.schedule.agents if isinstance(a, Car)])
    print(f"Finalizado. Carros finales: {final_cars}")
    
    if final_cars >= 12: # Permitimos 1 de margen
        print("✅ PRUEBA EXITOSA: La población se mantiene estable.")
    else:
        print(f"❌ PRUEBA FALLIDA: La población bajó demasiado ({final_cars}).")

if __name__ == "__main__":
    verify_simulation()
