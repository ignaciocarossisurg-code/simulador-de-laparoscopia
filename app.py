import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Configuración visual de la pantalla
st.set_page_config(
    page_title="Simulador Laparoscopía - Seguimiento",
    page_icon="🩺",
    layout="wide"
)

# Conexión con base de datos SQLite interna
def get_db():
    conn = sqlite3.connect("simulacion_laparo.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS alumnos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        comision TEXT,
        nivel TEXT
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS evaluaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alumno_id INTEGER NOT NULL,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ejercicio TEXT NOT NULL,
        tiempo_segundos REAL NOT NULL,
        errores INTEGER DEFAULT 0,
        depth_perception INTEGER NOT NULL,
        bimanual_dexterity INTEGER NOT NULL,
        efficiency INTEGER NOT NULL,
        tissue_handling INTEGER NOT NULL,
        autonomy INTEGER NOT NULL,
        puntaje_goals INTEGER NOT NULL,
        comentarios TEXT,
        FOREIGN KEY (alumno_id) REFERENCES alumnos(id)
    )''')
    c.execute('SELECT COUNT(*) as count FROM alumnos')
    if c.fetchone()['count'] == 0:
        c.execute("INSERT INTO alumnos (nombre, comision, nivel) VALUES ('Dr. Juan Pérez', 'Comisión A', 'Residente 1')")
        c.execute("INSERT INTO alumnos (nombre, comision, nivel) VALUES ('Dra. María González', 'Comisión A', 'Residente 2')")
    conn.commit()
    conn.close()

init_db()

# Carga de datos
def obtener_alumnos():
    conn = get_db()
    df = pd.read_sql_query("SELECT id, nombre, comision, nivel FROM alumnos ORDER BY nombre ASC", conn)
    conn.close()
    return df

def guardar_alumno(nombre, comision, nivel):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO alumnos (nombre, comision, nivel) VALUES (?, ?, ?)", (nombre, comision, nivel))
    conn.commit()
    conn.close()

def guardar_evaluacion(alumno_id, ejercicio, tiempo, errores, depth, bimanual, eff, tissue, auto, comments):
    goals_total = depth + bimanual + eff + tissue + auto
    conn = get_db()
    c = conn.cursor()
    c.execute('''
    INSERT INTO evaluaciones (
        alumno_id, ejercicio, tiempo_segundos, errores,
        depth_perception, bimanual_dexterity, efficiency,
        tissue_handling, autonomy, puntaje_goals, comentarios
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (alumno_id, ejercicio, tiempo, errores, depth, bimanual, eff, tissue, auto, goals_total, comments))
    conn.commit()
    conn.close()

def obtener_evaluaciones(alumno_id, ejercicio):
    conn = get_db()
    query = "SELECT * FROM evaluaciones WHERE alumno_id = ? AND ejercicio = ? ORDER BY id ASC"
    df = pd.read_sql_query(query, conn, params=(alumno_id, ejercicio))
    conn.close()
    return df

# Barra Lateral
st.sidebar.title("🩺 Simulación Quirúrgica")
df_alumnos = obtener_alumnos()

if df_alumnos.empty:
    st.sidebar.warning("No hay alumnos cargados.")
    alumno_id = None
else:
    opciones = {f"{row['nombre']} ({row['nivel']})": row['id'] for _, row in df_alumnos.iterrows()}
    alumno_str = st.sidebar.selectbox("Seleccionar Alumno:", list(opciones.keys()))
    alumno_id = opciones[alumno_str]

ejercicios = [
    "Transferencia de Clavijas (Peg Transfer)",
    "Corte de Patrón Circular (Pattern Cut)",
    "Ligadura con Endoloop",
    "Sutura y Nudo Intracorpóreo"
]
ejercicio_actual = st.sidebar.selectbox("Ejercicio:", ejercicios)

st.sidebar.markdown("---")
with st.sidebar.expander("➕ Cargar Nuevo Alumno"):
    with st.form("form_nuevo_alumno", clear_on_submit=True):
        n_nombre = st.text_input("Nombre y Apellido")
        n_comision = st.text_input("Comisión", value="Comisión A")
        n_nivel = st.selectbox("Nivel", ["Estudiante de Grado", "Adscripto", "Residente 1", "Residente 2", "Fellow"])
        if st.form_submit_button("Guardar"):
            if n_nombre.strip():
                guardar_alumno(n_nombre.strip(), n_comision, n_nivel)
                st.rerun()

