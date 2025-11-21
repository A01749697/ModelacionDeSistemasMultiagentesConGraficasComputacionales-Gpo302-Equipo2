# MesaServer/server.py
import asyncio
import websockets
import json
from model import CityModel
MODEL_WIDTH = 24
MODEL_HEIGHT = 24
WS_HOST = "localhost"
WS_PORT = 8765
# Instanciamos el modelo de la ciudad
model = CityModel(width=MODEL_WIDTH, height=MODEL_HEIGHT)
connected = set()
async def process_message(message: str):
    """Procesa mensajes JSON desde Unity.
    
    Simulación paso a paso controlada por el cliente:
    - Unity envía {'type': 'step'} para avanzar la simulación
    - El servidor ejecuta model.step() y responde automáticamente con el estado actualizado
    """
    try:
        data = json.loads(message)
    except Exception as e:
        print("Error parseando JSON:", e)
        return
    msg_type = data.get("type", "")
    
    if msg_type == "step":
        # Ejecutar un paso de la simulación
        model.step()
        print(f"✓ Paso de simulación ejecutado")
        # Nota: El estado actualizado se enviará automáticamente en handler()
        
    elif msg_type == "spawn_car":
        # Generar un nuevo coche
        car = model.spawn_car()
        print(f"✓ Coche {car.unique_id} generado en {car.pos}")
async def broadcast_state():
    """Envía el estado de todos los agentes a Unity.
    
    Formato JSON enviado:
    {
        "type": "update",
        "agents": [
            {
                "id": 1,
                "x": 5,
                "y": 10,
                "agent_type": "Car" | "TrafficLight" | "Obstacle" | "Destination",
                "state": "Green" | "Yellow" | "Red" (para semáforos) | "Moving" (coches) | null,
                "direction": "NS" | "EW" (solo semáforos) | null
            },
            ...
        ]
    }
    """
    if not connected:
        return
        
    agents_data = model.serialize_grid()
    world_state = {
        "type": "update", 
        "agents": agents_data
    }
    msg = json.dumps(world_state)
    
    # Enviar a todos los clientes conectados
    # websockets 10+ maneja el broadcast de forma eficiente
    await asyncio.gather(*[ws.send(msg) for ws in connected])
    print(f" Estado enviado a Unity: {len(agents_data)} agentes")
async def handler(ws):
    """Maneja la conexión de un cliente (Unity).
    
    Flujo de simulación paso a paso:
    1. Unity se conecta → Se envía estado inicial
    2. Unity envía {'type': 'step'} → model.step() se ejecuta → Estado actualizado se envía
    3. Unity recibe {'type': 'update', 'agents': [...]} con todos los agentes y sus estados
    """
    print("🎮 Unity conectado")
    connected.add(ws)
    try:
        # Enviar estado inicial al conectar
        print(" Enviando estado inicial...")
        await broadcast_state()
        
        # Procesar mensajes de Unity
        async for message in ws:
            await process_message(message)
            # Enviar estado actualizado inmediatamente después de procesar
            await broadcast_state()
            
    except websockets.ConnectionClosed:
        print("Unity desconectado")
    finally:
        connected.remove(ws)
async def main():
    async with websockets.serve(handler, WS_HOST, WS_PORT):
        print(f"🚀 Servidor Mesa corriendo en ws://{WS_HOST}:{WS_PORT}")
        print(f"📊 Modelo inicializado: {MODEL_WIDTH}x{MODEL_HEIGHT}")
        print(f"🔗 Grafo: {len(model.G.nodes)} nodos, {len(model.G.edges)} aristas")
        print(f"🅿️  Destinos: {len(model.destinations)}")
        print("Esperando conexión de Unity...")
        await asyncio.Future()  # run forever
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Servidor detenido.")