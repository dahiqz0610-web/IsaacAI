import base64
from datetime import datetime
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request

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

def es_telefono_valido(telefono: str) -> bool:
    """Valida que contenga entre 8 y 15 dígitos (con o sin código de país +)"""
    limpio = telefono.strip().replace(" ", "").replace("-", "")
    patron = r'^\+?[0-9]{8,15}$'
    return bool(re.match(patron, limpio))

def enviar_sms_otp(numero_destino, codigo_otp):
    """
    Si tienes credenciales de Twilio configuradas en st.secrets las usará.
    Si no, entra en modo desarrollo para probar el flujo sin costo.
    """
    twilio_sid = st.secrets.get("TWILIO_ACCOUNT_SID", "")
    twilio_token = st.secrets.get("TWILIO_AUTH_TOKEN", "")
    twilio_number = st.secrets.get("TWILIO_PHONE_NUMBER", "")

    if twilio_sid and twilio_token and twilio_number:
        try:
            from twilio.rest import Client
            client = Client(twilio_sid, twilio_token)
            client.messages.create(
                body=f"Tu código de verificación para Isaac AI es: {codigo_otp}",
                from_=twilio_number,
                to=numero_destino
            )
            return True, "SMS enviado correctamente a tu celular.", False
        except Exception as e:
            return False, f"Error al enviar SMS: {e}", True
    else:
        # Modo de prueba cuando no hay API de SMS configurada
        return True, "Modo de prueba activo (Sin servicio SMS de pago)", True

# ==========================================
# 🔐 GESTIÓN DE SESIÓN Y VERIFICACIÓN SMS
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.tipo_usuario = None  
    st.session_state.usuario_info = ""

if "paso_login" not in st.session_state:
    st.session_state.paso_login = "ingresar_telefono"

if "otp_generado" not in st.session_state:
    st.session_state.otp_generado = None

if "telefono_pendiente" not in st.session_state:
    st.session_state.telefono_pendiente = ""

# --- PANTALLA DE LOGIN ---
if not st.session_state.autenticado:
    st.title("🤖 Bienvenido a Isaac AI")
    
    opcion_acceso = st.radio("Selecciona tu método de acceso:", ["Ingresar con Teléfono (SMS)", "Acceder como Invitado"])
    
    if opcion_acceso == "Ingresar con Teléfono (SMS)":
        
        # PASO 1: Ingresar número de teléfono
        if st.session_state.paso_login == "ingresar_telefono":
            telefono = st.text_input(
                "Introduce tu número de celular:", 
                placeholder="Ejemplo: +50688888888 o 88888888"
            )
            
            if st.button("Enviar Código por SMS", use_container_width=True):
                if es_telefono_valido(telefono):
                    otp = str(random.randint(100000, 999999))
                    st.session_state.otp_generado = otp
                    st.session_state.telefono_pendiente = telefono.strip()
                    st.session_state.paso_login = "verificar_codigo"
                    st.rerun()
                else:
                    st.error("Número de teléfono inválido. Debe tener al menos 8 dígitos.")
        
        # PASO 2: Ingresar código de 6 dígitos
        elif st.session_state.paso_login == "verificar_codigo":
            exito_sms, msj_sms, es_modo_dev = enviar_sms_otp(
                st.session_state.telefono_pendiente, 
                st.session_state.otp_generado
            )

            st.markdown(f"""
            <div class="caja-otp">
                📱 Solicitud de SMS para el número: <b>{st.session_state.telefono_pendiente}</b>
            </div>
            """, unsafe_allow_html=True)

            # En modo de prueba te muestra el código en pantalla para avanzar rápido
            if es_modo_dev:
                st.info(f"🔑 **Código de prueba:** `{st.session_state.otp_generado}` *(Ingrésalo abajo)*")
            else:
                st.success("Se ha enviado un mensaje de texto a tu celular.")
            
            codigo_ingresado = st.text_input("Ingresa el código de 6 dígitos:", max_chars=6)
            
            col_validar, col_volver = st.columns([0.7, 0.3])
            
            with col_validar:
                if st.button("Verificar e Iniciar Sesión", use_container_width=True):
                    if codigo_ingresado.strip() == st.session_state.otp_generado:
                        st.session_state.autenticado = True
                        st.session_state.tipo_usuario = "Privilegiado"
                        st.session_state.usuario_info = f"📱 {st.session_state.telefono_pendiente}"
                        st.session_state.paso_login = "ingresar_telefono"
                        st.success("¡Verificación correcta!")
                        st.rerun()
                    else:
                        st.error("El código ingresado es incorrecto.")
            
            with col_volver:
                if st.button("Cambiar Número", use_container_width=True):
                    st.session_state.paso_login = "ingresar_telefono"
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
    
    if st.button("➕ Nueva conversación", use_container_width=True):
        nuevo_id = f"chat_{int(datetime.now().timestamp())}"
        st.session_state.conversaciones[nuevo_id] = {"titulo": "Nueva Conversación", "historial": []}
        st.session_state.chat_actual_id = nuevo_id
        
        base_datos_chats[usuario_actual] = st.session_state.conversaciones
        guardar_todas_las_conversaciones(base_datos_chats)
        st.rerun()
        
    st.markdown("---")

    criterio_busqueda = st.text_input("🔍 Buscar conversación...", placeholder="Filtrar...")
    
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

# Renderizar historial
for msg in chat_activo["historial"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

mensajes_enviados = sum(1 for m in chat_activo["historial"] if m["role"] == "user")
bloqueado_por_restriccion = st.session_state.tipo_usuario == "Invitado" and mensajes_enviados >= 5

if bloqueado_por_restriccion:
    st.error("⚠️ Límite del Modo Invitado alcanzado. Inicia sesión para continuar.")

if not bloqueado_por_restriccion:
    if prompt := st.chat_input("Escribe tu pregunta..."):
        
        with st.chat_message("user"):
            st.markdown(prompt)
        chat_activo["historial"].append({"role": "user", "content": prompt})
        
        if len(chat_activo["historial"]) == 1:
            chat_activo["titulo"] = prompt[:30].strip() + ("..." if len(prompt) > 30 else "")

        with st.chat_message("assistant"):
            ahora = datetime.now()
            contexto_sistema = f"Eres Isaac AI, una IA inteligente y directa. Fecha actual: {ahora.strftime('%d/%m/%Y')}."
            
            mensajes_api = [{"role": "system", "content": contexto_sistema}]
            
            for m in chat_activo["historial"][-5:]:
                role = m.get("role")
                content_texto = str(m.get("content", ""))
                if role in ["user", "assistant"] and content_texto.strip():
                    if mensajes_api[-1]["role"] == role:
                        mensajes_api[-1]["content"] += "\n" + content_texto
                    else:
                        mensajes_api.append({"role": role, "content": content_texto})

            try:
                marcador_texto = st.empty()
                texto_completo = ""
                
                stream = client.chat.completions.create(
                    model=MODELO_TEXTO,
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
