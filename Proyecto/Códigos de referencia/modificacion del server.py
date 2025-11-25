# visualization_server.py
from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.modules import CanvasGrid, ChartModule, TextElement
from mesa.visualization.UserParam import UserSettableParameter
from model_mesa_example import CityModel  # importa el modelo anterior
import threading, time

class RemainingText(TextElement):
    def render(self, model):
        total = sum(1 for a in model.schedule.agents if type(a).__name__=="Car")
        arrived = sum(1 for a in model.schedule.agents if type(a).__name__=="Car" and getattr(a,"arrived",False))
        return f"Autos: {total}  Llegados: {arrived}"

def portray(agent):
    if agent is None: return
    portrayal = {"Shape":"rect","Filled":"true","Layer":1,"w":1,"h":1}
    t = type(agent).__name__
    if t == "Obstacle":
        portrayal["Color"] = "sienna"
        portrayal["Layer"] = 0
    elif t == "TrafficLight":
        col = "green" if agent.state=="Green" else ("yellow" if agent.state=="Yellow" else "red")
        portrayal["Color"] = col
        portrayal["Layer"] = 2
        portrayal["Shape"] = "circle"
        portrayal["r"] = 0.5
    elif t == "Car":
        portrayal["Color"] = "blue" if not getattr(agent,"arrived",False) else "gray"
        portrayal["Layer"] = 3
        portrayal["text"] = str(getattr(agent,"unique_id", "?"))
        portrayal["text_color"] = "white"
    elif t == "Destination":
        portrayal["Color"] = "lightgreen"
        portrayal["Layer"] = 0
        portrayal["text"] = str(getattr(agent,"parking_number", "?"))
        portrayal["text_color"] = "black"
    return portrayal

grid = CanvasGrid(portray, 24, 24, 600, 600)
chart = ChartModule([{"Label":"Cars Arrived","Color":"Green"}])
remaining = RemainingText()

model_params = {
    # puedes permitir parámetros ajustables en UI si quieres
}

server = ModularServer(CityModel, [grid, remaining, chart], "CityModel Viz", model_params)

# Opcional: auto-run en hilo separado hasta que todos los autos hayan llegado.
AUTO_RUN = True
STEP_INTERVAL = 0.25  # segundos

def auto_runner():
    time.sleep(1.0)  # esperar que server inicie
    m = server.model
    while True:
        if m.all_cars_arrived():
            print("Todos los autos llegaron. Auto-run finalizado.")
            break
        m.step()
        time.sleep(STEP_INTERVAL)

if AUTO_RUN:
    t = threading.Thread(target=auto_runner, daemon=True)
    t.start()

if __name__ == "__main__":
    # Antes de lanzar, puedes spawnear algunos coches de prueba:
    for _ in range(5):
        server.model.spawn_car()
    server.launch()