from mesa import Agent
import networkx as nx
import random

class Car(Agent):
    """Agente que representa un vehículo en la simulación."""
    
    def __init__(self, unique_id, model, destination=None, parking_limit=3):
        super().__init__(unique_id, model)
        self.destination = destination
        self.state = "WANDERING" if destination is None else "DRIVING"
        self.parking_timer = 0
        self.parking_limit = parking_limit
        self.path = []
        self.patience = 3 # Intentos antes de recalcular ruta
        self.do_not_park_here = None # Evitar re-parking inmediato (Boomerang Bug)
        
        # DIAGNÓSTICO: Sistema de detección de atascos
        self.debug = (unique_id == 0)  # Por defecto solo agente 0
        
    def step(self):
        """Avanza un paso en la simulación."""
        
        # DEBUG: Mostrar estado al inicio
        if self.debug: print(f"🚗 AGENTE {self.unique_id} step() | pos={self.pos}, destination={self.destination}, state={self.state}")
        
        # 1. Freno por Choque: Si está chocado, no se mueve
        if self.state == "CRASHED":
            return

        # 2. Estado PARKED
        if self.state == "PARKED":
            self.parking_timer -= 1
            if self.parking_timer <= 0:
                # Salir del parking
                if self.destination:
                    self.do_not_park_here = self.destination # Recordar dónde estábamos
                    self.destination.release() # LIBERAR COLOR
                    self.destination = None
                
                self.state = "WANDERING"
                # No eliminamos al agente, sigue circulando
                if self.debug: print(f"🚗 AGENTE {self.unique_id} saliendo de parking -> WANDERING")
            return

        # 3. Navegación con Destino (DRIVING)
        if self.destination:
            # Si llegamos al destino
            if self.pos == self.destination.pos:
                self.state = "PARKED"
                self.parking_timer = self.parking_limit
                self.destination.occupant = self
                # No removemos de grid ni schedule
                return
            
            # Si no tenemos ruta, calcularla
            if not self.path:
                self.calculate_path()
            
            # Intentar seguir la ruta
            if self.path:
                next_pos = self.path[0]
                can_move = self.can_move_to(next_pos)
                
                if can_move:
                    self.model.grid.move_agent(self, next_pos)
                    self.path.pop(0)
                    self.patience = 3 
                else:
                    self.patience -= 1
                    if self.patience <= 0:
                        self.calculate_path()
                        self.patience = 3
        
        # 4. Navegación sin Destino (WANDERING)
        else:
            # Intentar negociar uno
            if self.debug: print(f"🔍 AGENTE {self.unique_id} sin destino, llamando broadcast_request()...")
            self.broadcast_request()
            
            # Si consiguió destino, cambiar a DRIVING (se procesará en el siguiente step o aquí mismo si quisiéramos)
            if self.destination:
                self.do_not_park_here = None # Ya encontramos nuevo destino, perdonar el anterior
                self.state = "DRIVING"
                self.calculate_path()
                return

            # Si sigue sin destino, vagar
            self.state = "WANDERING"
            next_pos = self.get_wandering_move()
            
            if next_pos:
                self.model.grid.move_agent(self, next_pos)
            # Si next_pos es None, se queda quieto (esperando semáforo)

    def get_wandering_move(self):
        """Decide el movimiento en modo WANDERING evitando el 'baile' en semáforos."""
        neighbors = self.model.grid.get_neighborhood(self.pos, moore=False, include_center=False)
        valid_options = []
        
        # 1. Obtener vecinos conectados por arista
        for n in neighbors:
            if self.model.G.has_edge(self.pos, n):
                weight = self.model.G.edges[self.pos, n]['weight']
                valid_options.append((n, weight))
        
        # 2. Ordenar por peso (menor peso = preferencia ir recto)
        valid_options.sort(key=lambda x: x[1])
        
        if not valid_options:
            return None
            
        # 3. Evaluar opciones
        # REGLA: Si la mejor opción (recto) está bloqueada por SEMÁFORO, esperar.
        # Si está bloqueada por COCHE, intentar la siguiente.
        
        best_pos, best_weight = valid_options[0]
        
        # A. Chequeo de Semáforo (Prioridad 1)
        if not self.can_pass_traffic_light(best_pos):
            if self.debug: print(f"🛑 AGENTE {self.unique_id} esperando en semáforo ROJO/AMARILLO hacia {best_pos}")
            return None # ESPERAR (No bailar)
            
        # B. Chequeo de Ocupación Física (Iterar opciones)
        for next_pos, weight in valid_options:
            # Ya chequeamos semáforo para la primera opción. 
            # Para las siguientes (cambio de carril), también deberíamos checar semáforo?
            # Si cambio de carril, el semáforo de ese carril aplica.
            if not self.can_pass_traffic_light(next_pos):
                continue # Si esa opción también tiene rojo, skip
                
            if self.can_move_to(next_pos):
                return next_pos
                
        return None

    def can_pass_traffic_light(self, pos):
        """
        Verifica si el semáforo permite el paso.
        FIX: Si ya estamos DENTRO de una intersección (self.pos tiene semáforo),
        siempre permitimos avanzar para despejar el cruce.
        """
        # 1. Checar si estoy dentro de la intersección
        my_cell_contents = self.model.grid.get_cell_list_contents([self.pos])
        am_i_in_intersection = any(isinstance(a, TrafficLight) for a in my_cell_contents)
        
        if am_i_in_intersection:
            return True # Regla de oro: Despejar intersección siempre
            
        # 2. Lógica normal de entrada (si vengo de la calle)
        cell_contents = self.model.grid.get_cell_list_contents([pos])
        for agent in cell_contents:
            if isinstance(agent, TrafficLight):
                if agent.state == "Green":
                    return True
                elif agent.state in ["Red", "Yellow"]:
                    # Bloqueo por ejes
                    dx = pos[0] - self.pos[0]
                    dy = pos[1] - self.pos[1]
                    
                    if agent.direction == "NS": # NS light blocks vertical movement
                        if dy != 0: return False
                    elif agent.direction == "EW": # EW light blocks horizontal movement
                        if dx != 0: return False
        return True

    def can_move_to(self, pos):
        """Verifica si el coche puede moverse a la posición dada (Semáforos, Coches, Obstáculos)."""
        if pos not in self.model.G:
            return False
        
        if not self.model.G.has_edge(self.pos, pos):
            return False
        
        # Verificar Semáforo primero (reutilizando lógica)
        if not self.can_pass_traffic_light(pos):
             return False
        
        cell_contents = self.model.grid.get_cell_list_contents([pos])
        
        # PROTECCIÓN DE ESTACIONAMIENTOS: No entrar a un Destination ajeno
        for agent in cell_contents:
            if isinstance(agent, Destination):
                if agent != self.destination:
                    return False
        
        # No puede moverse si hay otro coche u obstáculo
        for agent in cell_contents:
            if isinstance(agent, Car):
                return False
            if isinstance(agent, Obstacle):
                return False
        
        return True

    def broadcast_request(self):
        """Protocolo Contract Net: Solicitar ofertas a todos los destinos."""
        best_bid = float('inf')
        best_dest = None
        
        for dest in self.model.destinations:
            if dest == self.do_not_park_here:
                continue # Ignorar el lugar del que acabamos de salir
                
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
        """Calcula la ruta usando A* ponderado."""
        if self.destination and self.pos in self.model.G and self.destination.pos in self.model.G:
            try:
                self.path = nx.shortest_path(self.model.G, self.pos, self.destination.pos, weight='weight')
                if len(self.path) > 0:
                    self.path.pop(0)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                self.destination.release()
                self.destination = None
                self.state = "WANDERING"
                self.path = []


