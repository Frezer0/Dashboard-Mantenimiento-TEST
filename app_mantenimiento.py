import streamlit as st
import pandas as pd
import re
import plotly.express as px
import os
from datetime import datetime
import extra_streamlit_components as stx

import sqlalchemy  # DB Sql Progress
from sqlalchemy import text # para ejecutar SQL directo

DATABASE_URL = os.getenv("DATABASE_URL")

# =====================================================================
# CONSTANTES DE NEGOCIO — PRIORIDADES
# =====================================================================
# Mapeo de prioridad numérica (IW38/OMs) a texto unificado (igual que IW28/Avisos)
MAPEO_PRIORIDAD_OM = {
    1.0: '1 Muy Alta',
    5.0: '1 Muy Alta',
    6.0: '2 Alta',
    7.0: '3 Media',
    8.0: '4 Baja',
}

# Orden canónico para el filtro de prioridad
ORDEN_PRIORIDADES = ['1 Muy Alta', '2 Alta', '3 Media', '4 Baja', 'Programable', 'Urgencia', 'Emergencia']

def sort_prioridades(opciones: list) -> list:
    """Ordena las prioridades según el orden definido por el cliente."""
    def key_fn(p):
        try:
            return ORDEN_PRIORIDADES.index(p)
        except ValueError:
            return len(ORDEN_PRIORIDADES)  # desconocidas al final
    return sorted(opciones, key=key_fn)


@st.cache_data(ttl=60)
def cargar_datos():
    try:
        engine = sqlalchemy.create_engine(DATABASE_URL)
        avisos_df = pd.read_sql("SELECT * FROM avisos", engine)
        oms_df = pd.read_sql("SELECT * FROM oms", engine)
        
        columnas_clave = [
            'Centro emplazamiento', 'Grupo planificación', 'Denominación de la ubicación técnica', 
            'Status del sistema', 'Texto para prioridad', 'Prioridad', 
            'Tota general (plan)', 'Costes tot.reales', 'Creado el'
        ]
        
        for df in [avisos_df, oms_df]:
            if not df.empty:
                df.columns = df.columns.str.strip() # Limpiar espacios ocultos
                mapa = {c.lower(): cc for c in df.columns for cc in columnas_clave if c.lower() == cc.lower()}
                df.rename(columns=mapa, inplace=True)
                
        return avisos_df, oms_df
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

