import streamlit as st
import pandas as pd
import re
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
import pytz
import sqlalchemy  # DB Sql Progress
import time
from sqlalchemy import text # para ejecutar SQL directo
DATABASE_URL = os.getenv("DATABASE_URL")

# Si existe el archivo secrets de Streamlit, sobrescribe la variable de entorno
try:
    if "DATABASE_URL" in st.secrets:
        DATABASE_URL = st.secrets["DATABASE_URL"]
except Exception:
    pass

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

# Mapeo de Estatus a Descripciones (para tooltips)
DICCIONARIO_STATUS = {
    # --- STATUS AVISOS ---
    'MAEN': 'Clase de aviso modificado',
    'MEAB': 'Mensaje Abierto',
    'METR': 'Mensaje Tratamiento',
    'ORAS': 'Orden Asignada',
    'MECE': 'Mensaje Cerrado',

    # --- ORIGEN/EMISOR DE AVISOS ---
    'MANT': 'Aviso emitido por mantenimiento',
    'PROD': 'Aviso emitido por produccion',
    'ADMI': 'Aviso emitido por administracion',
    'PERS': 'Aviso emitido por personal',
    'PRED': 'Aviso emitido por Mant. Predic.',
    'PREV': 'Aviso emitido por Prev. Riesgos',
    'INGE': 'Aviso emitido por ingeneria',
    'AMBI': 'Aviso emitido por M. Ambiente',
    'IDOC': 'Generacion de IDOC',

    # --- APROBACIONES DE AVISOS ---
    'APRO': 'Aprobado',
    'MIRQ': 'Se requiere mas inforamcion',

    # --- STATUS DE LAS ORDENES DE MANTENIMIENTO (OMs) ---
    'CREA': 'Creado',
    'PPLN': 'Pendiente de planificacion',
    'PLAN': 'Planificado',
    'PPRG': 'Pendiente de programacion',
    'PROG': 'Programado',
    'RECH': 'Rechazado',
    'RETE': 'Retener',

    # --- STATUS COMBINADOS / CONDICIONANTES ---
    'EMAT': 'Esperando Materiales',
    'ESRV': 'Esperando servicios',
    'RDET': 'Reprogramar fecha de la detencion'
}

def obtener_descripcion_status(status_str):
    if pd.isna(status_str) or not isinstance(status_str, str): return ""
    return " - ".join([DICCIONARIO_STATUS.get(p, p) for p in status_str.upper().split()])

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
        if DATABASE_URL:
            engine = sqlalchemy.create_engine(DATABASE_URL)
            avisos_df = pd.read_sql("SELECT * FROM avisos", engine)
            oms_df = pd.read_sql("SELECT * FROM oms", engine)
        else:
            avisos_df = pd.read_excel('Avisos IW28.xlsx')
            oms_df = pd.read_excel('OMs IW38.xlsx')
        
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

# Recuperar el usuario desde los parámetros de la URL si existe
url_user = st.query_params.get("user")
if url_user and st.session_state.usuario_activo is None:
    st.session_state.usuario_activo = url_user

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
                    # Guardamos el usuario en la URL para que resista el F5
                    st.query_params["user"] = nombre_input.strip()
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


    
# (Bloque de presencia duplicado eliminado)

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

@st.dialog("🔄 Actualizar Base de Datos")
def modal_actualizar():
    st.write("Cargue los reportes base (IW28 e IW38). Se actualizarán para todos los usuarios en tiempo real.")
    arch_avisos = st.file_uploader("Avisos IW28 (.xlsx)", type=["xlsx"])
    arch_oms = st.file_uploader("OMs IW38 (.xlsx)", type=["xlsx"])
    
    if st.button("Guardar en Base de Datos", use_container_width=True):
        if not arch_avisos and not arch_oms:
            st.warning("Debes subir al menos un archivo.")
            return
            
        progress_bar = st.progress(0, text="Iniciando carga...")
        try:
            act = False
            progress_bar.progress(20, text="Procesando archivos...")
            
            # Usar SQL si hay DATABASE_URL configurada
            if DATABASE_URL:
                engine = sqlalchemy.create_engine(DATABASE_URL)
                if arch_avisos:
                    df_av = pd.read_excel(arch_avisos)
                    progress_bar.progress(50, text="Subiendo Avisos a la nube...")
                    df_av.to_sql('avisos', engine, if_exists='replace', index=False)
                    act = True
                    
                if arch_oms:
                    df_om = pd.read_excel(arch_oms)
                    progress_bar.progress(80, text="Subiendo OMs a la nube...")
                    df_om.to_sql('oms', engine, if_exists='replace', index=False)
                    act = True
                    
                if act:
                    st.cache_data.clear()
                    # Guardar quién hizo la actualización y cuándo en PostgreSQL
                    chile_tz = pytz.timezone('America/Santiago')
                    hora_str = datetime.now(chile_tz).strftime('%d-%m-%Y %H:%M')
                    
                    with engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE IF NOT EXISTS meta_actualizacion (
                                id INT PRIMARY KEY,
                                usuario VARCHAR(100),
                                hora VARCHAR(100)
                            )
                        """))
                        conn.execute(text("""
                            INSERT INTO meta_actualizacion (id, usuario, hora) 
                            VALUES (1, :usr, :hr)
                            ON CONFLICT (id) 
                            DO UPDATE SET usuario = :usr, hora = :hr
                        """), {"usr": st.session_state.usuario_activo, "hr": hora_str})
                        conn.commit()
                        
            # Si no hay DB configurada, guardar como Excel local (Modo de prueba local)
            else:
                if arch_avisos:
                    df_av = pd.read_excel(arch_avisos)
                    progress_bar.progress(50, text="Guardando Avisos localmente...")
                    df_av.to_excel('Avisos IW28.xlsx', index=False)
                    act = True
                    
                if arch_oms:
                    df_om = pd.read_excel(arch_oms)
                    progress_bar.progress(80, text="Guardando OMs localmente...")
                    df_om.to_excel('OMs IW38.xlsx', index=False)
                    act = True

            if act:
                progress_bar.progress(100, text="¡Carga completada con éxito!")
                st.cache_data.clear()
                time.sleep(1.0)
                st.rerun()
                
        except Exception as e:
            progress_bar.empty()
            st.error(f"Error durante la actualización: {e}")

# =====================================================================
# SISTEMA DE PRESENCIA EN DB (INVISIBLE)
# =====================================================================
usuarios_en_linea = []
if st.session_state.usuario_activo:
    try:
        if DATABASE_URL:
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
                    VALUES (:usr, CURRENT_TIMESTAMP AT TIME ZONE 'UTC' AT TIME ZONE 'America/Santiago')
                    ON CONFLICT (nombre) 
                    DO UPDATE SET ultimo_acceso = CURRENT_TIMESTAMP AT TIME ZONE 'UTC' AT TIME ZONE 'America/Santiago'
                """), {"usr": st.session_state.usuario_activo})
                
                result = conn.execute(text("""
                    SELECT nombre FROM usuarios_activos 
                    WHERE ultimo_acceso >= (NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'America/Santiago') - INTERVAL '5 minutes'
                """))
                usuarios_en_linea = [row[0] for row in result]
                conn.commit()
        else:
            # MOCK local para presencia
            usuarios_en_linea = [st.session_state.usuario_activo]
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
_hora_act = "Pendiente de Carga"
_quien_act = ''

