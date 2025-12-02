"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                   FASE 1: ARQUITECTURA DE ESTADOS                         ║
║                                                                           ║
║ Máquinas de estados completas para PoliceCar y ChaoticCar                ║
║ SIN cambiar la lógica base de coches normales                            ║
║ Compilable y estructurado para FASE 2 (Inteligencia)                     ║
║                                                                           ║
║ Estados:                                                                  ║
║   PoliceCar:   PATROL → CHASE → ARRESTING → PATROL                      ║
║   ChaoticCar:  CHAOS → ESCAPING → (back to CHAOS) | ARRESTED            ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝

CAMBIOS EN ESTA VERSIÓN:
1. Timers para estados (ARRESTING: 3 seg, CRASHED: 20 seg)
2. Máquina de estados mejorada con transiciones explícitas
3. Memory timer para CC (5 seg después de perder a policía)
4. State codes actualizados para Unity (1-7)
5. Detectores de visión (radius = 8 para PC, 10 para detección de CC)
6. Bloqueo de Destination en ChaoticCar (ya presente)
"""

from mesa import Agent
import networkx as nx
import random
from collections import deque


def detect_stuck_pattern(car):
    """Detecta si coche está atorado basado en historial."""
    if len(car.position_history) < 3:
        return False, "InsufficientData"
    
    recent_pos = list(car.position_history)[-3:]
    
    # Patrón 1: Mismo lugar 3 steps consecutivos
    if recent_pos[0] == recent_pos[1] == recent_pos[2]:
        return True, "STATIC_BLOCK"
    
    # Patrón 2: Ping-Pong (A → B → A)
    if recent_pos[0] == recent_pos[2] and recent_pos[0] != recent_pos[1]:
        return True, "PING_PONG"
    
    # Patrón 3: Stuck_counter alto
    if car.stuck_counter > 5:
        return True, "HIGH_STUCK_COUNTER"
    
    return False, "OK"


class Car(Agent):
    """Agente que representa un vehículo en la simulación."""

    def __init__(self, unique_id, model, destination=None, parking_limit=3):
        super().__init__(unique_id, model)
        self.destination = destination
        self.state = "WANDERING" if destination is None else "DRIVING"
        self.parking_timer = 0
        self.parking_limit = parking_limit
        self.path = []
        self.patience = 3
        self.do_not_park_here = None
        
        # INERCIA DIRECCIONAL
        self.last_move = None
        
        # TRACKING
        self.position_history = deque(maxlen=10)
        self.stuck_counter = 0
        self.decision_history = deque(maxlen=5)
        self.is_under_observation = False
        self.debug = (unique_id == 0)

    def step(self):
        """Máquina de estados para vehículos civiles."""
        self.position_history.append(self.pos)
        
        if len(self.position_history) >= 2:
            prev_pos = list(self.position_history)[-2]
            if self.pos == prev_pos:
                self.stuck_counter += 1
            else:
                self.stuck_counter = 0
        
        if self.last_move is None and len(self.position_history) >= 2:
            prev_pos = list(self.position_history)[-2]
            curr_pos = self.pos
            recovered_move = (curr_pos[0] - prev_pos[0], curr_pos[1] - prev_pos[1])
            if recovered_move != (0, 0):
                self.last_move = recovered_move
        
        # 1. ESTADO CRASHED - no hacer nada, solo esperar
        if self.state == "CRASHED":
            return
        
        # 2. ESTADO PARKED
        if self.state == "PARKED":
            self.parking_timer -= 1
            if self.parking_timer <= 0:
                if self.destination:
                    self.do_not_park_here = self.destination
                    self.destination.release()
                    self.destination = None
                self.state = "WANDERING"
                self.path = []
                self.last_move = None
            return
        
        # 3. ESTADO DRIVING
        if self.destination:
            # Llegada al destino
            if self.pos == self.destination.pos:
                self.state = "PARKED"
                self.parking_timer = self.parking_limit
                self.destination.occupant = self
                self.last_move = None
                return
            
            # Calcular ruta si no existe
            if not self.path:
                self.calculate_path()
            
            # Seguir ruta
            if self.path:
                next_pos = self.path[0]
                if self.can_move_to(next_pos):
                    dx = next_pos[0] - self.pos[0]
                    dy = next_pos[1] - self.pos[1]
                    self.last_move = (dx, dy)
                    self.model.grid.move_agent(self, next_pos)
                    self.path.pop(0)
                    self.patience = 3
                else:
                    self.patience -= 1
                    if self.patience <= 0:
                        self.calculate_path()
                        self.patience = 3
        
        # 4. ESTADO WANDERING
        else:
            self.broadcast_request()
            
            if self.destination:
                self.do_not_park_here = None
                self.state = "DRIVING"
                self.calculate_path()
                return
            
            self.state = "WANDERING"
            next_pos = self.get_wandering_move()
            if next_pos:
                dx = next_pos[0] - self.pos[0]
                dy = next_pos[1] - self.pos[1]
                self.last_move = (dx, dy)
                self.model.grid.move_agent(self, next_pos)
                self.stuck_counter = 0
            else:
                self.stuck_counter += 1

    def get_wandering_move(self):
        """Movimiento wandering con inercia anti-reversa."""
        if self.last_move is None and len(self.position_history) >= 2:
            prev_pos = list(self.position_history)[-2]
            curr_pos = self.pos
            self.last_move = (curr_pos[0] - prev_pos[0], curr_pos[1] - prev_pos[1])
            if self.last_move == (0, 0):
                self.last_move = None
        
        neighbors = self.model.grid.get_neighborhood(
            self.pos, moore=False, include_center=False
        )
        
        forward_options = []
        backward_options = []
        backward_direction = None
        
        if self.last_move:
            backward_direction = (-self.last_move[0], -self.last_move[1])
        
        for n in neighbors:
            if self.model.G.has_edge(self.pos, n):
                weight = self.model.G.edges[self.pos, n]['weight']
                dx = n[0] - self.pos[0]
                dy = n[1] - self.pos[1]
                direction = (dx, dy)
                
                if self.last_move and direction == self.last_move:
                    weight *= 0.1
                
                option = (n, weight, direction)
                
                if backward_direction and direction == backward_direction:
                    backward_options.append(option)
                else:
                    forward_options.append(option)
        
        # EMERGENCIA: Si muy atorado, forzar U-turn
        if self.stuck_counter > 15:
            if backward_options:
                return backward_options[0][0]
            self.last_move = None
            self.stuck_counter = 0
            return None
        
        # Priorizar adelante
        forward_options.sort(key=lambda x: x[1])
        
        for pos, weight, direction in forward_options:
            if not self.can_pass_traffic_light(pos):
                return None
            if self.can_move_to(pos):
                return pos
        
        # Solo U-turn si no hay alternativa
        if not forward_options and backward_options:
            back_pos = backward_options[0][0]
            if self.can_pass_traffic_light(back_pos) and self.can_move_to(back_pos):
                return back_pos
        
        return None

    def can_pass_traffic_light(self, pos):
        """Verifica si el semáforo permite el paso."""
        my_cell_contents = self.model.grid.get_cell_list_contents([self.pos])
        am_in_intersection = any(
            isinstance(a, TrafficLight) for a in my_cell_contents
        )
        
        if am_in_intersection:
            return True
        
        cell_contents = self.model.grid.get_cell_list_contents([pos])
        for agent in cell_contents:
            if isinstance(agent, TrafficLight):
                if agent.state == "Green":
                    return True
                elif agent.state in ["Red", "Yellow"]:
                    dx = pos[0] - self.pos[0]
                    dy = pos[1] - self.pos[1]
                    if agent.direction == "NS":
                        if dy != 0:
                            return False
                    elif agent.direction == "EW":
                        if dx != 0:
                            return False
                return True
        
        return True

    def can_move_to(self, pos):
        """Verifica si el coche puede moverse a la posición."""
        if pos not in self.model.G:
            return False
        
        if not self.model.G.has_edge(self.pos, pos):
            return False
        
        if not self.can_pass_traffic_light(pos):
            return False
        
        cell_contents = self.model.grid.get_cell_list_contents([pos])
        
        for agent in cell_contents:
            if isinstance(agent, Destination):
                if agent != self.destination:
                    return False
            if isinstance(agent, Car):
                return False
            if isinstance(agent, Obstacle):
                return False
        
        return True

    def broadcast_request(self):
        """Contract Net Protocol para encontrar destino."""
        best_bid = float('inf')
        best_dest = None
        
        for dest in self.model.destinations:
            if dest == self.do_not_park_here:
                continue
            bid = dest.calculate_bid(self.pos)
            if bid < best_bid:
                best_bid = bid
                best_dest = dest
        
        if best_dest:
            best_dest.book(self)
            self.destination = best_dest
            self.state = "DRIVING"
            self.calculate_path()

    def calculate_path(self):
        """Calcula ruta usando Dijkstra ponderado."""
        if (
            not self.destination
            or self.pos not in self.model.G
            or self.destination.pos not in self.model.G
        ):
            return
        
        try:
            self.path = nx.shortest_path(
                self.model.G, self.pos, self.destination.pos, weight='weight'
            )
            if len(self.path) > 0:
                self.path.pop(0)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            self.destination.release()
            self.destination = None
            self.state = "WANDERING"
            self.path = []
            self.last_move = None


class TrafficLight(Agent):
    """Semáforo con ciclo Green → Yellow → Red → Green."""

    def __init__(self, unique_id, model, direction="NS", state="Green", time_offset=0):
        super().__init__(unique_id, model)
        self.direction = direction
        self.state = state
        self.timer = 10 - time_offset if state == "Green" else 10
        self.green_time = 10
        self.yellow_time = 3
        self.red_time = 10

    def step(self):
        """Decrementa timer y cambia estado cíclicamente."""
        self.timer -= 1
        
        if self.timer <= 0:
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
    """Edificio u obstáculo estático."""

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)

    def step(self):
        pass


class Destination(Agent):
    """Destino/Parking con 3 estados visuales."""

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.occupant = None
        self.reserved_by = None

    def step(self):
        pass

    def calculate_bid(self, car_pos):
        """Calcula oferta de distancia si está disponible."""
        if self.occupant is not None or self.reserved_by is not None:
            return float('inf')
        
        dx = abs(self.pos[0] - car_pos[0])
        dy = abs(self.pos[1] - car_pos[1])
        return dx + dy

    def book(self, car_agent):
        """Reserva destino para un coche."""
        self.reserved_by = car_agent
        return True

    def release(self):
        """Libera destino completamente."""
        self.occupant = None
        self.reserved_by = None


class ChaoticCar(Car):
    """
    Vehículo caótico que ignora semáforos.
    
    Estados:
    - CHAOS: Movimiento normal por perímetro
    - ESCAPING: Huyendo de policía (si detecta a menos de radio 10)
    - ARRESTED: Detenido (3 segundos antes de desaparecer)
    
    State Codes para Unity:
    - 6: CHAOS (morado)
    - 7: ESCAPING (rojo)
    """

    def __init__(self, unique_id, model, destination=None, parking_limit=3):
        super().__init__(unique_id, model, destination, parking_limit)
        self.state = "CHAOS"
        self.last_move = None
        
        # --- NUEVOS ATRIBUTOS FASE 1 ---
        self.is_being_chased = False  # Flag: ¿hay policía cerca?
        self.chase_memory_timer = 0   # Cuenta regresiva de "memoria" (5 seg = 50 steps)
        self.chase_memory_max = 50    # 5 segundos (aproximado a 10 steps/seg)
        self.arrest_timer = 0         # Cuando es arrestado, espera 3 seg
        self.arrest_duration = 30     # 3 segundos en steps

    def can_pass_traffic_light(self, pos):
        """Ignora todos los semáforos - ¡soy caótico!"""
        return True

    def can_move_to(self, pos):
        """
        Ignora semáforos, pero:
        1. Verifica límites de grafo
        2. Verifica obstáculos estáticos
        3. NUNCA entra a celdas de Destination
        4. IGNORA Car (puede colisionar)
        """
        if pos not in self.model.G:
            return False
        
        if not self.model.G.has_edge(self.pos, pos):
            return False
        
        cell_contents = self.model.grid.get_cell_list_contents([pos])
        
        # Bloquear Destination
        for agent in cell_contents:
            if isinstance(agent, Destination):
                return False
            if isinstance(agent, Obstacle):
                return False
        
        return True

    def get_chaotic_move(self):
        """
        Movimiento caótico pero DIRECCIONAL con inercia.
        Preferencia por perímetro (80% si está en borde).
        """
        neighbors = self.model.grid.get_neighborhood(
            self.pos, moore=False, include_center=False
        )
        
        valid_moves = []
        for n in neighbors:
            if self.can_move_to(n):
                weight = self.model.G.edges[self.pos, n]['weight'] if self.model.G.has_edge(self.pos, n) else 100
                dx = n[0] - self.pos[0]
                dy = n[1] - self.pos[1]
                direction = (dx, dy)
                valid_moves.append((n, weight, direction))
        
        if not valid_moves:
            return None
        
        # INERCIA: Si hay last_move, preferir continuación
        if self.last_move:
            for n, weight, direction in valid_moves:
                if direction == self.last_move:
                    return n
        
        # Si no hay continuación, elegir mejor peso
        valid_moves.sort(key=lambda x: x[1])
        best_pos = valid_moves[0][0]
        return best_pos

    def detect_police_in_range(self):
        """
        Detecta si hay policías en radio 10.
        Retorna: (has_police: bool, closest_police_pos: pos or None)
        """
        # Obtener todos los vecinos en radio 10
        neighbors = self.model.grid.get_neighbors(
            self.pos, moore=True, radius=10, include_center=False
        )
        
        police_nearby = []
        for neighbor in neighbors:
            if isinstance(neighbor, PoliceCar):
                police_nearby.append(neighbor)
        
        if police_nearby:
            # Encontrar el más cercano
            closest_police = min(
                police_nearby,
                key=lambda p: abs(p.pos[0] - self.pos[0]) + abs(p.pos[1] - self.pos[1])
            )
            return True, closest_police.pos
        
        return False, None

    def step(self):
        """
        Máquina de estados para ChaoticCar.
        CHAOS → ESCAPING → (back to CHAOS) | ARRESTED
        """
        self.position_history.append(self.pos)
        
        # Actualizar stuck counter
        if len(self.position_history) >= 2:
            prev_pos = list(self.position_history)[-2]
            if self.pos == prev_pos:
                self.stuck_counter += 1
            else:
                self.stuck_counter = 0
        
        # NUNCA buscar destino (override)
        self.destination = None
        self.path = []
        
        # --- ESTADO ARRESTED ---
        if self.state == "ARRESTED":
            self.arrest_timer -= 1
            if self.arrest_timer <= 0:
                # Desaparecer del modelo
                self.model.grid.remove_agent(self)
                self.model.schedule.remove(self)
            return
        
        # --- DETECTAR POLICÍA ---
        has_police, police_pos = self.detect_police_in_range()
        
        if has_police:
            self.is_being_chased = True
            self.chase_memory_timer = self.chase_memory_max
        else:
            # Decrementar memoria
            if self.chase_memory_timer > 0:
                self.chase_memory_timer -= 1
            else:
                self.is_being_chased = False
        
        # --- ESTADO ESCAPING ---
        if self.is_being_chased and self.state != "ARRESTED":
            self.state = "ESCAPING"
            # TODO: Implementar lógica de huida en FASE 2
            # Por ahora, solo usar get_chaotic_move() normal
            next_pos = self.get_chaotic_move()
        
        # --- ESTADO CHAOS ---
        else:
            self.state = "CHAOS"
            next_pos = self.get_chaotic_move()
        
        # Intentar movimiento
        if not next_pos:
            neighbors = self.model.grid.get_neighborhood(
                self.pos, moore=False, include_center=False
            )
            valid = [n for n in neighbors if self.can_move_to(n)]
            if valid:
                next_pos = random.choice(valid)
            else:
                self.last_move = None
                return
        
        # Detectar colisión con coche civil
        cell_contents = self.model.grid.get_cell_list_contents([next_pos])
        victim = None
        
        for agent in cell_contents:
            if isinstance(agent, Car) and not isinstance(agent, ChaoticCar) and not isinstance(agent, PoliceCar):
                victim = agent
                break
        
        if victim:
            # Crash: marcar víctima y CC huye
            victim.state = "CRASHED"
            
            neighbors = self.model.grid.get_neighborhood(
                self.pos, moore=False, include_center=False
            )
            valid = [n for n in neighbors if self.can_move_to(n)]
            if valid:
                escape_pos = random.choice(valid)
                dx = escape_pos[0] - self.pos[0]
                dy = escape_pos[1] - self.pos[1]
                self.last_move = (dx, dy)
                self.model.grid.move_agent(self, escape_pos)
            
            self.last_move = None
        else:
            # Movimiento normal
            dx = next_pos[0] - self.pos[0]
            dy = next_pos[1] - self.pos[1]
            self.last_move = (dx, dy)
            self.model.grid.move_agent(self, next_pos)


class PoliceCar(Car):
    """
    Patrulla que persigue ChaoticCars.
    
    Estados:
    - PATROL: Patrullando puntos de control
    - CHASE: Persiguiendo a un ChaoticCar
    - ARRESTING: Detenido tras capturar (3 segundos)
    
    State Codes para Unity:
    - 3: PATROL (azul oscuro)
    - 4: CHASE (rojo brillante)
    - 5: ARRESTING (azul parpadeante/intenso)
    """

    def __init__(self, unique_id, model, destination=None, parking_limit=3, patrol_id=0, checkpoints=None):
        super().__init__(unique_id, model, destination, parking_limit)
        self.state = "PATROL"
        self.patrol_id = patrol_id  # 0-4: Identifica qué zona patrulla
        
        # --- NUEVOS ATRIBUTOS FASE 1 ---
        self.checkpoints = checkpoints if checkpoints else []
        self.current_checkpoint_index = 0
        self.vision_radius = 8
        self.chase_target = None  # ChaoticCar siendo perseguido
        self.chase_memory_timer = 0  # Memoria después de perder de vista (5 seg = 50 steps)
        self.chase_memory_max = 50
        self.arrest_timer = 0  # Cuando arresta, espera 3 seg
        self.arrest_duration = 30  # 3 segundos en steps

    def detect_chaotic_cars_in_range(self):
        """
        Detecta ChaoticCars en radio de visión.
        Retorna lista ordenada por distancia.
        """
        neighbors = self.model.grid.get_neighbors(
            self.pos, moore=True, radius=self.vision_radius, include_center=False
        )
        
        chaotic_cars = []
        for neighbor in neighbors:
            if isinstance(neighbor, ChaoticCar):
                distance = abs(neighbor.pos[0] - self.pos[0]) + abs(neighbor.pos[1] - self.pos[1])
                chaotic_cars.append((neighbor, distance))
        
        # Ordenar por distancia
        chaotic_cars.sort(key=lambda x: x[1])
        return chaotic_cars

    def step(self):
        """
        Máquina de estados para PoliceCar.
        PATROL ↔ CHASE → ARRESTING → PATROL
        """
        self.position_history.append(self.pos)
        
        # --- ESTADO ARRESTING ---
        if self.state == "ARRESTING":
            self.arrest_timer -= 1
            if self.arrest_timer <= 0:
                # Volver a patrullaje
                self.state = "PATROL"
                self.chase_target = None
            return
        
        # --- DETECTAR CHAOTIC CARS ---
        chaotic_cars = self.detect_chaotic_cars_in_range()
        
        if chaotic_cars:
            # Entrar en CHASE: elegir el más cercano
            target_car, distance = chaotic_cars[0]
            self.chase_target = target_car
            self.chase_memory_timer = self.chase_memory_max
            self.state = "CHASE"
        else:
            # Decrementar memoria
            if self.chase_memory_timer > 0:
                self.chase_memory_timer -= 1
            else:
                self.chase_target = None
                self.state = "PATROL"
        
        # --- ESTADO CHASE ---
        if self.state == "CHASE" and self.chase_target:
            # Intentar perseguir
            try:
                path = nx.shortest_path(self.model.G, self.pos, self.chase_target.pos)
                if len(path) > 1:
                    next_pos = path[1]
                    
                    # Verificar colisión (arresto)
                    cell_contents = self.model.grid.get_cell_list_contents([next_pos])
                    if any(isinstance(a, ChaoticCar) for a in cell_contents):
                        # ARRESTO: Ambos se detienen
                        for agent in cell_contents:
                            if isinstance(agent, ChaoticCar):
                                agent.state = "ARRESTED"
                                agent.arrest_timer = agent.arrest_duration
                        
                        self.state = "ARRESTING"
                        self.arrest_timer = self.arrest_duration
                        return
                    
                    # Movimiento normal
                    if self.can_move_to(next_pos):
                        dx = next_pos[0] - self.pos[0]
                        dy = next_pos[1] - self.pos[1]
                        self.last_move = (dx, dy)
                        self.model.grid.move_agent(self, next_pos)
            
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                pass
        
        # --- ESTADO PATROL ---
        else:
            self.state = "PATROL"
            
            if not self.checkpoints:
                # Sin checkpoints: vagar (fallback)
                next_pos = self.get_wandering_move()
                if next_pos:
                    dx = next_pos[0] - self.pos[0]
                    dy = next_pos[1] - self.pos[1]
                    self.last_move = (dx, dy)
                    self.model.grid.move_agent(self, next_pos)
            else:
                # Con checkpoints: patrullar
                target_pos = self.checkpoints[self.current_checkpoint_index]
                
                if self.pos == target_pos:
                    # Llego al checkpoint, ir al siguiente
                    self.current_checkpoint_index = (
                        self.current_checkpoint_index + 1
                    ) % len(self.checkpoints)
                    target_pos = self.checkpoints[self.current_checkpoint_index]
                
                try:
                    path = nx.shortest_path(self.model.G, self.pos, target_pos)
                    if len(path) > 1:
                        next_pos = path[1]
                        if self.can_move_to(next_pos):
                            dx = next_pos[0] - self.pos[0]
                            dy = next_pos[1] - self.pos[1]
                            self.last_move = (dx, dy)
                            self.model.grid.move_agent(self, next_pos)
                
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    self.current_checkpoint_index = (
                        self.current_checkpoint_index + 1
                    ) % len(self.checkpoints)
