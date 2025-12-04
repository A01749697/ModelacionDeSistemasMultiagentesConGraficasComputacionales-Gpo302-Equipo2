"""
╔═════════════════════════════════════════════════════════════════════════════╗
║                    MODEL.PY - FASE 1: SISTEMA DE SPAWN                     ║
║                                                                             ║
║ Cambios:                                                                    ║
║ 1. Límite estricto de 5 PCs (no más respawn)                              ║
║ 2. Spawn de CC desde túnel (esquina superior derecha: pos ~(22, 22))       ║
║ 3. Rutas de patrullaje predefinidas para cada PC                          ║
║ 4. State codes para Unity (1-7)                                           ║
║ 5. Sincronización de state_code en serialize_grid()                       ║
║                                                                             ║
╚═════════════════════════════════════════════════════════════════════════════╝
"""

from mesa import Model, Agent
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import networkx as nx
import random

# Mapa de la ciudad (24x24 - No toroidal)
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
    "vvS<<<<<v##^<<<<<<<<<<^^",
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
    """Modelo de ciudad con tráfico urbano multiagente."""

    def __init__(self, width=24, height=24, num_cars=20, parking_time=3, num_police=5, num_chaotic=10):
        super().__init__()
        self.width = width
        self.height = height
        self.num_cars = num_cars
        self.num_police = num_police  
        self.num_chaotic = num_chaotic  
        self.parking_time = parking_time
        self.spawn_timer = 0
        self.spawn_interval = 10  
        
        # Limitar a 5 PCs estrictamente
        self.num_police = min(self.num_police, 5)
        
        # Contador para limitar spawns totales de ChaoticCar
        self.chaotic_spawned_count = 0
        self.max_chaotic_total = self.num_chaotic  # Total permitido en toda la sesión
        
        # Scheduler y Grid
        self.schedule = RandomActivation(self)
        self.grid = MultiGrid(width, height, torus=False)
        
        # Grafo de navegación
        self.G = nx.DiGraph()
        self.destinations = []
        
        # Ubicación del túnel (esquina superior derecha aprox.)
        self.tunnel_spawn_point = (22, 22)
        
        # 1. Crear mapa con agentes
        self.setup_map()
        
        # 2. Crear grafo
        self.setup_graph()
        
        # 3. Calcular rutas de patrullaje
        self.police_patrol_routes = self.calculate_patrol_routes()
        
        # 4. Spawnear agentes iniciales
        for i in range(self.num_police):
            self.spawn_police(patrol_id=i)
        
        for _ in range(self.num_chaotic):
            self.spawn_chaotic_from_tunnel()
        
        for _ in range(self.num_cars):
            self.spawn_car(agent_type=Car)
        
        self.running = True

    def calculate_patrol_routes(self):
        """
        Define rutas de patrullaje para los 5 policías.
        Devuelve: Dict[patrol_id] = [checkpoint positions]
        """
        routes = {}
        
        # Ruta 0: Esquina superior izquierda
        routes[0] = [(1, 22), (1, 18), (5, 18), (5, 22)]
        
        # Ruta 1: Esquina superior derecha
        routes[1] = [(22, 22), (22, 18), (18, 18), (18, 22)]
        
        # Ruta 2: Esquina inferior izquierda
        routes[2] = [(1, 2), (1, 6), (5, 6), (5, 2)]
        
        # Ruta 3: Esquina inferior derecha
        routes[3] = [(22, 2), (22, 6), (18, 6), (18, 2)]
        
        # Ruta 4: Centro (patrulla en cruz)
        routes[4] = [(12, 12), (8, 12), (12, 8), (12, 12), (16, 12), (12, 16)]
        
        return routes

    def setup_map(self):
        """Lee city_map y coloca agentes en la grilla."""
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                x = col
                y = 23 - row
                
                if cell == '#':
                    obstacle = Obstacle(self.next_id(), self)
                    self.grid.place_agent(obstacle, (x, y))
                    self.schedule.add(obstacle)
                
                elif cell == 'S':
                    direction = None
                    state = None
                    timer_value = 10
                    
                    # Sincronización por vecindad
                    if col > 0 and city_map[row][col - 1] == 'S':
                        left_x = col - 1
                        left_y = 23 - row
                        left_agents = self.grid.get_cell_list_contents([(left_x, left_y)])
                        for agent in left_agents:
                            if isinstance(agent, TrafficLight):
                                direction = agent.direction
                                state = agent.state
                                timer_value = agent.timer
                                break
                    
                    if direction is None:
                        is_vertical = False
                        is_horizontal = False
                        
                        if row > 0 and city_map[row - 1][col] == 'v':
                            is_vertical = True
                        if row < len(city_map) - 1 and city_map[row + 1][col] == '^':
                            is_vertical = True
                        if col > 0 and city_map[row][col - 1] == '>':
                            is_horizontal = True
                        if col < len(city_map[row]) - 1 and city_map[row][col + 1] == '<':
                            is_horizontal = True
                        
                        if is_vertical:
                            direction = "NS"
                        elif is_horizontal:
                            direction = "EW"
                        else:
                            has_vertical = False
                            has_horizontal = False
                            if row > 0 and city_map[row - 1][col] in ['v', '^', 'S']:
                                has_vertical = True
                            if row < len(city_map) - 1 and city_map[row + 1][col] in ['v', '^', 'S']:
                                has_vertical = True
                            if col > 0 and city_map[row][col - 1] in ['<', '>', 'S']:
                                has_horizontal = True
                            if col < len(city_map[row]) - 1 and city_map[row][col + 1] in ['<', '>', 'S']:
                                has_horizontal = True
                            
                            if has_vertical and not has_horizontal:
                                direction = "NS"
                            elif has_horizontal and not has_vertical:
                                direction = "EW"
                            else:
                                direction = "NS" if (row + col) % 2 == 0 else "EW"
                        
                        if direction == "NS":
                            state = "Green"
                            timer_value = 10
                        else:
                            state = "Red"
                            timer_value = 10
                    
                    traffic_light = TrafficLight(self.next_id(), self, direction, state, 0)
                    traffic_light.timer = timer_value
                    self.grid.place_agent(traffic_light, (x, y))
                    self.schedule.add(traffic_light)
                
                elif cell == 'D':
                    destination = Destination(self.next_id(), self)
                    self.grid.place_agent(destination, (x, y))
                    self.schedule.add(destination)
                    self.destinations.append(destination)

    def setup_graph(self):
        self.G.clear()
        
        # Diccionarios de dirección (No modificar)
        direction_deltas = {
            '^': (0, 1), 'v': (0, -1), '>': (1, 0), '<': (-1, 0)
        }
        neighbor_offsets = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        
        # Contadores para validación en consola
        count_straight = 0
        count_turn = 0
        count_lane_change = 0
        
        for x in range(self.width):
            for y in range(self.height):
                # Obtener símbolo actual (recordar: row = height - 1 - y)
                row = (self.height - 1) - y
                col = x
                cell = city_map[row][col]
                
                if cell == '#':
                    continue
                
                self.G.add_node((x, y))
                
                # Evaluar 4 vecinos
                for dx, dy in neighbor_offsets:
                    nx_x, nx_y = x + dx, y + dy
                    
                    # 1. Validar límites del mapa
                    if not (0 <= nx_x < self.width and 0 <= nx_y < self.height):
                        continue
                        
                    n_row = (self.height - 1) - nx_y
                    n_col = nx_x
                    neighbor_cell = city_map[n_row][n_col]
                    
                    if neighbor_cell == '#':
                        continue
                    
                    # VECTOR DE MOVIMIENTO (Hacia dónde intento ir)
                    move_vec = (dx, dy)
                    
                    # --- LÓGICA DE CONEXIÓN ---
                    
                    # CASO A: De Calle a Calle (^ v < >)
                    if cell in direction_deltas and neighbor_cell in direction_deltas:
                        my_dir = direction_deltas[cell]
                        n_dir = direction_deltas[neighbor_cell]
                        
                        # REGLA 1: Inercia (Seguir recto)
                        # Si me muevo hacia donde apunto Y no es un choque frontal
                        if move_vec == my_dir and n_dir != (-my_dir[0], -my_dir[1]):
                            self.G.add_edge((x, y), (nx_x, nx_y), weight=1)
                            count_straight += 1
                            
                        # REGLA 2: Giro Natural (La "Regla de Oro")
                        # Si la calle destino apunta hacia donde me estoy moviendo.
                        # Esto permite entrar a una calle perpendicular si va en mi sentido.
                        elif n_dir == move_vec:
                            self.G.add_edge((x, y), (nx_x, nx_y), weight=1)
                            count_turn += 1
                            
                        # REGLA 3: Cambio de Carril (Lateral)
                        # Solo si ambos carriles van EXACTAMENTE a la misma dirección
                        elif n_dir == my_dir:
                            self.G.add_edge((x, y), (nx_x, nx_y), weight=3) # Costo mayor
                            count_lane_change += 1
                            
                    # CASO B: Hacia Intersección o Destino (S, D)
                    elif neighbor_cell in ['S', 'D']:
                        # Si vengo de una calle, validar no entrar en reversa pura
                        if cell in direction_deltas:
                            my_dir = direction_deltas[cell]
                            # Producto punto >= 0 (no opuestos)
                            if (my_dir[0] * dx + my_dir[1] * dy) >= 0:
                                self.G.add_edge((x, y), (nx_x, nx_y), weight=1)
                        # Si vengo de otra S/D (dentro de intersección grande), libre movimiento
                        else:
                            self.G.add_edge((x, y), (nx_x, nx_y), weight=1)
                            
                    # CASO C: De Intersección/Destino a Calle (Salida)
                    elif cell in ['S', 'D'] and neighbor_cell in direction_deltas:
                        n_dir = direction_deltas[neighbor_cell]
                        # Permitir entrar a la calle si no es en contraflujo (dot_prod >= 0)
                        # Esto permite incorporarse desde parking o salir de intersección girando
                        dot_prod = move_vec[0] * n_dir[0] + move_vec[1] * n_dir[1]
                        if dot_prod >= 0:
                            self.G.add_edge((x, y), (nx_x, nx_y), weight=1)

        print(f"📊 Grafo Generado: {count_straight} Rectas, {count_turn} Giros, {count_lane_change} Cambios de Carril")
        print(f"✅ Nodos: {self.G.number_of_nodes()}, Aristas: {self.G.number_of_edges()}")

    def get_random_spawn_point(self):
        """Obtiene un punto de spawn aleatorio en cualquier calle válida."""
        valid_positions = []
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                if cell in ['v', '^', '>', '<']:
                    x = col
                    y = 23 - row
                    valid_positions.append((x, y))
        
        if valid_positions:
            return random.choice(valid_positions)
        else:
            return (1, 1)

    def spawn_police(self, patrol_id=0, start_pos=None):
        """Spawnea un policía con ruta de patrullaje."""
        # Contar PCs activos
        current_police = sum(1 for a in self.schedule.agents if isinstance(a, PoliceCar))
        
        if current_police >= self.num_police:
            return  # No más de 5 PCs
        
        if start_pos is None:
            start_pos = self.get_random_spawn_point()
        
        # Obtener checkpoints para este patrol_id
        checkpoints = self.police_patrol_routes.get(patrol_id, [])
        
        police_car = PoliceCar(
            self.next_id(),
            self,
            destination=None,
            parking_limit=self.parking_time,
            patrol_id=patrol_id,
            checkpoints=checkpoints
        )
        
        self.grid.place_agent(police_car, start_pos)
        self.schedule.add(police_car)
        return police_car

    def spawn_chaotic_from_tunnel(self, start_pos=None):
        """Spawnea un ChaoticCar con dispersión para evitar arresto inmediato."""
        # [FINITE POOL] Verificar límite total antes de intentar spawn
        if self.chaotic_spawned_count >= self.max_chaotic_total:
            return None
        
        if start_pos is None:
            # [FIX] Puntos de spawn fijos en esquinas seguras (calles válidas)
            spawn_candidates = [(1, 1), (1, 22), (22, 1), (22, 22)]
            random.shuffle(spawn_candidates)
            
            start_pos = None
            
            # Intentar validar los 4 puntos antes de rendirse
            for pos in spawn_candidates:
                x, y = pos
                
                # 1. Validación de Terreno: No debe ser edificio (#)
                map_row = 23 - y
                map_col = x
                if city_map[map_row][map_col] == '#':
                    continue  # Punto inválido, probar siguiente
                
                # 2. Validación de Proximidad Policial: No policías a distancia < 2
                too_close_to_police = False
                for agent in self.schedule.agents:
                    if isinstance(agent, PoliceCar):
                        police_x, police_y = agent.pos
                        manhattan_dist = abs(x - police_x) + abs(y - police_y)
                        if manhattan_dist < 2:  # [CRITICAL] Radio reducido de 4 a < 2
                            too_close_to_police = True
                            break
                
                if too_close_to_police:
                    continue  # Punto bloqueado por policía, probar siguiente
                
                # Punto válido encontrado
                start_pos = pos
                break
            
            # Si los 4 puntos están bloqueados, abortar spawn en este step
            if start_pos is None:
                return None
        
        # Crear y spawnear el ChaoticCar
        chaotic_car = ChaoticCar(
            self.next_id(),
            self,
            destination=None,
            parking_limit=self.parking_time
        )
        
        self.grid.place_agent(chaotic_car, start_pos)
        self.schedule.add(chaotic_car)
        
        # [FINITE POOL] Incrementar contador de spawns totales
        self.chaotic_spawned_count += 1
        
        return chaotic_car

    def spawn_car(self, start_pos=None, agent_type=Car):
        """Genera un nuevo coche civil."""
        if start_pos is None:
            start_pos = self.get_random_spawn_point()
        
        car = agent_type(
            self.next_id(),
            self,
            destination=None,
            parking_limit=self.parking_time
        )
        
        self.grid.place_agent(car, start_pos)
        self.schedule.add(car)
        return car

    def step(self):
        """Ejecuta un paso de la simulación."""
        self.schedule.step()
        
        # Mantener counts
        current_cars = 0
        current_police = 0
        current_chaotic = 0
        
        for agent in self.schedule.agents:
            if isinstance(agent, PoliceCar):
                current_police += 1
            elif isinstance(agent, ChaoticCar):
                current_chaotic += 1
            elif type(agent) == Car:
                current_cars += 1
        
        # Respawn: Prioridad a Policía (nunca más de 5)
        self.spawn_timer += 1
        if self.spawn_timer >= self.spawn_interval:  # [CAMBIO] Usar variable configurable
            self.spawn_timer = 0
            
            if current_police < self.num_police:
                patrol_id = current_police % 5
                self.spawn_police(patrol_id=patrol_id)
            elif self.chaotic_spawned_count < self.max_chaotic_total:  # [FINITE POOL] Verificar total spawneado
                self.spawn_chaotic_from_tunnel()
            elif current_cars < self.num_cars:
                self.spawn_car(agent_type=Car)

    def serialize_grid(self):
        """Serializa grid para visualización (Unity/WebSocket)."""
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
                    "state_code": 0
                }
                
                # Información específica por tipo
                if isinstance(agent, TrafficLight):
                    agent_data["state"] = agent.state
                    agent_data["direction"] = agent.direction
                
                elif isinstance(agent, Car):
                    agent_data["state"] = agent.state
                    
                    # [NEW] Calculate direction for Unity rotation
                    if agent.last_move:
                        dx, dy = agent.last_move
                        if dx == 1: agent_data["direction"] = "East"
                        elif dx == -1: agent_data["direction"] = "West"
                        elif dy == 1: agent_data["direction"] = "North"
                        elif dy == -1: agent_data["direction"] = "South"
                    else:
                        # First turn, read map
                        map_row = 23 - y
                        map_col = x
                        if 0 <= map_row < len(city_map) and 0 <= map_col < len(city_map[0]):
                            symbol = city_map[map_row][map_col]
                            if symbol == '^': agent_data["direction"] = "North"
                            elif symbol == 'v': agent_data["direction"] = "South"
                            elif symbol == '>': agent_data["direction"] = "East"
                            elif symbol == '<': agent_data["direction"] = "West"
                    
                    # State codes FASE 1
                    if isinstance(agent, ChaoticCar):
                        if agent.state == "ARRESTED":
                            agent_data["state_code"] = 2  # Gris/desapareciendo
                        elif agent.state == "ESCAPING":
                            agent_data["state_code"] = 7  # Rojo
                        elif agent.state == "CHAOS":
                            agent_data["state_code"] = 6  # Morado
                        else:
                            agent_data["state_code"] = 6  # Default CHAOS
                    
                    elif isinstance(agent, PoliceCar):
                        if agent.state == "ARRESTING":
                            agent_data["state_code"] = 5  # Azul intenso
                        elif agent.state == "CHASE":
                            agent_data["state_code"] = 4  # Rojo brillante
                        elif agent.state == "PATROL":
                            agent_data["state_code"] = 3  # Azul oscuro
                        else:
                            agent_data["state_code"] = 3  # Default PATROL
                    
                    else:  # Car civil
                        if agent.state == "DRIVING":
                            agent_data["state_code"] = 0  # Verde
                        elif agent.state == "WANDERING":
                            agent_data["state_code"] = 1  # Amarillo
                        elif agent.state == "CRASHED":
                            agent_data["state_code"] = 2  # Gris
                        elif agent.state == "PARKED":
                            agent_data["state_code"] = 0  # Verde
                        else:
                            agent_data["state_code"] = 0
                
                elif isinstance(agent, Destination):
                    if agent.occupant is not None:
                        agent_data["state"] = "Occupied"
                    elif agent.reserved_by is not None:
                        agent_data["state"] = "Reserved"
                    else:
                        agent_data["state"] = "Free"
                
                data.append(agent_data)
        
        return data
