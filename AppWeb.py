import streamlit as st
import pandas as pd
import requests
import io
import json
from datetime import datetime, timezone, timedelta

# 1. Configuración profesional de la página
st.set_page_config(page_title="YOBEL - Almacén Plásticos", layout="centered")

# ====================================================================================
# 🛠️ SECCIÓN DE ENLACES: MANTÉN AQUÍ TUS URLS OFICIALES
# ====================================================================================
URL_HOJA_DE_CALCULO = "https://docs.google.com/spreadsheets/d/1UbjMP0OtiikjaCo9Ykr8kdOeB63VyFBJNB8RJDuDqXE/edit?gid=0#gid=0"
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbwz585fxOLSU4SfbfkD26b30ZXs5SrqqIWGGFkeDt6d4zdP50xntyVgkiGnXNabIHrlVg/exec"
CAPACIDAD_TOTAL_POSICIONES = 180
# ====================================================================================

# --- FUNCIONES DE APOYO (Normalización y Carga) ---
def normalizar_codigo_articulo(sku):
    if pd.isna(sku) or str(sku).strip() == "": return ""
    sku_limpio = str(sku).strip().split('.')[0]
    if sku_limpio.isdigit() and len(sku_limpio) == 8: return f"0{sku_limpio}"
    return sku_limpio

def generar_url_export(url_usuario):
    if "/d/" in url_usuario:
        id_sheet = url_usuario.split("/d/")[1].split("/")[0]
        return f"https://docs.google.com/spreadsheets/d/{id_sheet}/export?format=csv&gid=0"
    return url_usuario

URL_FINAL_CSV = generar_url_export(URL_HOJA_DE_CALCULO)

@st.cache_data(ttl=5)
def cargar_maestro_nube():
    try:
        df = pd.read_csv(URL_FINAL_CSV, skiprows=1, dtype=str)
        df = df.iloc[:126] 
        df.columns = [str(c).strip().upper() for c in df.columns]
        col_articulo, col_descripcion, col_logico = None, None, None
        for col in df.columns:
            c_limpia = col.replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U').replace('Á', 'A').replace('É', 'E')
            if 'ARTICULO' in c_limpia or 'SKU' in c_limpia: col_articulo = col
            elif 'DESCRIPCION' in c_limpia or 'PRODUCTO' in c_limpia: col_descripcion = col
            elif 'LOGICO' in c_limpia: col_logico = col
        if col_articulo and col_descripcion and col_logico:
            df = df.rename(columns={col_articulo: 'ARTICULO', col_descripcion: 'DESCRIPCIÓN', col_logico: 'LÓGICO'})
            df = df.dropna(subset=['ARTICULO', 'DESCRIPCIÓN'])
            df['ARTICULO'] = df['ARTICULO'].apply(normalizar_codigo_articulo).str.upper()
            df['LÓGICO'] = pd.to_numeric(df['LÓGICO'].astype(str).str.replace('.', '', regex=False).str.replace(',', '', regex=False), errors='coerce').fillna(0).astype(int)
            return df[['ARTICULO', 'DESCRIPCIÓN', 'LÓGICO']]
    except: pass
    return pd.DataFrame()

df_maestro = cargar_maestro_nube()

