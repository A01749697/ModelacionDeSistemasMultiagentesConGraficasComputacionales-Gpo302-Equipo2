# run_until_done.py
from model_mesa_example import CityModel
import time

m = CityModel()
# spawn un conjunto de autos
for _ in range(10):
    m.spawn_car()
steps = 0
while not m.all_cars_arrived():
    m.step()
    steps += 1
    if steps % 10 == 0:
        remaining = sum(1 for a in m.schedule.agents if type(a).__name__=="Car" and not getattr(a,"arrived",False))
        print(f"Paso {steps}: {remaining} autos restantes")
print(f"Simulación completa en {steps} pasos.")