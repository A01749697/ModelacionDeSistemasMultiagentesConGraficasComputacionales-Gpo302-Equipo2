# 🚨 INSTRUCCIONES EJECUTIVAS: DEBUGGING AVANZADO

## POSIBLES DIAGNÓSTICOS

Una vez veas el log, busca estos patrones:

### 1️⃣ PING-PONG (Oscilación)
```
Reason: PING_PONG
→ Neighbor A: MoveOK=True, elige A
Step +1: Reason: PING_PONG
→ Neighbor B (atrás): MoveOK=True, elige B
```
**Diagnóstico:** Sigue oscilando entre dos posiciones
**Acción:** Aumentar emergency escape threshold de 15 a 10 steps

### 2️⃣ BLOQUEO TOTAL
```
Step: 295, Pos: (21, 12)
→ Neighbor (21, 13): LightOK=True, MoveOK=False, Occupants: [Car]
→ Neighbor (22, 12): LightOK=True, MoveOK=False, Occupants: []
→ Neighbor (21, 11): LightOK=False, MoveOK=N/A
DECISION: Returning None
```
**Diagnóstico:** TODAS las opciones bloqueadas (legítimo atasco de tráfico)
**Acción:** Si solo ocurre 1-2 veces, es normal. Si es consistente, revisar generación de tráfico.

### 3️⃣ SEMÁFORO CONTRADICTORIO
```
→ Neighbor (21, 13): LightOK=True, MoveOK=True, LightStatus=Red (EW)
Pero MoveOK es True (debería ser False)
```
**Diagnóstico:** Bug en `can_pass_traffic_light()` o `can_move_to()`
**Acción:** Revisar lógica de dirección NS/EW

### 4️⃣ COCHE FANTASMA
```
→ Neighbor (22, 12): LightOK=True, MoveOK=False, Occupants: []
Pero MoveOK es False sin ocupante visible
```
**Diagnóstico:** Bug en `grid.get_cell_list_contents()`
**Acción:** Revisar si hay problema de sincronización del grid

---

## SI EMERGENCY ESCAPE SE ACTIVA

Si ves en el log:

```
🚨 EMERGENCY ESCAPE: Car 201 forcing move after 16 stuck steps
```

Significa que el sistema detectó un atasco de 16 steps y forzó un movimiento.

**Esto es BUENA NOTICIA:** El sistema se auto-corrigió.

Pero si esto ocurre frecuentemente (>5 veces en 300 steps), significa que hay un problema sistémico.

---

## PROPORCIONA ESTO DESPUÉS DE EJECUTAR

Cuando tengas los logs, haz esto:

1. **Busca la PRIMERA línea con "🚨 STUCK DETECTION":**
   ```bash
   grep -n "🚨 STUCK DETECTION" simulation_debug.log | head -1
   ```
   Dirá algo como: `1245:🚨 STUCK DETECTION`

2. **Extrae el contexto (50 líneas antes y después):**
   ```bash
   sed -n '1200,1300p' simulation_debug.log > stuck_context.txt
   ```

3. **Proporciona ese archivo** + el output del comando grep anterior

Con eso, podré identificar el bug exacto en < 5 minutos.

---

## COMANDOS RÁPIDOS DE BÚSQUEDA

```bash
# Contar cuántos coches se atascaron
grep "🚨 STUCK DETECTION" simulation_debug.log | wc -l

# Ver qué IDs de coche se atascan
grep "🚨 STUCK DETECTION" simulation_debug.log | cut -d: -f2 | sort | uniq -c

# Ver causas de atasco
grep "Reason:" simulation_debug.log | sort | uniq -c

# Ver si hay Emergency Escape
grep "EMERGENCY ESCAPE" simulation_debug.log | wc -l
```

---

## SUMARIO

| Acción | Comando |
|--------|---------|
| Ejecutar con logs | `python -u server_visualization.py 2>&1 \| tee sim.log` |
| Ver dónde se atasca | `grep "🚨 STUCK" sim.log \| head -5` |
| Ver contexto | `sed -n '1200,1300p' sim.log` |
| Contar atascos | `grep "🚨 STUCK" sim.log \| wc -l` |
| Identificar culpritos | `grep "🚨 STUCK" sim.log \| grep -oP "Car \K[0-9]+"` |

---

**¡Listo! Implementa PROMPT_DEBUG_RIGOROUS.py y ejecuta. Con los logs, resolveremos el bug definitivamente.** 🚀

---

Version: 1.0
Date: 2025-11-30
Status: 🟢 READY FOR EXECUTION
