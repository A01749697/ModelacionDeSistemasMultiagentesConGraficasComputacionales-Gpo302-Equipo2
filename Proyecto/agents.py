from mesa import Agent
import networkx as nx
import random

class Car(Agent):
    """Agente que representa un vehículo en la simulación."""
    
    def __init__(self, unique_id, model, destination=None, parking_limit=3):
        super().__init__(unique_id, model)
        self.destination = destination 
        self.path = []
        self.parking_time = 0
        self.parking_limit = parking_limit
        self.patience = 3
        self.state = "DRIVING" # DRIVING, PARKED, WANDERING
        
        # DIAGNÓSTICO: Activar debug solo para el primer coche
        self.debug = (unique_id == 0)
        
    def step(self):
        """Ejecuta un paso de movimiento del vehículo."""
        
        # 0. Si no tengo destino, buscar uno (Contract Net)
        if self.destination is None:
            self.broadcast_request()
            if self.destination is None:
                # Si falló la subasta, vagar un poco
                self.state = "WANDERING"
                self.wandering_step()
                return

        # MAQUINA DE ESTADOS
        if self.state == "PARKED":
            self.parking_time += 1
            if self.parking_time > self.parking_limit:
                # Salir del estacionamiento
                self.destination.release() # Liberar el agente destino
                self.model.grid.remove_agent(self)
                self.model.schedule.remove(self)
            return

        # Lógica de movimiento (DRIVING o WANDERING)
        # Verificar si llegamos al destino (comparando coordenadas)
        dest_pos = self.destination.pos if self.destination else None
        
        if dest_pos and self.pos == dest_pos:
            # Llegamos al destino
            # Verificar si sigue siendo nuestro (reserved_by == self)
            if self.destination.reserved_by == self:
                 # Éxito: Ocupar
                 self.state = "PARKED"
                 self.destination.occupant = self
                 self.parking_time = 0
            else:
                 # Conflicto: Alguien nos robó el lugar o expiró reserva
                 self.destination = None
                 self.state = "WANDERING"
            return
        
        # Si no tenemos ruta, calcularla
        if not self.path and self.destination:
            self.calculate_path()
        
        # Intentar moverse
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
        elif self.state == "WANDERING":
            self.wandering_step()

    def broadcast_request(self):
        """Protocolo Contract Net: Solicitar ofertas a todos los destinos."""
        best_bid = float('inf')
        best_dest = None
        
        for dest in self.model.destinations:
            bid = dest.calculate_bid(self.pos)
            if bid < best_bid:
                # Verificar alcanzabilidad (opcional pero recomendado)
                if nx.has_path(self.model.G, self.pos, dest.pos):
                    best_bid = bid
                    best_dest = dest
        
        if best_dest:
            best_dest.book(self)
            self.destination = best_dest
            self.state = "DRIVING"
            self.calculate_path()

    def wandering_step(self):
        """Movimiento inteligente cuando no hay destino (prefiere menor costo)."""
        neighbors = self.model.grid.get_neighborhood(self.pos, moore=False, include_center=False)
        valid_neighbors = []
        for n in neighbors:
            # FIX: Verificar explícitamente si existe arista en el grafo dirigido
            if self.can_move_to(n) and self.model.G.has_edge(self.pos, n):
                valid_neighbors.append(n)
        
        if valid_neighbors:
            # WANDERING INTELIGENTE: Preferir vecinos con menor peso (90% probabilidad)
            if random.random() < 0.9:
                # Elegir vecino con menor peso de arista
                min_weight = float('inf')
                best_neighbor = None
                for n in valid_neighbors:
                    edge_weight = self.model.G.edges[self.pos, n]['weight']
                    if edge_weight < min_weight:
                        min_weight = edge_weight
                        best_neighbor = n
                next_pos = best_neighbor
            else:
                # 10% del tiempo: elegir random para evitar bucles
                next_pos = random.choice(valid_neighbors)
            
            self.model.grid.move_agent(self, next_pos)
    
    def calculate_path(self):
        """Calcula el camino más corto usando A* con pesos."""
        if self.destination and self.pos in self.model.G and self.destination.pos in self.model.G:
            try:
                # PATHFINDING PONDERADO: Usar pesos para preferir rutas directas
                self.path = nx.shortest_path(self.model.G, self.pos, self.destination.pos, weight='weight')
                if self.path:
                    self.path.pop(0)  # Remover posición actual
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                self.destination = None # Invalidar destino inalcanzable
                self.state = "WANDERING"
                self.path = []
    
    def can_move_to(self, pos):
        """Verifica si el coche puede moverse a la posición dada."""
        if pos not in self.model.G:
            if self.debug: print(f"🛑 BLOCKED at {self.pos} -> {pos} | Reason: No Node in Graph")
            return False
        
        # FIX: Verificar dirección del grafo (One-Way Streets)
        if not self.model.G.has_edge(self.pos, pos):
            if self.debug: print(f"🛑 BLOCKED at {self.pos} -> {pos} | Reason: No Edge (Wrong Way)")
            return False
        
        cell_contents = self.model.grid.get_cell_list_contents([pos])
        
        # PROTECCIÓN DE ESTACIONAMIENTOS: No entrar a un Destination ajeno
        for agent in cell_contents:
            if isinstance(agent, Destination):
                if agent != self.destination:
                    if self.debug: print(f"🛑 BLOCKED at {self.pos} -> {pos} | Reason: Private Parking {agent.unique_id}")
                    return False
        
        # No puede moverse si hay otro coche
        for agent in cell_contents:
            if isinstance(agent, Car):
                if self.debug: print(f"🛑 BLOCKED at {self.pos} -> {pos} | Reason: Car Ahead {agent.unique_id}")
                return False
            
            # Lógica de semáforos permisiva
            if isinstance(agent, TrafficLight):
                if agent.state == "Green":
                    if self.debug: print(f"✅ MOVE OK at {self.pos} -> {pos} | Green Light")
                    return True # Pasa siempre
                elif agent.state in ["Red", "Yellow"]:
                    # Solo bloquea si intentas cruzar su eje
                    
                    # Calcular dirección de movimiento
                    dx = pos[0] - self.pos[0]
                    dy = pos[1] - self.pos[1]
                    
                    # Si el semáforo es NS (Norte-Sur), bloquea movimiento vertical
                    if agent.direction == "NS":
                        if dy != 0: # Intento moverme verticalmente
                            if self.debug: print(f"🛑 BLOCKED at {self.pos} -> {pos} | Reason: Red Light NS")
                            return False
                    # Si es EW (Este-Oeste), bloquea movimiento horizontal
                    elif agent.direction == "EW":
                        if dx != 0: # Intento moverme horizontalmente
                            if self.debug: print(f"🛑 BLOCKED at {self.pos} -> {pos} | Reason: Red Light EW")
                            return False
        
        if self.debug: print(f"✅ MOVE OK at {self.pos} -> {pos}")
        return True


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
        """Los obstáculos no tienen lógica de paso."""
        pass