class TrafficLight(Agent):
    """Agente que representa un semáforo con 3 estados: Green, Yellow, Red."""
    
    def __init__(self, unique_id, model, direction="NS", state="Green", time_offset=0):
        super().__init__(unique_id, model)
        self.direction = direction  # "NS" (Norte-Sur) o "EW" (Este-Oeste)
        self.state = state
        self.timer = 10 - time_offset if state == "Green" else 10 # Ajuste simple
        
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
        pass


class Destination(Agent):
    """Agente que representa un destino/estacionamiento."""
    
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.occupant = None
        self.reserved_by = None
    
    def step(self):
        pass

    def calculate_bid(self, car_pos):
        """Calcula una oferta basada en la distancia si está disponible."""
        if self.occupant is not None or self.reserved_by is not None:
            return float('inf') # No disponible
        
        # Calcular distancia Manhattan
        dx = abs(self.pos[0] - car_pos[0])
        dy = abs(self.pos[1] - car_pos[1])
        return dx + dy

    def book(self, car_agent):
        """Reserva el destino para un coche."""
        self.reserved_by = car_agent
        return True

    def release(self):
        """Libera el destino."""
        self.occupant = None
        self.reserved_by = None

class ChaoticCar(Car):
    """Vehículo que representa el caos. Ignora semáforos y choca."""
    def __init__(self, unique_id, model, destination=None, parking_limit=3):
        super().__init__(unique_id, model, destination, parking_limit)
        self.state = "CHAOS"

    def can_move_to(self, pos):
        """Ignora semáforos, solo verifica límites y obstáculos estáticos."""
        if pos not in self.model.G:
            return False
        if not self.model.G.has_edge(self.pos, pos):
            return False

        cell_contents = self.model.grid.get_cell_list_contents([pos])
        for agent in cell_contents:
            if isinstance(agent, Obstacle):
                return False
        return True

    def step(self):
        """Se mueve en cada tick sin delays."""
        # 1. Calcular ruta si no tiene (o vagar)
        if not self.path and self.destination:
            self.calculate_path()
        elif not self.path and not self.destination:
             # Usar lógica simple de wandering
             self.state = "WANDERING"
             next_pos = self.get_wandering_move() # Reutilizamos, pero Chaotic ignora semáforos en can_move_to
             if next_pos:
                 self.model.grid.move_agent(self, next_pos)
             return

        # 2. Moverse
        if self.path:
            next_pos = self.path[0]
            
            # Verificar colisión
            cell_contents = self.model.grid.get_cell_list_contents([next_pos])
            victim = None
            for agent in cell_contents:
                if isinstance(agent, Car) and not isinstance(agent, ChaoticCar):
                    victim = agent
                    break
            
            if victim:
                # CHOQUE
                victim.state = "CRASHED"
                # ChaoticCar huye
                self.destination = None 
                self.path = []
                # Simple wandering escape
                neighbors = self.model.grid.get_neighborhood(self.pos, moore=False, include_center=False)
                valid = [n for n in neighbors if self.can_move_to(n)]
                if valid:
                    self.model.grid.move_agent(self, random.choice(valid))
            else:
                if self.can_move_to(next_pos):
                    self.model.grid.move_agent(self, next_pos)
                    self.path.pop(0)
                else:
                    self.path = []

