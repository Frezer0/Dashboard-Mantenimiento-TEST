import streamlit as st
import pandas as pd
import re
import plotly.express as px
import os
from datetime import datetime
import pytz
import sqlalchemy  # DB Sql Progress
from sqlalchemy import text # para ejecutar SQL directo

DATABASE_URL = os.getenv("DATABASE_URL")

# =====================================================================
# =====================================================================
# CONSTANTES DE NEGOCIO — PRIORIDADES
# =====================================================================
QLIK_COLORS = ['#006580', '#A3334E', '#E5CDA8', '#7AB3A2', '#4C2C69']
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
        #avisos_df = pd.read_excel('Avisos IW28.xlsx')
        #oms_df = pd.read_excel('OMs IW38.xlsx')
        
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
        st.error(f"⚠️ No se pudieron cargar los datos. Revisa los archivos Excel o la conexión a la base de datos. Detalle: {e}")
        return pd.DataFrame(), pd.DataFrame()

# =====================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTÉTICA QLIK SENSE
# =====================================================================
st.set_page_config(page_title="Gestión de Avisos PPCM", layout="wide", page_icon="📊")

with open('style.css', 'r', encoding='utf-8') as f:
    css_content = f.read()
st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)

# =====================================================================
# SISTEMA DE SESIÓN (IDENTIFICACIÓN DE USUARIOS)
# =====================================================================
if "usuario_activo" not in st.session_state:
    st.session_state.usuario_activo = None

