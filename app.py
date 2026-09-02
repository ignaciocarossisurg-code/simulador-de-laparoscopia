import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import subprocess
import sys

# ==========================================
# CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(
    page_title="Simulador Laparoscópico Quirúrgico",
    page_icon="🩺",
    layout="wide"
)

# ==========================================
# BASE DE DATOS SQLITE
# ==========================================
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
        distancia_izq REAL DEFAULT 0,
        distancia_der REAL DEFAULT 0,
        distancia_total REAL DEFAULT 0,
        ratio_bimanual REAL DEFAULT 1.0,
        depth_perception INTEGER DEFAULT 4,
        bimanual_dexterity INTEGER DEFAULT 4,
        efficiency INTEGER DEFAULT 4,
        tissue_handling INTEGER DEFAULT 4,
        autonomy INTEGER DEFAULT 4,
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

# ==========================================
# GESTIÓN DE DATOS
# ==========================================
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

def reiniciar_intentos_alumno(alumno_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM evaluaciones WHERE alumno_id = ?", (alumno_id,))
    conn.commit()
    conn.close()

def guardar_intento_manual(alumno_id, ejercicio, t, err, goals, comments):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
    INSERT INTO evaluaciones (
        alumno_id, ejercicio, tiempo_segundos, errores,
        distancia_izq, distancia_der, distancia_total, ratio_bimanual,
        puntaje_goals, comentarios
    ) VALUES (?, ?, ?, ?, 0, 0, 0, 1.0, ?, ?)
    ''', (alumno_id, ejercicio, t, err, goals, comments))
    conn.commit()
    conn.close()

def obtener_evaluaciones(alumno_id, ejercicio):
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM evaluaciones WHERE alumno_id = ? AND ejercicio = ? ORDER BY id ASC", conn, params=(alumno_id, ejercicio))
    conn.close()
    return df

# ==========================================
# BARRA LATERAL
# ==========================================
st.sidebar.title("🩺 Simulación Quirúrgica")
df_alumnos = obtener_alumnos()

if df_alumnos.empty:
    st.sidebar.warning("No hay alumnos.")
    alumno_id = None
else:
    opciones = {f"{r['nombre']} ({r['nivel']})": r['id'] for _, r in df_alumnos.iterrows()}
    alumno_str = st.sidebar.selectbox("Seleccionar Alumno:", list(opciones.keys()))
    alumno_id = opciones[alumno_str]

ejercicios = [
    "Transferencia de Clavijas (Peg Transfer)",
    "Corte de Patrón Circular (Pattern Cut)",
    "Ligadura con Endoloop",
    "Sutura y Nudo Intracorpóreo"
]
ejercicio_actual = st.sidebar.selectbox("Ejercicio en Curso:", ejercicios)

st.sidebar.markdown("---")
with st.sidebar.expander("➕ Cargar Nuevo Alumno"):
    with st.form("f_nuevo"):
        n_nom = st.text_input("Nombre y Apellido")
        n_com = st.text_input("Comisión", value="Comisión A")
        n_niv = st.selectbox("Nivel", ["Estudiante de Grado", "Adscripto", "Residente 1", "Residente 2", "Fellow"])
        if st.form_submit_button("Guardar"):
            if n_nom.strip():
                guardar_alumno(n_nom.strip(), n_com, n_niv)
                st.rerun()

with st.sidebar.expander("⚙️ Gestión de Alumno"):
    if alumno_id:
        if st.button("🗑️ Reiniciar intentos de este alumno", use_container_width=True):
            reiniciar_intentos_alumno(alumno_id)
            st.sidebar.success("Historial reiniciado.")
            st.rerun()

# ==========================================
# CUERPO PRINCIPAL
# ==========================================
st.title("🎯 Evaluación y Curvas de Aprendizaje Laparoscópico")

col_izq, col_der = st.columns([1.1, 1.4], gap="large")

# ----------------------------------------------------
# COLUMNA IZQUIERDA: CÁMARA NATIVA
# ----------------------------------------------------
with col_izq:
    st.subheader("📹 Captura de Ejercicio")
    
    st.markdown("##### Opción A: Registro por Cámara en Vivo")
    st.info("Al presionar el botón se abrirá la ventana de video nativa de alta fluidez. Presioná **'q'** o tocá el botón rojo en pantalla con la pinza para terminar.")

    if st.button("🎥 Iniciar Sesión con Cámara", use_container_width=True, type="primary"):
        with st.spinner("Cámara activa. Realizando tracking en vivo..."):
            # Lanza tracker.py en el hilo principal del sistema
            proceso = subprocess.run([sys.executable, "tracker.py", str(alumno_id), ejercicio_actual])
            st.success("✅ Intento finalizado y guardado en la base de datos.")
            st.rerun()

    st.markdown("---")
    st.markdown("##### Opción B: Carga Manual (Docente)")
    with st.form("form_manual"):
        c_t, c_e = st.columns(2)
        with c_t:
            t_man = st.number_input("Tiempo (segundos):", value=90.0, step=1.0)
        with c_e:
            e_man = st.number_input("Errores / Caídas:", value=0, step=1)
        g_man = st.slider("Puntaje GOALS Total (5 a 25):", 5, 25, 20)
        obs_man = st.text_area("Observaciones del evaluador:", placeholder="Comentarios...")
        if st.form_submit_button("💾 Guardar Manualmente", use_container_width=True):
            guardar_intento_manual(alumno_id, ejercicio_actual, t_man, e_man, g_man, obs_man)
            st.success("Guardado.")
            st.rerun()

# ----------------------------------------------------
# COLUMNA DERECHA: DASHBOARD Y CURVAS
# ----------------------------------------------------
with col_der:
    st.subheader("📈 Desempeño y Métricas Cinemáticas")
    if alumno_id:
        df_intentos = obtener_evaluaciones(alumno_id, ejercicio_actual)
        if df_intentos.empty:
            st.warning("Sin intentos registrados para este ejercicio.")
        else:
            total = len(df_intentos)
            mejor_t = df_intentos['tiempo_segundos'].min()
            mejor_dist = df_intentos[df_intentos['distancia_total'] > 0]['distancia_total'].min() if (df_intentos['distancia_total'] > 0).any() else 0
            
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
            k3.metric("Mejor Trayectoria", f"{int(mejor_dist)} px" if mejor_dist > 0 else "N/A")
            
            ultimos_2 = df_intentos.tail(2)
            if len(ultimos_2) >= 2 and (ultimos_2['tiempo_segundos'] <= meta_t).all() and (ultimos_2['puntaje_goals'] >= 21).all():
                k4.success("🌟 COMPETENTE")
            else:
                k4.info("🔄 En Formación")
            
            tab1, tab2, tab3 = st.tabs(["📊 Curva CUSUM", "📏 Economía de Movimiento", "📋 Historial"])
            
            with tab1:
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
                fig.update_layout(title="Curva CUSUM (Suma Acumulativa)", xaxis_title="Intento", yaxis_title="Puntaje", height=300, template="plotly_white", margin=dict(l=10, r=10, t=35, b=10))
                st.plotly_chart(fig, use_container_width=True)
                
            with tab2:
                fig_dist = go.Figure()
                fig_dist.add_trace(go.Bar(x=df_intentos['intento'], y=df_intentos['distancia_izq'], name='Mano Izq (px)', marker_color='#4CAF50'))
                fig_dist.add_trace(go.Bar(x=df_intentos['intento'], y=df_intentos['distancia_der'], name='Mano Der (px)', marker_color='#2196F3'))
                fig_dist.update_layout(barmode='stack', title="Distancia Recorrida por Mano (Trayectoria)", xaxis_title="Intento", yaxis_title="Píxeles", height=300, template="plotly_white", margin=dict(l=10, r=10, t=35, b=10))
                st.plotly_chart(fig_dist, use_container_width=True)
                
            with tab3:
                cols = ['id', 'fecha', 'tiempo_segundos', 'distancia_izq', 'distancia_der', 'distancia_total', 'ratio_bimanual', 'puntaje_goals', 'comentarios']
                st.dataframe(df_intentos[cols], use_container_width=True)