# Leer la última actualización desde PostgreSQL
try:
    if DATABASE_URL:
        engine_meta = sqlalchemy.create_engine(DATABASE_URL)
        with engine_meta.connect() as conn:
            res = conn.execute(text("SELECT usuario, hora FROM meta_actualizacion WHERE id = 1")).fetchone()
            if res:
                _quien_act = res[0]
                _hora_act = res[1]
except Exception:
    pass

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
        # Intentar mapear códigos numéricos. Si falla (ej. ya viene como texto "1 Muy Alta" u otro código), preservar el valor original.
        mapped_prio = pd.to_numeric(oms_df[col_prio_om], errors='coerce').map(MAPEO_PRIORIDAD_OM)
        oms_df['Prioridad'] = mapped_prio.fillna(oms_df[col_prio_om]).replace(r'^\s*$', 'Sin Prioridad', regex=True).fillna('Sin Prioridad').astype(str)
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
        # Limpiar variables de la URL para que no inicie sesión automáticamente de nuevo
        st.query_params.clear()
        
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
    # Lista base solicitada por el usuario
    status_base = [
        'CREA', 'PPLN', 'PLAN', 'PPRG', 'PROG', 'RECH', 'RETE', 
        'EMAT', 'ESRV', 'RDET', 
        'MAEN', 'MEAB', 'METR', 'ORAS', 'MECE', 
        'OTRO STATUS'
    ]
    
    # Extraer status reales de Avisos
    status_reales_av = list(av_temp['Status Filtro'].unique()) if not av_temp.empty and 'Status Filtro' in av_temp.columns else []
    
    # Extraer status reales de OMs (que pueden venir combinados ej: "CREA EMAT")
    status_reales_om = set()
    if not om_temp.empty and 'Status de usuario' in om_temp.columns:
        for s in om_temp['Status de usuario'].dropna():
            status_reales_om.update(str(s).split())
            
    status_todos = sorted(set(status_base) | set(status_reales_av) | status_reales_om)
    status_sel = filtro_gerencial("STATUS", status_todos, "fs")

# Filtrar Avisos y OMs solo si hay una selección específica
if status_sel and len(status_sel) < len(status_todos):
    # Avisos es match exacto del status principal (4 letras)
    if 'Status Filtro' in av_temp.columns:
        av_temp = av_temp[av_temp['Status Filtro'].isin(status_sel)]
    
    # OMs es match de cualquiera de las palabras en "Status de usuario"
    if not om_temp.empty and 'Status de usuario' in om_temp.columns:
        patron_om = r'\b(?:' + '|'.join(status_sel) + r')\b'
        om_temp = om_temp[om_temp['Status de usuario'].astype(str).str.contains(patron_om, case=False, regex=True)]

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
tab1, tab_om, tab4, tab2, tab5 = st.tabs([
    "📊 Resumen Avisos", 
    "✅ Resumen OMs",
    "👥 Carga de Trabajo", 
    "📋 Detalle Avisos y OMs", 
    "🗃️ Explorador de Datos"
])