# Pantalla de Login Premium
if st.session_state.usuario_activo is None:
    st.markdown("""
    <style>
    /* Fondo degradado en toda la página */
    .stApp {
        background: linear-gradient(135deg, #0a2a35 0%, #006580 50%, #0d4a5e 100%) !important;
    }
    .block-container {
        padding-top: 12vh !important;
    }
    /* Ocultar sidebar en login */
    [data-testid="stSidebar"] { display: none !important; }
    /* La CARD es el stForm */
    [data-testid="stForm"] {
        background: #ffffff !important;
        border: none !important;
        border-radius: 16px !important;
        padding: 32px 32px 24px !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2) !important;
        animation: loginUp 0.4s ease !important;
    }
    @keyframes loginUp {
        from { opacity:0; transform: translateY(18px); }
        to   { opacity:1; transform: translateY(0); }
    }
    /* Input */
    [data-testid="stTextInput"] > div > div > input {
        border-radius: 8px !important;
        border: 1px solid #E2E8F0 !important;
        padding: 12px 14px !important;
        font-size: 0.9rem !important;
        background: #F8FAFC !important;
        color: #0F172A !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stTextInput"] > div > div > input:focus {
        border-color: #006580 !important;
        box-shadow: 0 0 0 2px rgba(0,101,128,0.15) !important;
        background: #fff !important;
    }
    /* Botón */
    [data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, #006580, #0a4a5e) !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 10px !important;
        box-shadow: 0 4px 10px rgba(0,101,128,0.3) !important;
        transition: all 0.2s ease !important;
        margin-top: 10px !important;
    }
    [data-testid="stFormSubmitButton"] button:hover {
        background: linear-gradient(135deg, #004d61, #083847) !important;
        box-shadow: 0 6px 15px rgba(0,101,128,0.4) !important;
        transform: translateY(-1px) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col_login, col3 = st.columns([1.2, 1.3, 1.2])
    with col_login:
        with st.form("form_login", clear_on_submit=False):
            # Todo el encabezado va DENTRO del form para que sea una sola card unificada
            st.markdown("""
        <div style="text-align:center; margin-bottom:15px;">
            <span style="
                display:inline-flex; align-items:center; justify-content:center;
                width:50px; height:50px;
                background: linear-gradient(135deg, #006580, #0a2a35);
                border-radius:12px; font-size:1.4rem;
                box-shadow: 0 6px 16px rgba(0,101,128,0.3);
                margin-bottom:12px;
            ">📊</span>
            <h2 style="
                color:#0F172A; font-size:1.4rem; font-weight:700;
                letter-spacing:-0.02em; margin:0 0 4px;
            ">Gestión PPCM</h2>
            <p style="color:#64748B; font-size:0.85rem; margin:0 0 12px;">
                Portal de Análisis &middot; Mantenimiento
            </p>
            <p style="color:#64748B; font-size:0.8rem; margin:0 0 20px;">
                🔒 Por favor, identifíquese para acceder a la aplicación de análisis.
            </p>
            <p style="
                font-size:0.7rem; font-weight:600; color:#64748B;
                text-transform:uppercase; letter-spacing:0.05em;
                margin:0 0 6px; text-align:left;
            ">Nombre de Usuario</p>
        </div>
        """, unsafe_allow_html=True)

            nombre_input = st.text_input(
                "usuario", label_visibility="collapsed",
                placeholder=""
            )
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            btn_ingresar = st.form_submit_button("Ingresar →", use_container_width=True)

            if btn_ingresar:
                if nombre_input.strip():
                    st.session_state.usuario_activo = nombre_input.strip()
                    st.rerun()
                else:
                    st.error("⚠️ Por favor, ingresa tu nombre para continuar.")

            st.markdown("""
            <p style="text-align:center; font-size:0.68rem; color:#CBD5E1;
                       margin-top:18px; letter-spacing:0.03em;">
                Solo personal autorizado
            </p>
            """, unsafe_allow_html=True)

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
    if 'RECH' in status_str: return 'RECH'
    if 'CREA' in status_str: return 'CREA'
    if 'PPRG' in status_str: return 'PPRG'
    if 'PPLN' in status_str: return 'PPLN'
    if 'PLAN' in status_str: return 'PLAN'
    if 'RETE' in status_str: return 'RETE'
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
                # Guardar quién hizo la actualización y cuándo
                st.session_state['ultima_actualizacion_usuario'] = st.session_state.usuario_activo
                #st.session_state['ultima_actualizacion_hora'] = datetime.today().strftime('%d-%m-%Y %H:%M')
                chile_tz = pytz.timezone('America/Santiago')
                st.session_state['ultima_actualizacion_hora'] = datetime.now(chile_tz).strftime('%d-%m-%Y %H:%M')
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
st.markdown("<h1 style='color: #333; font-weight: 300; margin-bottom: 0px; padding-bottom: 0px; font-size: 2.6rem;'>Gestión de avisos y OMs</h1>", unsafe_allow_html=True)

# Badge de usuario + usuarios conectados + última actualización
_label_usuarios = "Usuarios Conectados" if len(usuarios_en_linea) > 1 else "Usuario Conectado"
_nombres_linea = " · ".join(usuarios_en_linea) if usuarios_en_linea else st.session_state.usuario_activo
chile_tz = pytz.timezone('America/Santiago')
_hora_act = st.session_state.get('ultima_actualizacion_hora', datetime.now(chile_tz).strftime('%d-%m-%Y %H:%M'))
_quien_act = st.session_state.get('ultima_actualizacion_usuario', '')
_uploader_html = f'<span style="color:#CBD5E1; margin: 0 5px;">·</span><span style="color:#64748B; font-weight:500;">{_quien_act}</span>' if _quien_act else ''

st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 16px; margin-top: 8px; margin-bottom: 16px; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 8px; background-color: #F1F5F9; padding: 5px 14px; border-radius: 20px; border: 1px solid #E2E8F0; font-size: 0.82rem; color: #475569;">
            <div style="width: 7px; height: 7px; background-color: #10B981; border-radius: 50%; box-shadow: 0 0 5px rgba(16,185,129,0.5); flex-shrink:0;"></div>
            <span style="color:#64748B; font-weight:600; letter-spacing:0.02em;">{_label_usuarios}:</span>
            <span style="font-weight: 600; color: #0F172A;">{_nombres_linea}</span>
        </div>
        <div style="font-size: 0.78rem; color: #94A3B8; letter-spacing: 0.02em;">
            Actualizado: <b style="color:#006580;">{_hora_act}</b>{_uploader_html}
        </div>
    </div>
""", unsafe_allow_html=True)

st.markdown("<hr style='margin-top: 0px; margin-bottom: 20px; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
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
        avisos_df['Días Abierto'] = (pd.to_datetime('today') - avisos_df['Creado el']).dt.days.clip(lower=0)
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
# SIDEBAR (OPCIONES Y ESTADO)
# =====================================================================
with st.sidebar:
    st.markdown("""
        <div style="padding: 6px 0 18px 0; border-bottom: 1px solid #F1F5F9; margin-bottom: 16px;">
            <span style="font-size: 0.65rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.08em;">Panel de control</span>
        </div>
    """, unsafe_allow_html=True)

    if st.button("🧹  Limpiar Filtros", use_container_width=True):
        for key in ["fz", "fp", "fs", "fpr", "fl"]:
            st.session_state[key] = []
        st.rerun()

    if st.button("📥  Cargar Datos", use_container_width=True):
        modal_actualizar()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("🔒  Cerrar Sesión", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# =====================================================================
# FILTROS SUPERIORES (ESTILO QLIK - MULTISELECT CON SCROLL CSS)
# =====================================================================


col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)

def filtro_gerencial(label, opciones_totales, key, sort_func=None):
    """Filtro multiselect con cascada estricta."""
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
    # Mostrar los status que realmente existen en los datos + fallback a la lista completa
    status_base = ['METR ORAS', 'METR', 'MEAB', 'MECE', 'MAEN', 'RECH', 'CREA', 'PPRG', 'PPLN', 'PLAN', 'RETE', 'OTRO STATUS']
    status_reales = list(av_temp['Status Filtro'].unique()) if not av_temp.empty else []
    status_todos = sorted(set(status_base) | set(status_reales))
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
# PESTAÑAS DE CONTENIDO (TODO INCLUIDO)
# =====================================================================
tab_om, tab1, tab4, tab3, tab2, tab5 = st.tabs([
    "✅ Resumen OMs",
    "📊 Resumen Avisos", 
    "👥 Carga de Trabajo", 
    "📅 Línea de Tiempo", 
    "📋 Detalle Avisos y OMs", 
    "🗃️ Explorador de Datos"
])

# ---------------------------------------------------------------------
# TAB OM: RESUMEN DE OMS
# ---------------------------------------------------------------------
with tab_om:
    st.subheader("✅ Resumen de OMs por Programador")
    if not om_filt.empty:
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("TOTAL OMs", len(om_filt))
        
        # Métricas cruzadas de Avisos — búsqueda exacta para evitar que METR ORAS infle METR
        cant_tratados   = len(av_filt[av_filt['Status Filtro'] == 'METR'])
        cant_sin_aprob  = len(av_filt[av_filt['Status Filtro'] == 'MEAB'])
        cant_rechazados = len(av_filt[av_filt['Status Filtro'].isin(['MECE', 'MAEN', 'RECH'])])
        
        col_m2.metric("Avisos tratados Sin OM", cant_tratados)
        col_m3.metric("Avisos Sin Aprovacion", cant_sin_aprob)
        col_m4.metric("Avisos Rechazados", cant_rechazados)
        
        st.markdown("<hr style='margin-top: 0.5rem; margin-bottom: 1rem;'>", unsafe_allow_html=True)
        
        # 1. Crear Tabla Pivot
        df_grouped_om = om_filt.copy()
        def agrupar_om(s):
            s = str(s).upper()
            if 'CREA' in s: return 'CREA'
            if 'PPRG' in s: return 'PPRG'
            if 'PPLN' in s: return 'PPLN'
            if 'PLAN' in s: return 'PLAN'
            if 'RETE' in s: return 'RETE'
            return 'OTRO'
        df_grouped_om['Status Agrupado'] = df_grouped_om['Status de usuario'].apply(agrupar_om)
        
        tabla_oms_pivot = pd.crosstab(index=df_grouped_om['Programador'], columns=df_grouped_om['Status Agrupado'], margins=True, margins_name='TOTAL OMs')
        
        cols_deseadas_om = ['CREA', 'PPRG', 'PPLN', 'PLAN', 'RETE', 'TOTAL OMs']
        for col in cols_deseadas_om:
            if col not in tabla_oms_pivot.columns: tabla_oms_pivot[col] = 0
        tabla_oms_pivot = tabla_oms_pivot[cols_deseadas_om].reset_index()
        
        st.dataframe(tabla_oms_pivot, use_container_width=True, hide_index=True)
        
        # 2. Botón Interruptor para Gráficos
        if st.toggle("📊 Mostrar gráficos de OMs", key="toggle_graf_om"):
            st.markdown("<div class='qlik-container'>", unsafe_allow_html=True)
            col_g_om1, col_g_om2, col_g_om3 = st.columns(3)
            
            with col_g_om1:
                st.markdown("**OMs por Prioridad**")
                df_prio_om = om_filt.groupby('Prioridad').size().reset_index(name='Cantidad')
                fig_donut_om = px.pie(df_prio_om, values='Cantidad', names='Prioridad', hole=0.65, color_discrete_sequence=QLIK_COLORS)
                fig_donut_om.update_traces(textposition='inside', textinfo='value')
                fig_donut_om.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=True, paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_donut_om, use_container_width=True)
                
            with col_g_om2:
                st.markdown("**OMs por Status y Programador**")
                df_om_bar = df_grouped_om.groupby(['Programador', 'Status Agrupado']).size().reset_index(name='Cantidad')
                fig_bar_om = px.bar(df_om_bar, x='Programador', y='Cantidad', color='Status Agrupado', color_discrete_sequence=QLIK_COLORS)
                fig_bar_om.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_bar_om, use_container_width=True)
                
            with col_g_om3:
                st.markdown("**Total OMs por Centro de Emplazamiento**")
                df_centro = om_filt.groupby('ZONA').size().reset_index(name='Total OMs')
                fig_bar = px.bar(df_centro, x='ZONA', y='Total OMs', color='ZONA', text='Total OMs', color_discrete_map={'ARAUCO': '#DEB887', 'CHILLAN': '#800040', 'OTRAS': '#006580'})
                fig_bar.update_traces(textposition='outside')
                fig_bar.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_bar, use_container_width=True)
                
            st.markdown("</div>", unsafe_allow_html=True)
    else: 
        st.info("Sin datos para el resumen de OMs.")

