import streamlit as st
import pandas as pd
import requests
import io
import json
from datetime import datetime

# 1. Configuración profesional de la página
st.set_page_config(page_title="Yobel WMS - Conteo Cíclico Cloud", layout="centered")

# ====================================================================================
# 🛠️ SECCIÓN DE ENLACES: COPIA Y PEGA LAS URLS COMPLETAS DESDE TU NAVEGADOR
# ====================================================================================
# PEGA AQUÍ LA URL COMPLETA de tu nuevo Google Sheets (el que guardaste como nativo)
URL_HOJA_DE_CALCULO = "https://https://docs.google.com/spreadsheets/d/1UbjMP0OtiikjaCo9Ykr8kdOeB63VyFBJNB8RJDuDqXE/edit?gid=0#gid=0"

# PEGA AQUÍ LA URL COMPLETA que te dio Google al implementar tu Apps Script (termina en /exec)
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbwz585fxOLSU4SfbfkD26b30ZXs5SrqqIWGGFkeDt6d4zdP50xntyVgkiGnXNabIHrlVg/exec"
# ====================================================================================

# Función interna para limpiar y preparar el enlace de descarga de Google
def generar_url_export(url_usuario):
    if "/d/" in url_usuario:
        id_sheet = url_usuario.split("/d/")[1].split("/")[0]
        return f"https://docs.google.com/spreadsheets/d/{id_sheet}/export?format=csv&gid=0"
    return url_usuario

URL_FINAL_CSV = generar_url_export(URL_HOJA_DE_CALCULO)