# =====================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTÉTICA QLIK SENSE
# =====================================================================
st.set_page_config(page_title="Gestión de Avisos PPCM", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    /* Ocultar elementos predeterminados de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Fondo principal y contenedor */
    .stApp {
        background-color: #F5F5F5;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 98%;
    }

    /* Cajas de filtros multiselect (Simulación Qlik) */
    div[data-testid="stMultiSelect"] {
        background-color: #FFFFFF;
        border: 1px solid #D9D9D9;
        border-radius: 2px;
        padding: 5px;
    }
    div[data-testid="stMultiSelect"] label {
        font-size: 0.8rem;
        color: #555555;
        text-transform: uppercase;
        font-weight: 700;
    }

    /* Tarjetas de Métricas (KPIs QLIK) */
    div[data-testid="metric-container"] {
        background-color: #FFFFFF;
        border: 1px solid #D9D9D9;
        border-radius: 2px;
        padding: 15px 10px;
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        box-shadow: 0px 1px 3px rgba(0,0,0,0.05);
    }
    div[data-testid="metric-container"] label {
        color: #666666;
        font-size: 0.85rem;
        font-weight: 600;
    }
    div[data-testid="metric-container"] div {
        color: #006580 !important; /* Color Teal Qlik */
        font-size: 2.2rem !important;
        font-weight: 400;
    }

    /* Estilo para las pestañas de Streamlit */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #FFFFFF;
        border-bottom: 1px solid #D9D9D9;
        padding-left: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #555555;
        font-weight: 600;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    
    /* Contenedores blancos para gráficos */
    .qlik-container {
        background-color: #FFFFFF;
        border: 1px solid #D9D9D9;
        border-radius: 2px;
        padding: 15px;
        margin-bottom: 15px;
    }
    span[data-baseweb="tag"] {
        background-color: #EFEFEF !important; /* Fondo gris muy suave */
        color: #444444 !important;            /* Texto oscuro */
        border: 1px solid #E0E0E0 !important; /* Borde apenas visible */
        border-radius: 4px !important;        /* Bordes ligeramente redondeados */
        font-weight: 400 !important;
    }
    
    /* Cambiar el color del ícono "X" para cerrar el tag */
    span[data-baseweb="tag"] span[role="button"] {
        color: #666666 !important;
    }
    span[data-baseweb="tag"] span[role="button"]:hover {
        background-color: transparent !important;
        color: #000000 !important; /* Se oscurece un poco al pasar el mouse */
    }
    span[data-baseweb="tag"] svg {
        fill: #888888 !important;
    }
    /* =======================================================
       ESTILOS PREMIUM PARA LA BARRA LATERAL (SIDEBAR)
       ======================================================= */
    /* Fondo limpio para la barra lateral */
    [data-testid="stSidebar"] {
        background-color: #FAFAFA !important;
        border-right: 1px solid #E5E7EB !important;
    }

    /* Tarjeta de Usuario Minimalista */
    .user-card {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 14px;
        margin-bottom: 8px;
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 6px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        font-size: 0.88rem;
        color: #374151;
        transition: all 0.2s ease;
    }

    /* Tarjeta para el Usuario Actual */
    .user-card-you {
        border-left: 3px solid #006580 !important;
        background-color: #F0F9FA !important;
    }

    .user-info {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    /* Punto verde con brillo suave (Efecto En Línea) */
    .status-dot {
        width: 8px;
        height: 8px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
        display: inline-block;
    }

    /* Badge "Tú" */
    .badge-you {
        font-size: 0.68rem;
        font-weight: 700;
        color: #006580;
        background: #E0F2FE;
        padding: 2px 8px;
        border-radius: 12px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Estilo elegante para el botón de Cerrar Sesión en la Sidebar */
    [data-testid="stSidebar"] button {
        border: 1px solid #D1D5DB !important;
        background-color: #FFFFFF !important;
        color: #4B5563 !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
        padding: 6px 12px !important;
        transition: all 0.2s ease !important;
    }

    [data-testid="stSidebar"] button:hover {
        border-color: #EF4444 !important;
        color: #EF4444 !important;
        background-color: #FEF2F2 !important;
    }
    
    </style>
""", unsafe_allow_html=True)

# =====================================================================
# SISTEMA DE SESIÓN (IDENTIFICACIÓN DE USUARIOS - CON COOKIES)
# =====================================================================

# Inicializar el administrador de cookies
cookie_manager = stx.CookieManager()

# Intentar leer el usuario desde las cookies del navegador
usuario_cookie = cookie_manager.get(cookie="usuario_mantenimiento")

if "usuario_activo" not in st.session_state:
    st.session_state.usuario_activo = usuario_cookie

# Pantalla de Login (Si no hay sesión en memoria ni en cookies)
if st.session_state.usuario_activo is None:
    st.markdown("<h2 style='text-align: center; color: #006580; margin-top: 100px;'>Portal de Análisis PPCM</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("🔒 Por favor, identifíquese para acceder a la aplicación de análisis.")
        
        with st.form("form_login"):
            nombre_input = st.text_input("Nombre del Usuario:")
            btn_ingresar = st.form_submit_button("Ingresar", use_container_width=True)
            
            if btn_ingresar:
                if nombre_input.strip():
                    # Guardar en Session State
                    st.session_state.usuario_activo = nombre_input.strip()
                    
                    # Guardar en Cookie (dura 1 día)
                    cookie_manager.set("usuario_mantenimiento", nombre_input.strip(), max_age=86400)
                    
                    st.rerun()
                else:
                    st.error("Debe ingresar un nombre válido.")
    st.stop()
    
# =====================================================================
# SISTEMA DE PRESENCIA (QUIÉN ESTÁ EN LÍNEA)
# =====================================================================
if st.session_state.usuario_activo:
    try:
        engine = sqlalchemy.create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # 1. Crear tabla si no existe
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS usuarios_activos (
                    nombre VARCHAR(100) PRIMARY KEY,
                    ultimo_acceso TIMESTAMP
                )
            """))
            
            # 2. Actualizar el "último acceso" del usuario actual (Upsert)
            conn.execute(text("""
                INSERT INTO usuarios_activos (nombre, ultimo_acceso) 
                VALUES (:usr, CURRENT_TIMESTAMP)
                ON CONFLICT (nombre) 
                DO UPDATE SET ultimo_acceso = CURRENT_TIMESTAMP
            """), {"usr": st.session_state.usuario_activo})
            
            # 3. Leer quiénes han estado activos en los últimos 5 minutos
            result = conn.execute(text("""
                SELECT nombre FROM usuarios_activos 
                WHERE ultimo_acceso >= NOW() - INTERVAL '5 minutes'
            """))
            usuarios_en_linea = [row[0] for row in result]
            conn.commit() # Guardamos los cambios
            
    except Exception as e:
        usuarios_en_linea = [st.session_state.usuario_activo]
        # st.toast(f"Error en presencia: {e}") # Opcional por si quieres ver fallos

# =====================================================================
# FUNCIONES BASE Y REGLAS DE NEGOCIO
# =====================================================================
def asignar_programador(row):
    grupo = row.get('Grupo planificación')
    centro = str(row.get('Centro emplazamiento', '')).strip().upper()
    ubicacion = str(row.get('Denominación de la ubicación técnica', '')).upper()
    
    try: 
        grupo = int(float(grupo)) 
    except: 
        pass
    
    # --- LÓGICA REFINADA: Fernando Correa por Centro ---
    if grupo == 200:
        if centro == 'BCF1':
            return 'Fernando Correa | Arauco'
        elif centro == 'FCF1':
            return 'Fernando Correa | Chillán'
        else:
            return 'Fernando Correa | Otros'
    # ---------------------------------------------------
    
    elif grupo == 100:
        if centro == 'FCF1': 
            return 'Miguel Arevalos'
        elif centro == 'BCF1':
            if re.search(r'\b(16|17|18|19|47|48|49|50)\b', ubicacion): 
                return 'Jonathan Mercado'
            elif re.search(r'\b(12|13|14|15|45|46|51)\b', ubicacion) or 'C.COMB' in ubicacion: 
                return 'Gerardo Jerez'
                
    return 'Otro / Sin Asignar'

def asignar_zona(centro):
    centro = str(centro).strip().upper()
    if centro == 'BCF1': return 'ARAUCO'
    elif centro == 'FCF1': return 'CHILLAN'
    else: return 'OTRAS'

def extraer_status_objetivo(status_str):
    status_str = str(status_str).upper()
    if 'ORAS' in status_str: return 'METR ORAS'
    if 'METR' in status_str: return 'METR'
    if 'MEAB' in status_str: return 'MEAB'
    if 'MECE' in status_str: return 'MECE'
    if 'MAEN' in status_str: return 'MAEN'
    return 'OTRO STATUS'



# =====================================================================
# DB  
# ===================================================================== 

@st.dialog("🔄 Cargar Archivos SAP a la Nube")
def modal_actualizar():
    st.write("Cargue los reportes base (IW28 e IW38). Se actualizarán para todos los usuarios en tiempo real.")
    arch_avisos = st.file_uploader("Avisos IW28 (.xlsx)", type=["xlsx"])
    arch_oms = st.file_uploader("OMs IW38 (.xlsx)", type=["xlsx"])
    
    if st.button("Guardar en Base de Datos", use_container_width=True):
        try:
            engine = sqlalchemy.create_engine(DATABASE_URL)
            act = False
            
            if arch_avisos:
                df_av = pd.read_excel(arch_avisos)
                # Guardamos directamente en la tabla 'avisos' de PostgreSQL (reemplazando la anterior)
                df_av.to_sql('avisos', engine, if_exists='replace', index=False)
                act = True
                
            if arch_oms:
                df_om = pd.read_excel(arch_oms)
                # Guardamos directamente en la tabla 'oms' de PostgreSQL (reemplazando la anterior)
                df_om.to_sql('oms', engine, if_exists='replace', index=False)
                act = True
                
            if act:
                st.cache_data.clear()
                st.success("¡Datos actualizados en la nube con éxito!")
                st.rerun()
        except Exception as e:
            st.error(f"Error al conectar con la base de datos: {e}")

# =====================================================================
# SISTEMA DE PRESENCIA EN DB (INVISIBLE)
# =====================================================================
usuarios_en_linea = []
if st.session_state.usuario_activo:
    try:
        engine = sqlalchemy.create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS usuarios_activos (
                    nombre VARCHAR(100) PRIMARY KEY,
                    ultimo_acceso TIMESTAMP
                )
            """))
            conn.execute(text("""
                INSERT INTO usuarios_activos (nombre, ultimo_acceso) 
                VALUES (:usr, CURRENT_TIMESTAMP)
                ON CONFLICT (nombre) 
                DO UPDATE SET ultimo_acceso = CURRENT_TIMESTAMP
            """), {"usr": st.session_state.usuario_activo})
            
            result = conn.execute(text("""
                SELECT nombre FROM usuarios_activos 
                WHERE ultimo_acceso >= NOW() - INTERVAL '5 minutes'
            """))
            usuarios_en_linea = [row[0] for row in result]
            conn.commit()
    except Exception:
        usuarios_en_linea = [st.session_state.usuario_activo]

# =====================================================================
# ENCABEZADO MINIMALISTA
# =====================================================================
col_t1, col_t2 = st.columns([8, 2])

with col_t1:
    st.markdown("<h1 style='color: #333; font-weight: 300; margin-bottom: 0px; padding-bottom: 0px; font-size: 2.6rem;'>Gestión de avisos y OMs</h1>", unsafe_allow_html=True)
    
    # Texto en línea idéntico a tu imagen
    st.markdown(f"""
        <div style="font-size: 1.05rem; color: #555; margin-top: 10px; margin-bottom: 15px; display: flex; align-items: center; gap: 15px; font-family: sans-serif;">
            <span><span style="color: #666;">👤 Usuario:</span> <b>{st.session_state.usuario_activo}</b></span>
            <span style="color: #ccc;">|</span>
            <span><span style="color: #2E7D32;">👥 Usuarios activos:</span> <b style="color: #333;">{len(usuarios_en_linea)}</b></span>
        </div>
    """, unsafe_allow_html=True)

with col_t2:
    if st.button("⚙️ Cargar Datos", use_container_width=True):
        modal_actualizar()
        
    # Botón de cierre de sesión a prueba de fallos
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

st.markdown("<hr style='margin-top: 0px; margin-bottom: 20px; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
avisos_df, oms_df = cargar_datos()


# =====================================================================
# PROCESAMIENTO BASE (CREACIÓN DE COLUMNAS ANTES DE FILTRAR)
# =====================================================================
if not avisos_df.empty:
    if 'Centro emplazamiento' in avisos_df.columns:
        avisos_df['ZONA'] = avisos_df['Centro emplazamiento'].apply(asignar_zona)
    else:
        avisos_df['ZONA'] = 'OTRAS'
        
    avisos_df['Programador'] = avisos_df.apply(asignar_programador, axis=1)
    
    if 'Status del sistema' in avisos_df.columns:
        avisos_df['Status Filtro'] = avisos_df['Status del sistema'].apply(extraer_status_objetivo)
    else:
        avisos_df['Status Filtro'] = 'OTRO STATUS'
        
    avisos_df['Prioridad'] = avisos_df.get('Texto para prioridad', pd.Series(['Sin Prioridad']*len(avisos_df))).fillna('Sin Prioridad').astype(str)
    avisos_df['Denominación de la ubicación técnica'] = avisos_df.get('Denominación de la ubicación técnica', pd.Series(['Desconocida']*len(avisos_df))).fillna('Desconocida')
    
    if 'Creado el' in avisos_df.columns:
        avisos_df['Creado el'] = pd.to_datetime(avisos_df['Creado el'], errors='coerce')
        avisos_df['Días Abierto'] = (pd.to_datetime('today') - avisos_df['Creado el']).dt.days
    else:
        avisos_df['Días Abierto'] = 0
        avisos_df['Creado el'] = pd.NaT
else:
    avisos_df = pd.DataFrame(columns=['ZONA', 'Programador', 'Status Filtro', 'Prioridad', 'Denominación de la ubicación técnica', 'Creado el', 'Días Abierto', 'Aviso'])

if not oms_df.empty:
    if 'Centro emplazamiento' in oms_df.columns:
        oms_df['ZONA'] = oms_df['Centro emplazamiento'].apply(asignar_zona)
    else:
        oms_df['ZONA'] = 'OTRAS'

    oms_df['Programador'] = oms_df.apply(asignar_programador, axis=1)

    # Mapear prioridad numérica (IW38) a texto unificado (igual que Avisos IW28)
    col_prio_om = next((c for c in oms_df.columns if c.lower() == 'prioridad'), None)
    if col_prio_om:
        oms_df['Prioridad'] = pd.to_numeric(oms_df[col_prio_om], errors='coerce').map(MAPEO_PRIORIDAD_OM).fillna('Sin Prioridad')
    else:
        oms_df['Prioridad'] = 'Sin Prioridad'

    oms_df['Denominación de la ubicación técnica'] = oms_df.get('Denominación de la ubicación técnica', pd.Series(['Desconocida']*len(oms_df))).fillna('Desconocida')
    oms_df['Tota general (plan)'] = pd.to_numeric(oms_df.get('Tota general (plan)', pd.Series([0]*len(oms_df))), errors='coerce').fillna(0)
    oms_df['Costes tot.reales'] = pd.to_numeric(oms_df.get('Costes tot.reales', pd.Series([0]*len(oms_df))), errors='coerce').fillna(0)

    # Normalizar columna Equipo a entero para mejor legibilidad
    if 'Equipo' in oms_df.columns:
        oms_df['Equipo'] = pd.to_numeric(oms_df['Equipo'], errors='coerce').fillna(0).astype(int)

    # Procesar fecha de creación de OMs para Carga de Trabajo
    col_fecha_om = next((c for c in oms_df.columns if 'fecha' in c.lower() and 'cre' in c.lower()), None)
    if col_fecha_om:
        oms_df['Fecha Creacion OM'] = pd.to_datetime(oms_df[col_fecha_om], errors='coerce')
    else:
        oms_df['Fecha Creacion OM'] = pd.NaT
else:
    oms_df = pd.DataFrame(columns=['ZONA', 'Programador', 'Prioridad', 'Tota general (plan)', 'Costes tot.reales', 'Denominación de la ubicación técnica', 'Orden', 'Status de usuario', 'Equipo', 'Fecha Creacion OM'])

# =====================================================================
# FILTROS SUPERIORES (ESTILO QLIK - MULTISELECT CON SCROLL CSS)
# =====================================================================
col_clear, _ = st.columns([1.5, 10.5])
with col_clear:
    if st.button("🧹 Limpiar Filtro", use_container_width=True):
        # Resetear TODOS los filtros a lista vacía (vacío visual = ver todo)
        for key in ["fz", "fp", "fs", "fpr", "fl"]:
            st.session_state[key] = []
        st.rerun()

col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)

def filtro_gerencial(label, opciones_totales, key, sort_func=None):
    """Filtro multiselect con cascada estricta.
    - sort_func: función opcional para ordenar las opciones (ej. sort_prioridades).
    - Si el usuario no selecciona nada, devuelve todas las opciones disponibles (sin filtro).
    """
    st.markdown(f"<span style='font-size: 0.75rem; color: #777; font-weight: bold;'>🔍 {label.upper()}</span>", unsafe_allow_html=True)

    opciones_raw = list(set([str(op) for op in opciones_totales if pd.notna(op)]))
    if sort_func:
        opciones_limpias = sort_func(opciones_raw)
    else:
        opciones_limpias = sorted(opciones_raw)

    # Cascada: limpiar de session_state las opciones que ya no existen en este contexto filtrado
    if key in st.session_state and isinstance(st.session_state[key], list):
        st.session_state[key] = [op for op in st.session_state[key] if op in opciones_limpias]

    seleccionados = st.multiselect(
        label,
        options=opciones_limpias,
        key=key,
        label_visibility="collapsed"
    )

    # Si la caja está vacía, se asume el 100% de la data disponible (sin filtro)
    if not seleccionados:
        return opciones_limpias
    return seleccionados

# --- LÓGICA DE CASCADA ESTRICTA ---
# Cada filtro se alimenta del DataFrame ya reducido por los filtros previos.

with col_f1:
    zonas_todos = list(set(avisos_df['ZONA'].unique()) | set(oms_df['ZONA'].unique()))
    zonas_sel = filtro_gerencial("ZONA / CENTRO", zonas_todos, "fz")

av_temp = avisos_df[avisos_df['ZONA'].isin(zonas_sel)]
om_temp = oms_df[oms_df['ZONA'].isin(zonas_sel)]

with col_f2:
    # Programadores presentes en ambos datasets, dado el filtro de zona
    progs_todos = list(set(av_temp['Programador'].unique()) | set(om_temp['Programador'].unique()))
    progs_sel = filtro_gerencial("PROGRAMADOR", progs_todos, "fp")

av_temp = av_temp[av_temp['Programador'].isin(progs_sel)]
om_temp = om_temp[om_temp['Programador'].isin(progs_sel)]

with col_f3:
    # Status disponibles dado el filtro zona+programador (solo avisos tienen status)
    status_todos = av_temp['Status Filtro'].unique()
    status_sel = filtro_gerencial("STATUS AVISO", status_todos, "fs")

av_temp = av_temp[av_temp['Status Filtro'].isin(status_sel)]

with col_f4:
    # Prioridades unificadas (texto) dado el filtro acumulado
    prioridades_todos = list(set(av_temp['Prioridad'].unique()) | set(om_temp['Prioridad'].unique()))
    prioridades_sel = filtro_gerencial("PRIORIDAD", prioridades_todos, "fpr", sort_func=sort_prioridades)

av_temp = av_temp[av_temp['Prioridad'].isin(prioridades_sel)]
om_temp = om_temp[om_temp['Prioridad'].isin(prioridades_sel)]

with col_f5:
    # Ubicaciones técnicas del contexto completamente filtrado (cascada real)
    lineas_todos = list(set(av_temp['Denominación de la ubicación técnica'].unique()) | set(om_temp['Denominación de la ubicación técnica'].unique()))
    lineas_sel = filtro_gerencial("UBICACIÓN TÉCNICA", lineas_todos, "fl")

# DF FINALES PARA EL DASHBOARD
av_filt = av_temp[av_temp['Denominación de la ubicación técnica'].isin(lineas_sel)]
om_filt = om_temp[om_temp['Denominación de la ubicación técnica'].isin(lineas_sel)]

# =====================================================================
# KPIs PRINCIPALES
# =====================================================================
st.markdown("<br>", unsafe_allow_html=True)
col_k1, col_k2, col_k3, col_k4, col_k5 = st.columns(5)

total_plan = om_filt['Tota general (plan)'].sum()
total_real = om_filt['Costes tot.reales'].sum()
desviacion_clp = total_real - total_plan

col_k1.metric("AVISOS ACTIVOS", f"{len(av_filt):,}")
col_k2.metric("COSTO REAL", f"${total_real:,.0f}".replace(',', '.'))
col_k3.metric("DESVIACIÓN (CLP)", f"${desviacion_clp:,.0f}".replace(',', '.'))
col_k4.metric("COSTO PLANIFICADO", f"${total_plan:,.0f}".replace(',', '.'))
col_k5.metric("FECHA ACTUALIZACIÓN", datetime.today().strftime('%d-%m-%Y'))
st.markdown("<br>", unsafe_allow_html=True)



# =====================================================================
# PESTAÑAS DE CONTENIDO (TODO INCLUIDO)
# =====================================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Resumen Avisos", 
    "📋 Detalle Avisos y OMs", 
    "📅 Línea de Tiempo", 
    "👥 Carga de Trabajo", 
    "🗃️ Explorador de Datos"
])

# ---------------------------------------------------------------------
# TAB 1: RESUMEN EJECUTIVO
# ---------------------------------------------------------------------
with tab1:
    qlik_colors = ['#006580', '#A3334E', '#E5CDA8', '#7AB3A2', '#4C2C69']
    
    # --- SECCIÓN 1: RESUMEN DE AVISOS ---
    st.subheader("📋 Resumen de Avisos por Programador")
    if not av_filt.empty:
        # 1. Crear Tabla
        tabla_avisos_pivot = pd.crosstab(index=av_filt['Programador'], columns=av_filt['Status Filtro'], margins=True, margins_name='Total general')
        cols_deseadas = ['MEAB', 'METR', 'METR ORAS', 'Total general']
        for col in cols_deseadas:
            if col not in tabla_avisos_pivot.columns: tabla_avisos_pivot[col] = 0
        tabla_avisos_pivot = tabla_avisos_pivot[cols_deseadas].reset_index()
        
        st.dataframe(tabla_avisos_pivot, use_container_width=True, hide_index=True)
        
        # 2. Botón Interruptor para Gráficos
        if st.toggle("📊 Mostrar gráficos de Avisos"):
            st.markdown("<div class='qlik-container'>", unsafe_allow_html=True)
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                st.markdown("**Avisos por Prioridad**")
                df_prio = av_filt.groupby('Prioridad').size().reset_index(name='Cantidad')
                fig_donut = px.pie(df_prio, values='Cantidad', names='Prioridad', hole=0.65, color_discrete_sequence=qlik_colors)
                fig_donut.update_traces(textposition='inside', textinfo='value')
                fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=True, paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_donut, use_container_width=True)
                
            with col_g2:
                st.markdown("**Avisos por Status y Programador**")
                df_av_bar = av_filt.groupby(['Programador', 'Status Filtro']).size().reset_index(name='Cantidad')
                fig_bar_av = px.bar(df_av_bar, x='Programador', y='Cantidad', color='Status Filtro', color_discrete_sequence=['#A3334E', '#006580', '#E5CDA8'])
                fig_bar_av.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_bar_av, use_container_width=True)
                
            st.markdown("</div>", unsafe_allow_html=True)
    else: 
        st.info("Sin datos para el resumen de avisos.")

    st.markdown("---")

    # --- SECCIÓN 2: RESUMEN COMBINADO ---
    st.subheader("💼 Resumen Combinado (Avisos y OMs con Costo Planificado)")
    av_count = av_filt.groupby('Programador').size().reset_index(name='Cuenta de Aviso')
    om_agg = om_filt.groupby('Programador').agg(Cuenta_de_Orden=('Orden', 'count'), Suma_Plan=('Tota general (plan)', 'sum')).reset_index()
    comb_df = pd.merge(av_count, om_agg, on='Programador', how='outer').fillna(0)
    
    if not comb_df.empty:
        # 1. Crear Tabla
        total_row = pd.DataFrame({'Programador': ['Total general'], 'Cuenta de Aviso': [comb_df['Cuenta de Aviso'].sum()], 'Cuenta_de_Orden': [comb_df['Cuenta_de_Orden'].sum()], 'Suma_Plan': [comb_df['Suma_Plan'].sum()]})
        comb_df_disp = pd.concat([comb_df, total_row], ignore_index=True)
        
        comb_df_disp.rename(columns={'Programador': 'Etiquetas de fila', 'Cuenta_de_Orden': 'Cuenta de Orden', 'Suma_Plan': 'Suma de Tota general (plan)'}, inplace=True)
        comb_df_disp['Cuenta de Aviso'] = comb_df_disp['Cuenta de Aviso'].astype(int)
        comb_df_disp['Cuenta de Orden'] = comb_df_disp['Cuenta de Orden'].astype(int)
        comb_df_disp['Suma de Tota general (plan)'] = comb_df_disp['Suma de Tota general (plan)'].apply(lambda x: f"${x:,.0f}".replace(',', '.'))
        
        st.dataframe(comb_df_disp, use_container_width=True, hide_index=True)
        
        # 2. Botón Interruptor para Gráficos
        if st.toggle("📊 Mostrar gráficos Combinados"):
            st.markdown("<div class='qlik-container'>", unsafe_allow_html=True)
            col_g3, col_g4 = st.columns(2)
            
            with col_g3:
                st.markdown("**Total OMs por Centro de Emplazamiento**")
                if not om_filt.empty:
                    df_centro = om_filt.groupby('ZONA').size().reset_index(name='Total OMs')
                    fig_bar = px.bar(df_centro, x='ZONA', y='Total OMs', color='ZONA', text='Total OMs', color_discrete_map={'ARAUCO': '#DEB887', 'CHILLAN': '#800040', 'OTRAS': '#006580'})
                    fig_bar.update_traces(textposition='outside')
                    fig_bar.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_bar, use_container_width=True)
                else: 
                    st.info("Sin datos")
                    
            with col_g4:
                st.markdown("**Costo Planificado por Programador**")
                # Se grafica omitiendo el "Total general" para no distorsionar las barras
                fig_cost = px.bar(comb_df, x='Programador', y='Suma_Plan', text='Suma_Plan', color_discrete_sequence=['#006580'])
                fig_cost.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
                fig_cost.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_cost, use_container_width=True)
                
            st.markdown("</div>", unsafe_allow_html=True)
            
    else: 
        st.info("Sin datos para el resumen combinado.")

# ---------------------------------------------------------------------
# TAB 2: DETALLE AVISOS Y OMs (CON GRÁFICOS)
# ---------------------------------------------------------------------
with tab2:
    col_t2a, col_t2b = st.columns(2)
    
    with col_t2a:
        st.subheader("Desglose de Avisos")
        if not av_filt.empty:
            tabla_avisos = av_filt.groupby(['Status Filtro', 'Prioridad']).size().reset_index(name='Cantidad')
            st.dataframe(tabla_avisos, use_container_width=True, hide_index=True)
            
            fig_av = px.bar(tabla_avisos, x='Status Filtro', y='Cantidad', color='Prioridad', barmode='group', text='Cantidad', color_discrete_sequence=qlik_colors)
            fig_av.update_traces(textposition='outside', hovertemplate="<b>Status:</b> %{x}<br><b>Cantidad:</b> %{y}<extra></extra>")
            fig_av.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_av, use_container_width=True)
        else: st.info("No hay Avisos para mostrar.")
            
    with col_t2b:
        st.subheader("Desglose de OMs y Costos")
        if not om_filt.empty:
            tabla_oms = om_filt.groupby(['Prioridad', 'Status de usuario']).agg(Cantidad=('Orden', 'count'), Costo_Plan=('Tota general (plan)', 'sum'), Costo_Real=('Costes tot.reales', 'sum')).reset_index()
            st.dataframe(tabla_oms.style.format({'Costo_Plan': '${:,.0f}', 'Costo_Real': '${:,.0f}'}), use_container_width=True, hide_index=True)
            
            fig_om = px.bar(tabla_oms, x='Prioridad', y='Costo_Plan', color='Status de usuario', title='Costo Plan ($)', custom_data=['Cantidad'], color_discrete_sequence=qlik_colors)
            fig_om.update_traces(hovertemplate="<b>Prioridad:</b> %{x}<br><b>Costo Plan:</b> $%{y:,.0f}<br><b>OMs:</b> %{customdata[0]}<extra></extra>")
            fig_om.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_om, use_container_width=True)
        else: st.info("No hay OMs para mostrar.")

# ---------------------------------------------------------------------
# TAB 3: LÍNEA DE TIEMPO
# ---------------------------------------------------------------------
with tab3:
    st.subheader("Evolución de Solicitudes (Mensual/Anual)")
    st.caption("📅 Los datos se agrupan por la **fecha de creación** del aviso (campo 'Creado el' del IW28).")
    av_time = av_filt.dropna(subset=['Creado el']).copy()
    if not av_time.empty:
        av_time['Año'] = av_time['Creado el'].dt.year.astype(str)
        av_time['Mes_Num'] = av_time['Creado el'].dt.month
        meses_es = {1: 'ene', 2: 'feb', 3: 'mar', 4: 'abr', 5: 'may', 6: 'jun', 7: 'jul', 8: 'ago', 9: 'sept', 10: 'oct', 11: 'nov', 12: 'dic'}
        av_time['Mes'] = av_time['Mes_Num'].map(meses_es)
        
        df_t = av_time.groupby(['Status Filtro', 'Año', 'Mes_Num', 'Mes']).size().reset_index(name='Cantidad').sort_values(by=['Año', 'Mes_Num'])
        orden_meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]
        titulos = {'MEAB': 'AVISOS PENDIENTES APROBACIÓN (MEAB)', 'METR': 'AVISOS APROBADOS PENDIENTES OM (METR)', 'METR ORAS': 'OM PENDIENTE PLANIFICACIÓN (METR ORAS)'}
        
        for st_val in ['MEAB', 'METR', 'METR ORAS']:
            df_plot = df_t[df_t['Status Filtro'] == st_val]
            if not df_plot.empty:
                st.markdown(f"**{titulos[st_val]}**")
                fig_time = px.bar(df_plot, x='Mes', y='Cantidad', color='Año', barmode='group', text='Cantidad', category_orders={"Mes": orden_meses}, color_discrete_sequence=['#006580', '#A3334E', '#E5CDA8'])
                fig_time.update_traces(textposition='outside')
                fig_time.update_layout(xaxis_title="", yaxis_title="", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=300)
                st.plotly_chart(fig_time, use_container_width=True)
    else: st.info("No hay fechas válidas para graficar en esta selección.")

# ---------------------------------------------------------------------
# TAB 4: EFICIENCIA Y COSTOS POR PROGRAMADOR
# ---------------------------------------------------------------------
with tab4:
    # ----------------------------------------------------------------
    # SECCIÓN 1: CARGA DE TRABAJO POR PROGRAMADOR (OMs creadas × día)
    # ----------------------------------------------------------------
    st.subheader("📦 Carga de Trabajo por Programador")
    st.caption("Contador de OMs creadas por día y por programador, basado en la fecha de creación del IW38.")

    if not om_filt.empty and 'Fecha Creacion OM' in om_filt.columns:
        df_carga = om_filt.dropna(subset=['Fecha Creacion OM']).copy()
        df_carga['Fecha'] = df_carga['Fecha Creacion OM'].dt.date

        fechas_validas = df_carga['Fecha'].dropna()
        if not fechas_validas.empty:
            f_min, f_max = fechas_validas.min(), fechas_validas.max()
            col_d1, col_d2, col_d3 = st.columns([2, 2, 6])
            with col_d1:
                fecha_inicio = st.date_input("📅 Desde", value=f_min, min_value=f_min, max_value=f_max, key="carga_desde")
            with col_d2:
                fecha_fin = st.date_input("📅 Hasta", value=f_max, min_value=f_min, max_value=f_max, key="carga_hasta")
            df_carga = df_carga[(df_carga['Fecha'] >= fecha_inicio) & (df_carga['Fecha'] <= fecha_fin)]

        # Tabla resumen: total OMs, días activos, promedio diario
        df_resumen_carga = df_carga.groupby('Programador').agg(
            Total_OMs=('Orden', 'count'),
            Dias_Activos=('Fecha', 'nunique'),
        ).reset_index()
        df_resumen_carga['Promedio_OMs_por_Dia'] = (
            df_resumen_carga['Total_OMs'] / df_resumen_carga['Dias_Activos']
        ).round(1)
        df_resumen_carga.rename(columns={
            'Total_OMs': 'Total OMs',
            'Dias_Activos': 'Días con Actividad',
            'Promedio_OMs_por_Dia': 'Promedio OMs/Día'
        }, inplace=True)
        # Fila de total
        total_carga = pd.DataFrame({
            'Programador': ['Total general'],
            'Total OMs': [int(df_resumen_carga['Total OMs'].sum())],
            'Días con Actividad': ['-'],
            'Promedio OMs/Día': ['-']
        })
        st.dataframe(
            pd.concat([df_resumen_carga, total_carga], ignore_index=True),
            use_container_width=True, hide_index=True
        )

        # Toggle + selector de tipo de gráfico
        if st.toggle("📊 Mostrar Gráfico de Carga de Trabajo"):
            tipo_graf = st.radio(
                "Tipo de gráfico:",
                ["📊 Barras por Día", "📅 Barras por Semana", "📈 Línea de Tendencia", "🗓️ Heatmap"],
                horizontal=True,
                key="tipo_grafico_carga"
            )

            df_agg_dia = df_carga.groupby(['Fecha', 'Programador']).size().reset_index(name='OMs Creadas')
            df_agg_dia['Fecha'] = pd.to_datetime(df_agg_dia['Fecha'])
            colores_prog = ['#006580', '#A3334E', '#E5CDA8', '#7AB3A2', '#4C2C69']

            if tipo_graf == "📊 Barras por Día":
                fig_carga = px.bar(
                    df_agg_dia, x='Fecha', y='OMs Creadas', color='Programador',
                    barmode='group', text='OMs Creadas',
                    color_discrete_sequence=colores_prog,
                    labels={'Fecha': 'Fecha de Creación', 'OMs Creadas': 'Nº OMs'}
                )
                fig_carga.update_traces(textposition='outside')
                fig_carga.update_xaxes(tickformat='%d-%m-%Y', tickangle=45)

            elif tipo_graf == "📅 Barras por Semana":
                df_agg_dia['Semana'] = df_agg_dia['Fecha'].dt.to_period('W').astype(str)
                df_sem = df_agg_dia.groupby(['Semana', 'Programador'])['OMs Creadas'].sum().reset_index()
                fig_carga = px.bar(
                    df_sem, x='Semana', y='OMs Creadas', color='Programador',
                    barmode='group', text='OMs Creadas',
                    color_discrete_sequence=colores_prog,
                    labels={'Semana': 'Semana', 'OMs Creadas': 'Nº OMs'}
                )
                fig_carga.update_traces(textposition='outside')
                fig_carga.update_xaxes(tickangle=45)

            elif tipo_graf == "📈 Línea de Tendencia":
                fig_carga = px.line(
                    df_agg_dia, x='Fecha', y='OMs Creadas', color='Programador',
                    markers=True,
                    color_discrete_sequence=colores_prog,
                    labels={'Fecha': 'Fecha de Creación', 'OMs Creadas': 'Nº OMs'}
                )
                fig_carga.update_xaxes(tickformat='%d-%m-%Y', tickangle=45)

            elif tipo_graf == "🗓️ Heatmap":
                fig_carga = px.density_heatmap(
                    df_agg_dia, x='Fecha', y='Programador', z='OMs Creadas',
                    color_continuous_scale='Blues',
                    labels={'Fecha': 'Fecha', 'Programador': 'Programador', 'OMs Creadas': 'OMs'}
                )
                fig_carga.update_xaxes(tickformat='%d-%m-%Y', tickangle=45)

            fig_carga.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=420,
                margin=dict(t=30, b=10, l=10, r=10)
            )
            st.plotly_chart(fig_carga, use_container_width=True)
    else:
        st.info("No hay datos de carga de trabajo disponibles para el período seleccionado.")

    # ----------------------------------------------------------------
    # SECCIÓN 2: EFICIENCIA PRESUPUESTARIA (sección secundaria)
    # ----------------------------------------------------------------
    st.markdown("---")
    st.subheader("💰 Análisis de Eficiencia Presupuestaria")

    if not om_filt.empty:
        df_eficiencia = om_filt.groupby('Programador').agg(
            Planificado=('Tota general (plan)', 'sum'),
            Real=('Costes tot.reales', 'sum'),
            Cant_OMs=('Orden', 'count')
        ).reset_index()

        df_eficiencia['Desviacion_CLP'] = df_eficiencia['Real'] - df_eficiencia['Planificado']

        fig_costos = px.bar(
            df_eficiencia.melt(id_vars='Programador', value_vars=['Planificado', 'Real']),
            x='Programador', y='value', color='variable', barmode='group',
            title="Comparativa Planificado vs Real por Programador",
            labels={'value': 'Monto (CLP)', 'variable': 'Tipo de Costo'},
            color_discrete_sequence=['#006580', '#A3334E']
        )
        fig_costos.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_costos, use_container_width=True)

        st.markdown("### Detalle de Desviaciones (CLP)")
        df_eficiencia_disp = df_eficiencia.copy()
        for col_e in ['Planificado', 'Real', 'Desviacion_CLP']:
            df_eficiencia_disp[col_e] = df_eficiencia_disp[col_e].apply(lambda x: f"${x:,.0f}".replace(',', '.'))
        st.dataframe(df_eficiencia_disp, use_container_width=True, hide_index=True)
    else:
        st.info("No hay datos de costos suficientes para el análisis.")

# ---------------------------------------------------------------------
# TAB 5: EXPLORADOR DE DATOS CRUDOS
# ---------------------------------------------------------------------
with tab5:
    st.subheader("Matriz Interactiva (Avisos)")
    if not av_filt.empty:
        st.dataframe(av_filt[['Aviso', 'ZONA', 'Programador', 'Status Filtro', 'Prioridad', 'Denominación de la ubicación técnica', 'Creado el', 'Días Abierto']], use_container_width=True, hide_index=True)
    else: st.info("No hay datos de Avisos para mostrar.")
        
    st.markdown("---")
    st.subheader("Matriz Interactiva (OMs)")
    if not om_filt.empty:
        # Columnas base + columnas opcionales (Equipo, Texto breve, Denom. objeto técnico)
        cols_om_base = ['Orden', 'ZONA', 'Programador', 'Status de usuario', 'Prioridad',
                        'Denominación de la ubicación técnica', 'Tota general (plan)', 'Costes tot.reales']
        cols_om_extra = [c for c in ['Equipo', 'Texto breve', 'Denominación de objeto técnico']
                         if c in om_filt.columns]
        st.dataframe(om_filt[cols_om_base + cols_om_extra], use_container_width=True, hide_index=True)
    else:
        st.info("No hay datos de OMs para mostrar.")
