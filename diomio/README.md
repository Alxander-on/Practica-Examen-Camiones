# LogiSmart

Aplicación de escritorio en español para evaluación de accesos, clasificación de
incidentes, consulta explicativa RAG y registro de riesgos éticos. La interfaz
principal usa una barra lateral, tema oscuro y acentos verdes.

## Inicio

1. Instala Python 3.10 o posterior y MongoDB local o Atlas.
2. Copia `.env.example` como `.env` y sustituye el marcador de contraseña en
   `MONGODB_URI` por la contraseña vigente de Atlas. El ejemplo está preparado
   para `utvt.qqqotrr.mongodb.net`, base `Alexander-D73` y colección de bitácora
   `actividad`. Las demás funciones usan además las colecciones independientes
   `camiones`, `incidentes`, `riesgos_eticos` y `evaluaciones_llm`. No guardes
   credenciales en el código ni publiques el archivo `.env`.
3. Instala dependencias: `python -m pip install -r requirements.txt`.
4. Instala/ejecuta Ollama y descarga el modelo elegido, por ejemplo:
   `ollama pull llama3.2`.
5. Inicia la suite: `python main.py`. El tutor introductorio se ejecuta también
   por separado con `python p02primertutor_llm.py`.

La aplicación se puede abrir sin servicios disponibles; muestra el estado de
MongoDB y los errores de conexión en la GUI. MongoDB es necesario para guardar y
recuperar datos. Ollama es opcional para clasificación (hay respaldo por reglas)
y para respuestas generativas. La conexión se puede probar y cambiar durante
la sesión desde Configuración.

`UMBRAL_REVISION` controla desde qué prioridad se exige revisión humana
(`BAJA`, `MEDIA`, `ALTA` o `CRITICA`). `MODO_SIMULACION_CORREO=true` desactiva
las llamadas al LLM para la clasificación de correos y usa exclusivamente reglas.

## Capas y colecciones

- `main.py`: navegación e interacción GUI; trabajo de red en hilos y cambios de
  widgets en el hilo de Tk.
- `conexion_db.py`: persistencia MongoDB, CRUD, historial de estados y
  agregación semanal.
- `motor_reglas.py`: reglas proposicionales y explicaciones.
- `clasificador_hibrido.py`: reglas, JSON validado con Pydantic, reintento,
  respaldo y comparación de 30 correos etiquetados.
- `asistente_rag.py`: recupera primero registros en MongoDB y después pide una
  respuesta acotada al contexto.
- `p02primertutor_llm.py`: primera práctica, tutor con prompt configurable e
  historial resumible.

Colecciones: `camiones` (ID, placa, empresa, autorización y certificación),
`accesos` (premisas P/Q/R/S/C/M/H, resultados, explicación, operador y fecha),
`incidentes` (correo, clasificación, datos, estado e historial),
`riesgos_eticos` (descripción, probabilidad, impacto, mitigación, puntaje
residual e histórico) y `evaluaciones_llm` (prompt, resultado, modelo, latencia
y coincidencia con reglas). Se cargan camiones, una decisión de inspección y un
incidente de demostración para CAM-102, además de riesgos éticos, solo cuando
las colecciones correspondientes están vacías.

## Reglas de acceso

- Base: `A = P ∧ S ∧ ¬Q`; `E = P ∧ (R ∨ Q)`.
- R3: el acceso normal requiere certificación vigente (`C`).
- R4: material peligroso en horario restringido (`M ∧ H`) bloquea el acceso
  normal y requiere inspección.
- Certificación vencida también bloquea el acceso normal y fuerza inspección.

`tablas_verdad.py` imprime la tabla base completa y las tablas de las
ampliaciones R3/R4. Las extensiones son deliberadamente explícitas y auditables.

## Evaluación y riesgos

En Incidentes, el botón **Evaluar 30 correos** calcula exactitud por categoría,
matriz de confusión y latencia para reglas, LLM e híbrido. Los resultados LLM
dependen del modelo y de Ollama disponible; no se presentan como mediciones si
el servicio/modelo no responde (aparecen como no disponibles, no como cero).
La muestra incluida es un conjunto demostrativo fijo: sus resultados no miden
generalización a correos reales ni sustituyen una evaluación externa. La matriz
gráfica muestra probabilidad/impacto y cada
riesgo conserva el puntaje residual introducido después de mitigación.

El asistente cita la colección e identificador de cada registro recuperado y no
consulta Ollama cuando MongoDB no tiene datos coincidentes. Las preguntas de
conteo de camiones se responden con un conteo directo de la colección
`camiones`. La instrucción de contexto reduce el riesgo de alucinación, pero no
sustituye la revisión humana. Las preguntas por detalles de los camiones
devuelven directamente los registros de esa colección; si Ollama agota el
tiempo de espera tras recuperar contexto, se muestran los registros encontrados
junto con el error técnico.
Los resultados automatizados son apoyo al operador, no una decisión autónoma de
seguridad.

## Pruebas

Ejecuta las pruebas de lógica sin servicios externos:

```powershell
python -m unittest discover -s tests -v
```

La conexión real a MongoDB y Ollama se verifica desde Configuración y desde las
funciones de la GUI.
