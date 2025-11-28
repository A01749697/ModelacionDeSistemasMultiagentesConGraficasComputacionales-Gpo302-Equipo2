using UnityEngine;

/// <summary>
/// AgentController maneja la visualización de un agente individual.
/// Python es la autoridad - este script solo actualiza la posición suavemente.
/// </summary>
public class AgentController : MonoBehaviour
{
    [Header("Agent Properties")]
    public int agentID = -1;
    
    [Header("Movement Settings")]
    public float moveSpeed = 10f; // Velocidad de interpolación
    
    private Vector3 targetPosition;
    private bool isInitialized = false;

    /// <summary>
    /// Inicializa el agente con su ID y posición inicial.
    /// </summary>
    public void Init(int id, Vector3 initialPosition)
    {
        agentID = id;
        targetPosition = initialPosition;
        transform.localPosition = initialPosition; // Evita "vuelo" desde origen
        isInitialized = true;
    }

    /// <summary>
    /// Actualiza la posición objetivo. El movimiento será suave gracias a Lerp en Update.
    /// </summary>
    public void UpdatePosition(Vector3 newPosition)
    {
        targetPosition = newPosition;
    }

    void Update()
    {
        if (!isInitialized) return;

        // Interpolación suave hacia la posición objetivo
        transform.localPosition = Vector3.Lerp(
            transform.localPosition,
            targetPosition,
            Time.deltaTime * moveSpeed
        );
    }
}