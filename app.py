import base64
from datetime import datetime
import json
import os
import random
import re
import smtplib
import time
import traceback
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from groq import Groq
import streamlit as st

# ==========================================
# CONFIGURACIÓN VISUAL DE LA INTERFAZ (UI)
# ==========================================
st.set_page_config(
    page_title="Isaac AI",
    page_icon="🤖",
    layout="centered"
)

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stChatMessage {
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 0.5rem;
        }
        .caja-otp {
            background-color: rgba(0, 229, 255, 0.05);
            border: 1px solid rgba(0, 229, 255, 0.3);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CONFIGURACIÓN DE ARCHIVOS Y PERSISTENCIA
# ==========================================
ARCHIVO_CHATS_PERMANENTE = "historial_chats.json"

def cargar_todas_las_conversaciones():
    if os.path.exists(ARCHIVO_CHATS_PERMANENTE):
        with open(ARCHIVO_CHATS_PERMANENTE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def guardar_todas_las_conversaciones(datos_totales):
    with open(ARCHIVO_CHATS_PERMANENTE, "w", encoding="utf-8") as f:
        json.dump(datos_totales, f, indent=4, ensure_ascii=False)

def es_correo_valido(correo: str) -> bool:
    patron = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
    return bool(re.match(patron, correo.strip().lower()))

def enviar_codigo_smtp(correo_destino, codigo_otp):
    """
    Intenta enviar el correo vía SMTP si están configurados los secrets.
    Si no hay credenciales SMTP, muestra el código en pantalla para desarrollo.
    """
    smtp_server = st.secrets.get("SMTP_SERVER", "")
    smtp_port = int(st.secrets.get("SMTP_PORT", 587))
    smtp_user = st.secrets.get("SMTP_USER", "")
    smtp_password = st.secrets.get("SMTP_PASSWORD", "")

    if smtp_user and smtp_password:
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = correo_destino
            msg['Subject'] = f"{codigo_otp} es tu código de verificación para Isaac AI"

            cuerpo = f"Tu código de acceso de 6 dígitos es: {codigo_otp}"
            msg.attach(MIMEText(cuerpo, 'plain'))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, correo_destino, msg.as_string())
            server.quit()
            return True, "Código enviado a tu bandeja de entrada."
        except Exception as e:
            return False, f"Error al enviar correo: {e}"
    else:
        # Modo fallback/desarrollo si no hay servidor SMTP configurado
        return True, f"🔑 (Modo Dev) Tu código de verificación es: **{codigo_otp}**"

def encode_image_to_base64(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# ==========================================
# 🔐 GESTIÓN DE SESIÓN Y VERIFICACIÓN OTP
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.tipo_usuario = None  
    st.session_state.usuario_info = ""

if "paso_login" not in st.session_state:
    st.session_state.paso_login = "ingresar_correo" # 'ingresar_correo' o 'verificar_codigo'

if "otp_generado" not in st.session_state:
    st.session_state.otp_generado = None

if "correo_pendiente" not in st.session_state:
    st.session_state.correo_pendiente = ""

if "codigo_actualizacion" not in st.session_state:
    st.session_state.codigo_actualizacion = "123"

# --- PANTALLA DE LOGIN ---
if not st.session_state.autenticado:
    st.title("🤖 Bienvenido a Isaac AI")
    
    opcion_acceso = st.radio("Selecciona tu método de acceso:", ["Continuar con Cuenta Gmail", "Acceder como Invitado"])
    
    if opcion_acceso == "Continuar con Cuenta Gmail":
        
        # PASO 1: Ingresar correo
        if st.session_state.paso_login == "ingresar_correo":
            correo = st.text_input("Introduce tu correo electrónico (@gmail.com):", placeholder="usuario@gmail.com")
            
            if st.button("Enviar Código de Verificación", use_container_width=True):
                if es_correo_valido(correo):
                    otp = str(random.randint(100000, 999999))
                    st.session_state.otp_generado = otp
                    st.session_state.correo_pendiente = correo.lower().strip()
                    
                    exito, mensaje = enviar_codigo_smtp(st.session_state.correo_pendiente, otp)
                    if exito:
                        st.session_state.paso_login = "verificar_codigo"
                        st.success(mensaje)
                        st.rerun()
                    else:
                        st.error(mensaje)
                else:
                    st.error("Formato de correo inválido. Debe ser una dirección real terminada en @gmail.com")
        
        # PASO 2: Ingresar código OTP de 6 dígitos
        elif st.session_state.paso_login == "verificar_codigo":
            st.markdown(f"""
            <div class="caja-otp">
                📧 Hemos enviado un código de 6 dígitos a <b>{st.session_state.correo_pendiente}</b>
            </div>
            """, unsafe_allow_html=True)
            
            codigo_ingresado = st.text_input("Ingresa el código de 6 dígitos:", max_chars=6)
            
            col_validar, col_volver = st.columns([0.7, 0.3])
            
            with col_validar:
                if st.button("Verificar e Iniciar Sesión", use_container_width=True):
                    if codigo_ingresado.strip() == st.session_state.otp_generado:
                        st.session_state.autenticado = True
                        st.session_state.tipo_usuario = "Privilegiado"
                        st.session_state.usuario_info = st.session_state.correo_pendiente
                        st.session_state.paso_login = "ingresar_correo"
                        st.success("¡Autenticación exitosa!")
                        st.rerun()
                    else:
                        st.error("El código ingresado es incorrecto.")
            
            with col_volver:
                if st.button("Cambiar Correo", use_container_width=True):
                    st.session_state.paso_login = "ingresar_correo"
                    st.rerun()

    else:
        st.write("⚠️ El modo invitado no almacena conversaciones de forma permanente.")
        if st.button("Entrar en Modo Invitado", use_container_width=True):
            st.session_state.autenticado = True
            st.session_state.tipo_usuario = "Invitado"
            st.session_state.usuario_info = "Invitado"
            st.rerun()
            
    st.stop()

# ==========================================
# CONEXIÓN A GROQ API Y MODELOS
# ==========================================
@st.cache_resource
def conectar_groq():
    api_key = st.secrets.get("GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    return Groq(api_key=api_key)

client = conectar_groq()

MODELO_TEXTO = "llama-3.3-70b-versatile"
MODELO_RAPIDO = "llama-3.1-8b-instant"
MODELO_VISION = "llama-3.2-11b-vision-preview"

@st.cache_data(ttl=3600)
def detectar_pais_silencioso():
    try:
        url = "http://ip-api.com/json/"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=1) as response:
            datos = json.loads(response.read().decode())
            return f"{datos.get('city', 'Desconocida')}, {datos.get('country', 'Desconocido')}"
    except Exception:
        return "Ubicación Desconocida"

if "ubicacion" not in st.session_state:
    st.session_state.ubicacion = detectar_pais_silencioso()

# ==========================================
# 🔄 SINCRONIZACIÓN DE HISTORIAL
# ==========================================
base_datos_chats = cargar_todas_las_conversaciones()
usuario_actual = st.session_state.usuario_info

if usuario_actual not in base_datos_chats or not base_datos_chats[usuario_actual]:
    base_datos_chats[usuario_actual] = {
        "chat_inicial": {"titulo": "Nueva Conversación", "historial": []}
    }
    guardar_todas_las_conversaciones(base_datos_chats)

st.session_state.conversaciones = base_datos_chats[usuario_actual]

if ("chat_actual_id" not in st.session_state or 
    st.session_state.chat_actual_id not in st.session_state.conversaciones):
    st.session_state.chat_actual_id = list(st.session_state.conversaciones.keys())[0]

# ==========================================
# 💾 BARRA LATERAL CON AJUSTES
# ==========================================
with st.sidebar:
    st.write(f"### 👤 {st.session_state.usuario_info}")
    st.caption(f"📍 {st.session_state.ubicacion}")
    
    if st.button("➕ Nueva conversación", use_container_width=True):
        nuevo_id = f"chat_{int(datetime.now().timestamp())}"
        st.session_state.conversaciones[nuevo_id] = {"titulo": "Nueva Conversación", "historial": []}
        st.session_state.chat_actual_id = nuevo_id
        
        base_datos_chats[usuario_actual] = st.session_state.conversaciones
        guardar_todas_las_conversaciones(base_datos_chats)
        st.rerun()
        
    st.markdown("---")
    
    with st.expander("🔑 Código de actualización rápida", expanded=False):
        nuevo_codigo = st.text_input("Código de comando:", value=st.session_state.codigo_actualizacion)
        if nuevo_codigo:
            st.session_state.codigo_actualizacion = nuevo_codigo.strip()

    criterio_busqueda = st.text_input("🔍 Buscar conversación...", placeholder="Filtrar por tema...")
    
    st.write("#### 💬 Recientes")
    for id_chat, datos_chat in list(st.session_state.conversaciones.items()):
        if criterio_busqueda.lower() in datos_chat["titulo"].lower():
            es_activo = id_chat == st.session_state.chat_actual_id
            marcador = "📌 " if es_activo else "• "
            
            col_btn, col_del = st.columns([0.8, 0.2])
            with col_btn:
                if st.button(f"{marcador}{datos_chat['titulo']}", key=f"btn_{id_chat}", use_container_width=True):
                    st.session_state.chat_actual_id = id_chat
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_{id_chat}"):
                    del st.session_state.conversaciones[id_chat]
                    if not st.session_state.conversaciones:
                        nuevo_id = f"chat_{int(datetime.now().timestamp())}"
                        st.session_state.conversaciones[nuevo_id] = {"titulo": "Nueva Conversación", "historial": []}
                    st.session_state.chat_actual_id = list(st.session_state.conversaciones.keys())[0]
                    base_datos_chats[usuario_actual] = st.session_state.conversaciones
                    guardar_todas_las_conversaciones(base_datos_chats)
                    st.rerun()

    st.markdown("---")
    if st.button("🔒 Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ==========================================
# 💬 INTERFAZ PRINCIPAL DE CHAT
# ==========================================
chat_activo = st.session_state.conversaciones[st.session_state.chat_actual_id]
st.title(f"{chat_activo['titulo']}")

col_modo, col_potencia = st.columns(2)
with col_modo:
    modo_operacion = st.radio("Formato de respuesta:", ["💬 Texto / Chat"], key="selector_modo_ia")

with col_potencia:
    nivel_potencia = st.radio("Nivel de procesamiento:", ["⚡ Normal", "🚀 Pro (Doble Revisión)"], key="selector_potencia")

# Área opcional de imágenes para análisis visual
with st.expander("📷 Adjuntar Imagen para Análisis", expanded=False):
    imagen_subida = st.file_uploader("Sube una imagen:", type=["png", "jpg", "jpeg", "webp"], key="uploader_imagen")
    if imagen_subida:
        st.image(imagen_subida, caption="Imagen cargada correctamente", use_container_width=True)

st.markdown("---")

# Renderizar historial de conversación
for msg in chat_activo["historial"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

mensajes_enviados = sum(1 for m in chat_activo["historial"] if m["role"] == "user")
bloqueado_por_restriccion = st.session_state.tipo_usuario == "Invitado" and mensajes_enviados >= 5

if bloqueado_por_restriccion:
    st.error("⚠️ Límite del Modo Invitado alcanzado. Inicia sesión con Gmail para continuar.")

if not bloqueado_por_restriccion:
    if prompt := st.chat_input("Escribe tu pregunta..."):
        
        with st.chat_message("user"):
            st.markdown(prompt)
        chat_activo["historial"].append({"role": "user", "content": prompt})
        
        if len(chat_activo["historial"]) == 1:
            chat_activo["titulo"] = prompt[:30].strip() + ("..." if len(prompt) > 30 else "")

        # Comando de actualización rápida
        if prompt.strip().lower().startswith(st.session_state.codigo_actualizacion.lower()) and "actualiz" in prompt.lower():
            st.cache_data.clear()
            st.cache_resource.clear()
            msg_exito = f"🔄 **Sistema actualizado.** Memoria caché limpia."
            chat_activo["historial"].append({"role": "assistant", "content": msg_exito})
            guardar_todas_las_conversaciones(base_datos_chats)
            st.rerun()

        # Respuesta en Modo Texto
        else:
            with st.chat_message("assistant"):
                ahora = datetime.now()
                contexto_sistema = f"Eres Isaac AI, una IA inteligente y directa. Fecha actual: {ahora.strftime('%d/%m/%Y')}."
                
                mensajes_api = [{"role": "system", "content": contexto_sistema}]
                
                # Construir historial seguro sin duplicados
                for m in chat_activo["historial"][-5:]:
                    role = m.get("role")
                    content_texto = str(m.get("content", ""))
                    if role in ["user", "assistant"] and content_texto.strip():
                        if mensajes_api[-1]["role"] == role:
                            mensajes_api[-1]["content"] += "\n" + content_texto
                        else:
                            mensajes_api.append({"role": role, "content": content_texto})

                modelo_a_usar = MODELO_TEXTO
                
                # Manejo seguro de imágenes (Sin borrar la regla system)
                if imagen_subida is not None:
                    try:
                        base64_img = encode_image_to_base64(imagen_subida)
                        modelo_a_usar = MODELO_VISION
                        mensajes_api.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                            ]
                        })
                    except Exception as e:
                        st.warning(f"Error al procesar la imagen adjunta: {e}")

                try:
                    marcador_texto = st.empty()
                    texto_completo = ""
                    
                    stream = client.chat.completions.create(
                        model=modelo_a_usar,
                        messages=mensajes_api,
                        stream=True,
                        temperature=0.3,
                        max_tokens=800
                    )
                    
                    for parte in stream:
                        contenido = parte.choices[0].delta.content if parte.choices and parte.choices[0].delta else None
                        if contenido:
                            texto_completo += contenido
                            marcador_texto.markdown(texto_completo + "▌")
                            time.sleep(0.005)
                            
                    marcador_texto.markdown(texto_completo)

                except Exception as e:
                    texto_completo = f"🚨 **Error de API:** {e}"
                    st.markdown(texto_completo)
                    
                chat_activo["historial"].append({"role": "assistant", "content": texto_completo})
        
        base_datos_chats[usuario_actual] = st.session_state.conversaciones
        guardar_todas_las_conversaciones(base_datos_chats)
        st.rerun()
