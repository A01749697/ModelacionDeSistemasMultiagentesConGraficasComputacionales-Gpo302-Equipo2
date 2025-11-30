from mesa.visualization.modules import CanvasGrid, TextElement
from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.UserParam import Slider

from model import CityModel
from agents import Car, TrafficLight, Obstacle, Destination, ChaoticCar, PoliceCar

class Legend(TextElement):
    def render(self, model):
        return """
        <div style="color:black;background-color:white;padding:5px;border:1px solid black;margin-bottom:10px;">
        <b>LEYENDA:</b><br>
        🚙 Normal: 🔵 Viajando | 🟠 Buscando | ⚪ Chocado<br>
        😈 Caótico: 🟣 (Ignora semáforos)<br>
        🚓 Policía: ⚫ Patrullando | 🔴🔵 Persecución (Sirena)<br>
        🅿️ Parking: 🟢 Libre | 🟡 Reservado | 🔴 Ocupado
        </div>
        """

def agent_portrayal(agent):
    """
    Define cómo se visualiza cada agente en la interfaz web.
    """
    if agent is None:
        return
    
    portrayal = {
        "Shape": "circle",
        "Filled": "true",
        "Layer": 0,
        "w": 1,
        "h": 1
    }

    if isinstance(agent, Car):
        portrayal["Shape"] = "circle"
        portrayal["r"] = 0.5
        portrayal["Layer"] = 1
        portrayal["text"] = str(agent.unique_id)
        portrayal["text_color"] = "white"

        # Colores dinámicos para Car
        if isinstance(agent, ChaoticCar):
            if agent.state == "CRASHED":
                portrayal["Color"] = "black"
            else:
                portrayal["Color"] = "purple"
        elif isinstance(agent, PoliceCar):
            if agent.state == "CHASE":
                # Efecto Sirena: Parpadeo Rojo/Azul
                portrayal["Color"] = "red" if agent.model.schedule.steps % 2 == 0 else "blue"
            else:
                portrayal["Color"] = "black" # Patrulla discreta
        else: # Car normal
            if agent.state == "DRIVING":
                portrayal["Color"] = "blue"
            elif agent.state == "WANDERING":
                portrayal["Color"] = "orange"
            elif agent.state == "CRASHED":
                portrayal["Color"] = "grey"
            else:
                portrayal["Color"] = "blue"

    elif isinstance(agent, TrafficLight):
        portrayal["Shape"] = "circle"
        portrayal["Color"] = "green" if agent.state == "Green" else ("yellow" if agent.state == "Yellow" else "red")
        portrayal["r"] = 0.5
        portrayal["Layer"] = 1
        portrayal["text"] = agent.direction
        portrayal["text_color"] = "black"

    elif isinstance(agent, Obstacle):
        portrayal["Shape"] = "rect"
        portrayal["Color"] = "grey"
        portrayal["w"] = 1
        portrayal["h"] = 1
        portrayal["Layer"] = 0

    elif isinstance(agent, Destination):
        portrayal["Shape"] = "rect"
        portrayal["w"] = 1
        portrayal["h"] = 1
        portrayal["Layer"] = 0
        
        if agent.occupant is not None:
            portrayal["Color"] = "red"
        elif agent.reserved_by is not None:
            portrayal["Color"] = "yellow"
        else:
            portrayal["Color"] = "green"
        
    return portrayal

# Configuración del grid
# El mapa es de 24x24
width = 24
height = 24
pixel_ratio = 20  # Pixeles por celda
grid = CanvasGrid(agent_portrayal, width, height, width * pixel_ratio, height * pixel_ratio)
legend = Legend()

# Configuración del servidor
server = ModularServer(
    CityModel,
    [grid, legend],
    "Traffic Simulation",
    {
        "width": width, 
        "height": height,
        "num_cars": Slider("Number of Cars", 13, 1, 30, 1),
        "num_police": Slider("Number of Police", 2, 0, 10, 1),
        "num_chaotic": Slider("Number of Chaotic", 2, 0, 10, 1),
        "parking_time": Slider("Parking Time", 3, 1, 20, 1)
    }
)

server.port = 8521 # Puerto por defecto

if __name__ == "__main__":
    server.launch()
