from mesa import Model, Agent
from mesa.time import RandomActivation
from mesa.space import MultiGrid
import networkx as nx
import random

# Mapa de la ciudad 24x24

city_map = [
    "v<<<<<<<<<<<S<<<<<<<<<<<", 
    "v<<<<<<<<<<<S<<<<<<<<<<^", 
    "vv##vv##vvSS########D#^^",
    "SS#Dvv##vv^^#D########^^",  
    "vvS<<<<<vv^^>>>>>>>>>>S^",  
    "vvS<<<<<vv^^>>>>>>>>>>S^", 
    "vv##^^##vv^^#######D##SS", 
    "SS##^^##vv^^##########^^", 
    "vvS<<<<<<<<<<<<<<<<<<<^^",
    "vvS<<<<<v##^>>>>>>>>>>^^",
    "vv>>>>>>v##^>>>>>>>>>S^^",
    "vv>>>>>>>>>>>>>>>>>>>S^^", 
    "vv#D^^##vv^^####vv####SS", 
    "vv##^^##vv^^####vv####^^", 
    "vv##^^##vv^^##D#vv####^^",
    "vv##^^D#vv^^<<<<vv###D^^",
    "vv>>>>>>vv^^<<<<vv####^^",
    "vv>>>>>>vv^^####vv####^^",
    "vv####D#vv^^D###vv####^^",
    "vv######vv^^####vvD###^^",
    "vv######vv^^####vv####^^",
    "vv##D###SS^^##D#SS####^^",
    "vv>>>>>>S>>>>>>S>>>>>>^^",
    ">>>>>>>>S>>>>>>S>>>>>>^^"   
]

class Car(Agent):
    """Agente que representa un vehículo en la simulación."""
    
    def __init__(self, unique_id, model, destination=None):
        super().__init__(unique_id, model)
        self.destination = destination  # Coordenada (x, y) del destino
        self.path = []  # Lista de coordenadas para seguir
        
    def step(self):
        """Ejecuta un paso de movimiento del vehículo."""
        if not self.path and self.destination:
            # Calcular path usando A* si aún no tenemos uno
            self.calculate_path()
        
        if self.path:
            next_pos = self.path[0]
            # Verificar si la siguiente celda está libre o tiene semáforo
            if self.can_move_to(next_pos):
                self.model.grid.move_agent(self, next_pos)
                self.path.pop(0)
                
                # Si llegamos al destino, remover el coche
                if self.pos == self.destination:
                    self.model.grid.remove_agent(self)
                    self.model.schedule.remove(self)
    
    def calculate_path(self):
        """Calcula el camino más corto usando A* en el grafo de NetworkX."""
        if self.destination and self.pos in self.model.G and self.destination in self.model.G:
            try:
                self.path = nx.shortest_path(self.model.G, self.pos, self.destination)
                self.path.pop(0)  # Remover posición actual
            except nx.NetworkXNoPath:
                self.path = []
    
    def can_move_to(self, pos):
        """Verifica si el coche puede moverse a la posición dada."""
        cell_contents = self.model.grid.get_cell_list_contents([pos])
        
        # No puede moverse si hay otro coche
        for agent in cell_contents:
            if isinstance(agent, Car):
                return False
            
            # Verificar semáforo
            if isinstance(agent, TrafficLight):
                # Determinar dirección del movimiento
                dx = pos[0] - self.pos[0]
                dy = pos[1] - self.pos[1]
                
                # Si el coche se mueve en NS (dy != 0) y el semáforo controla NS
                if dy != 0 and agent.direction == "NS":
                    return agent.state == "Green"
                # Si el coche se mueve en EW (dx != 0) y el semáforo controla EW
                elif dx != 0 and agent.direction == "EW":
                    return agent.state == "Green"
        
        return True


class TrafficLight(Agent):
    """Agente que representa un semáforo con 3 estados: Green, Yellow, Red."""
    
    def __init__(self, unique_id, model, direction="NS"):
        super().__init__(unique_id, model)
        self.state = "Green"  # Estados: "Green", "Yellow", "Red"
        self.timer = 10  # Tiempo en cada estado
        self.direction = direction  # "NS" (Norte-Sur) o "EW" (Este-Oeste)
        
        # Tiempos por estado
        self.green_time = 10
        self.yellow_time = 3
        self.red_time = 10
        
    def step(self):
        """Cambia el estado del semáforo según el timer."""
        self.timer -= 1
        
        if self.timer <= 0:
            # Cambiar de estado cíclicamente
            if self.state == "Green":
                self.state = "Yellow"
                self.timer = self.yellow_time
            elif self.state == "Yellow":
                self.state = "Red"
                self.timer = self.red_time
            elif self.state == "Red":
                self.state = "Green"
                self.timer = self.green_time


class Obstacle(Agent):
    """Agente que representa un edificio u obstáculo estático."""
    
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
    
    def step(self):
        """Los obstáculos no tienen lógica de paso."""
        pass


