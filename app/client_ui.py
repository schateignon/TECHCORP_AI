import asyncio
import json
import requests
import streamlit as st
from mcp import ClientSession
from mcp.client.sse import sse_client
from logger import log_mcp_call

# --- CONFIGURATION DES ENDPOINTS ---
MCP_SSE_URL = "http://localhost:8001/sse"
OLLAMA_URL = "http://localhost:11434/api/generate"

# --- SÉCURITÉ & GUARDRAILS (10.2) ---
FORBIDDEN_KEYWORDS = [
    "ignore", "contourne", "bypass", ".env", "password", 
    "mot de passe", "secret", "root", "shadow", "drop table"
]

CRITICAL_TOOLS = ["create_ticket", "restart_service", "delete_ticket", "execute_command"]

def contains_prompt_injection(user_input: str) -> bool:
    clean_input = user_input.lower()
    return any(keyword in clean_input for keyword in FORBIDDEN_KEYWORDS)

def map_tool_source(tool_name: str) -> str:
    """Mappe le nom de l'outil vers la source d'audit correspondante (11.1)."""
    mapping = {
        "check_server_availability": "network_check",
        "get_last_service_check": "network_check",
        "get_server_info": "postgresql",
        "get_recent_events": "postgresql",
        "list_open_tickets": "ticketing_api",
        "create_ticket": "ticketing_api"
    }
    return mapping.get(tool_name, "system")

def execute_mcp_action(tool_name: str, args: dict, user_question: str):
    """Exécute un outil via MCP SSE et désérialise/aplatit le JSON retourné."""
    async def _call():
        async with sse_client(MCP_SSE_URL) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=args)
                
                parsed_output = []
                for item in result.content:
                    text_val = item.text if hasattr(item, 'text') else str(item)
                    try:
                        data = json.loads(text_val)
                        # Si le résultat est une liste, on l'étend pour éviter les listes imbriquées
                        if isinstance(data, list):
                            parsed_output.extend(data)
                        else:
                            parsed_output.append(data)
                    except json.JSONDecodeError:
                        parsed_output.append(text_val)
                return parsed_output

    source = map_tool_source(tool_name)

    return log_mcp_call(
        user_question=user_question,
        tool_name=tool_name,
        tool_arguments=args,
        source=source,
        func_to_execute=lambda: asyncio.run(_call())
    )

def generate_final_answer(prompt: str, mcp_results: list):
    """Génère la réponse textuelle finale de l'assistant via le LLM Ollama."""
    with st.spinner("📝 Rédaction du rapport d'exploitation..."):
        sys_msg_final = "Tu es un assistant Ops. Rédige un rapport clair, synthétique et professionnel en français à partir des données fournies."
        prompt_final = f"Demande utilisateur : {prompt}\nDonnées obtenues via les outils MCP : {json.dumps(mcp_results)}"

        payload_final = {
            "model": "qwen2.5:3b",
            "prompt": f"{sys_msg_final}\n\n{prompt_final}",
            "stream": False
        }

        try:
            res_final = requests.post(OLLAMA_URL, json=payload_final, timeout=90).json()
            final_text = res_final.get("response", "")
            st.chat_message("assistant").write(final_text)
        except Exception as e:
            st.error(f"Erreur lors de la génération du rapport : {e}")

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="TECHCORP Ops Assistant", page_icon="⚙️")
st.title("⚙️ TECHCORP - Assistant Diagnostic SI")

if "pending_action" not in st.session_state:
    st.session_state["pending_action"] = None

prompt = st.chat_input("Posez une question sur l'état des serveurs ou des tickets...")

if prompt:
    if contains_prompt_injection(prompt):
        st.error("🚨 **Alerte Sécurité** : Requête bloquée. Tentative d'accès non autorisé ou de contournement détectée.")
    else:
        st.chat_message("user").write(prompt)
        
        # PASSE 1 : IDENTIFICATION DES OUTILS
        with st.spinner("🤖 Analyse de la demande..."):
            sys_msg_tools = """Tu es un assistant Ops TECHCORP.
Analyse la demande de l'utilisateur et sélectionne les outils nécessaires :

Outils disponibles :
1. `get_server_info` : Récupère la fiche d'un serveur (args: {"hostname": "SRV-..."})
2. `check_server_availability` : Test réseau TCP/HTTP (args: {"hostname": "SRV-..."})
3. `list_open_tickets` : Liste les tickets ouverts (args: {"priority": "...", "hostname": "..."})
4. `get_recent_events` : Événements récents (args: {"hostname": "...", "limit": 5})
5. `get_last_service_check` : Historique de disponibilité (args: {"hostname": "..."})
6. `create_ticket` : Création de ticket (args: {"hostname": "...", "priority": "CRITICAL", "title": "...", "confirm": False})

Réponds STRICTEMENT sous la forme JSON : {"tools": [{"name": "...", "args": {...}}]}"""

            payload_tools = {
                "model": "qwen2.5:3b",
                "prompt": f"{sys_msg_tools}\n\nDemande : {prompt}",
                "stream": False,
                "format": "json"
            }

            try:
                res = requests.post(OLLAMA_URL, json=payload_tools, timeout=60).json()
                llm_response = json.loads(res.get("response", "{}"))
                tools_to_run = llm_response.get("tools", [])
            except Exception as e:
                st.error(f"Erreur d'analyse LLM : {e}")
                tools_to_run = []

        mcp_results = []
        has_critical = False

        # PASSE 2 : DÉTECTION ET DÉLÉGATION DE LA CONFIRMATION HUMAINE
        for tool in tools_to_run:
            tool_name = tool.get("name")
            args = tool.get("args", {})

            if tool_name in CRITICAL_TOOLS:
                has_critical = True
                # Stockage en session de l'action à valider
                st.session_state["pending_action"] = {
                    "tool_name": tool_name,
                    "args": args,
                    "prompt": prompt
                }
            else:
                with st.spinner(f"⚙️ Exécution de {tool_name}..."):
                    res_mcp = execute_mcp_action(tool_name, args, prompt)
                    mcp_results.append({"tool": tool_name, "result": res_mcp})

        if not has_critical and mcp_results:
            generate_final_answer(prompt, mcp_results)

# --- BLOC DE CONFIRMATION HUMAINE (HITL) ---
if st.session_state["pending_action"]:
    action = st.session_state["pending_action"]
    
    st.warning("⚠️ **Validation Humaine Requise (HITL)**")
    st.write(f"L'assistant souhaite exécuter une action sensible : **`{action['tool_name']}`**")
    st.json(action["args"])

    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Confirmer et Exécuter", type="primary"):
            # Passage explicite de confirm=True pour l'outil
            confirmed_args = {**action["args"], "confirm": True}
            
            with st.spinner("🚀 Exécution de l'action confirmée..."):
                res_mcp = execute_mcp_action(action["tool_name"], confirmed_args, action["prompt"])
                mcp_results = [{"tool": action["tool_name"], "result": res_mcp}]
            
            generate_final_answer(action["prompt"], mcp_results)
            st.session_state["pending_action"] = None
            st.rerun()

    with col2:
        if st.button("❌ Annuler L'Action"):
            st.info("Action annulée par l'opérateur.")
            st.session_state["pending_action"] = None
            st.rerun()