# --- 2. CARGA DEL MAESTRO CON DIAGNÓSTICO EN VIVO ---
@st.cache_data(ttl=5)
def cargar_maestro_nube():
    try:
        if "TU_NUEVO_CODIGO_LARGO_AQUI" in URL_FINAL_CSV or "docs.google.com" not in URL_FINAL_CSV:
            st.error("⚠️ URL DE GOOGLE SHEETS INVÁLIDA: Por favor, pega la URL real de tu navegador en la línea 15.")
            return pd.DataFrame()
            
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
            df['ARTICULO'] = df['ARTICULO'].astype(str).str.strip().str.upper()
            df['DESCRIPCIÓN'] = df['DESCRIPCIÓN'].astype(str).str.strip()
            df['LÓGICO'] = df['LÓGICO'].astype(str).str.strip().str.replace('.', '', regex=False).str.replace(',', '', regex=False)
            df['LÓGICO'] = pd.to_numeric(df['LÓGICO'], errors='coerce').fillna(0).astype(int)
            return df[['ARTICULO', 'DESCRIPCIÓN', 'LÓGICO']]
        else:
            st.error(f"❌ ERROR DE COLUMNAS: No se encontraron campos como 'Articulo', 'Descripción' o 'Lógico'. Columnas reales detectadas: {list(df.columns)}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"🚨 ERROR CRÍTICO AL CONECTAR CON GOOGLE: {e}")
        st.info("💡 Consejo: Verifica que hiciste clic en el botón azul 'Compartir' en tu Sheets y lo cambiaste a 'Cualquier persona con el enlace' en modo Lector.")
        return pd.DataFrame()

df_maestro = cargar_maestro_nube()

# --- 3. LECTURA DEL KARDEX DESDE LA NUBE ---
def obtener_historico_nube():
    if "TU_URL_DE_APPS_SCRIPT_AQUI" in URL_APPS_SCRIPT:
        return pd.DataFrame(columns=['HORA', 'ARTICULO', 'DESCRIPCIÓN', 'CANTIDAD', 'OPERARIO'])
    try:
        response = requests.get(URL_APPS_SCRIPT, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                df.columns = [str(c).upper() for c in df.columns]
                return df
    except Exception as e:
        st.sidebar.warning(f"⚠️ Alerta Kardex Nube: No se pudo leer el historial histórico ({e})")
    return pd.DataFrame(columns=['HORA', 'ARTICULO', 'DESCRIPCIÓN', 'CANTIDAD', 'OPERARIO'])

# --- 4. LÓGICA DE PROCESAMIENTO DE ESCANEO ---
def ejecutar_conteo_sku():
    sku_input = st.session_state.scanner.strip().upper()
    if not sku_input: return

    if not df_maestro.empty:
        sku_busqueda = sku_input.lstrip('0')
        match = df_maestro[df_maestro['ARTICULO'].astype(str).str.lstrip('0').str.upper() == sku_busqueda]
        
        if not match.empty:
            sku_real = match.iloc[0]['ARTICULO']
            st.session_state.sku_activo = sku_real
            cant_unidades = int(st.session_state.cantidad_paso)
            desc_prod = match.iloc[0]['DESCRIPCIÓN']
            op_actual = st.session_state.username.strip()
            
            payload = {
                "hora": datetime.now().strftime("%H:%M:%S"),
                "articulo": sku_real,
                "descripcion": desc_prod,
                "cantidad": cant_unidades,
                "operario": op_actual
            }
            
            try:
                if "TU_URL_DE_APPS_SCRIPT_AQUI" not in URL_APPS_SCRIPT:
                    res = requests.post(URL_APPS_SCRIPT, data=json.dumps(payload), timeout=5)
                    if res.status_code == 200:
                        st.session_state.feedback = f"✅ Sincronizado en la Nube: +{cant_unidades} und para {desc_prod}"
                    else:
                        st.session_state.feedback = f"⚠️ Guardado con advertencia. Código HTTP: {res.status_code}"
                else:
                    st.session_state.feedback = f"⚠️ Modo Local Activo: Conecta tu Apps Script para mandar a la nube."
            except Exception as e:
                st.session_state.feedback = f"❌ Error de red al enviar el dato: {e}"
        else:
            st.session_state.feedback = f"❌ El código '{sku_input}' no existe en el sistema."
    st.session_state.scanner = ""

def ejecutar_conteo_por_boton():
    if 'sku_activo' in st.session_state and st.session_state.sku_activo:
        sku_real = st.session_state.sku_activo
        match = df_maestro[df_maestro['ARTICULO'] == sku_real]
        if not match.empty:
            cant_unidades = int(st.session_state.cantidad_paso)
            desc_prod = match.iloc[0]['DESCRIPCIÓN']
            op_actual = st.session_state.username.strip()
            
            payload = {
                "hora": datetime.now().strftime("%H:%M:%S"),
                "articulo": sku_real,
                "descripcion": desc_prod,
                "cantidad": cant_unidades,
                "operario": op_actual
            }
            try:
                if "TU_URL_DE_APPS_SCRIPT_AQUI" not in URL_APPS_SCRIPT:
                    requests.post(URL_APPS_SCRIPT, data=json.dumps(payload), timeout=5)
                st.session_state.feedback = f"✅ Añadido a la Nube: +{cant_unidades} und para {desc_prod}"
            except:
                st.session_state.feedback = "❌ Error de red al sumar unidades."

# --- 5. INTERFAZ GRÁFICA ---
if df_maestro.empty:
    st.warning("🔄 Sincronizando enlace maestro con Google Sheets...")
    st.info("Revisa arriba si la app arrojó un cuadro de error detallado.")
    st.stop()

if 'username' not in st.session_state or not st.session_state.username.strip():
    st.title("📦 Yobel SCM - Registro Cloud")
    nombre_input = st.text_input("Ingrese su Nombre y Apellido:", key="temp_name")
    if st.button("INGRESAR AL SISTEMA", type="primary", use_container_width=True):
        if nombre_input.strip():
            st.session_state.username = nombre_input.strip()
            st.rerun()
    st.stop()

st.title("🚀 Yobel SCM - Conteo Cíclico en Tiempo Real")
st.sidebar.markdown(f"### 👤 Operario Activo:\n**{st.session_state.username}**")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.username = ""
    st.session_state.sku_activo = None
    st.rerun()

st.markdown("### 📥 Captura de Datos")
col_cant, col_scan = st.columns([1, 3])
with col_cant:
    st.number_input("Cantidad:", min_value=1, value=1, step=1, key="cantidad_paso")
with col_scan:
    st.text_input("Escanear Artículo:", key="scanner", on_change=ejecutar_conteo_sku)

if 'sku_activo' in st.session_state and st.session_state.sku_activo:
    col1, col2 = st.columns(2)
    with col1: st.button("➕ SUMAR AL CÓDIGO ACTIVO", type="primary", use_container_width=True, on_click=ejecutar_conteo_por_boton)
    with col2: st.button("🔄 CAMBIAR CÓDIGO", type="secondary", use_container_width=True, on_click=lambda: st.session_state.update({"sku_activo": None}))

if 'feedback' in st.session_state:
    st.info(st.session_state.feedback)

df_historico = obtener_historico_nube()

st.write("---")
st.subheader("🔍 Inspección del Artículo")
if 'sku_activo' in st.session_state and st.session_state.sku_activo:
    sku = st.session_state.sku_activo
    info_maestro = df_maestro[df_maestro['ARTICULO'] == sku].iloc[0]
    
    total_acumulado = 0
    if not df_historico.empty and 'CANTIDAD' in df_historico.columns:
        df_sku = df_historico[df_historico['ARTICULO'].astype(str).str.upper().str.lstrip('0') == str(sku).lstrip('0')]
        total_acumulado = pd.to_numeric(df_sku['CANTIDAD'], errors='coerce').sum()

    c1, c2, c3 = st.columns(3)
    with c1: st.metric(label="Código", value=str(sku)), st.caption(info_maestro['DESCRIPCIÓN'])
    with c2: st.metric(label="📊 Stock Lógico", value=f"{info_maestro['LÓGICO']:,}".replace(",", "."))
    with c3: st.metric(label="📦 Acumulado Nube (Todos)", value=f"{int(total_acumulado):,}".replace(",", "."))

st.write("---")
st.subheader("🕒 Kardex Global (Movimientos en tiempo real)")
if not df_historico.empty and 'HORA' in df_historico.columns:
    st.dataframe(df_historico[['HORA', 'ARTICULO', 'CANTIDAD', 'OPERARIO']].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_historico[['HORA', 'ARTICULO', 'DESCRIPCIÓN', 'CANTIDAD', 'OPERARIO']].to_excel(writer, index=False, sheet_name='Kardex_Global')
    
    st.sidebar.write("---")
    st.sidebar.download_button(label="📥 DESCARGAR KARDEX GLOBAL (.XLSX)", data=buffer.getvalue(), file_name="Kardex_Global.xlsx", use_container_width=True)
else:
    st.caption("No hay movimientos registrados en la nube aún.")    