class Destination(Agent):
    """Agente que representa un destino/estacionamiento."""
    
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
    
    def step(self):
        """Los destinos no tienen lógica de paso."""
        pass


class CityModel(Model):
    """Modelo de la ciudad con tráfico urbano."""
    
    def __init__(self, width=24, height=24):
        super().__init__()
        self.grid = MultiGrid(width, height, torus=False)
        self.schedule = RandomActivation(self)
        self.current_id = 0
        
        # Grafo dirigido para navegación
        self.G = nx.DiGraph()
        
        # Listas para trackear agentes
        self.destinations = []
        
        # Inicializar el mapa
        self.setup_map()
        
        # Crear el grafo de navegación
        self.setup_graph()
    
    def setup_map(self):
        """Lee city_map y coloca los agentes correspondientes en la grilla."""
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                
                # Conversión de coordenadas: (col, 23-row) para invertir Y
                x = col
                y = 23 - row
                
                if cell == '#':
                    # Crear obstáculo
                    obstacle = Obstacle(self.next_id(), self)
                    self.grid.place_agent(obstacle, (x, y))
                    # No agregar obstáculos al scheduler
                    
                elif cell == 'S':
                    # Crear semáforo - determinar dirección según contexto
                    # Por simplicidad, alternar entre NS y EW
                    direction = "NS" if (row + col) % 2 == 0 else "EW"
                    traffic_light = TrafficLight(self.next_id(), self, direction)
                    self.grid.place_agent(traffic_light, (x, y))
                    self.schedule.add(traffic_light)
                    
                elif cell == 'D':
                    # Crear destino
                    destination = Destination(self.next_id(), self)
                    self.grid.place_agent(destination, (x, y))
                    self.destinations.append((x, y))
                    # No agregar destinos al scheduler
    
    def setup_graph(self):
        """Crea un grafo dirigido de NetworkX con las calles."""
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                
                # Conversión de coordenadas
                x = col
                y = 23 - row
                
                # Solo agregar nodos para celdas transitables
                if cell in ['v', '^', '>', '<', 'S', 'D']:
                    self.G.add_node((x, y))
                    
                    # Agregar aristas según la dirección
                    if cell == 'v':  # Sur (Y disminuye)
                        if y > 0:
                            self.G.add_edge((x, y), (x, y - 1))
                    elif cell == '^':  # Norte (Y aumenta)
                        if y < 23:
                            self.G.add_edge((x, y), (x, y + 1))
                    elif cell == '>':  # Este (X aumenta)
                        if x < 23:
                            self.G.add_edge((x, y), (x + 1, y))
                    elif cell == '<':  # Oeste (X disminuye)
                        if x > 0:
                            self.G.add_edge((x, y), (x - 1, y))
                    elif cell == 'S':
                        # Semáforos conectan en todas direcciones
                        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                            nx_pos = (x + dx, y + dy)
                            if 0 <= nx_pos[0] < 24 and 0 <= nx_pos[1] < 24:
                                self.G.add_edge((x, y), nx_pos)
                    elif cell == 'D':
                        # Destinos conectan como nodos finales
                        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                            nx_pos = (x + dx, y + dy)
                            if 0 <= nx_pos[0] < 24 and 0 <= nx_pos[1] < 24:
                                self.G.add_edge((x, y), nx_pos)
    
    def spawn_car(self, start_pos=None, destination=None):
        """Genera un nuevo coche en la simulación."""
        if start_pos is None:
            # Buscar una posición válida en el borde
            start_pos = self.get_random_spawn_point()
        
        if destination is None and self.destinations:
            # Elegir destino aleatorio
            destination = random.choice(self.destinations)
        
        car = Car(self.next_id(), self, destination)
        self.grid.place_agent(car, start_pos)
        self.schedule.add(car)
        return car
    
    def get_random_spawn_point(self):
        """Obtiene un punto de spawn aleatorio en las calles."""
        valid_positions = []
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                if cell in ['v', '^', '>', '<']:
                    x = col
                    y = 23 - row
                    valid_positions.append((x, y))
        
        return random.choice(valid_positions) if valid_positions else (1, 1)
    
    def next_id(self):
        """Genera un ID único para un agente."""
        self.current_id += 1
        return self.current_id
    
    def step(self):
        """Ejecuta un paso de la simulación."""
        self.schedule.step()
    
    def serialize_grid(self):
        """Serializa el grid para Unity con información detallada."""
        data = []
        for cell_content, (x, y) in self.grid.coord_iter():
            for agent in cell_content:
                agent_data = {
                    "id": agent.unique_id,
                    "x": x,
                    "y": y,
                    "agent_type": type(agent).__name__,
                    "state": None,
                    "direction": None
                }
                
                # Agregar información específica por tipo
                if isinstance(agent, TrafficLight):
                    agent_data["state"] = agent.state
                    agent_data["direction"] = agent.direction
                elif isinstance(agent, Car):
                    agent_data["state"] = "Moving"
                
                data.append(agent_data)
        
        return data