def obtener_historico_nube():
    try:
        response = requests.get(URL_APPS_SCRIPT, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                df.columns = [str(c).upper() for c in df.columns]
                if 'ARTICULO' in df.columns: df['ARTICULO'] = df['ARTICULO'].apply(normalizar_codigo_articulo).str.upper()
                return df
    except: pass
    return pd.DataFrame()

# --- LÓGICA DE ESCANEO ---
def ejecutar_conteo_sku():
    sku_input = normalizar_codigo_articulo(st.session_state.scanner.strip().upper())
    if not sku_input or df_maestro.empty: return
    match = df_maestro[df_maestro['ARTICULO'] == sku_input]
    if not match.empty:
        sku_real = match.iloc[0]['ARTICULO']
        st.session_state.sku_activo = sku_real
        lote_input = st.session_state.lote_paso.strip().upper() if st.session_state.lote_paso.strip() else "SIN LOTE"
        hora_peru = datetime.now(timezone(timedelta(hours=-5)))
        payload = {
            "hora": hora_peru.strftime("%d/%m/%Y %H:%M:%S"),
            "rack": st.session_state.rack_paso,
            "nivel": st.session_state.nivel_paso,
            "articulo": sku_real,
            "descripcion": match.iloc[0]['DESCRIPCIÓN'],
            "lote": lote_input,
            "cantidad": int(st.session_state.cantidad_paso),
            "operario": st.session_state.username.strip()
        }
        try:
            requests.post(URL_APPS_SCRIPT, data=json.dumps(payload), timeout=5)
            st.session_state.feedback = f"✅ Ubicación {st.session_state.rack_paso}-{st.session_state.nivel_paso}: +{st.session_state.cantidad_paso} und para {match.iloc[0]['DESCRIPCIÓN']}"
        except: st.session_state.feedback = "❌ Error de red."
    else: st.session_state.feedback = f"❌ Código '{sku_input}' no existe."
    st.session_state.scanner = ""

# ====================================================================================
# 🚪 INTERFAZ DE BIENVENIDA (DISEÑO MEJORADO)
# ====================================================================================
if 'username' not in st.session_state or not st.session_state.username.strip():
    # Contenedor para centrar logo y título
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
    
    with col_logo2:
        # Logo oficial horizontal de Yobel
        st.image("https://ii.ct-stc.com/3/logos/empresas/2025/12/05/yobel-supply-chain-management-sa-BA7800713145E8A3181330thumbnail.png", use_container_width=True)
        
        # Título Estilizado
        st.markdown("""
            <h1 style='text-align: center; color: #000000; font-family: tahoma; font-size: 32px; margin-top: -10px;'>
                ALMACÉN PLÁSTICOS
            </h1>
            <p style='text-align: center; color: #000000; font-size: 18px;'>Registro de Conteo Cíclico</p>
            <hr style='border: 1px solid #000000;'>
        """, unsafe_allow_html=True)

    # Formulario de ingreso
    nombre_input = st.text_input("Nombre y Apellido del Operario:", key="temp_name", placeholder="Ej: Beyker")
    if st.button("INGRESAR AL SISTEMA", type="primary", use_container_width=True):
        if nombre_input.strip():
            st.session_state.username = nombre_input.strip()
            st.rerun()
    st.stop()

# ====================================================================================
# 🚀 INTERFAZ PRINCIPAL (DESPUÉS DEL LOGIN)
# ====================================================================================
st.markdown(f"<h2 style='color: #000000;'> Control de Inventario</h2>", unsafe_allow_html=True)
st.sidebar.markdown(f"### 👤 Colaborador:\n**{st.session_state.username}**")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.username = ""
    st.rerun()

# --- Resto del código (Ubicación, Captura, Métricas) ---
st.markdown("### 📥 Ubicación")
col_r, col_n = st.columns(2)
with col_r: st.selectbox("RACK:", options=["1", "2", "3","4","5","F75-3","Preformas","Horizontal"], key="rack_paso")
with col_n: st.selectbox("NIVEL:", options=["1er","2do","3er","4to"], key="nivel_paso")

st.markdown("### 📥 Captura")
c_c, c_l, c_s = st.columns([1, 1.5, 2.5])
with c_c: st.number_input("Cant:", min_value=1, value=1, key="cantidad_paso")
with c_l: st.text_input("Lote:", value="", placeholder="Ej: 3377887", key="lote_paso")
with c_s: st.text_input("Código:", key="scanner", on_change=ejecutar_conteo_sku)

if 'feedback' in st.session_state: st.info(st.session_state.feedback)

# Métricas e Inspección (Sección UCA)
df_historico = obtener_historico_nube()
st.write("---")
if not df_historico.empty and 'RACK' in df_historico.columns:
    pos_ocupadas = df_historico.groupby(['RACK', 'NIVEL']).size().shape[0]
    uca = (pos_ocupadas / CAPACIDAD_TOTAL_POSICIONES) * 100
    m1, m2 = st.columns(2)
    m1.metric("📈 UCA (Utilización)", f"{uca:.1f}%")
    m2.metric("📍 Posiciones", f"{pos_ocupadas} / {CAPACIDAD_TOTAL_POSICIONES}")

# Kardex y Tabla
if not df_historico.empty:
    st.subheader("🕒 Kardex Global")
    st.dataframe(df_historico[['HORA', 'RACK', 'NIVEL', 'ARTICULO', 'CANTIDAD', 'OPERARIO']].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)