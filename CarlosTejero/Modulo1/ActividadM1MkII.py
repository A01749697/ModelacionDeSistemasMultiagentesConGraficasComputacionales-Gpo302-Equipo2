import random
import pandas as pd
import mesa
import matplotlib.pyplot as plt
from mesa.datacollection import DataCollector


class Celda:
    """Representación ligera de una celda con estado."""
    def __init__(self, unique_id, model, estado="limpia"):
        self.unique_id = unique_id
        self.model = model
        self.estado = estado
        self.pos = None  


class Robot:
    """Robot reactivo: aspira si la celda está sucia, 
    sino se mueve aleatoriamente."""
    def __init__(self, unique_id, model, posicion=(0, 0)):
        self.unique_id = unique_id
        self.model = model
        self.pos = None  
        self.posicion = posicion
        self.movimientos = 0

    def elegir_direccion(self):
        direcciones = [
            (0, 1), (1, 0), (0, -1), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]
        return self.model.random.choice(direcciones)

    def calcular_nueva_posicion(self, posicion, direccion):
        x, y = posicion
        dx, dy = direccion
        return (x + dx, y + dy)

    def limpiar(self, celda):
        celda.estado = "limpia"

    def step(self):
        x, y = self.posicion
        contenidos = self.model.grid.get_cell_list_contents([(x, y)])
        celda_actual = next((c for c in contenidos if isinstance(c, Celda)), None)

        if celda_actual and celda_actual.estado == "sucia":
            self.limpiar(celda_actual)
        else:
            direccion = self.elegir_direccion()
            nueva_pos = self.calcular_nueva_posicion(self.posicion, direccion)
            if not self.model.grid.out_of_bounds(nueva_pos):
                self.model.grid.move_agent(self, nueva_pos)
                self.posicion = nueva_pos
                self.movimientos += 1


class Entorno(mesa.Model):
    """Modelo de simulación del entorno."""

    def __init__(self, num_agentes, M, N, prob_suciedad, tiempo_max, seed=None):
        super().__init__()
        if seed is not None:
            random.seed(seed)
            self.random.seed(seed)

        self.M = M
        self.N = N
        self.num_agentes = num_agentes
        self.prob_suciedad = prob_suciedad
        self.tiempo_max = tiempo_max
        self.tiempo_actual = 0
        self.running = True

        self.grid = mesa.space.MultiGrid(M, N, torus=False)

        for x in range(M):
            for y in range(N):
                estado = "sucia" if self.random.random() < prob_suciedad else "limpia"
                cel = Celda(f"cel_{x}_{y}", self, estado=estado)
                self.grid.place_agent(cel, (x, y))

        # crear robots en la celda (0,0)
        self.robots = []
        for i in range(num_agentes):
            r = Robot(f"robot_{i}", self, posicion=(0, 0))
            self.grid.place_agent(r, (0, 0))
            r.pos = (0, 0)
            r.posicion = (0, 0)
            self.robots.append(r)

        # DataCollector
        self.datacollector = DataCollector(
            model_reporters={
                "Celdas Limpias": lambda m: m.contar_celdas("limpia"),
                "Celdas Sucias": lambda m: m.contar_celdas("sucia"),
                "Movimientos Totales": lambda m: sum(r.movimientos for r in getattr(m, 'robots', []))
            },
            agent_reporters={
                "Movimientos": "movimientos",# recolecta movimientos de cada robot
                "Posicion": lambda a: getattr(a,"posicion", None)#recolecta posición del robot
            }
        )

    def contar_celdas(self, estado):
        total = 0
        for x in range(self.M):
            for y in range(self.N):
                agentes = self.grid.get_cell_list_contents([(x, y)])
                cel = next((c for c in agentes if isinstance(c, Celda)), None)
                if cel and cel.estado == estado:
                    total += 1
        return total

    def step(self):
        self.datacollector.collect(self)
        # scheduler manual: mezclar y ejecutar
        orden = list(self.robots)
        self.random.shuffle(orden)
        for a in orden:
            a.step()

        self.tiempo_actual += 1
        if self.tiempo_actual >= self.tiempo_max or self.contar_celdas("sucia") == 0:
            self.running = False


def run_experiment(configs, n_repeticiones=10, output_csv="resultados.csv"):
    """Ejecuta experimentos para una lista de configuraciones.

    configs: lista de tuplas (num_agentes, M, N, prob_suciedad, tiempo_max)
    """
    rows = []
    for (num_agentes, M, N, prob_suciedad, tiempo_max) in configs:
        for rep in range(n_repeticiones):
            seed = rep + 1000 * num_agentes
            m = Entorno(num_agentes, M, N, prob_suciedad, tiempo_max, seed=seed)
            
            m.datacollector.collect(m)
            
            inicial_sucias=sum(1 for x in range(M) 
                    for y in range(N) 
                    if any(isinstance(c, Celda) 
                    and c.estado == "sucia" 
                    for c in m.grid.get_cell_list_contents([(x, y)])) )
            
            tiempo_hasta_limpio=None
            
            while m.running:
                m.step()
                if tiempo_hasta_limpio is None and m.contar_celdas("sucia")==0:
                    tiempo_hasta_limpio=m.tiempo_actual

            # Recopilado de resultados
            tiempo = m.tiempo_actual
            limpio_flag=(m.contar_celdas("sucia")==0)
            porcentaje = 100 * m.contar_celdas("limpia") / (M * N)
            movimientos = sum(r.movimientos for r in m.robots)
            
            rows.append({
                "num_agentes": num_agentes,
                "M": M,
                "N": N,
                "prob_suciedad": prob_suciedad,
                "rep": rep,
                "seed": seed,
                "tiempo": tiempo,
                "tiempo_hasta_limpio": tiempo_hasta_limpio,
                "limpio": limpio_flag,
                "porcentaje_limpio": porcentaje,
                "movimientos": movimientos,
                "celdas_iniciales_sucias": inicial_sucias
            })
            print(f"Config{num_agentes} agentes, reps {rep} hechas. limpias{limpio_flag}")
            
    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False)
    return df


