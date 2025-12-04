using UnityEngine;

/// <summary>
/// AgentController maneja la visualización de un agente individual.
/// Python es la autoridad - este script solo actualiza la posición y rotación suavemente.
/// </summary>
public class AgentController : MonoBehaviour
{
    [Header("Agent Properties")]
    public int agentID = -1;
    
    [Header("Movement Settings")]
    public float moveSpeed = 10f;     // Velocidad de interpolación de posición
    public float rotationSpeed = 10f; // Velocidad de interpolación de rotación
    
    private Vector3 targetPosition;
    private bool isInitialized = false;

    /// <summary>
    /// Inicializa el agente con su ID y posición inicial.
    /// </summary>
    public void Init(int id, Vector3 initialPosition)
    {
        agentID = id;
        targetPosition = initialPosition;
        transform.localPosition = initialPosition; 
        isInitialized = true;
    }

    /// <summary>
    /// Actualiza la posición objetivo.
    /// </summary>
    public void UpdatePosition(Vector3 newPosition)
    {
        targetPosition = newPosition;
    }

    void Update()
    {
        if (!isInitialized) return;

        // 1. Interpolación suave de posición
        transform.localPosition = Vector3.Lerp(
            transform.localPosition,
            targetPosition,
            Time.deltaTime * moveSpeed
        );

        // 2. Lógica de Rotación
        // Calculamos el vector hacia donde nos estamos moviendo
        Vector3 direction = targetPosition - transform.localPosition;
        
        // Aplanamos el vector para ignorar inclinaciones verticales
        direction.y = 0;

        // Solo rotamos si el movimiento es significativo (para evitar errores con vectores cero)
        if (direction.sqrMagnitude > 0.01f)
        {
            // Calculamos la rotación objetivo mirando hacia el vector de movimiento
            Quaternion targetRotation = Quaternion.LookRotation(direction);

            // Interpolamos suavemente la rotación actual hacia la objetivo
            transform.localRotation = Quaternion.Slerp(
                transform.localRotation,
                targetRotation,
                Time.deltaTime * rotationSpeed
            );
        }
    }
}