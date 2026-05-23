import streamlit as st
import pandas as pd
import requests
import io
import json
from datetime import datetime

# 1. Configuración profesional de la página
st.set_page_config(page_title="Yobel WMS - Conteo Cíclico Cloud", layout="centered")

# ====================================================================================
# 🛠️ SECCIÓN DE ENLACES: MANTÉN AQUÍ TUS URLS OFICIALES
# ====================================================================================
URL_HOJA_DE_CALCULO = "https://docs.google.com/spreadsheets/d/1UbjMP0OtiikjaCo9Ykr8kdOeB63VyFBJNB8RJDuDqXE/edit?gid=0#gid=0"

# ⚠️ RECUERDA COLOCAR AQUÍ TU URL DE GOOGLE APPS SCRIPT (LA QUE TERMINA EN /EXEC)
URL_APPS_SCRIPT = "TU_URL_DE_APPS_SCRIPT_AQUI"
# ====================================================================================

# --- 🎯 FUNCIÓN DE BLINDAJE LOGÍSTICO (Elimina .0 y devuelve el cero inicial) ---
def normalizar_codigo_articulo(sku):
    if pd.isna(sku) or str(sku).strip() == "":
        return ""
    sku_limpio = str(sku).strip().split('.')[0]
    if sku_limpio.isdigit() and len(sku_limpio) == 8:
        return f"0{sku_limpio}"
    return sku_limpio

def generar_url_export(url_usuario):
    if "/d/" in url_usuario:
        id_sheet = url_usuario.split("/d/")[1].split("/")[0]
        return f"https://docs.google.com/spreadsheets/d/{id_sheet}/export?format=csv&gid=0"
    return url_usuario

URL_FINAL_CSV = generar_url_export(URL_HOJA_DE_CALCULO)

# --- 2. CARGA DEL MAESTRO DESDE GOOGLE SHEETS ---
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
            df['DESCRIPCIÓN'] = df['DESCRIPCIÓN'].astype(str).str.strip()
            
            df['LÓGICO'] = df['LÓGICO'].astype(str).str.strip().str.replace('.', '', regex=False).str.replace(',', '', regex=False)
            df['LÓGICO'] = pd.to_numeric(df['LÓGICO'], errors='coerce').fillna(0).astype(int)
            
            return df[['ARTICULO', 'DESCRIPCIÓN', 'LÓGICO']]
    except Exception as e:
        st.error(f"🚨 Error de comunicación con Google Sheets: {e}")
    return pd.DataFrame()

df_maestro = cargar_maestro_nube()

