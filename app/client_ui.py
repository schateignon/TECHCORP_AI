import asyncio
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st
from app.orchestrator import investigate, confirm_ticket
from app.logger import audit

st.set_page_config(page_title="TECHCORP · Exploitation", page_icon="🖥️", layout="wide")
st.title("TECHCORP · Assistant d’exploitation")
st.caption("Serveurs, tickets et vérifications réseau")
st.session_state.setdefault("messages", [])
st.session_state.setdefault("pending", None)

with st.sidebar:
    st.subheader("Exemples de questions")
    st.caption("Modèle : " + os.getenv("OLLAMA_MODEL", "qwen2.5:3b"))
    st.info("Le dossier data_demo contient des données fictives pour les essais.")
    examples = ["Quels tickets critiques sont ouverts ?", "Donne-moi la fiche de SRV-DB-01.",
                "SRV-WEB-01 fonctionne-t-il réellement ?", "Quels serveurs présentent des données contradictoires ?",
                "Quelle procédure pour un incident DNS critique ?"]
    choice = None
    for example in examples:
        if st.button(example, disabled=bool(st.session_state.pending), use_container_width=True):
            choice = example
    if st.button("Nouvelle conversation", disabled=bool(st.session_state.pending)):
        st.session_state.messages = []
        st.rerun()
    st.caption("Aucune commande système n’est disponible au LLM.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message.get("request_id"):
            st.caption("Trace : " + message["request_id"])
        if message.get("results"):
            with st.expander("Voir les outils appelés et leurs résultats"):
                for result in message["results"]:
                    st.markdown("**" + result["tool"] + "** · " + result["status"])
                    st.json(result)

prompt = st.chat_input("Posez une question sur le SI TECHCORP…", disabled=bool(st.session_state.pending))
prompt = prompt or choice
if prompt:
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.spinner("Consultation des données…"):
        try:
            response = asyncio.run(investigate(prompt))
            st.session_state.messages.append({"role":"assistant","content":response["answer"],
                "results":response["results"],"request_id":response["request_id"]})
            if response["pending"]:
                st.session_state.pending = {"actions":response["pending"],"question":prompt,
                                            "request_id":response["request_id"]}
        except Exception:
            st.session_state.messages.append({"role":"assistant","content":
                "Analyse interrompue : vérifier Ollama, MCP et leur configuration. Aucun diagnostic n’est validé."})
    st.rerun()

if st.session_state.pending:
    pending = st.session_state.pending
    action = pending["actions"][0]
    st.warning("Création de ticket : confirmation humaine requise")
    st.json(action["args"])
    left, right = st.columns(2)
    if left.button("Confirmer la création", type="primary"):
        # Consommer avant l'appel pour éviter un double clic ou un rejeu automatique après erreur.
        pending["actions"].pop(0)
        st.session_state.pending = pending if pending["actions"] else None
        try:
            with st.spinner("Création du ticket…"):
                result = asyncio.run(confirm_ticket(action,pending["question"],pending["request_id"]))
            st.session_state.messages.append({"role":"assistant","content":"Ticket créé après votre confirmation.",
                "request_id":pending["request_id"],"results":[{"tool":"create_ticket","status":"success","result":result}]})
        except Exception:
            st.session_state.messages.append({"role":"assistant","content":
                "Création non confirmée par l’API. Vérifiez les tickets avant de réessayer pour éviter un doublon."})
        st.rerun()
    if right.button("Annuler cette création"):
        pending["actions"].pop(0)
        audit(pending["request_id"],pending["question"],"create_ticket",action["args"],
              "application",status="cancelled")
        st.session_state.pending = pending if pending["actions"] else None
        st.session_state.messages.append({"role":"assistant","content":"Création annulée. Aucun appel d’écriture effectué."})
        st.rerun()
