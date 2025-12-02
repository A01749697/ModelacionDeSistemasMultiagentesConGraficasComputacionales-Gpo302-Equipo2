

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
        
        # CRASH TIMER
        self.crash_timer = 0

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
        
        # 1. ESTADO CRASHED - desaparecer después de 5 steps
        if self.state == "CRASHED":
            self.crash_timer -= 1
            if self.crash_timer <= 0:
                # Desaparecer del modelo
                self.model.grid.remove_agent(self)
                self.model.schedule.remove(self)
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
        
        # PHYSICS FIX: Límite de ocupación (máximo 2 coches por celda)
        cars_in_cell = [a for a in cell_contents if isinstance(a, Car)]
        if len(cars_in_cell) >= 2:
            return False  # Celda llena, busca otro camino
        
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
        self.arrest_timer = 0         # Cuando es arrestado, espera 5 steps
        self.arrest_duration = 5      # 5 steps para desaparecer
        self.debug = True # Force debug for ChaoticCar in this file

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
        # BOUNDARY CHECK: Rechazar movimientos fuera del mapa
        if pos[0] < 0 or pos[0] >= 24 or pos[1] < 0 or pos[1] >= 24:
            return False

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

    def get_escape_move(self, police_pos):
        """
        Elige el movimiento que maximice la distancia Manhattan al policía.
        MEJORAS:
        - Urban Diving: Penaliza celdas del perímetro para fomentar rutas internas
        - Inertia: 90% probabilidad de continuar en la misma dirección si es óptima
        """
        neighbors = self.model.grid.get_neighborhood(
            self.pos, moore=False, include_center=False
        )
        
        valid_moves = []
        for n in neighbors:
            if self.can_move_to(n):
                # Calcular distancia al policía si me muevo a n
                dist = abs(n[0] - police_pos[0]) + abs(n[1] - police_pos[1])
                
                # URBAN DIVING: Penalizar si 'n' está en el borde del mapa
                if n[0] <= 1 or n[0] >= 22 or n[1] <= 1 or n[1] >= 22:
                    dist -= 2  # Hacemos que esta opción sea menos atractiva
                
                valid_moves.append((n, dist))
        
        if self.debug:
            print(f"[CHAOTIC {self.unique_id}] Escape options: {valid_moves}")

        if not valid_moves:
            return None
        
        # Maximizar distancia
        valid_moves.sort(key=lambda x: x[1], reverse=True)
        
        # Tomar el mejor (o uno de los mejores si hay empate)
        best_dist = valid_moves[0][1]
        best_moves = [pos for pos, dist in valid_moves if dist == best_dist]
        
        # INERCIA: Priorizar last_move con 90% probabilidad si está en los mejores
        final_move = random.choice(best_moves)  # Elección por defecto
        if self.last_move:
            ideal_pos_with_inertia = (self.pos[0] + self.last_move[0], self.pos[1] + self.last_move[1])
            if ideal_pos_with_inertia in best_moves and random.random() < 0.9:
                final_move = ideal_pos_with_inertia

        if self.debug:
            print(f"[CHAOTIC {self.unique_id}] Chose {final_move} (Dist: {best_dist})")
        
        return final_move

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
                
                # BORDER PENALTY: Evitar que ChaoticCar gravite al borde en estado CHAOS
                if n[0] <= 1 or n[0] >= 22 or n[1] <= 1 or n[1] >= 22:
                    # Reducir weight para hacer menos atractivo este movimiento
                    weight += 5
                    # Actualizar el último elemento de valid_moves con el weight penalizado
                    valid_moves[-1] = (n, weight, direction)
        
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
                # CLEANUP FIX: Notificar a policías que me persiguen
                for agent in self.model.schedule.agents:
                    if isinstance(agent, PoliceCar):
                        if agent.chase_target == self:
                            agent.chase_target = None
                            agent.last_known_pos = None
                            agent.state = "PATROL"
                
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
            # Lógica de huida: Maximizar distancia al policía más cercano
            # (police_pos se actualizó arriba en detect_police_in_range)
            if police_pos:
                next_pos = self.get_escape_move(police_pos)
            else:
                next_pos = None

            # Fallback si acorralado: movimiento caótico normal
            if next_pos is None:
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
            victim.crash_timer = 5  # Desaparecerá en 5 steps
            
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
        self.last_known_pos = None # Última posición conocida del objetivo
        self.chase_memory_timer = 0  # Memoria después de perder de vista (5 seg = 50 steps)
        self.chase_memory_max = 50
        self.arrest_timer = 0  # Cuando arresta, espera 5 steps
        self.arrest_duration = 8  # 5 steps para desaparecer
        self.cooldown_timer = 0  # [NUEVO] Cooldown post-arresto (anti spawn camping)
        self.debug = True # Force debug for PoliceCar in this file

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
                # LOGIC FIX: Ignorar criminales ya capturados
                if neighbor.state == "ARRESTED":
                    continue  # No perseguir objetivos ya arrestados
                distance = abs(neighbor.pos[0] - self.pos[0]) + abs(neighbor.pos[1] - self.pos[1])
                chaotic_cars.append((neighbor, distance))
        
        # Ordenar por distancia
        chaotic_cars.sort(key=lambda x: x[1])
        return chaotic_cars

    def can_pass_traffic_light(self, pos):
        """
        FASE 2 - SIRENAS: Policía ignora semáforos durante persecución.
        """
        if self.state == "CHASE":
            return True  # Sirenas encendidas, no se detiene
        else:
            # En PATROL, respetar semáforos
            return super().can_pass_traffic_light(pos)

    def step(self):
        """
        Máquina de estados para PoliceCar.
        PATROL ↔ CHASE → ARRESTING → PATROL
        """
        self.position_history.append(self.pos)
        
        # --- COOLDOWN (BUROCRACIA POST-ARRESTO) ---
        if self.cooldown_timer > 0:
            self.cooldown_timer -= 1
            self.state = "PATROL"  # Forzar patrullaje durante cooldown
            # Ejecutar lógica de patrullaje (saltar a PATROL al final)
            # No detectar ni perseguir durante cooldown
            if self.debug:
                print(f"[POLICE {self.unique_id}] 📋 Processing paperwork... Cooldown: {self.cooldown_timer}")
        
        # --- ESTADO ARRESTING ---
        if self.state == "ARRESTING":
            self.arrest_timer -= 1
            if self.arrest_timer <= 0:
                # Volver a patrullaje CON COOLDOWN
                self.state = "PATROL"
                self.chase_target = None
                self.cooldown_timer = 20  # [NUEVO] 20 steps (~2 seg) sin poder arrestar
                if self.debug:
                    print(f"[POLICE {self.unique_id}] ✅ Arrest completed. Starting cooldown (20 steps)")
            return
        
        # --- DETECTAR CHAOTIC CARS (SOLO SI NO HAY COOLDOWN) ---
        chaotic_cars = []
        
        if self.cooldown_timer == 0:  # [NUEVO] Solo detectar si no está en cooldown
            chaotic_cars = self.detect_chaotic_cars_in_range()
            
            # CLEANUP FIX: Validar que el objetivo actual sigue existiendo
            if self.chase_target:
                # Verificar si el objetivo fue removido del modelo
                if self.chase_target not in self.model.schedule.agents:
                    self.chase_target = None
                    self.last_known_pos = None
                    self.chase_memory_timer = 0
            
            if chaotic_cars:
                # Entrar en CHASE: elegir el más cercano
                target_car, distance = chaotic_cars[0]
                self.chase_target = target_car
                self.last_known_pos = target_car.pos
                self.chase_memory_timer = self.chase_memory_max
                self.state = "CHASE"
            else:
                # Decrementar memoria
                if self.chase_memory_timer > 0:
                    self.chase_memory_timer -= 1
                    # Mantener estado CHASE si hay memoria
                    self.state = "CHASE"
                else:
                    self.chase_target = None
                    self.last_known_pos = None
                    self.state = "PATROL"
        else:
            # Durante cooldown: forzar PATROL, ignorar criminales
            self.state = "PATROL"
            self.chase_target = None
            self.last_known_pos = None
        
        # --- ESTADO CHASE ---
        if self.state == "CHASE":
            # ANTI-INFINITE-LOOP: Si policía y criminal están en la MISMA celda
            manhattan_dist_check = abs(self.chase_target.pos[0] - self.pos[0]) + abs(self.chase_target.pos[1] - self.pos[1]) if self.chase_target else 999
            
            if manhattan_dist_check == 0 and self.chase_target and self.chase_target.state != "ARRESTED":
                # ¡Están encima! Ejecutar arresto automático
                self.state = "ARRESTING"
                self.arrest_timer = self.arrest_duration
                # Actualizar target
                self.chase_target.state = "ARRESTED"
                self.chase_target.arrest_timer = self.chase_target.arrest_duration
                
                if self.debug:
                    print(f"[POLICE {self.unique_id}] FORCED ARREST at {self.pos}! (Loop breaker activated)")
                
                return  # Salir del step, no continuar persecución

            # TURBO SPEED: Ejecutar movimiento 2 veces por step
            for turbo_iteration in range(2):
                # Si ya arrestamos, salir
                if self.state == "ARRESTING":
                    break

                target_pos = None
                
                # 1. Determinar destino (Target real o Memoria)
                if self.chase_target and self.chase_target.pos:
                    # Si lo veo (o está en el modelo), ir a su posición actual
                    # NOTA: detect_chaotic_cars_in_range ya valida visión, pero aquí
                    # aseguramos que el objeto sigue existiendo
                    if self.chase_target in [c[0] for c in chaotic_cars]:
                         target_pos = self.chase_target.pos
                         self.last_known_pos = target_pos
                    elif self.last_known_pos:
                         target_pos = self.last_known_pos
                elif self.last_known_pos:
                    target_pos = self.last_known_pos
                
                if target_pos:
                    # CLOSE-RANGE ARREST: Policía puede arrestar si criminal está a distancia <= 1
                    if self.chase_target and self.chase_target in self.model.schedule.agents:
                        dist_to_target = abs(self.chase_target.pos[0] - self.pos[0]) + abs(self.chase_target.pos[1] - self.pos[1])
                        
                        if dist_to_target <= 1 and self.chase_target.state != "ARRESTED":
                            # ARRESTO A CORTA DISTANCIA: Criminal acorralado/cercado
                            self.state = "ARRESTING"
                            self.arrest_timer = self.arrest_duration
                            
                            # Marcar target como arrestado
                            self.chase_target.state = "ARRESTED"
                            self.chase_target.arrest_timer = self.chase_target.arrest_duration
                            
                            if self.debug:
                                print(f"[POLICE {self.unique_id}] CLOSE-RANGE ARREST at distance {dist_to_target}! Surrounded target {self.chase_target.unique_id}")
                            
                            break  # Salir del turbo loop, no hacer más movimientos este step

                    # TÁCTICA DE BARRERA: Verificar si estamos bloqueando
                    manhattan_dist = abs(target_pos[0] - self.pos[0]) + abs(target_pos[1] - self.pos[1])
                    
                    # Calcular ruta primero
                    try:
                        path = nx.shortest_path(self.model.G, self.pos, target_pos)
                        path_length = len(path) - 1  # Número de pasos
                        
                        # CONDICIÓN DE BARRERA: Cerca en línea recta pero lejos en grafo
                        if manhattan_dist < 4 and path_length > 15:
                            if self.debug:
                                print(f"[POLICE {self.unique_id}] FORMING BARRIER! Visual Dist: {manhattan_dist}, Graph Path: {path_length}. Holding position.")
                            # Mantenerse en posición (no moverse)
                            continue  # Saltar al siguiente turbo_iteration o salir del loop

                        if self.debug:
                            print(f"[POLICE {self.unique_id}] Chasing target at {target_pos}. My Pos: {self.pos}")
                            print(f"[POLICE {self.unique_id}] Path found: {path}")

                        if len(path) > 1:
                            next_pos = path[1]
                            
                            # 3. Verificar ARRESTO (Colisión permitida)
                            cell_contents = self.model.grid.get_cell_list_contents([next_pos])
                            chaotic_in_next = [a for a in cell_contents if isinstance(a, ChaoticCar)]
                            
                            if chaotic_in_next:
                                # ¡ARRESTO! Moverse encima del criminal
                                self.model.grid.move_agent(self, next_pos)
                                
                                # Actualizar estados
                                self.state = "ARRESTING"
                                self.arrest_timer = self.arrest_duration
                                
                                for cc in chaotic_in_next:
                                    cc.state = "ARRESTED"
                                    cc.arrest_timer = cc.arrest_duration
                                break  # Salir del turbo loop

                            # 4. Movimiento normal de persecución
                            if self.can_move_to(next_pos):
                                dx = next_pos[0] - self.pos[0]
                                dy = next_pos[1] - self.pos[1]
                                
                                if self.debug:
                                    print(f"[POLICE {self.unique_id}] Moving to {next_pos} (Vector: {dx, dy})")

                                self.last_move = (dx, dy)
                                self.model.grid.move_agent(self, next_pos)
                            else:
                                # Si está bloqueado, intentar acercarse por Manhattan (fallback)
                                neighbors = self.model.grid.get_neighborhood(self.pos, moore=False, include_center=False)
                                valid_neighbors = [n for n in neighbors if self.can_move_to(n)]
                                if valid_neighbors:
                                    best_n = min(valid_neighbors, key=lambda n: abs(n[0]-target_pos[0]) + abs(n[1]-target_pos[1]))
                                    self.model.grid.move_agent(self, best_n)

                    except (nx.NetworkXNoPath, nx.NodeNotFound):
                        # Si no hay ruta, intentar acercarse heurísticamente
                        neighbors = self.model.grid.get_neighborhood(self.pos, moore=False, include_center=False)
                        valid_neighbors = [n for n in neighbors if self.can_move_to(n)]
                        if valid_neighbors:
                            best_n = min(valid_neighbors, key=lambda n: abs(n[0]-target_pos[0]) + abs(n[1]-target_pos[1]))
                            self.model.grid.move_agent(self, best_n)
        
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