# ---------------------------------------------------------------------
# TAB OM: RESUMEN DE OMS
# ---------------------------------------------------------------------
with tab_om:
    if not om_filt.empty:
        # --- SECCION 0: KPIs Operativos (Formato Compacto) ---
        # Calcular Espera de Servicios (ESRV) y Materiales (EMAT)
        espera_servicios = om_filt['Status de usuario'].astype(str).str.contains(r'\bESRV\b', case=False, regex=True).sum() if 'Status de usuario' in om_filt.columns else 0
        espera_materiales = om_filt['Status de usuario'].astype(str).str.contains(r'\bEMAT\b', case=False, regex=True).sum() if 'Status de usuario' in om_filt.columns else 0
        
        # Calcular Abiertas (ABIE) y Liberadas (LIB) por separado
        if 'Status del sistema' in om_filt.columns:
            oms_abiertas = om_filt['Status del sistema'].astype(str).str.contains(r'ABIE', case=False, regex=True).sum()
            oms_liberadas = om_filt['Status del sistema'].astype(str).str.contains(r'LIB', case=False, regex=True).sum()
        else:
            oms_abiertas = om_filt['Status de usuario'].astype(str).str.contains(r'ABIE', case=False, regex=True).sum() if 'Status de usuario' in om_filt.columns else 0
            oms_liberadas = om_filt['Status de usuario'].astype(str).str.contains(r'LIB', case=False, regex=True).sum() if 'Status de usuario' in om_filt.columns else 0
            
        st.markdown(f"""
        <div style="display: flex; justify-content: center; gap: 16px; padding: 12px 16px; margin-top: 5px; margin-bottom: 25px; background-color: #F8FAFC; border-radius: 8px; border: 1px solid #E2E8F0; align-items: center; flex-wrap: wrap;">
            <div style="font-size: 0.90rem; color: #475569;">
                <span style="font-size: 1.0rem; margin-right: 4px;">🛠️</span>
                <strong>Espera Servicios (ESRV):</strong> <span style="color: #0F172A; font-weight: 700; font-size: 1.0rem;">{f"{espera_servicios:,}".replace(',', '.')}</span>
            </div>
            <div style="width: 1px; height: 20px; background-color: #CBD5E1;"></div>
            <div style="font-size: 0.90rem; color: #475569;">
                <span style="font-size: 1.0rem; margin-right: 4px;">📦</span>
                <strong>Espera Materiales (EMAT):</strong> <span style="color: #0F172A; font-weight: 700; font-size: 1.0rem;">{f"{espera_materiales:,}".replace(',', '.')}</span>
            </div>
            <div style="width: 1px; height: 20px; background-color: #CBD5E1;"></div>
            <div style="font-size: 0.90rem; color: #475569;">
                <span style="font-size: 1.0rem; margin-right: 4px;">📂</span>
                <strong>Abiertas (ABIE):</strong> <span style="color: #0F172A; font-weight: 700; font-size: 1.0rem;">{f"{oms_abiertas:,}".replace(',', '.')}</span>
            </div>
            <div style="width: 1px; height: 20px; background-color: #CBD5E1;"></div>
            <div style="font-size: 0.90rem; color: #475569;">
                <span style="font-size: 1.0rem; margin-right: 4px;">🟢</span>
                <strong>Liberadas (LIB):</strong> <span style="color: #0F172A; font-weight: 700; font-size: 1.0rem;">{f"{oms_liberadas:,}".replace(',', '.')}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # --- SECCION 1: Dashboard Financiero ---
        st.subheader("Desglose de OMs y Costos")
        
        # 1. KPIs Financieros
        total_oms = len(om_filt)
        total_plan = om_filt['Tota general (plan)'].sum()
        total_real = om_filt['Costes tot.reales'].sum()
        desviacion = total_real - total_plan # Variación de Costo: Positivo = Sobrecosto, Negativo = Ahorro
        
        # Formateo correcto para que Streamlit detecte el signo negativo primero y lo ponga verde/abajo
        if desviacion < 0:
            delta_str = f"-${abs(desviacion):,.0f}".replace(',', '.')
        else:
            delta_str = f"${desviacion:,.0f}".replace(',', '.')
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Total OMs", f"{total_oms:,}")
        kpi2.metric("Pto. Planificado", f"${total_plan:,.0f}".replace(',', '.'))
        kpi3.metric("Costo Real", f"${total_real:,.0f}".replace(',', '.'))
        kpi4.metric(
            "Desviación Global", 
            f"${desviacion:,.0f}".replace(',', '.').replace('$-', '-$'),
            delta=delta_str, 
            delta_color="inverse"
        )
        

        # 2. Nueva Vista Entendible: Gráfico de Barras y Tabla Agrupada
        col_w1, col_w2 = st.columns([1, 1.2])
        
        with col_w1:
            st.markdown("**Comparativa de Costos (Planificado vs Real)**")
            # Barras Agrupadas por Prioridad
            df_barras = om_filt.groupby('Prioridad').agg(
                Planificado=('Tota general (plan)', 'sum'),
                Real=('Costes tot.reales', 'sum')
            ).reset_index()
            
            df_barras_melt = df_barras.melt(id_vars='Prioridad', value_vars=['Planificado', 'Real'], var_name='Tipo de Costo', value_name='Monto')
            
            # Crear texto con formato para el gráfico
            df_barras_melt['Monto_str'] = df_barras_melt['Monto'].apply(lambda x: f"${x:,.0f}".replace(',', '.'))
            
            fig_barras = px.bar(
                df_barras_melt, x='Prioridad', y='Monto', color='Tipo de Costo', barmode='group',
                color_discrete_map={'Planificado': '#006580', 'Real': '#A3334E'}, text='Monto_str'
            )
            fig_barras.update_traces(
                textposition='outside',
                hovertemplate="<b>Prioridad:</b> %{x}<br><b>%{data.name}:</b> %{text}<extra></extra>"
            )
            fig_barras.update_layout(margin=dict(t=30, l=10, r=10, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
            st.plotly_chart(fig_barras, use_container_width=True)
                
        with col_w2:
            st.markdown("**Tabla Analítica de OMs (Por Prioridad y Status)**")
            st.caption("Resumen completo de cantidades y presupuestos")
            df_tabla = om_filt.groupby(['Prioridad', 'Status de usuario']).agg(
                Cantidad=('Orden', 'count'),
                Planificado=('Tota general (plan)', 'sum'),
                Real=('Costes tot.reales', 'sum')
            ).reset_index()
            
            # Desviación = Real - Plan (Ahorro en Negativo, Sobrecosto en Positivo)
            df_tabla['Desviación'] = df_tabla['Real'] - df_tabla['Planificado']
            
            # MultiIndex para una vista limpia (Streamlit renderiza esto como agrupaciones)
            df_tabla = df_tabla.set_index(['Prioridad', 'Status de usuario'])
            
            # Aplicamos formato de moneda a las columnas financieras (usando lambda para forzar puntos de miles)
            formato = {
                'Cantidad': lambda x: f"{x:,.0f}".replace(',', '.'),
                'Planificado': lambda x: f"${x:,.0f}".replace(',', '.').replace('$-', '-$'),
                'Real': lambda x: f"${x:,.0f}".replace(',', '.').replace('$-', '-$'),
                'Desviación': lambda x: f"${x:,.0f}".replace(',', '.').replace('$-', '-$')
            }
            
            def color_desviacion(val):
                color = '#10B981' if val < 0 else '#A3334E' if val > 0 else 'black'
                return f'color: {color}; font-weight: bold;'
            
            # Dar color a la columna Desviación y formatear
            styler = df_tabla.style.map(color_desviacion, subset=['Desviación']).format(formato)
            
            st.dataframe(styler, use_container_width=True)
            
        st.markdown("<hr style='margin-top: 1rem; margin-bottom: 1rem;'>", unsafe_allow_html=True)
        
        # --- SECCION 2: Resumen por Programador ---
        st.subheader("✅ Resumen de OMs por Programador")
        
        df_grouped_om = om_filt.copy()
        
        # 1. Crear Tablas Pivot (Resumen General)
        col_res1, col_res2 = st.columns([1, 1.5])
        
        with col_res1:
            st.markdown("**Distribución por Prioridad**")
            st.caption("Cantidad de OMs asignadas a cada programador según su prioridad.")
            tabla_prio = pd.crosstab(index=df_grouped_om['Programador'], columns=df_grouped_om['Prioridad'], margins=True, margins_name='TOTAL')
            st.dataframe(tabla_prio.reset_index(), use_container_width=True, hide_index=True)
            
        with col_res2:
            st.markdown("**Distribución por Status**")
            st.caption("Cantidad de OMs asignadas a cada programador según el estado actual.")
            tabla_oms_pivot = pd.crosstab(index=df_grouped_om['Programador'], columns=df_grouped_om['Status de usuario'], margins=True, margins_name='TOTAL')
            st.dataframe(tabla_oms_pivot.reset_index(), use_container_width=True, hide_index=True)

        # 2. Detalle Completo (Solo si hay 1 programador seleccionado)
        if df_grouped_om['Programador'].nunique() == 1:
            prog_name = df_grouped_om['Programador'].iloc[0]
            st.markdown("<br>", unsafe_allow_html=True)
            st.info(f"Mostrando detalle completo de OMs asignadas a: **{prog_name}**")
            
            cols_to_show = ['Orden', 'Prioridad', 'Status de usuario', 'Equipo', 'Denominación de la ubicación técnica', 'Tota general (plan)', 'Costes tot.reales']
            cols_to_show = [c for c in cols_to_show if c in df_grouped_om.columns]
            
            df_detalle = df_grouped_om[cols_to_show].copy()
            
            # Formatear IDs para que Streamlit no los trate como números con comas
            if 'Orden' in df_detalle.columns:
                df_detalle['Orden'] = df_detalle['Orden'].astype(str).str.replace(r'\.0$', '', regex=True)
            if 'Equipo' in df_detalle.columns:
                df_detalle['Equipo'] = df_detalle['Equipo'].astype(str).str.replace(r'\.0$', '', regex=True)
            
            formato_detalle = {}
            if 'Tota general (plan)' in df_detalle.columns:
                formato_detalle['Tota general (plan)'] = lambda x: f"${x:,.0f}".replace(',', '.') if pd.notnull(x) else '$0'
            if 'Costes tot.reales' in df_detalle.columns:
                formato_detalle['Costes tot.reales'] = lambda x: f"${x:,.0f}".replace(',', '.') if pd.notnull(x) else '$0'
                
            st.dataframe(df_detalle.style.format(formato_detalle), use_container_width=True, hide_index=True)
        
        # 2. Botón Interruptor para Gráficos
        if st.toggle("📊 Mostrar gráficos de OMs", key="toggle_graf_om"):
            st.markdown("<div class='qlik-container'>", unsafe_allow_html=True)
            col_g_om1, col_g_om2, col_g_om3 = st.columns(3)
            
            with col_g_om1:
                st.markdown("**OMs por Prioridad**")
                df_prio_om = om_filt.groupby('Prioridad').size().reset_index(name='Cantidad')
                fig_donut_om = px.pie(df_prio_om, values='Cantidad', names='Prioridad', hole=0.65, color_discrete_sequence=QLIK_COLORS)
                fig_donut_om.update_traces(
                    textposition='inside', textinfo='value',
                    hovertemplate="<b>Prioridad:</b> %{label}<br><b>Cantidad:</b> %{value}<extra></extra>"
                )
                fig_donut_om.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=True, paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_donut_om, use_container_width=True)
                
            with col_g_om2:
                st.markdown("**OMs por Status y Programador**")
                df_om_bar = df_grouped_om.groupby(['Programador', 'Status de usuario']).size().reset_index(name='Cantidad')
                df_om_bar['Descripción'] = df_om_bar['Status de usuario'].apply(obtener_descripcion_status)
                fig_bar_om = px.bar(df_om_bar, x='Programador', y='Cantidad', color='Status de usuario', hover_data={'Descripción': True}, color_discrete_sequence=QLIK_COLORS)
                fig_bar_om.update_traces(hovertemplate="<b>Programador:</b> %{x}<br><b>Status:</b> %{data.name}<br><b>Descripción:</b> %{customdata[0]}<br><b>Cantidad:</b> %{y}<extra></extra>")
                fig_bar_om.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_bar_om, use_container_width=True)
                
            with col_g_om3:
                st.markdown("**Total OMs por Centro de Emplazamiento**")
                df_centro = om_filt.groupby('ZONA').size().reset_index(name='Total OMs')
                fig_bar = px.bar(df_centro, x='ZONA', y='Total OMs', color='ZONA', text='Total OMs', color_discrete_map={'ARAUCO': '#DEB887', 'CHILLAN': '#800040', 'OTRAS': '#006580'})
                fig_bar.update_traces(
                    textposition='outside',
                    hovertemplate="<b>Zona:</b> %{x}<br><b>Total OMs:</b> %{y}<extra></extra>"
                )
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
        # 1. Crear Tabla
        df_grouped_av = av_filt.copy()
        
        # 1. Crear Tablas Pivot (Resumen General)
        col_res1, col_res2 = st.columns([1, 1.5])
        
        with col_res1:
            st.markdown("**Distribución por Prioridad**")
            st.caption("Cantidad de Avisos asignados a cada programador según su prioridad.")
            tabla_prio_av = pd.crosstab(index=df_grouped_av['Programador'], columns=df_grouped_av['Prioridad'], margins=True, margins_name='TOTAL')
            st.dataframe(tabla_prio_av.reset_index(), use_container_width=True, hide_index=True)
            
        with col_res2:
            st.markdown("**Distribución por Status**")
            st.caption("Cantidad de Avisos asignados a cada programador según el estado actual.")
            tabla_avisos_pivot = pd.crosstab(index=df_grouped_av['Programador'], columns=df_grouped_av['Status Filtro'], margins=True, margins_name='TOTAL Avisos')
            
            # Forzar la aparición de columnas clave aunque estén en 0
            cols_fijas = ['CREA', 'PPRG', 'PPLN', 'PLAN', 'RETE', 'RECH', 'MAEN', 'MEAB', 'METR', 'METR ORAS', 'MECE', 'OTRO STATUS']
            for c in cols_fijas:
                if c not in tabla_avisos_pivot.columns:
                    tabla_avisos_pivot[c] = 0
                    
            # Reordenar las columnas manteniendo 'Programador' en index y 'TOTAL Avisos' al final
            cols_ordenadas = [c for c in cols_fijas if c in tabla_avisos_pivot.columns]
            otras_cols = [c for c in tabla_avisos_pivot.columns if c not in cols_fijas and c != 'TOTAL Avisos']
            tabla_avisos_pivot = tabla_avisos_pivot[cols_ordenadas + otras_cols + ['TOTAL Avisos']]
            
            st.dataframe(tabla_avisos_pivot.reset_index(), use_container_width=True, hide_index=True)
            
        # 2. Detalle Completo (Solo si hay 1 programador seleccionado)
        if df_grouped_av['Programador'].nunique() == 1:
            prog_name = df_grouped_av['Programador'].iloc[0]
            st.markdown("<br>", unsafe_allow_html=True)
            st.info(f"Mostrando detalle completo de Avisos asignados a: **{prog_name}**")
            
            cols_to_show_av = ['Aviso', 'Prioridad', 'Status del sistema', 'Status Filtro', 'Status Renombrado', 'Denominación de la ubicación técnica', 'Creado el', 'Días Abierto']
            cols_to_show_av = [c for c in cols_to_show_av if c in df_grouped_av.columns]
            
            df_detalle_av = df_grouped_av[cols_to_show_av].copy()
            
            # Formatear IDs para que Streamlit no los trate como números con comas
            if 'Aviso' in df_detalle_av.columns:
                df_detalle_av['Aviso'] = df_detalle_av['Aviso'].astype(str).str.replace(r'\.0$', '', regex=True)
                
            st.dataframe(df_detalle_av, use_container_width=True, hide_index=True)
        
        # 2. Botón Interruptor para Gráficos
        if st.toggle("📊 Mostrar gráficos de Avisos"):
            st.markdown("<div class='qlik-container'>", unsafe_allow_html=True)
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                st.markdown("**Avisos por Prioridad**")
                df_prio = av_filt.groupby('Prioridad').size().reset_index(name='Cantidad')
                fig_donut = px.pie(df_prio, values='Cantidad', names='Prioridad', hole=0.65, color_discrete_sequence=QLIK_COLORS)
                fig_donut.update_traces(
                    textposition='inside', textinfo='value',
                    hovertemplate="<b>Prioridad:</b> %{label}<br><b>Cantidad:</b> %{value}<extra></extra>"
                )
                fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=True, paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_donut, use_container_width=True)
                
            with col_g2:
                st.markdown("**Avisos por Status y Programador**")
                df_av_bar = av_filt.groupby(['Programador', 'Status Filtro']).size().reset_index(name='Cantidad')
                df_av_bar['Descripción'] = df_av_bar['Status Filtro'].apply(obtener_descripcion_status)
                fig_bar_av = px.bar(df_av_bar, x='Programador', y='Cantidad', color='Status Filtro', hover_data={'Descripción': True}, color_discrete_sequence=['#A3334E', '#006580', '#E5CDA8'])
                fig_bar_av.update_traces(hovertemplate="<b>Programador:</b> %{x}<br><b>Status:</b> %{data.name}<br><b>Descripción:</b> %{customdata[0]}<br><b>Cantidad:</b> %{y}<extra></extra>")
                fig_bar_av.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_bar_av, use_container_width=True)
                
            st.markdown("</div>", unsafe_allow_html=True)
    else: 
        st.info("Sin datos para el resumen de avisos.")

    st.markdown("---")

    # --- SECCIÓN 2: RESUMEN COMBINADO ---
    st.subheader("💼 Resumen Combinado (Cantidad de Avisos y OMs)")
    av_count = av_filt.groupby('Programador').size().reset_index(name='Cuenta de Aviso')
    om_agg = om_filt.groupby('Programador').agg(Cuenta_de_Orden=('Orden', 'count')).reset_index()
    comb_df = pd.merge(av_count, om_agg, on='Programador', how='outer').fillna(0)
    
    if not comb_df.empty:
        # 1. Crear Tabla
        total_row = pd.DataFrame({'Programador': ['Total general'], 'Cuenta de Aviso': [comb_df['Cuenta de Aviso'].sum()], 'Cuenta_de_Orden': [comb_df['Cuenta_de_Orden'].sum()]})
        comb_df_disp = pd.concat([comb_df, total_row], ignore_index=True)
        
        comb_df_disp.rename(columns={'Programador': 'Etiquetas de fila', 'Cuenta_de_Orden': 'Cuenta de Orden'}, inplace=True)
        comb_df_disp['Cuenta de Aviso'] = comb_df_disp['Cuenta de Aviso'].astype(int)
        comb_df_disp['Cuenta de Orden'] = comb_df_disp['Cuenta de Orden'].astype(int)
        
        num_cols_comb = [c for c in comb_df_disp.columns if c != 'Etiquetas de fila']
        st.dataframe(comb_df_disp.style.set_properties(subset=num_cols_comb, **{'text-align': 'center'}), use_container_width=True, hide_index=True)
        
        # 2. Botón Interruptor para Gráficos
        if st.toggle("📊 Mostrar gráfico Combinado"):
            st.markdown("<div class='qlik-container'>", unsafe_allow_html=True)
            
            st.markdown("**Cantidad de Avisos y OMs por Programador**")
            # Preparar datos para barras agrupadas
            comb_melt = comb_df.melt(id_vars=['Programador'], value_vars=['Cuenta de Aviso', 'Cuenta_de_Orden'], var_name='Tipo', value_name='Cantidad')
            comb_melt['Tipo'] = comb_melt['Tipo'].replace({'Cuenta de Aviso': 'Avisos', 'Cuenta_de_Orden': 'Órdenes (OMs)'})
            
            fig_comb = px.bar(comb_melt, x='Programador', y='Cantidad', color='Tipo', barmode='group', color_discrete_sequence=['#E4A11B', '#006580'])
            fig_comb.update_traces(
                texttemplate='%{y}', textposition='outside',
                hovertemplate="<b>Programador:</b> %{x}<br><b>%{data.name}:</b> %{y}<extra></extra>"
            )
            fig_comb.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend_title_text='')
            st.plotly_chart(fig_comb, use_container_width=True)
                
            st.markdown("</div>", unsafe_allow_html=True)
            
    else: 
        st.info("Sin datos para el resumen combinado.")

# ---------------------------------------------------------------------
# TAB 2: DETALLE AVISOS Y OMs (CON GRÁFICOS)
# ---------------------------------------------------------------------
with tab2:
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
    
    # ---------------------------------------------------------------------
    # 1. TOP KPIs DETALLADOS (AVISOS, OMS Y PROGRAMADOR)
    # ---------------------------------------------------------------------
    # AVISOS
    tot_av = len(av_filt)
    av_crea = len(av_filt[av_filt['Status Filtro'].astype(str).str.contains('CREA', case=False, na=False)]) if not av_filt.empty and 'Status Filtro' in av_filt.columns else 0
    av_ppln = len(av_filt[av_filt['Status Filtro'].astype(str).str.contains('PPLN', case=False, na=False)]) if not av_filt.empty and 'Status Filtro' in av_filt.columns else 0
    av_plan = len(av_filt[av_filt['Status Filtro'].astype(str).str.contains('PLAN', case=False, na=False)]) if not av_filt.empty and 'Status Filtro' in av_filt.columns else 0
    av_rete = len(av_filt[av_filt['Status Filtro'].astype(str).str.contains('RETE', case=False, na=False)]) if not av_filt.empty and 'Status Filtro' in av_filt.columns else 0
    
    # OMS
    tot_om = len(om_filt)
    om_abie = len(om_filt[om_filt['Status de usuario'].astype(str).str.contains('ABIE', case=False, na=False)]) if not om_filt.empty and 'Status de usuario' in om_filt.columns else 0
    om_lib = len(om_filt[om_filt['Status de usuario'].astype(str).str.contains('LIB', case=False, na=False)]) if not om_filt.empty and 'Status de usuario' in om_filt.columns else 0
    om_esrv = len(om_filt[om_filt['Status de usuario'].astype(str).str.contains('ESRV', case=False, na=False)]) if not om_filt.empty and 'Status de usuario' in om_filt.columns else 0
    om_emat = len(om_filt[om_filt['Status de usuario'].astype(str).str.contains('EMAT', case=False, na=False)]) if not om_filt.empty and 'Status de usuario' in om_filt.columns else 0

    # PROGRAMADOR ESTRELLA (Dinámico - Afectado por los filtros)
    if not om_filt.empty and 'Programador' in om_filt.columns:
        prog_counts = om_filt['Programador'].value_counts()
        top_prog = prog_counts.idxmax() if not prog_counts.empty else "N/A"
        top_prog_oms = prog_counts.max() if not prog_counts.empty else 0
        
        if top_prog != "N/A":
            df_top = om_filt[om_filt['Programador'] == top_prog]
            top_prog_costo = df_top['Costes tot.reales'].sum() if 'Costes tot.reales' in df_top.columns else 0
            top_prog_lib = len(df_top[df_top['Status de usuario'].astype(str).str.contains('LIB', case=False, na=False)]) if 'Status de usuario' in df_top.columns else 0
            top_prog_abie = len(df_top[df_top['Status de usuario'].astype(str).str.contains('ABIE', case=False, na=False)]) if 'Status de usuario' in df_top.columns else 0
        else:
            top_prog_costo = 0
            top_prog_lib = 0
            top_prog_abie = 0
    else:
        top_prog = "N/A"
        top_prog_oms = 0
        top_prog_costo = 0
        top_prog_lib = 0
        top_prog_abie = 0
        
    st.markdown(f"""
    <div style="display: flex; gap: 20px; justify-content: space-between; margin-bottom: 30px;">
        <div class="kpi-card-hover" style="flex: 1; background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border-left: 5px solid #006580; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: transform 0.2s;">
            <p style="margin: 0; font-size: 0.9rem; color: #64748b; font-weight: 600; text-transform: uppercase;">📋 Avisos Activos</p>
            <h2 style="margin: 10px 0 15px 0; font-size: 2.2rem; color: #0f172a;">{tot_av:,}</h2>
            <div style="display: flex; justify-content: space-between; font-size: 0.9rem; color: #334155; border-top: 1px solid #E2E8F0; padding-top: 10px;">
                <div style="text-align: center;"><strong>CREA</strong><br><span style="color: #64748b;">{av_crea:,}</span></div>
                <div style="text-align: center;"><strong>PPLN</strong><br><span style="color: #64748b;">{av_ppln:,}</span></div>
                <div style="text-align: center;"><strong>PLAN</strong><br><span style="color: #64748b;">{av_plan:,}</span></div>
                <div style="text-align: center;"><strong>RETE</strong><br><span style="color: #64748b;">{av_rete:,}</span></div>
            </div>
        </div>
        <div class="kpi-card-hover" style="flex: 1; background: linear-gradient(135deg, #ffffff 0%, #fef2f2 100%); border-left: 5px solid #A3334E; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: transform 0.2s;">
            <p style="margin: 0; font-size: 0.9rem; color: #64748b; font-weight: 600; text-transform: uppercase;">🛠️ Órdenes (OMs) Activas</p>
            <h2 style="margin: 10px 0 15px 0; font-size: 2.2rem; color: #A3334E;">{tot_om:,}</h2>
            <div style="display: flex; justify-content: space-between; font-size: 0.9rem; color: #334155; border-top: 1px solid #E2E8F0; padding-top: 10px;">
                <div style="text-align: center;"><strong>ABIE</strong><br><span style="color: #64748b;">{om_abie:,}</span></div>
                <div style="text-align: center;"><strong>LIB</strong><br><span style="color: #64748b;">{om_lib:,}</span></div>
                <div style="text-align: center;"><strong>ESRV</strong><br><span style="color: #64748b;">{om_esrv:,}</span></div>
                <div style="text-align: center;"><strong>EMAT</strong><br><span style="color: #64748b;">{om_emat:,}</span></div>
            </div>
        </div>
        <div class="kpi-card-hover" style="flex: 1; background: linear-gradient(135deg, #ffffff 0%, #f0fdf4 100%); border-left: 5px solid #7AB3A2; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: transform 0.2s;">
            <p style="margin: 0; font-size: 0.9rem; color: #64748b; font-weight: 600; text-transform: uppercase;">🏆 Top Programador</p>
            <h2 style="margin: 10px 0 5px 0; font-size: 1.6rem; color: #0f172a;">{top_prog}</h2>
            <div style="display: flex; gap: 15px; margin-bottom: 5px;">
                <div><span style="font-size: 1.1rem; font-weight: 700; color: #0f172a;">{top_prog_oms:,}</span> <span style="font-size: 0.8rem; color: #64748b;">OMs</span></div>
                <div><span style="font-size: 1.1rem; font-weight: 700; color: #0f172a;">${top_prog_costo:,.0f}</span> <span style="font-size: 0.8rem; color: #64748b;">Costo</span></div>
            </div>
            <div style="display: flex; justify-content: space-around; font-size: 0.9rem; color: #334155; border-top: 1px solid #E2E8F0; padding-top: 10px;">
                <div style="text-align: center;"><strong>ABIE</strong><br><span style="color: #64748b;">{top_prog_abie:,}</span></div>
                <div style="text-align: center;"><strong>LIB</strong><br><span style="color: #64748b;">{top_prog_lib:,}</span></div>
            </div>
        </div>
    </div>
    <style>
        .kpi-card-hover:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 15px rgba(0,0,0,0.1) !important;
        }}
    </style>
    """.replace(',', '.'), unsafe_allow_html=True)

    # ---------------------------------------------------------------------
    # 2. GRÁFICOS GERENCIALES (SIDE-BY-SIDE)
    # ---------------------------------------------------------------------
    if st.toggle("📊 Mostrar gráficos de Avisos", value=True, key="toggle_graf_tab2"):
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("<h4 style='text-align: center; color: #334155; margin-bottom: 0px;'>Distribución de Avisos por Status</h4>", unsafe_allow_html=True)
            if not av_filt.empty:
                df_av_status = av_filt['Status Filtro'].value_counts().reset_index()
                df_av_status.columns = ['Status Filtro', 'Cantidad']
                if not df_av_status.empty:
                    df_av_status['Descripción'] = df_av_status['Status Filtro'].apply(obtener_descripcion_status)
                    
                    fig_donut = px.pie(
                        df_av_status, values='Cantidad', names='Status Filtro', 
                        hole=0.55, custom_data=['Descripción'], color_discrete_sequence=QLIK_COLORS
                    )
                    fig_donut.update_traces(
                        textposition='outside', textinfo='percent+label',
                        hovertemplate="<b>%{label}</b><br>Desc: %{customdata[0]}<br>Cantidad: %{value}<extra></extra>"
                    )
                    fig_donut.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20), height=350, paper_bgcolor='rgba(0,0,0,0)')
                    # Anotación en el centro
                    fig_donut.add_annotation(text=f"<b>{len(av_filt)}</b><br>Avisos", x=0.5, y=0.5, font_size=20, showarrow=False)
                    st.plotly_chart(fig_donut, use_container_width=True)
                else:
                    st.info("No hay desglose de status para graficar.")
            else:
                st.info("Sin datos de Avisos.")

        with col_chart2:
            st.markdown("<h4 style='text-align: center; color: #334155; margin-bottom: 0px;'>Distribución de OMs por Prioridad</h4>", unsafe_allow_html=True)
            if not om_filt.empty:
                df_om_prio = om_filt.groupby(['Prioridad', 'Status de usuario']).size().reset_index(name='Cantidad')
                if not df_om_prio.empty:
                    fig_bar_om = px.bar(
                        df_om_prio, x='Prioridad', y='Cantidad', color='Status de usuario',
                        barmode='stack', text='Cantidad', color_discrete_sequence=QLIK_COLORS
                    )
                    fig_bar_om.update_traces(textposition='inside', hovertemplate="<b>Prioridad:</b> %{x}<br><b>Status:</b> %{data.name}<br><b>Total:</b> %{y}<extra></extra>")
                    fig_bar_om.update_layout(margin=dict(t=20, b=20, l=10, r=10), height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_bar_om, use_container_width=True)
                else:
                    st.info("No hay desglose de prioridades para graficar.")
            else:
                st.info("Sin datos de OMs.")

    st.markdown("<hr style='margin-top: 10px; margin-bottom: 30px; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # ---------------------------------------------------------------------
    # 3. TABLAS DE RESUMEN (PIVOT TABLES)
    # ---------------------------------------------------------------------
    st.markdown("<h4 style='text-align: center; color: #334155; margin-top: 20px; margin-bottom: 20px;'>Resumen Estructurado de Datos</h4>", unsafe_allow_html=True)
    
    col_res_av, col_res_om = st.columns(2)

    with col_res_av:
        st.markdown("**📋 Resumen de Avisos (Cantidades)**")
        if not av_filt.empty:
            # Tabla dinámica: Status Filtro vs Prioridad
            try:
                resumen_av = pd.crosstab(
                    av_filt['Status Filtro'].apply(obtener_descripcion_status), 
                    av_filt['Prioridad'],
                    margins=True, margins_name="Total General"
                )
                st.dataframe(resumen_av, use_container_width=True)
            except Exception as e:
                # Fallback simple
                df_av_sum = av_filt.groupby(['Prioridad', 'Status Filtro']).size().reset_index(name='Cantidad Avisos')
                st.dataframe(df_av_sum, use_container_width=True, hide_index=True)
        else:
            st.write("No hay Avisos para resumir.")

    with col_res_om:
        st.markdown("**🛠️ Resumen de OMs (Cantidades y Costos)**")
        if not om_filt.empty:
            # Agrupación por Prioridad y Status
            df_om_sum = om_filt.groupby(['Prioridad', 'Status de usuario']).agg(
                Cantidad_OMs=('Orden', 'count'),
                Costo_Planificado=('Tota general (plan)', 'sum'),
                Costo_Real=('Costes tot.reales', 'sum')
            ).reset_index()
            
            # Formatear números a moneda
            df_om_sum['Costo_Planificado'] = df_om_sum['Costo_Planificado'].apply(lambda x: f"${x:,.0f}".replace(',', '.'))
            df_om_sum['Costo_Real'] = df_om_sum['Costo_Real'].apply(lambda x: f"${x:,.0f}".replace(',', '.'))
            
            st.dataframe(df_om_sum, use_container_width=True, hide_index=True)
        else:
            st.write("No hay OMs para resumir.")

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
        df_carga['Semana_Num'] = df_carga['Fecha Creacion OM'].dt.isocalendar().week
        df_carga['Semana'] = "Semana " + df_carga['Semana_Num'].astype(str)

        fechas_validas = df_carga['Fecha'].dropna()
        if not fechas_validas.empty:
            f_min, f_max = fechas_validas.min(), fechas_validas.max()
            
            # Safeguard against NaT
            if pd.isna(f_min) or pd.isna(f_max):
                import datetime
                f_min = f_max = datetime.date.today()
                
            col_d1, col_d2, col_d3 = st.columns([2, 2, 6])
            with col_d1:
                fecha_inicio = st.date_input("📅 Desde", value=f_min, min_value=f_min, max_value=f_max, key="carga_desde")
            with col_d2:
                fecha_fin = st.date_input("📅 Hasta", value=f_max, min_value=f_min, max_value=f_max, key="carga_hasta")
            df_carga = df_carga[(df_carga['Fecha'] >= fecha_inicio) & (df_carga['Fecha'] <= fecha_fin)]

        if df_carga.empty:
            st.warning("No hay OMs creadas en el rango de fechas seleccionado.")
        else:
            # Tabla resumen limpia: solo total OMs
            df_resumen_carga = df_carga.groupby('Programador').agg(
                Total_OMs=('Orden', 'count')
            ).reset_index()
            df_resumen_carga.rename(columns={'Total_OMs': 'Total OMs'}, inplace=True)
            
            # Fila de total
            total_carga = pd.DataFrame({
                'Programador': ['Total general'],
                'Total OMs': [int(df_resumen_carga['Total OMs'].sum())]
            })
            st.dataframe(
                pd.concat([df_resumen_carga, total_carga], ignore_index=True),
                use_container_width=True, hide_index=True
            )
    
            # Gráfico único de barras por semana
            df_agg_sem = df_carga.groupby(['Semana_Num', 'Semana', 'Programador']).size().reset_index(name='OMs Creadas')
            df_agg_sem = df_agg_sem.sort_values('Semana_Num')
            colores_prog = ['#006580', '#A3334E', '#E5CDA8', '#7AB3A2', '#4C2C69']
    
            fig_carga = px.bar(
                df_agg_sem, x='Semana', y='OMs Creadas', color='Programador',
                barmode='group', text='OMs Creadas',
                color_discrete_sequence=colores_prog,
                labels={'Semana': 'Semana del Año', 'OMs Creadas': 'Nº OMs'}
            )
            fig_carga.update_traces(textposition='outside', hovertemplate="<b>%{x}</b><br><b>Programador:</b> %{data.name}<br><b>Cantidad:</b> %{y}<extra></extra>")
            fig_carga.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=420,
                margin=dict(t=30, b=10, l=10, r=10),
                xaxis_title=None
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
        fig_costos.update_traces(hovertemplate="<b>Programador:</b> %{x}<br><b>%{data.name}:</b> $%{y:,.0f}<extra></extra>")
        fig_costos.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_costos, use_container_width=True)
        
        st.markdown("### Detalle de Desviaciones (CLP)")
        
        # --- AQUÍ SE QUITA EL COLOR Y SE DA UN FORMATO LIMPIO ---
        df_eficiencia_disp = df_eficiencia.copy()
        for col in ['Planificado', 'Real', 'Desviacion_CLP']:
            df_eficiencia_disp[col] = df_eficiencia_disp[col].apply(lambda x: f"${x:,.0f}".replace(',', '.'))
            
        num_cols_efi = [c for c in df_eficiencia_disp.columns if c != 'Programador']
        st.dataframe(df_eficiencia_disp.style.set_properties(subset=num_cols_efi, **{'text-align': 'center'}), use_container_width=True, hide_index=True)
    else: 
        st.info("No hay datos de costos suficientes para el análisis.")

# ---------------------------------------------------------------------
# TAB 5: EXPLORADOR DE DATOS CRUDOS
# ---------------------------------------------------------------------
with tab5:
    st.subheader("⚠️ Auditoría de Asignaciones (Otro / Sin Asignar)")
    st.write("Esta sección muestra los registros que no cumplieron las reglas (Grupo de Planificación, Centro, o Ubicación Técnica) y cayeron en 'Otro / Sin Asignar'.")
    
    col_aud_1, col_aud_2 = st.columns(2)
    with col_aud_1:
        st.markdown("**Avisos sin Asignar**")
        av_sin_asignar = avisos_df[avisos_df['Programador'] == 'Otro / Sin Asignar']
        if not av_sin_asignar.empty:
            cols_show_av = [c for c in ['Aviso', 'Centro emplazamiento', 'Grupo planificación', 'Denominación de la ubicación técnica'] if c in av_sin_asignar.columns]
            st.dataframe(av_sin_asignar[cols_show_av], use_container_width=True, hide_index=True)
        else:
            st.success("¡Todos los avisos tienen un programador!")
            
    with col_aud_2:
        st.markdown("**OMs sin Asignar**")
        om_sin_asignar = oms_df[oms_df['Programador'] == 'Otro / Sin Asignar']
        if not om_sin_asignar.empty:
            cols_show_om = [c for c in ['Orden', 'Centro emplazamiento', 'Grupo planificación', 'Denominación de la ubicación técnica'] if c in om_sin_asignar.columns]
            st.dataframe(om_sin_asignar[cols_show_om], use_container_width=True, hide_index=True)
        else:
            st.success("¡Todas las OMs tienen un programador!")
            
    st.markdown("---")
    
    st.subheader("Matriz Interactiva (Avisos)")
    if not av_filt.empty:
        st.dataframe(av_filt[['Aviso', 'ZONA', 'Programador', 'Status Filtro', 'Prioridad', 'Denominación de la ubicación técnica', 'Creado el', 'Días Abierto']], use_container_width=True, hide_index=True)
    else: st.info("No hay datos de Avisos para mostrar.")
        
    st.markdown("---")
    st.subheader("Matriz Interactiva (OMs)")
    if not om_filt.empty:
        cols_om_strict = [
            'Prioridad', 
            'Denominación de la ubicación técnica', 
            'Equipo', 
            'Denominación del objeto técnico', 
            'Denominación de objeto técnico', # Fallback por si en el excel dice "de" en lugar de "del"
            'Texto breve', 
            'Tota general (plan)', 
            'Costes tot.reales',
            'Plan de Verificación',
            'Verificación Manual'
        ]
        cols_to_show = [c for c in cols_om_strict if c in om_filt.columns]
        # Remover duplicados manteniendo el orden
        cols_to_show = list(dict.fromkeys(cols_to_show))
        st.dataframe(om_filt[cols_to_show], use_container_width=True, hide_index=True)
    else:
        st.info("No hay datos de OMs para mostrar.")
