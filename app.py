import streamlit as st
from groq import Groq
from datetime import datetime
import os
import json
import urllib.request
import urllib.parse

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
    </style>
""", unsafe_allow_html=True)

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

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.tipo_usuario = None  
    st.session_state.usuario_info = ""

if not st.session_state.autenticado:
    st.title("🤖 Bienvenido a Isaac AI")
    st.write("Inicia sesión para recuperar tus conversaciones y diseños guardados:")
    
    opcion_acceso = st.radio("Selecciona tu método de acceso:", ["Continuar con Cuenta Google / Gmail", "Acceder como Invitado"])
    
    if opcion_acceso == "Continuar con Cuenta Google / Gmail":
        correo = st.text_input("Introduce tu correo electrónico:", placeholder="usuario@gmail.com")
        if st.button("Verificar e Iniciar Sesión", use_container_width=True):
            if correo.lower().endswith("@gmail.com"):
                st.session_state.autenticado = True
                st.session_state.tipo_usuario = "Privilegiado"
                st.session_state.usuario_info = correo.lower().strip()
                st.success(f"Sesión iniciada como {correo}")
                st.rerun()
            else:
                st.error("Se requiere una cuenta de Gmail válida (@gmail.com) para guardar tu historial.")
    else:
        st.write("⚠️ El modo invitado no almacena conversaciones ni imágenes de forma permanente.")
        if st.button("Entrar en Modo Invitado", use_container_width=True):
            st.session_state.autenticado = True
            st.session_state.tipo_usuario = "Invitado"
            st.session_state.usuario_info = "Invitado"
            st.rerun()
            
    st.stop()

@st.cache_resource
def conectar_groq():
    api_key = st.secrets.get("GROQ_API_KEY", "")
    return Groq(api_key=api_key)

client = conectar_groq()
MODELO = "llama-3.1-8b-instant"

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

base_datos_chats = cargar_todas_las_conversaciones()
usuario_actual = st.session_state.usuario_info

if usuario_actual not in base_datos_chats or not base_datos_chats[usuario_actual]:
    base_datos_chats[usuario_actual] = {
        "chat_inicial": {"titulo": "Nueva Conversación", "historial": []}
    }
    guardar_todas_las_conversaciones(base_datos_chats)

if "conversaciones" not in st.session_state:
    st.session_state.conversaciones = base_datos_chats[usuario_actual]

if "chat_actual_id" not in st.session_state:
    st.session_state.chat_actual_id = list(st.session_state.conversaciones.keys())[0]

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
    criterio_busqueda = st.text_input("🔍 Buscar conversación...", placeholder="Filtrar por tema...")
    
    st.write("#### 💬 Recientes")
    for id_chat, datos_chat in list(st.session_state.conversaciones.items()):
        if criterio_busqueda.lower() in datos_chat["titulo"].lower():
            es_activo = id_chat == st.session_state.chat_actual_id
            marcador = "📌 " if es_activo else "• "
            
            if st.button(f"{marcador}{datos_chat['titulo']}", key=id_chat, use_container_width=True):
                st.session_state.chat_actual_id = id_chat
                st.rerun()
                
    st.markdown("---")
    if st.button("🔒 Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

chat_activo = st.session_state.conversaciones[st.session_state.chat_actual_id]

st.title(f"{chat_activo['titulo']}")
st.markdown("---")

for msg in chat_activo["historial"]:
    with st.chat_message(msg["role"]):
        if msg.get("tipo") == "imagen":
            st.image(msg["content"], use_container_width=True)
        else:
            st.markdown(msg["content"])

mensajes_enviados = sum(1 for m in chat_activo["historial"] if m["role"] == "user")
bloqueado_por_restriccion = False
if st.session_state.tipo_usuario == "Invitado" and mensajes_enviados >= 5:
    bloqueado_por_restriccion = True
    st.error("⚠️ Límite del Modo Invitado alcanzado.")

if not bloqueado_por_restriccion:
    if prompt := st.chat_input("Pídeme un código, escribe 'dibuja un tucán' o 'describe una imagen'..."):
        
        with st.chat_message("user"):
            st.markdown(prompt)
        chat_activo["historial"].append({"role": "user", "content": prompt})
        
        if len(chat_activo["historial"]) == 1:
            chat_activo["titulo"] = prompt[:30].strip() + ("..." if len(prompt) > 30 else "")

        texto_lower = prompt.lower()
        palabras_creacion = ["dibuja", "dibujame", "crea", "creame", "genera", "generame", "pinta", "pintame", "haz una imagen", "hazme una imagen", "foto de", "imagen de"]
        quiere_imagen = any(p in texto_lower for p in palabras_creacion) and not any(p in texto_lower for p in ["describe", "describeme", "como es", "explica"])

        if quiere_imagen:
            with st.chat_message("assistant"):
                marcador_estado = st.empty()
                prompt_url = urllib.parse.quote(prompt)
                seed = int(datetime.now().timestamp())
                url_final_imagen = f"https://image.pollinations.ai/prompt/{prompt_url}?width=800&height=800&nologo=true&seed={seed}"
                
                marcador_estado.image(url_final_imagen, use_container_width=True)
                
                chat_activo["historial"].append({
                    "role": "assistant", 
                    "content": url_final_imagen, 
                    "tipo": "imagen"
                })
        else:
            ahora = datetime.now()
            contexto_sistema = f"Eres Isaac AI, una IA avanzada y resolutiva. Responde en español de forma directa. Fecha: {ahora.strftime('%d/%m/%Y')}"
            
            mensajes_api = [{"role": "system", "content": contexto_sistema}]
            mensajes_api.extend(chat_activo["historial"])
            
            with st.chat_message("assistant"):
                marcador_texto = st.empty()
                texto_completo = ""
                
                try:
                    stream = client.chat.completions.create(
                        model=MODELO, 
                        messages=mensajes_api, 
                        stream=True, 
                        temperature=0.4,
                        max_tokens=1024
                    )
                    for parte in stream:
                        contenido = parte.choices[0].delta.content
                        if contenido:
                            texto_completo += contenido
                            marcador_texto.markdown(texto_completo + "▌")
                    marcador_texto.markdown(texto_completo)
                except Exception as e:
                    st.error(f"Error: {e}")
                    texto_completo = "Hubo un inconveniente al procesar la solicitud."
                    marcador_texto.markdown(texto_completo)
                    
            chat_activo["historial"].append({"role": "assistant", "content": texto_completo})
        
        base_datos_chats[usuario_actual] = st.session_state.conversaciones
        guardar_todas_las_conversaciones(base_datos_chats)
        st.rerun()