# ---------------------------------------------------------------------
# TAB 1: RESUMEN EJECUTIVO
# ---------------------------------------------------------------------
with tab1:
    # --- SECCIÓN 1: RESUMEN DE AVISOS ---
    st.subheader("📋 Resumen de Avisos por Programador")
    if not av_filt.empty:
        col_m1, col_m2, col_m3, col_m4, col_m5, col_m6 = st.columns(6)
        col_m1.metric("TOTAL AVISOS", len(av_filt))
        
        # Métricas cruzadas de OMs — búsqueda exacta por campo 'Status de usuario'
        cant_crea = len(om_filt[om_filt['Status de usuario'].str.upper().str.contains('CREA', na=False)])
        cant_pprg = len(om_filt[om_filt['Status de usuario'].str.upper().str.contains('PPRG', na=False)])
        cant_ppln = len(om_filt[om_filt['Status de usuario'].str.upper().str.contains('PPLN', na=False)])
        cant_plan = len(om_filt[om_filt['Status de usuario'].str.upper().str.contains('PLAN', na=False) & ~om_filt['Status de usuario'].str.upper().str.contains('PPLN', na=False)])
        cant_rete = len(om_filt[om_filt['Status de usuario'].str.upper().str.contains('RETE', na=False)])
        
        col_m2.metric("CREA", cant_crea)
        col_m3.metric("PPRG", cant_pprg)
        col_m4.metric("PPLN", cant_ppln)
        col_m5.metric("PLAN", cant_plan)
        col_m6.metric("RETE", cant_rete)
        
        st.markdown("<hr style='margin-top: 0.5rem; margin-bottom: 1rem;'>", unsafe_allow_html=True)
        
        # 1. Crear Tabla
        df_grouped_av = av_filt.copy()
        
        # Mapeo con etiquetas de negocio comprensibles (corrige status crudos SAP)
        def agrupar_av(s):
            s = str(s).upper()
            if 'METR ORAS' in s: return 'OM Pend. Planificación'
            if 'METR' in s: return 'Aprobado Sin OM'
            if 'MEAB' in s: return 'Pendiente Aprobación'
            if 'RECH' in s or 'MECE' in s or 'MAEN' in s: return 'Rechazados/Cerrados'
            if 'CREA' in s: return 'Creado'
            if 'PPRG' in s: return 'Pre-programado'
            if 'PPLN' in s: return 'Pre-planificado'
            if 'PLAN' in s: return 'Planificado'
            if 'RETE' in s: return 'Retenido'
            return 'Otros'
            
        df_grouped_av['Status Renombrado'] = df_grouped_av['Status Filtro'].apply(agrupar_av)
        
        tabla_avisos_pivot = pd.crosstab(index=df_grouped_av['Programador'], columns=df_grouped_av['Status Renombrado'], margins=True, margins_name='TOTAL Avisos')
        # Mostrar todas las columnas que existan en los datos + el total
        cols_deseadas = ['Aprobado Sin OM', 'Pendiente Aprobación', 'OM Pend. Planificación', 'Rechazados/Cerrados', 'Creado', 'Pre-programado', 'Pre-planificado', 'Planificado', 'Retenido', 'Otros', 'TOTAL Avisos']
        cols_presentes = [c for c in cols_deseadas if c in tabla_avisos_pivot.columns]
        
        tabla_avisos_pivot = tabla_avisos_pivot[cols_presentes].reset_index()
        
        st.dataframe(tabla_avisos_pivot, use_container_width=True, hide_index=True)
        
        # 2. Botón Interruptor para Gráficos
        if st.toggle("📊 Mostrar gráficos de Avisos"):
            st.markdown("<div class='qlik-container'>", unsafe_allow_html=True)
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                st.markdown("**Avisos por Prioridad**")
                df_prio = av_filt.groupby('Prioridad').size().reset_index(name='Cantidad')
                fig_donut = px.pie(df_prio, values='Cantidad', names='Prioridad', hole=0.65, color_discrete_sequence=QLIK_COLORS)
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
                st.markdown("**Costo Planificado por Programador**")
                # Se grafica omitiendo el "Total general" para no distorsionar las barras
                fig_cost = px.bar(comb_df, x='Programador', y='Suma_Plan', text='Suma_Plan', color_discrete_sequence=['#006580'])
                fig_cost.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
                fig_cost.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_cost, use_container_width=True)
                
            with col_g4:
                st.empty() # Espacio disponible si se agrega otro gráfico
                
            st.markdown("</div>", unsafe_allow_html=True)
            
    else: 
        st.info("Sin datos para el resumen combinado.")