class Destination(Agent):
    """Agente que representa un destino/estacionamiento."""
    
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.occupant = None
        self.reserved_by = None
    
    def step(self):
        """Los destinos no tienen lógica de paso activa, reaccionan a mensajes."""
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
            
        # FIX: ChaoticCar TAMBIÉN debe respetar dirección de calle para evitar deadlocks
        if not self.model.G.has_edge(self.pos, pos):
            return False

        # No verificamos contenido de celda aquí para permitir 'choque' en step
        # Pero si es un Obstacle (edificio), sí deberíamos respetar física básica?
        # El user dice: "Si intenta moverse a una celda ocupada por otro Car... No se detiene. Choca."
        # Asumimos que Obstacle es muro.
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
             self.wandering_step()
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
                self.wandering_step() 
            else:
                # Movimiento normal (o choque con otro ChaoticCar/PoliceCar si no filtramos)
                if self.can_move_to(next_pos):
                    self.model.grid.move_agent(self, next_pos)
                    self.path.pop(0)
                else:
                    # Bloqueado por edificio o fuera de mapa
                    self.wandering_step()
        else:
            self.wandering_step()

class PoliceCar(Car):
    """Patrulla checkpoints y persigue ChaoticCars."""
    def __init__(self, unique_id, model, destination=None, parking_limit=3, checkpoints=None):
        super().__init__(unique_id, model, destination, parking_limit)
        # Si no se dan checkpoints, generar algunos aleatorios
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
                self.wandering_step()
                return

            target_pos = self.checkpoints[self.current_checkpoint_index]
            
            # Si llegamos al checkpoint, siguiente
            if self.pos == target_pos:
                self.current_checkpoint_index = (self.current_checkpoint_index + 1) % len(self.checkpoints)
                target_pos = self.checkpoints[self.current_checkpoint_index]
            
            # Ir al checkpoint
            try:
                path = nx.shortest_path(self.model.G, self.pos, target_pos)
                if len(path) > 1:
                    next_pos = path[1]
                    if self.can_move_to(next_pos):
                        self.model.grid.move_agent(self, next_pos)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                # Si no puede llegar, saltar checkpoint
                self.current_checkpoint_index = (self.current_checkpoint_index + 1) % len(self.checkpoints)