if __name__ == "__main__":
    
     # ===== EJEMPLO 1: Corrida única con visualización =====
    print("=" * 60)
    print("EJEMPLO 1: Corrida única (10 robots, 10x10, 54 pasos max)")
    print("=" * 60)
    
    modelo = Entorno(num_agentes=10, M=10, N=10, prob_suciedad=0.58, tiempo_max=54, seed=556)
    while modelo.running:
        modelo.step()

    # Extraer datos del modelo
    df_modelo = modelo.datacollector.get_model_vars_dataframe()
    print("\nÚltimas 5 filas de datos del modelo:")
    print(df_modelo.tail())
    print(f"\nMovimientos totales: {sum(r.movimientos for r in modelo.robots)}")
    print(f"Celdas limpias finales: {modelo.contar_celdas('limpia')}/{modelo.M * modelo.N}")

    # Visualización de datos del modelo
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Gráfica 1: Celdas limpias vs sucias
    axes[0].plot(df_modelo.index, df_modelo["Celdas Limpias"], label="Limpias", marker="o")
    axes[0].plot(df_modelo.index, df_modelo["Celdas Sucias"], label="Sucias", marker="x")
    axes[0].set_xlabel("Tiempo (pasos)")
    axes[0].set_ylabel("Número de celdas")
    axes[0].set_title("Evolución de celdas limpias vs sucias")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Gráfica 2: Movimientos totales
    axes[1].plot(df_modelo.index, df_modelo["Movimientos Totales"], label="Movimientos", color="green", marker="s")
    axes[1].set_xlabel("Tiempo (pasos)")
    axes[1].set_ylabel("Movimientos acumulados")
    axes[1].set_title("Movimientos totales de todos los robots")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("visualizacion_ejemplo1.png", dpi=100)
    print("\n✓ Gráficas guardadas en 'visualizacion_ejemplo1.png'")
    plt.show()

    # ===== EJEMPLO 2: Barrido de experimentos con múltiples configuraciones =====
    print("\n" + "=" * 60)
    print("EJEMPLO 2: Barrido experimental (varía número de robots)")
    print("=" * 60)
    
    configs = [
        (1, 10, 10, 0.3, 500),
        (2, 10, 10, 0.3, 500),
        (4, 10, 10, 0.3, 500),
        (8, 10, 10, 0.3, 500)
    ]
    
    df_experimentos = run_experiment(configs, n_repeticiones=5, output_csv="resultados_barrido.csv")
    
    # Resumen por número de agentes
    resumen = df_experimentos.groupby("num_agentes").agg({
        "tiempo": ["mean", "std"],
        "movimientos": ["mean", "std"],
        "porcentaje_limpio": ["mean", "std"]
    }).round(2)
    
    print("\nResumen de experimentos:")
    print(resumen)
    
    # Visualización del barrido
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    
    # Gráfica 1: Tiempo promedio vs número de agentes
    tiempo_mean = df_experimentos.groupby("num_agentes")["tiempo"].mean()
    tiempo_std = df_experimentos.groupby("num_agentes")["tiempo"].std()
    axes[0].bar(tiempo_mean.index, tiempo_mean.values, yerr=tiempo_std.values, capsize=5, alpha=0.7, color="blue")
    axes[0].set_xlabel("Número de robots")
    axes[0].set_ylabel("Tiempo promedio (pasos)")
    axes[0].set_title("Tiempo hasta limpiar vs Número de robots")
    axes[0].grid(True, alpha=0.3, axis="y")
    
    # Gráfica 2: Movimientos promedio vs número de agentes
    mov_mean = df_experimentos.groupby("num_agentes")["movimientos"].mean()
    mov_std = df_experimentos.groupby("num_agentes")["movimientos"].std()
    axes[1].bar(mov_mean.index, mov_mean.values, yerr=mov_std.values, capsize=5, alpha=0.7, color="green")
    axes[1].set_xlabel("Número de robots")
    axes[1].set_ylabel("Movimientos promedio")
    axes[1].set_title("Movimientos vs Número de robots")
    axes[1].grid(True, alpha=0.3, axis="y")
    
    # Gráfica 3: Porcentaje limpio vs número de agentes
    porc_mean = df_experimentos.groupby("num_agentes")["porcentaje_limpio"].mean()
    porc_std = df_experimentos.groupby("num_agentes")["porcentaje_limpio"].std()
    axes[2].bar(porc_mean.index, porc_mean.values, yerr=porc_std.values, capsize=5, alpha=0.7, color="orange")
    axes[2].set_xlabel("Número de robots")
    axes[2].set_ylabel("% de celdas limpias")
    axes[2].set_title("Limpieza final vs Número de robots")
    axes[2].grid(True, alpha=0.3, axis="y")
    
    plt.tight_layout()
    plt.savefig("visualizacion_experimentos.png", dpi=100)
    print("\n✓ Gráficas del barrido guardadas en 'visualizacion_experimentos.png'")
    plt.show() 