class PoliceCar(Car):
    """Patrulla checkpoints y persigue ChaoticCars."""
    def __init__(self, unique_id, model, destination=None, parking_limit=3, checkpoints=None):
        super().__init__(unique_id, model, destination, parking_limit)
        if checkpoints is None:
            self.checkpoints = []
        else:
            self.checkpoints = checkpoints
        self.current_checkpoint_index = 0
        self.state = "PATROL"
    
    def step(self):
        # 1. Detectar ChaoticCar
        neighbors = self.model.grid.get_neighbors(self.pos, moore=True, radius=5, include_center=False)
        target = None
        for n in neighbors:
            if isinstance(n, ChaoticCar):
                target = n
                break
        
        if target:
            self.state = "CHASE"
            try:
                path = nx.shortest_path(self.model.G, self.pos, target.pos)
                if len(path) > 1:
                    next_pos = path[1]
                    if self.can_move_to(next_pos):
                        self.model.grid.move_agent(self, next_pos)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                pass
        else:
            self.state = "PATROL"
            if not self.checkpoints:
                # Wandering logic
                next_pos = self.get_wandering_move()
                if next_pos:
                    self.model.grid.move_agent(self, next_pos)
                return

            target_pos = self.checkpoints[self.current_checkpoint_index]
            
            if self.pos == target_pos:
                self.current_checkpoint_index = (self.current_checkpoint_index + 1) % len(self.checkpoints)
                target_pos = self.checkpoints[self.current_checkpoint_index]
            
            try:
                path = nx.shortest_path(self.model.G, self.pos, target_pos)
                if len(path) > 1:
                    next_pos = path[1]
                    if self.can_move_to(next_pos):
                        self.model.grid.move_agent(self, next_pos)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                self.current_checkpoint_index = (self.current_checkpoint_index + 1) % len(self.checkpoints)
