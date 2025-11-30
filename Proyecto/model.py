from mesa import Model, Agent
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import networkx as nx
import random

# Ciudad Mapeada 24x24 (Racoon City)

city_map = [
    "v<<<<<<<<<<<S<<<<<<<<<<<", 
    "v<<<<<<<<<<<S<<<<<<<<<<^", 
    "vv##vv##vvSS########D#^^",
    "SS#Dvv##vv^^#D########^^",  
    "vvS<<<<<vv^^>>>>>>>>>S^^",  
    "vvS<<<<<vv^^>>>>>>>>>S^^", 
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
    "vv>>>>>S>>>>>>>S>>>>>>^^",
    ">>>>>>>S>>>>>>>S>>>>>>^^"   
]

from agents import Car, TrafficLight, Obstacle, Destination, ChaoticCar, PoliceCar


class CityModel(Model):
    """Modelo de la ciudad con tráfico urbano."""
    
    def __init__(self, width=24, height=24, num_cars=10, parking_time=3, num_police=2, num_chaotic=2):
        super().__init__()
        self.width = width
        self.height = height
        self.num_cars = num_cars
        self.num_police = num_police
        self.num_chaotic = num_chaotic
        self.parking_time = parking_time
        self.spawn_timer = 0
        
        self.schedule = RandomActivation(self)
        self.grid = MultiGrid(width, height, torus=False)
        self.G = nx.DiGraph()
        self.destinations = []
        
        # 1. Crear el mapa y el grafo
        self.setup_map()
        self.setup_graph()
        
        # 2. Spawnear agentes iniciales
        # Primero Policías
        for _ in range(self.num_police):
            self.spawn_car(agent_type=PoliceCar)
            
        # Luego Caóticos
        for _ in range(self.num_chaotic):
            self.spawn_car(agent_type=ChaoticCar)
            
        # Finalmente Coches Normales
        for _ in range(self.num_cars):
            self.spawn_car(agent_type=Car)
            
        self.running = True # Required for Mesa visualization
    
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
                    self.schedule.add(obstacle)
                    
                elif cell == 'S':
                    # Crear semáforo con Sincronización por Vecindad
                    
                    direction = None
                    state = None
                    timer_value = 10
                    
                    # 1. Chequeo de Grupo (Sync): Verificar si hay semáforo a la IZQUIERDA
                    if col > 0 and city_map[row][col-1] == 'S':
                        # Buscar el agente TrafficLight en la posición izquierda
                        left_x = col - 1
                        left_y = 23 - row
                        left_agents = self.grid.get_cell_list_contents([(left_x, left_y)])
                        
                        for agent in left_agents:
                            if isinstance(agent, TrafficLight):
                                # Copiar atributos del semáforo vecino (Sincronización)
                                direction = agent.direction
                                state = agent.state
                                timer_value = agent.timer
                                break
                    
                    # 2. Si no hay vecino 'S' a la izquierda (Es un Líder)
                    if direction is None:
                        # Determinar dirección mirando el flujo de la calle
                        is_vertical = False
                        is_horizontal = False
                        
                        # Checar flujo vertical (v arriba o ^ abajo)
                        if row > 0 and city_map[row-1][col] == 'v': is_vertical = True
                        if row < len(city_map)-1 and city_map[row+1][col] == '^': is_vertical = True
                        
                        # Checar flujo horizontal (> izquierda o < derecha)
                        if col > 0 and city_map[row][col-1] == '>': is_horizontal = True
                        if col < len(city_map[row])-1 and city_map[row][col+1] == '<': is_horizontal = True
                        
                        # Determinar dirección basado en flujo detectado
                        if is_vertical:
                            direction = "NS"
                        elif is_horizontal:
                            direction = "EW"
                        else:
                            # Fallback: usar heurística original si no se detecta flujo claro
                            has_vertical = False
                            has_horizontal = False
                            
                            if row > 0 and city_map[row-1][col] in ['v', '^', 'S']: has_vertical = True
                            if row < len(city_map)-1 and city_map[row+1][col] in ['v', '^', 'S']: has_vertical = True
                            
                            if col > 0 and city_map[row][col-1] in ['<', '>', 'S']: has_horizontal = True
                            if col < len(city_map[row])-1 and city_map[row][col+1] in ['<', '>', 'S']: has_horizontal = True
                            
                            if has_vertical and not has_horizontal:
                                direction = "NS"
                            elif has_horizontal and not has_vertical:
                                direction = "EW"
                            else:
                                # Intersección: Alternar
                                direction = "NS" if (row + col) % 2 == 0 else "EW"
                        
                        # Establecer estado inicial basado en Exclusión Mutua
                        if direction == "NS":
                            state = "Green"
                            timer_value = 10
                        else:  # "EW"
                            state = "Red"
                            timer_value = 10  # Desfasado
                    
                    # Crear el semáforo con los atributos determinados/copiados
                    traffic_light = TrafficLight(self.next_id(), self, direction, state, 0)
                    traffic_light.timer = timer_value  # Asignar timer después de creación
                    self.grid.place_agent(traffic_light, (x, y))
                    self.schedule.add(traffic_light)
                    
                elif cell == 'D':
                    # Crear destino
                    destination = Destination(self.next_id(), self)
                    self.grid.place_agent(destination, (x, y))
                    self.schedule.add(destination)
                    self.destinations.append(destination) # Guardar agente, no pos
    
    def setup_graph(self):
        """Crea un grafo dirigido estricto basado en las flechas y reglas de tránsito."""
        self.G.clear()
        
        w = self.grid.width
        h = self.grid.height
        
        # Mapeo de direcciones a deltas (dx, dy)
        direction_deltas = {
            '^': (0, 1),
            'v': (0, -1),
            '>': (1, 0),
            '<': (-1, 0)
        }
        
        neighbor_offsets = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                x = col
                y = 23 - row
                
                if cell == '#':
                    continue
                
                self.G.add_node((x, y))
                
                # REGLA DE INTEGRIDAD DE AUTOPISTA
                # 1. Identificar si la celda actual es parte de una vía multicarril
                is_highway = False
                if cell in direction_deltas:
                    # Determinar vecinos laterales según dirección
                    if cell in ['^', 'v']:  # Vertical: laterales son izquierda/derecha
                        lateral_offsets = [(1, 0), (-1, 0)]
                    else:  # Horizontal '<', '>': laterales son arriba/abajo
                        lateral_offsets = [(0, 1), (0, -1)]
                    
                    # Verificar si algún lateral tiene la misma dirección
                    for lat_dx, lat_dy in lateral_offsets:
                        lat_x = x + lat_dx
                        lat_y = y + lat_dy
                        
                        if 0 <= lat_x < w and 0 <= lat_y < h:
                            lat_row = 23 - lat_y
                            lat_col = lat_x
                            lateral_cell = city_map[lat_row][lat_col]
                            
                            if lateral_cell == cell:  # Misma dirección = Highway
                                is_highway = True
                                break
                
                for dx, dy in neighbor_offsets:
                    nx_x = x + dx
                    nx_y = y + dy
                    
                    if not (0 <= nx_x < w and 0 <= nx_y < h):
                        continue
                        
                    n_row = 23 - nx_y
                    n_col = nx_x
                    neighbor_cell = city_map[n_row][n_col]
                    
                    if neighbor_cell == '#':
                        continue
                        
                    can_connect = False
                    reason = ""
                    
                    # A. Conexión Frontal
                    if cell in direction_deltas:
                        expected_dx, expected_dy = direction_deltas[cell]
                        if (dx, dy) == (expected_dx, expected_dy):
                            is_contraflow = False
                            if cell == '^' and neighbor_cell == 'v': is_contraflow = True
                            if cell == 'v' and neighbor_cell == '^': is_contraflow = True
                            if cell == '>' and neighbor_cell == '<': is_contraflow = True
                            if cell == '<' and neighbor_cell == '>': is_contraflow = True
                            
                            if not is_contraflow:
                                can_connect = True
                                reason = "Forward"
                    
                    # B. Cambio de Carril
                    if cell in ['^', 'v', '<', '>'] and neighbor_cell == cell:
                        my_dir = direction_deltas[cell]
                        if my_dir[0]*dx + my_dir[1]*dy == 0:
                            can_connect = True
                            reason = "LaneChange"
                            
                    # C. Giros
                    if cell in direction_deltas and neighbor_cell in direction_deltas:
                        if cell in ['^', 'v'] and neighbor_cell in ['<', '>']:
                            n_dir = direction_deltas[neighbor_cell]
                            if (dx, dy) == n_dir:
                                can_connect = True
                                reason = "Turn"
                        elif cell in ['<', '>'] and neighbor_cell in ['^', 'v']:
                            n_dir = direction_deltas[neighbor_cell]
                            if (dx, dy) == n_dir:
                                can_connect = True
                                reason = "Turn"

                    # D. Intersecciones
                    if neighbor_cell in ['S', 'D']:
                        can_connect = True
                        reason = "ToIntersection"
                        
                    if cell in ['S', 'D']:
                        if neighbor_cell in direction_deltas:
                            n_dir = direction_deltas[neighbor_cell]
                            if (dx, dy) == n_dir:
                                can_connect = True
                                reason = "FromIntersection"
                        elif neighbor_cell in ['S', 'D']:
                            can_connect = True
                            reason = "IntersectionLink"
                    
                    # 2. APLICAR RESTRICCIÓN DE AUTOPISTA
                    # Bloquear giros ilegales desde highways
                    if is_highway and reason == "Turn":
                        can_connect = False

                    if can_connect:
                        # SISTEMA DE PESOS: Asignar costo según tipo de movimiento
                        weight = 1  # Default
                        
                        if reason == "Forward":
                            weight = 1  # Preferencia máxima
                        elif reason == "Turn":
                            weight = 2  # Penalización moderada
                        elif reason == "LaneChange":
                            weight = 5  # Penalización alta (evita zig-zag)
                        elif reason in ["ToIntersection", "FromIntersection", "IntersectionLink"]:
                            weight = 1  # Sin penalización
                        
                        # PROTECCIÓN DE ESTACIONAMIENTOS: Si el destino es 'D', peso altísimo
                        if neighbor_cell == 'D':
                            weight = 100  # Evita usar parkings como atajos
                        
                        self.G.add_edge((x, y), (nx_x, nx_y), weight=weight)
    
    def spawn_car(self, start_pos=None, agent_type=Car):
        """Genera un nuevo coche en la simulación."""
        if start_pos is None:
            start_pos = self.get_random_spawn_point()
        
        # Crear coche SIN destino inicial (lo buscará él mismo)
        # Nota: PoliceCar y ChaoticCar heredan de Car, así que esto funciona
        car = agent_type(self.next_id(), self, destination=None, parking_limit=self.parking_time)
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
    
    def step(self):
        """Ejecuta un paso de la simulación."""
        self.schedule.step()
        
        # Dinámica de Población: Mantener counts de cada tipo
        # Contar agentes actuales
        current_cars = 0
        current_police = 0
        current_chaotic = 0
        
        for agent in self.schedule.agents:
            if isinstance(agent, PoliceCar):
                current_police += 1
            elif isinstance(agent, ChaoticCar):
                current_chaotic += 1
            elif isinstance(agent, Car): # Car normal (excluyendo subclases si isinstance checkea herencia)
                # Ojo: isinstance(PoliceCar(), Car) es True.
                # Necesitamos checar tipo exacto para 'Car' normal
                if type(agent) == Car:
                    current_cars += 1
        
        self.spawn_timer += 1
        if self.spawn_timer >= 2: # Intentar cada 2 ticks
            self.spawn_timer = 0
            
            # Prioridad de respawn: Policía > Caótico > Normal
            if current_police < self.num_police:
                self.spawn_car(agent_type=PoliceCar)
            elif current_chaotic < self.num_chaotic:
                self.spawn_car(agent_type=ChaoticCar)
            elif current_cars < self.num_cars:
                self.spawn_car(agent_type=Car)
        
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
                    "direction": None,
                    "state_code": 0 # Default state code
                }
                
                # Agregar información específica por tipo
                if isinstance(agent, TrafficLight):
                    agent_data["state"] = agent.state
                    agent_data["direction"] = agent.direction
                elif isinstance(agent, Car):
                    agent_data["state"] = agent.state
                    # Asignar códigos de estado para Unity
                    if isinstance(agent, ChaoticCar):
                         agent_data["state_code"] = 2 if agent.state == "CRASHED" else 0 # 0=Normal/Chaos, 2=Crashed
                    elif isinstance(agent, PoliceCar):
                         if agent.state == "PATROL": agent_data["state_code"] = 3
                         elif agent.state == "CHASE": agent_data["state_code"] = 4
                    else:
                         if agent.state == "DRIVING": agent_data["state_code"] = 0
                         elif agent.state == "WANDERING": agent_data["state_code"] = 1
                         elif agent.state == "CRASHED": agent_data["state_code"] = 2

                elif isinstance(agent, Destination):
                    if agent.occupant is not None:
                        agent_data["state"] = "Occupied"
                    elif agent.reserved_by is not None:
                        agent_data["state"] = "Reserved"
                    else:
                        agent_data["state"] = "Free"
                
                data.append(agent_data)
        
        return data