# --- 3. LECTURA DEL KARDEX DESDE LA NUBE ---
def obtener_historico_nube():
    if "TU_URL_DE_APPS_SCRIPT_AQUI" in URL_APPS_SCRIPT:
        return pd.DataFrame(columns=['HORA', 'ARTICULO', 'DESCRIPCIÓN', 'LOTE', 'CANTIDAD', 'OPERARIO'])
    try:
        response = requests.get(URL_APPS_SCRIPT, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                df.columns = [str(c).upper() for c in df.columns]
                
                if 'ARTICULO' in df.columns:
                    df['ARTICULO'] = df['ARTICULO'].apply(normalizar_codigo_articulo).str.upper()
                return df
    except:
        pass
    return pd.DataFrame(columns=['HORA', 'ARTICULO', 'DESCRIPCIÓN', 'LOTE', 'CANTIDAD', 'OPERARIO'])

# --- 4. LÓGICA DE PROCESAMIENTO DE ESCANEO ---
def ejecutar_conteo_sku():
    sku_input = normalizar_codigo_articulo(st.session_state.scanner.strip().upper())
    if not sku_input: return

    if not df_maestro.empty:
        match = df_maestro[df_maestro['ARTICULO'] == sku_input]
        
        if not match.empty:
            sku_real = match.iloc[0]['ARTICULO']
            st.session_state.sku_activo = sku_real
            cant_unidades = int(st.session_state.cantidad_paso)
            lote_input = st.session_state.lote_paso.strip().upper() if st.session_state.lote_paso.strip() else "SIN LOTE"
            desc_prod = match.iloc[0]['DESCRIPCIÓN']
            op_actual = st.session_state.username.strip()
            
            # 📦 Se añade la variable 'lote' al paquete que viaja a Google Drive
            payload = {
                "hora": datetime.now().strftime("%H:%M:%S"),
                "articulo": sku_real,
                "descripcion": desc_prod,
                "lote": lote_input,
                "cantidad": cant_unidades,
                "operario": op_actual
            }
            
            try:
                if "TU_URL_DE_APPS_SCRIPT_AQUI" not in URL_APPS_SCRIPT:
                    requests.post(URL_APPS_SCRIPT, data=json.dumps(payload), timeout=5)
                st.session_state.feedback = f"✅ Sincronizado en la Nube: +{cant_unidades} und (Lote: {lote_input}) para {desc_prod}"
            except:
                st.session_state.feedback = "❌ Error de red al enviar a la nube."
        else:
            st.session_state.feedback = f"❌ El código '{sku_input}' no existe en el maestro."
    st.session_state.scanner = ""

def ejecutar_conteo_por_boton():
    if 'sku_activo' in st.session_state and st.session_state.sku_activo:
        sku_real = st.session_state.sku_activo
        match = df_maestro[df_maestro['ARTICULO'] == sku_real]
        if not match.empty:
            cant_unidades = int(st.session_state.cantidad_paso)
            lote_input = st.session_state.lote_paso.strip().upper() if st.session_state.lote_paso.strip() else "SIN LOTE"
            desc_prod = match.iloc[0]['DESCRIPCIÓN']
            op_actual = st.session_state.username.strip()
            
            payload = {
                "hora": datetime.now().strftime("%H:%M:%S"),
                "articulo": sku_real,
                "descripcion": desc_prod,
                "lote": lote_input,
                "cantidad": cant_unidades,
                "operario": op_actual
            }
            try:
                if "TU_URL_DE_APPS_SCRIPT_AQUI" not in URL_APPS_SCRIPT:
                    requests.post(URL_APPS_SCRIPT, data=json.dumps(payload), timeout=5)
                st.session_state.feedback = f"✅ Añadido a la Nube: +{cant_unidades} und (Lote: {lote_input}) para {desc_prod}"
            except:
                st.session_state.feedback = "❌ Error de red al sumar unidades."

# --- 5. INTERFAZ GRÁFICA ---
if df_maestro.empty:
    st.warning("🔄 Sincronizando con Google Sheets...")
    st.stop()

# CONTROL DE ACCESO
if 'username' not in st.session_state or not st.session_state.username.strip():
    st.title("📦 Yobel SCM - Registro Cloud")
    nombre_input = st.text_input("Ingrese su Nombre y Apellido:", key="temp_name")
    if st.button("INGRESAR AL SISTEMA", type="primary", use_container_width=True):
        if nombre_input.strip():
            st.session_state.username = nombre_input.strip()
            st.rerun()
    st.stop()

st.title("🚀 Yobel SCM - Conteo Cíclico Real-Time")
st.sidebar.markdown(f"### 👤 Operario Activo:\n**{st.session_state.username}**")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.username = ""
    st.session_state.sku_activo = None
    st.rerun()

st.markdown("### 📥 Captura de Datos")

# Repartimos la fila en 3 columnas: Cantidad, Lote y Escáner
col_cant, col_lote, col_scan = st.columns([1, 1.5, 2.5])
with col_cant:
    st.number_input("Cantidad:", min_value=1, value=1, step=1, key="cantidad_paso")
with col_lote:
    st.text_input("Lote del Artículo:", value="", placeholder="Ej: L2026", key="lote_paso")
with col_scan:
    st.text_input("Escanear Artículo:", key="scanner", on_change=ejecutar_conteo_sku)

if 'sku_activo' in st.session_state and st.session_state.sku_activo:
    col1, col2 = st.columns(2)
    with col1: st.button("➕ SUMAR AL CÓDIGO ACTIVO", type="primary", use_container_width=True, on_click=ejecutar_conteo_por_boton)
    with col2: st.button("🔄 CAMBIAR CÓDIGO", type="secondary", use_container_width=True, on_click=lambda: st.session_state.update({"sku_activo": None}))

if 'feedback' in st.session_state:
    st.info(st.session_state.feedback)

# TRAER HISTORIAL RECIENTE
df_historico = obtener_historico_nube()

st.write("---")
st.subheader("🔍 Inspección del Artículo")
if 'sku_activo' in st.session_state and st.session_state.sku_activo:
    sku = st.session_state.sku_activo
    info_maestro = df_maestro[df_maestro['ARTICULO'] == sku].iloc[0]
    
    total_acumulado = 0
    if not df_historico.empty and 'CANTIDAD' in df_historico.columns:
        df_sku = df_historico[df_historico['ARTICULO'] == sku]
        total_acumulado = pd.to_numeric(df_sku['CANTIDAD'], errors='coerce').sum()

    c1, c2, c3 = st.columns(3)
    with c1: 
        st.metric(label="Código de Artículo", value=str(sku))
        st.caption(f"**Producto:** {info_maestro['DESCRIPCIÓN']}")
    with c2: 
        st.metric(label="📊 Stock Lógico", value=f"{info_maestro['LÓGICO']:,}".replace(",", "."))
    with c3: 
        st.metric(label="📦 Acumulado Nube (Todos)", value=f"{int(total_acumulado):,}".replace(",", "."))
else:
    st.info("💡 Escanee un artículo para desplegar su ficha de auditoría.")

st.write("---")
st.subheader("🕒 Kardex Global (Movimientos en tiempo real)")
if not df_historico.empty and 'HORA' in df_historico.columns:
    # Mostramos las columnas incluyendo LOTE de manera ordenada
    columnas_visibles = ['HORA', 'ARTICULO', 'LOTE', 'CANTIDAD', 'OPERARIO']
    # Filtro por si alguna fila vieja de la nube no tiene la columna Lote armada
    columnas_validas = [col for col in columnas_visibles if col in df_historico.columns]
    
    df_mostrar = df_historico[columnas_validas].copy()
    df_mostrar['ARTICULO'] = df_mostrar['ARTICULO'].astype(str)
    
    st.dataframe(df_mostrar.tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_historico[[col for col in ['HORA', 'ARTICULO', 'DESCRIPCIÓN', 'LOTE', 'CANTIDAD', 'OPERARIO'] if col in df_historico.columns]].to_excel(writer, index=False, sheet_name='Kardex_Global')
    
    st.sidebar.write("---")
    st.sidebar.download_button(label="📥 DESCARGAR KARDEX GLOBAL (.XLSX)", data=buffer.getvalue(), file_name="Kardex_Global.xlsx", use_container_width=True)
else:
    st.caption("No hay movimientos registrados en la nube aún.")