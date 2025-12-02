using UnityEngine;
using NativeWebSocket;
using Newtonsoft.Json.Linq;
using System.Collections.Generic;
using System.Threading.Tasks;

/// <summary>
/// MesaSync es el cliente de Unity que se conecta al servidor Python (autoridad).
/// Unity solo visualiza - Python controla la simulación.
/// </summary>
public class MesaSync : MonoBehaviour
{
    public static MesaSync Instance;
    private WebSocket websocket;
    
    [Header("Prefabs")]
    public GameObject carPrefab;
    public GameObject trafficLightPrefab;
    public GameObject obstaclePrefab;
    public GameObject destinationPrefab;
    
    [Header("Settings")]
    public Transform agentsRoot;
    public float stepInterval = 0.1f; // Tiempo entre pasos de simulación

    [Header("Traffic Light Materials")]
    public Material greenLightMaterial;
    public Material yellowLightMaterial;
    public Material redLightMaterial;

    // Diccionario para rastrear agentes activos en Unity
    private Dictionary<int, GameObject> unityAgents = new Dictionary<int, GameObject>();
    private float stepTimer = 0f;

    async void Awake()
    {
        Instance = this;
        string url = "ws://localhost:8765";
        Debug.Log($"[MesaSync] Initializing WebSocket connection to {url}...");

        websocket = new WebSocket(url);

        websocket.OnOpen += () =>
        {
            Debug.Log("[MesaSync] Connection open!");
        };

        websocket.OnMessage += (bytes) =>
        {
            var msg = System.Text.Encoding.UTF8.GetString(bytes);
            HandleMessage(msg);
        };

        websocket.OnError += (e) =>
        {
            Debug.LogError($"[MesaSync] WebSocket Error: {e}");
        };

        websocket.OnClose += (e) =>
        {
            Debug.Log($"[MesaSync] WebSocket closed. Code: {e}");
        };

        try
        {
            Debug.Log("[MesaSync] Attempting to connect...");
            await websocket.Connect();
            Debug.Log("[MesaSync] Connect() called successfully.");
        }
        catch (System.Exception ex)
        {
            Debug.LogError($"[MesaSync] Exception during Connect: {ex.Message}");
        }
    }

    private void HandleMessage(string msg)
    {
        // Ejecutamos esto en el hilo principal usando el Dispatcher
        UnityMainThreadDispatcher.Instance().Enqueue(() => {
            try
            {
                JObject data = JObject.Parse(msg);
                var type = (string)data["type"];
                if (type == "update")
                {
                    var agents = (JArray)data["agents"];
                    ApplyMesaState(agents);
                }
            }
            catch (System.Exception e)
            {
                Debug.LogError($"[MesaSync] Error handling message: {e.Message}");
            }
        });
    }

    /// <summary>
    /// Sincroniza el estado de Unity con el estado de Python.
    /// Patrón: Spawn nuevos, Update existentes, Destroy eliminados.
    /// </summary>
    private void ApplyMesaState(JArray agents)
    {
        // Marcamos los agentes vistos en esta actualización
        HashSet<int> seen = new HashSet<int>();
        
        foreach (var a in agents)
        {
            int id = (int)a["id"];
            int x = (int)a["x"];
            int y = (int)a["y"];
            string agentType = (string)a["agent_type"];
            string state = a["state"]?.ToString();
            string direction = a["direction"]?.ToString();
            
            seen.Add(id);
            Vector3 newPosition = new Vector3(x, 0f, y);

            // SPAWN: Crear agente si no existe
            if (!unityAgents.ContainsKey(id))
            {
                GameObject prefab = GetPrefabForType(agentType);
                if (prefab != null)
                {
                    GameObject go = Instantiate(prefab, agentsRoot);
                    go.name = $"{agentType}_{id}";
                    
                    // Inicializar AgentController
                    var ctrl = go.GetComponent<AgentController>();
                    if (ctrl != null)
                    {
                        ctrl.Init(id, newPosition);
                    }
                    else
                    {
                        // Si no tiene AgentController, posicionar directamente
                        go.transform.localPosition = newPosition;
                    }
                    
                    unityAgents[id] = go;
                    Debug.Log($"[MesaSync] ✨ Spawned {agentType} with ID {id} at ({x}, {y})");
                }
            }
            // UPDATE: Actualizar posición de agente existente
            else
            {
                GameObject go = unityAgents[id];
                if (go != null)
                {
                    var ctrl = go.GetComponent<AgentController>();
                    if (ctrl != null)
                    {
                        // Delegar interpolación al AgentController
                        ctrl.UpdatePosition(newPosition);
                    }
                    else
                    {
                        // Si no tiene AgentController, mover directamente
                        go.transform.localPosition = newPosition;
                    }
                }
            }

            // Actualizar estado específico del tipo de agente
            if (agentType == "TrafficLight")
            {
                UpdateTrafficLight(id, state, direction);
            }
            else if (agentType == "Car")
            {
                UpdateCar(id, state);
            }
        }

        // DESTROY: Eliminar agentes que ya no existen en Mesa
        List<int> toRemove = new List<int>();
        foreach (var kv in unityAgents)
        {
            if (!seen.Contains(kv.Key))
                toRemove.Add(kv.Key);
        }
        
        foreach (int id in toRemove)
        {
            Debug.Log($"[MesaSync] 🗑️ Removing agent {id}");
            if (unityAgents.ContainsKey(id) && unityAgents[id] != null)
            {
                Destroy(unityAgents[id]);
                unityAgents.Remove(id);
            }
        }
    }

    private GameObject GetPrefabForType(string agentType)
    {
        switch (agentType)
        {
            case "Car":
                return carPrefab;
            case "TrafficLight":
                return trafficLightPrefab;
            case "Obstacle":
                return obstaclePrefab;
            case "Destination":
                return destinationPrefab;
            default:
        // Por ejemplo, animaciones según el estado
    }

    void Update()
    {
        // Despachar mensajes del WebSocket
        if (websocket != null)
        {
            #if !UNITY_WEBGL || UNITY_EDITOR
            websocket.DispatchMessageQueue();
            #endif
        }

        // Temporizador para enviar comandos de step
        stepTimer += Time.deltaTime;
        if (stepTimer >= stepInterval)
        {
            stepTimer = 0f;
            SendStepCommand();
        }
    }

    private async void SendStepCommand()
    {
        if (websocket == null || websocket.State != WebSocketState.Open)
            return;

        JObject payload = new JObject();
        payload["type"] = "step";
        string msg = payload.ToString();
        
        await websocket.SendText(msg);
    }

    public async Task SendSpawnCarCommand()
    {
        if (websocket == null || websocket.State != WebSocketState.Open)
            return;

        JObject payload = new JObject();
        payload["type"] = "spawn_car";
        string msg = payload.ToString();
        
        await websocket.SendText(msg);
        Debug.Log("[MesaSync] Spawn car command sent");
    }

    private async void OnApplicationQuit()
    {
        if (websocket != null)
            await websocket.Close();
    }
}