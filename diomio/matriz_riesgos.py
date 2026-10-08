import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd

class GestorRiesgosEticos:
    def __init__(self, db_manager):
        self.db = db_manager

    def agregar_riesgo(self, modulo, descripcion, categoria, probabilidad, impacto, mitigacion, residual):
        return self.db.guardar_riesgo(modulo, descripcion, categoria, probabilidad, impacto, mitigacion, residual)

    def obtener_lista_riesgos(self):
        return self.db.obtener_riesgos()

    def generar_grafico_matriz(self, parent_frame):
        """Genera y empaqueta la gráfica Matplotlib dentro de un contenedor Tkinter"""
        riesgos = self.obtener_lista_riesgos()
        
        fig, ax = plt.subplots(figsize=(5.5, 4.2), dpi=100)
        fig.patch.set_facecolor('#2b2b2b') # Fondo oscuro coincidente con CustomTkinter
        ax.set_facecolor('#1e1e1e')

        if riesgos:
            df = pd.DataFrame(riesgos)
            # Dibujar puntos
            ax.scatter(
                df['probabilidad'], 
                df['impacto'], 
                s=df['puntaje_inicial'] * 60, 
                c=df['puntaje_inicial'], 
                cmap='Reds', 
                edgecolors='white',
                alpha=0.85
            )
            
            # Etiquetar puntos
            for idx, row in df.iterrows():
                ax.annotate(
                    f"R{idx+1}", 
                    (row['probabilidad'], row['impacto']),
                    xytext=(5, 5), textcoords='offset points',
                    color='white', fontsize=9, fontweight='bold'
                )

        ax.set_xlim(0.5, 5.5)
        ax.set_ylim(0.5, 5.5)
        ax.set_xticks([1, 2, 3, 4, 5])
        ax.set_yticks([1, 2, 3, 4, 5])
        ax.set_xlabel('Probabilidad (1-5)', color='white', fontsize=10)
        ax.set_ylabel('Impacto (1-5)', color='white', fontsize=10)
        ax.set_title('Matriz de Riesgos Éticos y Operativos (Impacto vs Probabilidad)', color='white', fontsize=11, fontweight='bold')
        ax.tick_params(colors='white')
        
        # Sombra de cuadrícula
        ax.grid(True, color='#444444', linestyle='--', alpha=0.5)

        # Ajuste estético
        plt.tight_layout()

        # Renderizar en Tkinter
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        return canvas.get_tk_widget()