# Pantalla Principal
st.title("🎯 Evaluación y Curva de Aprendizaje")

col_form, col_analitica = st.columns([1.1, 1.4], gap="large")

with col_form:
    st.subheader("📋 Registro de Intento")
    with st.form("form_eval", clear_on_submit=False):
        col_t, col_e = st.columns(2)
        with col_t:
            tiempo_seg = st.number_input("Tiempo (segundos):", min_value=1.0, max_value=1200.0, value=95.0, step=1.0)
        with col_e:
            errores = st.number_input("Errores / Caídas:", min_value=0, max_value=50, value=0, step=1)
            
        st.markdown("#### Escala GOALS (1 al 5)")
        depth = st.slider("1. Percepción de Profundidad:", 1, 5, 3)
        bimanual = st.slider("2. Destreza Bimanual:", 1, 5, 3)
        efficiency = st.slider("3. Eficiencia y Economía:", 1, 5, 3)
        tissue = st.slider("4. Manejo de Tejidos:", 1, 5, 3)
        autonomy = st.slider("5. Autonomía:", 1, 5, 4)
        
        st.info(f"**Puntaje GOALS Total:** `{depth + bimanual + efficiency + tissue + autonomy} / 25 pts`")
        comentarios = st.text_area("Observaciones / Feedback:", placeholder="Comentarios del docente...")
        
        if st.form_submit_button("💾 Guardar Intento", use_container_width=True):
            if alumno_id:
                guardar_evaluacion(alumno_id, ejercicio_actual, tiempo_seg, errores, depth, bimanual, efficiency, tissue, autonomy, comentarios)
                st.success("Guardado correctamente.")
                st.rerun()

with col_analitica:
    st.subheader("📈 Progreso y Curva CUSUM")
    if alumno_id:
        df_intentos = obtener_evaluaciones(alumno_id, ejercicio_actual)
        if df_intentos.empty:
            st.warning("Aún no hay intentos registrados para este ejercicio. Guarde el primer intento a la izquierda para ver el gráfico.")
        else:
            total = len(df_intentos)
            mejor_t = df_intentos['tiempo_segundos'].min()
            goals_prom = df_intentos['puntaje_goals'].mean()
            
            benchmarks = {
                "Transferencia de Clavijas (Peg Transfer)": 98.0,
                "Corte de Patrón Circular (Pattern Cut)": 120.0,
                "Ligadura con Endoloop": 60.0,
                "Sutura y Nudo Intracorpóreo": 140.0
            }
            meta_t = benchmarks.get(ejercicio_actual, 100.0)
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Intentos", f"{total}")
            k2.metric("Mejor Tiempo", f"{mejor_t:.1f} s")
            k3.metric("GOALS Prom.", f"{goals_prom:.1f}/25")
            
            # Criterio de competencia (últimos 2 intentos dentro de la meta de tiempo y GOALS >= 21)
            ultimos_2 = df_intentos.tail(2)
            if len(ultimos_2) >= 2 and (ultimos_2['tiempo_segundos'] <= meta_t).all() and (ultimos_2['puntaje_goals'] >= 21).all():
                k4.success("🌟 COMPETENTE")
            else:
                k4.info("🔄 En Formación")
            
            # Gráfico CUSUM
            df_intentos['exito'] = (df_intentos['tiempo_segundos'] <= meta_t) & (df_intentos['puntaje_goals'] >= 21)
            cusum = []
            acc = 0
            for ex in df_intentos['exito']:
                acc += 0.5 if ex else -1.0
                cusum.append(acc)
            
            df_intentos['intento'] = range(1, total + 1)
            df_intentos['cusum'] = cusum
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_intentos['intento'], y=df_intentos['cusum'], mode='lines+markers', name='CUSUM', line=dict(color='#1E88E5', width=3)))
            fig.add_hline(y=3.0, line_dash="dash", line_color="green", annotation_text="Meta de Competencia")
            fig.update_layout(title="Curva de Aprendizaje Acumulativa (CUSUM)", xaxis_title="Intento", yaxis_title="Puntaje", height=320, template="plotly_white", margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("Ver tabla con todos los intentos"):
                st.dataframe(df_intentos[['id', 'fecha', 'tiempo_segundos', 'errores', 'puntaje_goals', 'comentarios']], use_container_width=True)