# ---------------------------------------------------------------------
# TAB 2: DETALLE AVISOS Y OMs (CON GRÁFICOS)
# ---------------------------------------------------------------------
with tab2:
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
    col_f1, col_f2, col_f3, col_f4 = st.columns([1, 1, 1, 1])
    t_plan = om_filt['Tota general (plan)'].sum()
    t_real = om_filt['Costes tot.reales'].sum()
    d_clp = t_plan - t_real  # Positivo = ahorro vs plan; Negativo = sobrecosto
    col_f1.metric("COSTO PLANIFICADO", f"${t_plan:,.0f}".replace(',', '.'))
    col_f2.metric("COSTO REAL", f"${t_real:,.0f}".replace(',', '.'))
    col_f3.metric("DESVIACIÓN (CLP)", f"${d_clp:,.0f}".replace(',', '.'))
    st.markdown("<hr style='margin-top: 25px; margin-bottom: 25px; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
    
    col_t2a, col_t2b = st.columns(2)
    
    with col_t2a:
        st.subheader("Desglose de Avisos")
        if not av_filt.empty:
            tabla_avisos = av_filt.groupby(['Status Filtro', 'Prioridad']).size().reset_index(name='Cantidad')
            st.dataframe(tabla_avisos, use_container_width=True, hide_index=True)
            
            fig_av = px.bar(tabla_avisos, x='Status Filtro', y='Cantidad', color='Prioridad', barmode='group', text='Cantidad', color_discrete_sequence=QLIK_COLORS)
            fig_av.update_traces(textposition='outside', hovertemplate="<b>Status:</b> %{x}<br><b>Cantidad:</b> %{y}<extra></extra>")
            fig_av.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_av, use_container_width=True)
        else: st.info("No hay Avisos para mostrar.")
            
    with col_t2b:
        st.subheader("Desglose de OMs y Costos")
        if not om_filt.empty:
            tabla_oms = om_filt.groupby(['Status de usuario', 'Prioridad']).agg(Cantidad=('Orden', 'count'), Costo_Plan=('Tota general (plan)', 'sum'), Costo_Real=('Costes tot.reales', 'sum')).reset_index()
            st.dataframe(tabla_oms.style.format({'Costo_Plan': '${:,.0f}', 'Costo_Real': '${:,.0f}'}), use_container_width=True, hide_index=True)
            
            # Gráfico comparativo Plan vs Real por Prioridad (corrige: antes solo mostraba Plan)
            tabla_oms_melt = tabla_oms.groupby('Prioridad').agg(Costo_Plan=('Costo_Plan','sum'), Costo_Real=('Costo_Real','sum')).reset_index()
            tabla_oms_melt = tabla_oms_melt.melt(id_vars='Prioridad', value_vars=['Costo_Plan', 'Costo_Real'], var_name='Tipo', value_name='Monto')
            tabla_oms_melt['Tipo'] = tabla_oms_melt['Tipo'].map({'Costo_Plan': 'Planificado', 'Costo_Real': 'Real'})
            fig_om = px.bar(tabla_oms_melt, x='Prioridad', y='Monto', color='Tipo', barmode='group',
                            title='Costo Planificado vs Real por Prioridad',
                            color_discrete_map={'Planificado': '#006580', 'Real': '#A3334E'},
                            text='Monto')
            fig_om.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
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
        titulos = {
            'MEAB':      'PENDIENTE APROBACIÓN (MEAB)',
            'METR':      'APROBADOS PENDIENTES OM (METR)',
            'METR ORAS': 'OM PENDIENTE PLANIFICACIÓN (METR ORAS)',
            'CREA':      'CREADOS (CREA)',
            'PPRG':      'PRE-PROGRAMADOS (PPRG)',
            'PPLN':      'PRE-PLANIFICADOS (PPLN)',
            'PLAN':      'PLANIFICADOS (PLAN)',
            'RETE':      'RETENIDOS (RETE)',
            'RECH':      'RECHAZADOS (RECH)',
        }
        # Selector de status a graficar (por defecto los 3 principales)
        status_disponibles = [s for s in titulos.keys() if s in df_t['Status Filtro'].unique()]
        status_sel_time = st.multiselect(
            "Status a visualizar:",
            options=status_disponibles,
            default=[s for s in ['MEAB', 'METR', 'METR ORAS'] if s in status_disponibles],
            key="time_status_sel"
        )
        
        for st_val in status_sel_time:
            df_plot = df_t[df_t['Status Filtro'] == st_val]
            if not df_plot.empty:
                st.markdown(f"**{titulos.get(st_val, st_val)}**")
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
        
        df_eficiencia['Desviacion_CLP'] = df_eficiencia['Planificado'] - df_eficiencia['Real']  # Positivo = ahorro
        
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
        
        # --- AQUÍ SE QUITA EL COLOR Y SE DA UN FORMATO LIMPIO ---
        df_eficiencia_disp = df_eficiencia.copy()
        for col in ['Planificado', 'Real', 'Desviacion_CLP']:
            df_eficiencia_disp[col] = df_eficiencia_disp[col].apply(lambda x: f"${x:,.0f}".replace(',', '.'))
            
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
