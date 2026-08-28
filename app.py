import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import cv2
import time
import math
from collections import deque

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

def guardar_intento(alumno_id, ejercicio, t, err, d_izq, d_der, d_tot, ratio, goals, comments):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
    INSERT INTO evaluaciones (
        alumno_id, ejercicio, tiempo_segundos, errores,
        distancia_izq, distancia_der, distancia_total, ratio_bimanual,
        puntaje_goals, comentarios
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (alumno_id, ejercicio, t, err, d_izq, d_der, d_tot, ratio, goals, comments))
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
    alumno_str = ""
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

# ==========================================
# CUERPO PRINCIPAL
# ==========================================
st.title("🎯 Evaluación y Curvas de Aprendizaje Laparoscópico")

col_izq, col_der = st.columns([1.1, 1.4], gap="large")

# ----------------------------------------------------
# COLUMNA IZQUIERDA: CÁMARA Y TRACKING
# ----------------------------------------------------
with col_izq:
    st.subheader("📹 Captura de Ejercicio")
    
    st.markdown("##### Opción A: Registro por Cámara en Vivo")
    st.caption("ℹ️ *Para finalizar el ejercicio sin demoras: pasá la punta de la pinza por el botón rojo superior derecho del video o presioná el botón web abajo.*")

    if "grabando" not in st.session_state:
        st.session_state.grabando = False

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("▶️ Iniciar Cámara", use_container_width=True, type="primary", disabled=st.session_state.grabando):
            st.session_state.grabando = True
            st.session_state.tiempo_arranque = time.time()
            st.rerun()

    with col_btn2:
        btn_detener_web = st.button("⏹️ Finalizar y Guardar", use_container_width=True, disabled=not st.session_state.grabando)

    frame_placeholder = st.empty()

    if st.session_state.grabando:
        VERDE_BAJO = np.array([35, 80, 80])
        VERDE_ALTO = np.array([85, 255, 255])
        AZUL_BAJO = np.array([95, 100, 100])
        AZUL_ALTO = np.array([135, 255, 255])

        puntos_izq = deque(maxlen=32)
        puntos_der = deque(maxlen=32)
        dist_izq = 0.0
        dist_der = 0.0
        ult_izq = None
        ult_der = None

        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        t_inicio = st.session_state.get("tiempo_arranque", time.time())
        tiempo_sobre_boton = 0

        # Coordenadas del botón interactivo superior derecho (x: 480 a 630, y: 10 a 60)
        BTN_X1, BTN_Y1, BTN_X2, BTN_Y2 = 470, 10, 630, 60

        while st.session_state.grabando:
            ret, frame = cap.read()
            if not ret:
                break

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # 1. Tracking Verde (Izquierda)
            mask_v = cv2.inRange(hsv, VERDE_BAJO, VERDE_ALTO)
            mask_v = cv2.erode(mask_v, None, iterations=1)
            mask_v = cv2.dilate(mask_v, None, iterations=1)
            cnts_v, _ = cv2.findContours(mask_v, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            c_izq = None
            if len(cnts_v) > 0:
                c = max(cnts_v, key=cv2.contourArea)
                if cv2.contourArea(c) > 80:
                    ((x, y), _) = cv2.minEnclosingCircle(c)
                    c_izq = (int(x), int(y))
                    cv2.circle(frame, c_izq, 6, (0, 255, 0), -1)
                    cv2.putText(frame, "Izq", (c_izq[0] + 8, c_izq[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                    if ult_izq is not None:
                        dist_izq += math.hypot(c_izq[0] - ult_izq[0], c_izq[1] - ult_izq[1])
                    ult_izq = c_izq
            puntos_izq.appendleft(c_izq)

            # 2. Tracking Azul (Derecha)
            mask_a = cv2.inRange(hsv, AZUL_BAJO, AZUL_ALTO)
            mask_a = cv2.erode(mask_a, None, iterations=1)
            mask_a = cv2.dilate(mask_a, None, iterations=1)
            cnts_a, _ = cv2.findContours(mask_a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            c_der = None
            if len(cnts_a) > 0:
                c = max(cnts_a, key=cv2.contourArea)
                if cv2.contourArea(c) > 80:
                    ((x, y), _) = cv2.minEnclosingCircle(c)
                    c_der = (int(x), int(y))
                    cv2.circle(frame, c_der, 6, (255, 0, 0), -1)
                    cv2.putText(frame, "Der", (c_der[0] + 8, c_der[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
                    if ult_der is not None:
                        dist_der += math.hypot(c_der[0] - ult_der[0], c_der[1] - ult_der[1])
                    ult_der = c_der
            puntos_der.appendleft(c_der)

            # Estelas de movimiento
            for i in range(1, len(puntos_izq)):
                if puntos_izq[i - 1] and puntos_izq[i]:
                    cv2.line(frame, puntos_izq[i - 1], puntos_izq[i], (0, 255, 0), 2)
            for i in range(1, len(puntos_der)):
                if puntos_der[i - 1] and puntos_der[i]:
                    cv2.line(frame, puntos_der[i - 1], puntos_der[i], (255, 0, 0), 2)

            t_actual = round(time.time() - t_inicio, 1)

            # 3. Panel de métricas superior izquierdo
            cv2.rectangle(frame, (10, 10), (250, 95), (0, 0, 0), -1)
            cv2.putText(frame, f"Tiempo: {t_actual} s", (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, f"Dist. Izq: {int(dist_izq)} px", (20, 57), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(frame, f"Dist. Der: {int(dist_der)} px", (20, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 100), 1)

            # 4. Botón interactivo superior derecho en pantalla
            pinza_en_boton = False
            for pt in [c_izq, c_der]:
                if pt and (BTN_X1 <= pt[0] <= BTN_X2) and (BTN_Y1 <= pt[1] <= BTN_Y2):
                    pinza_en_boton = True
                    break

            if pinza_en_boton:
                tiempo_sobre_boton += 1
                color_boton = (0, 255, 0) # Verde al activarse
            else:
                tiempo_sobre_boton = 0
                color_boton = (0, 0, 255) # Rojo en reposo

            cv2.rectangle(frame, (BTN_X1, BTN_Y1), (BTN_X2, BTN_Y2), color_boton, -1)
            cv2.rectangle(frame, (BTN_X1, BTN_Y1), (BTN_X2, BTN_Y2), (255, 255, 255), 2)
            cv2.putText(frame, "FINALIZAR", (BTN_X1 + 18, BTN_Y1 + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)

            # Cierre automático si toca el botón en pantalla (~15 cuadros) o botón web
            if tiempo_sobre_boton >= 15 or btn_detener_web:
                st.session_state.grabando = False
                cap.release()
                
                t_fin = max(round(time.time() - t_inicio, 1), 1.0)
                d_tot = round(dist_izq + dist_der, 1)
                ratio = round(dist_izq / dist_der, 2) if dist_der > 0 else 1.0
                goals_auto = 22 if (t_fin <= 100 and d_tot < 4000) else (18 if t_fin <= 140 else 14)
                
                guardar_intento(
                    alumno_id, ejercicio_actual, t_fin, 0,
                    round(dist_izq, 1), round(dist_der, 1), d_tot, ratio, goals_auto,
                    f"Tracking cinemático. Total: {int(d_tot)}px | Ratio: {ratio}"
                )
                st.success(f"✅ Ejercicio Finalizado: {t_fin} segundos | Distancia Total: {int(d_tot)}px")
                time.sleep(1)
                st.rerun()
                break

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
            guardar_intento(alumno_id, ejercicio_actual, t_man, e_man, 0, 0, 0, 1.0, g_man, obs_man)
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
                cols = ['id', 'fecha', 'tiempo_segundos', 'distancia_total', 'ratio_bimanual', 'puntaje_goals', 'comentarios']
                st.dataframe(df_intentos[cols], use_container_width=True)