import streamlit as st
import pandas as pd
from supabase import create_client, Client
import hashlib
import time
from datetime import datetime, timedelta
from streamlit_calendar import calendar

st.set_page_config(page_title="Gestionale MMR", page_icon="🏎️", layout="wide")

# --- CONNESSIONE AL DATABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def upload_file_to_supabase(file_bytes, file_name, bucket="preventivi"):
    try:
        timestamp = int(time.time())
        nome_sicuro = file_name.replace(" ", "_")
        path = f"{timestamp}_{nome_sicuro}"
        supabase.storage.from_(bucket).upload(path, file_bytes)
        return supabase.storage.from_(bucket).get_public_url(path)
    except Exception as e:
        st.error(f"Errore caricamento {file_name}: {e}")
        return None

def formatta_data_it(data_stringa):
    try:
        return datetime.strptime(str(data_stringa), "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return data_stringa

if 'utente_loggato' not in st.session_state:
    st.session_state['utente_loggato'] = False
    st.session_state['dati_utente'] = None

# --- ACCESSO E REGISTRAZIONE ---
if not st.session_state['utente_loggato']:
    st.title("🏎️ Accesso Gestionale MMR")
    tab_login, tab_reg = st.tabs(["Accedi", "Registrati"])
    
    with tab_login:
        st.subheader("Accedi al tuo account")
        username_login = st.text_input("Username (nome.cognome)", key="login_user").lower()
        password_login = st.text_input("Password", type="password", key="login_pass")
        if st.button("Accedi"):
            if username_login and password_login:
                hashed_pw = hash_password(password_login)
                risposta = supabase.table("membri").select("*").eq("username", username_login).eq("password", hashed_pw).execute()
                if len(risposta.data) > 0:
                    st.session_state['utente_loggato'] = True
                    st.session_state['dati_utente'] = risposta.data[0]
                    st.rerun()
                else:
                    st.error("Username o password errati!")
            else:
                st.warning("Inserisci username e password.")
                
    with tab_reg:
        st.subheader("Crea un nuovo account")
        nome = st.text_input("Nome")
        cognome = st.text_input("Cognome")
        email = st.text_input("Email")
        divisioni_mmr = [
            "Business", "Powertrain CV", "Powertrain EV", "Frame and Body", 
            "Aerodynamics and Thermal Managment", "Vehicle Dynamics", 
            "Electronics", "Actuations", "Autonomous Driving", 
            "Marketing", "Manufacturing", "Communication"
        ]
        divisione = st.selectbox("Divisione", divisioni_mmr)
        ruolo = st.selectbox("Ruolo", ["Membro", "Division Leader", "Team Leader", "CTO"])
        
        admin_code = ""
        if ruolo in ["Division Leader", "Team Leader", "CTO"]:
            admin_code = st.text_input("Password di sistema (Solo Direttivo)", type="password")
            
        password_reg = st.text_input("Scegli una password", type="password", key="reg_pass")
        
        if st.button("Registrati"):
            if nome and cognome and email and password_reg:
                if ruolo in ["Division Leader", "Team Leader", "CTO"] and admin_code != "MoreModenaRacing37!":
                    st.error("Codice direttivo errato!")
                else:
                    username = f"{nome.strip().lower()}.{cognome.strip().lower()}"
                    check = supabase.table("membri").select("*").eq("username", username).execute()
                    if len(check.data) > 0:
                        st.error(f"Lo username {username} esiste già!")
                    else:
                        nuovo_utente = {
                            "nome": nome.strip().capitalize(),
                            "cognome": cognome.strip().capitalize(),
                            "username": username,
                            "email": email,
                            "ruolo": ruolo,
                            "divisione": divisione,
                            "password": hash_password(password_reg)
                        }
                        supabase.table("membri").insert(nuovo_utente).execute()
                        st.success("Account creato! Ora fai l'accesso.")
            else:
                st.warning("Compila tutti i campi!")

# --- APP PRINCIPALE ---
else:
    utente = st.session_state['dati_utente']
    is_direttivo = utente['ruolo'] in ["CTO", "Team Leader", "Division Leader"]
    ruolo_display = "CFO (Admin)" if is_direttivo and utente['divisione'] == "Business" else utente['ruolo']
    
    st.sidebar.title(f"Ciao, {utente['nome']}!")
    st.sidebar.write(f"**Ruolo:** {ruolo_display}")
    st.sidebar.write(f"**Divisione:** {utente['divisione']}")
    
    if st.sidebar.button("🚪 Esci"):
        st.session_state['utente_loggato'] = False
        st.session_state['dati_utente'] = None
        st.rerun()
        
    st.sidebar.divider()
    
    opzioni_menu = [
        "🏠 Home", "📅 Calendari", "🏢 Aree di Lavoro", "📋 Task Manager", 
        "🧪 Test & Pista", "📖 Dizionario Componenti", "📦 BOM (Bill of Materials)", 
        "👤 Area Personale", "👥 Rubrica Contatti"
    ]
    if is_direttivo:
        opzioni_menu.extend(["📄 Scadenze Documenti", "📂 Documenti Membri", "🛒 Gestione Acquisti", "📊 Bilancio Budget", "⚙️ Gestione Utenti"])
        
    menu = st.sidebar.radio("Scegli la sezione:", opzioni_menu)
    stati_acquisto = ["Inoltrato", "Inviato a tecnico responsabile", "Inviato a responsabile dei fondi", "Inviato a Responsabile amministrativo", "Buono d'ordine emesso", "Pagato"]

    # ==========================================
    # 1. HOME CON DASHBOARD E MINI CALENDARIO IN BASSO
    # ==========================================
    if menu == "🏠 Home":
        st.title("🏎️ Home Gestionale MMR")
        
        if is_direttivo:
            st.header("📊 Dashboard Direttivo")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🚨 Prossime Scadenze")
                scadenze = supabase.table("scadenze_documenti").select("*").order("data_scadenza").execute().data
                oggi = datetime.now().date()
                scadenze_future = [s for s in scadenze if datetime.strptime(s['data_scadenza'], "%Y-%m-%d").date() >= oggi] if scadenze else []
                if scadenze_future:
                    for s in scadenze_future[:5]:
                        st.error(f"📄 **{s['nome_documento']}** - Scade il: {formatta_data_it(s['data_scadenza'])}")
                else:
                    st.write("Nessuna scadenza a breve.")
                
                st.subheader("🚐 Richieste Furgone")
                richieste_furgone = supabase.table("calendario_macchina").select("*").eq("furgone_richiesto", True).in_("stato_furgone", ["In attesa", "Furgone prenotato"]).execute().data
                if richieste_furgone:
                    for req in richieste_furgone:
                        stato_icon = "⏳" if req['stato_furgone'] == "In attesa" else "✅"
                        st.write(f"{stato_icon} **{req['titolo']}** ({formatta_data_it(req['data_inizio'])}) - Stato: {req['stato_furgone']}")
                        if utente['ruolo'] in ["Team Leader", "CTO"] or (utente['ruolo'] == "Division Leader" and utente['divisione'] == "Communication"):
                            if req['stato_furgone'] == "In attesa":
                                if st.button("Conferma Furgone", key=f"furg_{req['id']}"):
                                    supabase.table("calendario_macchina").update({"stato_furgone": "Furgone prenotato"}).eq("id", req['id']).execute()
                                    st.rerun()
                else:
                    st.write("Nessuna richiesta furgone.")

                if ruolo_display == "CFO (Admin)":
                    st.subheader("💰 Nuovi Acquisti (Da approvare)")
                    acq_pendenti = supabase.table("acquisti").select("*").eq("stato", "Inoltrato").execute().data
                    if acq_pendenti:
                        for a in acq_pendenti:
                            st.warning(f"🛒 {a['divisione']}: {a['oggetto']} (€{a['costo_no_iva']})")
                    else:
                        st.write("Nessuna nuova richiesta di acquisto.")

            with col2:
                st.subheader("🏢 Prenotazioni MO25 (In attesa)")
                pren_pendenti = supabase.table("prenotazioni_aule").select("*").eq("stato", "In attesa").execute().data
                if pren_pendenti:
                    for p in pren_pendenti:
                        if utente['ruolo'] in ["CTO", "Team Leader"] or p['divisione'] == utente['divisione']:
                            st.warning(f"📅 {formatta_data_it(p['data_prenotazione'])} | {p['ora_inizio']} - {p['divisione']} ({p['richiedente']})")
                else:
                    st.write("Nessuna prenotazione aule in attesa per te.")
                    
                st.subheader("🔐 Richieste Accesso Aree (In attesa)")
                if utente['ruolo'] == "Division Leader":
                    acc_pendenti = supabase.table("accessi_divisioni").select("*").eq("divisione_richiesta", utente['divisione']).eq("stato", "In attesa").execute().data
                else:
                    acc_pendenti = supabase.table("accessi_divisioni").select("*").eq("stato", "In attesa").execute().data
                if acc_pendenti:
                    for r in acc_pendenti:
                        st.warning(f"👤 {r['username']} ➔ {r['divisione_richiesta']}")
                else:
                    st.write("Nessuna richiesta di accesso pendente.")
            
            st.divider()
            
            st.subheader("🏎️ Panoramica Rapida Calendario Macchina")
            eventi_mc_home = supabase.table("calendario_macchina").select("*").execute().data
            scadenze_home = supabase.table("scadenze_documenti").select("*").execute().data
            
            mini_events = []
            colori_auto = {"M26-ED (Elettrica)": "#1d3557", "M26-LH (Ibrida)": "#e63946", "Ibrida Rossa": "#f77f00"}
            
            if eventi_mc_home:
                for e in eventi_mc_home:
                    colore = colori_auto.get(e.get('vettura'), "#e63946")
                    if e.get("tutto_il_giorno", True):
                        end_d = datetime.strptime(e['data_fine'], "%Y-%m-%d") + timedelta(days=1)
                        mini_events.append({"title": f"[{e.get('vettura','Auto')}] {e['titolo']}", "start": e['data_inizio'], "end": end_d.strftime("%Y-%m-%d"), "allDay": True, "color": colore, "className": "evento-all-day-evidenziato"})
                    else:
                        mini_events.append({"title": f"[{e.get('vettura','Auto')}] {e['titolo']}", "start": f"{e['data_inizio']}T{e['ora_inizio']}", "end": f"{e['data_fine']}T{e['ora_fine']}", "allDay": False, "color": colore})
            
            if scadenze_home:
                for s in scadenze_home:
                    mini_events.append({"title": f"🚨 {s['nome_documento']}", "start": s['data_scadenza'], "end": s['data_scadenza'], "allDay": True, "color": "#d90429", "className": "evento-all-day-evidenziato"})

            mini_options = {
                "headerToolbar": {"left": "prev,next today", "center": "title", "right": "timeGridWeek"},
                "initialView": "timeGridWeek",
                "height": "300px",
                "locale": "it",
                "firstDay": 1
            }
            
            st.markdown("""
                <style>
                .fc-event.evento-all-day-evidenziato {
                    background-color: #d90429 !important;
                    border: 2px solid #ffffff !important;
                    font-weight: bold !important;
                    padding: 2px 4px !important;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.5) !important;
                }
                </style>
            """, unsafe_allow_html=True)

            calendar(events=mini_events, options=mini_options, key="mini_cal_macchina")
            st.divider()
        else:
            st.info("Benvenuto! Usa il menu laterale per navigare tra le sezioni del gestionale.")

    # ==========================================
    # 2. TASK MANAGER (NUOVO)
    # ==========================================
    elif menu == "📋 Task Manager":
        st.title("📋 Task Manager Divisioni")
        st.write("Gestisci le attività e i compiti operativi assegnati all'interno delle divisioni.")
        
        divisioni_mmr = [
            "Business", "Powertrain CV", "Powertrain EV", "Frame and Body", 
            "Aerodynamics and Thermal Managment", "Vehicle Dynamics", 
            "Electronics", "Actuations", "Autonomous Driving", 
            "Marketing", "Manufacturing", "Communication"
        ]
        
        with st.expander("➕ Assegna Nuovo Task"):
            with st.form("form_task"):
                t_titolo = st.text_input("Titolo Attività")
                t_div = st.selectbox("Divisione di Riferimento", divisioni_mmr)
                t_assegnato = st.text_input("Assegnato a (Username o Nome)")
                t_prio = st.selectbox("Priorità", ["Bassa", "Media", "Urgente"])
                t_scadenza = st.date_input("Scadenza Attività", format="DD/MM/YYYY")
                t_desc = st.text_area("Descrizione / Dettagli")
                
                if st.form_submit_button("Crea Task"):
                    if t_titolo:
                        supabase.table("task_divisioni").insert({
                            "divisione": t_div,
                            "titolo": t_titolo,
                            "descrizione": t_desc,
                            "assegnato_a": t_assegnato,
                            "priorita": t_prio,
                            "stato": "Da Fare",
                            "scadenza": str(t_scadenza),
                            "creato_da": utente['username']
                        }).execute()
                        st.success("Task creato con successo!")
                        st.rerun()
                    else:
                        st.error("Inserisci il titolo del task.")

        st.divider()
        
        try:
            tasks = supabase.table("task_divisioni").select("*").execute().data
            if tasks:
                # Se non sei direttivo, vedi solo i task della tua divisione o quelli assegnati a te
                if not is_direttivo:
                    tasks = [t for t in tasks if t['divisione'] == utente['divisione'] or t.get('assegnato_a') == utente['username']]
                
                st.subheader("Attività in Corso")
                col_f1, col_f2, col_f3 = st.columns(3)
                
                stati_task = ["Da Fare", "In Corso", "Completato"]
                colonne_kanban = st.columns(3)
                
                for idx, stato in enumerate(stati_task):
                    with colonne_kanban[idx]:
                        st.markdown(f"### {stato}")
                        filtro_tasks = [t for t in tasks if t.get('stato', 'Da Fare') == stato]
                        if filtro_tasks:
                            for t in filtro_tasks:
                                with st.container(border=True):
                                    st.write(f"**{t['titolo']}**")
                                    st.caption(f"🏢 {t['divisione']} | 👤 {t.get('assegnato_a', 'N/D')}")
                                    st.write(f"Scadenza: {formatta_data_it(t.get('scadenza'))}")
                                    
                                    # Pulsante per avanzare o modificare stato
                                    nuovo_stato = st.selectbox("Stato", stati_task, index=stati_task.index(stato), key=f"st_t_{t['id']}")
                                    if nuovo_stato != stato:
                                        supabase.table("task_divisioni").update({"stato": nuovo_stato}).eq("id", t['id']).execute()
                                        st.rerun()
                                        
                                    if st.button("🗑️ Elimina", key=f"del_t_{t['id']}"):
                                        supabase.table("task_divisioni").delete().eq("id", t['id']).execute()
                                        st.rerun()
                        else:
                            st.caption("Nessun task.")
            else:
                st.info("Nessun task registrato.")
        except Exception:
            st.info("Tabella task in configurazione su Supabase.")

    # ==========================================
    # 3. TEST & PISTA (NUOVO)
    # ==========================================
    elif menu == "🧪 Test & Pista":
        st.title("🧪 Registro Test & Sessioni in Pista")
        st.write("Archivio ufficiale dei test su pista, set-up vettura, dati telemetrici e riscontri cronometrici.")
        
        with st.expander("➕ Registra Nuova Sessione di Test"):
            with st.form("form_test"):
                c1, c2, c3 = st.columns(3)
                d_test = c1.date_input("Data Test", format="DD/MM/YYYY")
                luogo_test = c2.text_input("Autodromo / Luogo (es. Varano, Modena)")
                vettura_test = c3.selectbox("Vettura Testata", ["M26-ED (Elettrica)", "M26-LH (Ibrida)", "Ibrida Rossa"])
                
                c4, c5 = st.columns(2)
                pilota = c4.text_input("Pilota / Driver")
                meteo = c5.text_input("Meteo / Condizioni Asfalto (es. Asciutto, 25°C)")
                
                miglior_tempo = st.text_input("Miglior Tempo sul Giro (es. 1:04.23)")
                note_setup = st.text_area("Note di Set-up e Modifiche (Altezze, pressioni gomme, ali, ecc.)")
                file_telemetria = st.file_uploader("Carica File Telemetria / Report PDF (Opzionale)", type=["pdf", "csv", "zip"])
                
                if st.form_submit_button("Salva Sessione Test"):
                    if luogo_test:
                        url_tel = None
                        if file_telemetria:
                            url_tel = upload_file_to_supabase(file_telemetria.getvalue(), file_telemetria.name, "workspaces")
                        
                        supabase.table("sessioni_test").insert({
                            "data_test": str(d_test),
                            "luogo": luogo_test,
                            "vettura": vettura_test,
                            "condizioni_meteo": meteo,
                            "pilota": pilota,
                            "note_set_up": note_setup,
                            "miglior_tempo": miglior_tempo,
                            "url_telemetria": url_tel,
                            "creato_da": utente['username']
                        }).execute()
                        st.success("Sessione di test registrata con successo!")
                        st.rerun()
                    else:
                        st.error("Inserisci il luogo del test.")

        st.divider()
        st.subheader("Storico Test in Pista")
        
        try:
            sessioni = supabase.table("sessioni_test").select("*").order("data_test", desc=True).execute().data
            if sessioni:
                for s in sessioni:
                    with st.expander(f"🏁 [{formatta_data_it(s['data_test'])}] {s['luogo']} — Vettura: {s['vettura']} (Best: {s.get('miglior_tempo', 'N/D')})"):
                        c_s1, c_s2 = st.columns(2)
                        c_s1.write(f"**Pilota:** {s.get('pilota', 'N/D')}")
                        c_s1.write(f"**Meteo:** {s.get('condizioni_meteo', 'N/D')}")
                        c_s2.write(f"**Registrato da:** {s.get('creato_da', 'N/D')}")
                        
                        st.write(f"**Note di Set-up:** {s.get('note_set_up', 'Nessuna nota')}")
                        if s.get('url_telemetria'):
                            st.markdown(f"📊 **[Scarica File Telemetria / Report]({s['url_telemetria']})**")
            else:
                st.info("Nessun test registrato.")
        except Exception:
            st.info("Tabella test in configurazione su Supabase.")

    # ==========================================
    # 4. DIZIONARIO COMPONENTI
    # ==========================================
    elif menu == "📖 Dizionario Componenti":
        st.title("📖 Dizionario Componenti MMR")
        st.write("Qui puoi consultare, cercare o inserire i componenti della vettura, la loro funzione e le relative immagini esplicative.")
        
        with st.expander("➕ Inserisci Nuovo Componente"):
            with st.form("form_dizionario"):
                nome_comp = st.text_input("Nome Componente")
                divisione_comp = st.selectbox("Divisione di Competenza", [
                    "Business", "Powertrain CV", "Powertrain EV", "Frame and Body", 
                    "Aerodynamics and Thermal Managment", "Vehicle Dynamics", 
                    "Electronics", "Actuations", "Autonomous Driving", 
                    "Marketing", "Manufacturing", "Communication"
                ])
                descrizione_comp = st.text_area("Cosa fa e specifiche tecniche")
                foto_comp = st.file_uploader("Carica Foto/Schema Componente (Opzionale)", type=["png", "jpg", "jpeg"])
                
                if st.form_submit_button("Salva nel Dizionario"):
                    if nome_comp:
                        url_foto = None
                        if foto_comp:
                            url_foto = upload_file_to_supabase(foto_comp.getvalue(), foto_comp.name, "workspaces")
                        
                        supabase.table("dizionario_componenti").insert({
                            "nome": nome_comp,
                            "divisione": divisione_comp,
                            "descrizione": descrizione_comp,
                            "url_foto": url_foto,
                            "creato_da": utente['username']
                        }).execute()
                        st.success("Componente aggiunto al dizionario!")
                        st.rerun()
                    else:
                        st.error("Inserisci almeno il nome del componente.")

        st.divider()
        st.subheader("Elenco Componenti Registrati")
        
        try:
            componenti = supabase.table("dizionario_componenti").select("*").order("nome").execute().data
            if componenti:
                for c in componenti:
                    with st.expander(f"⚙️ {c['nome']} — *[{c['divisione']}]*"):
                        st.write(f"**Funzione / Specifiche:** {c['descrizione']}")
                        st.caption(f"Inserito da: {c.get('creato_da', 'N/D')}")
                        if c.get('url_foto'):
                            st.image(c['url_foto'], caption=c['nome'], width=400)
            else:
                st.info("Nessun componente inserito nel dizionario.")
        except Exception:
            st.info("Tabella dizionario in fase di configurazione su Supabase.")

    # ==========================================
    # 5. BOM - BILL OF MATERIALS
    # ==========================================
    elif menu == "📦 BOM (Bill of Materials)":
        st.title("📦 Bill of Materials (BOM) Vettura")
        st.write("Gestione strutturata della distinta base dei materiali e componenti per assemblaggio.")
        
        with st.expander("➕ Aggiungi Elemento alla BOM"):
            with st.form("form_bom"):
                c1, c2 = st.columns(2)
                codice_parte = c1.text_input("Codice Parte (es. FB-01-CHAS)")
                nome_parte = c2.text_input("Nome Componente")
                
                c3, c4, c5 = st.columns(3)
                gruppo_assieme = c3.selectbox("Sottoassieme Principale", [
                    "Telaio e Aerodinamica", "Powertrain / Motore", "Elettronica & Ecu", 
                    "Sospensioni e Dinamica", "Actuations & Pneumatica", "Altro"
                ])
                quantita = c4.number_input("Quantità", min_value=1, step=1, value=1)
                divisione_rif = c5.selectbox("Divisione Responsabile", [
                    "Business", "Powertrain CV", "Powertrain EV", "Frame and Body", 
                    "Aerodynamics and Thermal Managment", "Vehicle Dynamics", 
                    "Electronics", "Actuations", "Autonomous Driving", 
                    "Marketing", "Manufacturing", "Communication"
                ])
                
                materiale = st.text_input("Materiale / Specifiche (es. Alluminio 7075, CFRP)")
                stato_produzione = st.selectbox("Stato", ["Da Progettare", "In Progettazione", "In Produzione", "Pronto / Disponibile", "Montato"])
                
                if st.form_submit_button("Aggiungi alla BOM"):
                    if codice_parte and nome_parte:
                        supabase.table("bom_vettura").insert({
                            "codice": codice_parte,
                            "nome": nome_parte,
                            "assieme": gruppo_assieme,
                            "quantita": quantita,
                            "divisione": divisione_rif,
                            "materiale": materiale,
                            "stato": stato_produzione,
                            "aggiornato_da": utente['username']
                        }).execute()
                        st.success("Componente aggiunto alla BOM!")
                        st.rerun()
                    else:
                        st.error("Inserisci Codice e Nome del componente.")

        st.divider()
        
        try:
            bom_data = supabase.table("bom_vettura").select("*").order("assieme").execute().data
            if bom_data:
                df_bom = pd.DataFrame(bom_data)
                df_bom = df_bom[['codice', 'nome', 'assieme', 'quantita', 'divisione', 'materiale', 'stato', 'aggiornato_da']]
                df_bom.columns = ['Codice', 'Nome Componente', 'Assieme', 'Qtà', 'Divisione', 'Materiale', 'Stato', 'Agg. da']
                st.dataframe(df_bom, use_container_width=True, hide_index=True)
            else:
                st.info("La BOM è attualmente vuota.")
        except Exception:
            st.info("Tabella BOM in fase di configurazione su Supabase.")

    # ==========================================
    # 6. RUBRICA CONTATTI
    # ==========================================
    elif menu == "👥 Rubrica Contatti":
        st.title("👥 Rubrica Contatti")
        utenti_db = supabase.table("membri").select("nome, cognome, email, telefono, ruolo, divisione").execute().data
        if utenti_db:
            df = pd.DataFrame(utenti_db)
            df.columns = ['Nome', 'Cognome', 'Email', 'Telefono', 'Ruolo', 'Divisione']
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Nessun membro trovato.")

    # ==========================================
    # 7. AREA PERSONALE
    # ==========================================
    elif menu == "👤 Area Personale":
        st.title(f"👤 Area Personale di {utente['nome']} {utente['cognome']}")
        st.write("Inserisci i tuoi dati anagrafici e carica i documenti richiesti (tutti i campi e file sono opzionali).")
        
        dati_personali = supabase.table("membri").select("*").eq("id", utente['id']).execute().data[0]
        
        with st.form("form_area_personale"):
            telefono = st.text_input("Numero di telefono", value=dati_personali.get('telefono', '') or '')
            data_nascita = st.text_input("Data di nascita (es. DD/MM/AAAA)", value=dati_personali.get('data_nascita', '') or '')
            luogo_nascita = st.text_input("Luogo di nascita", value=dati_personali.get('luogo_nascita', '') or '')
            codice_fiscale = st.text_input("Codice Fiscale", value=dati_personali.get('codice_fiscale', '') or '')
            
            st.divider()
            st.subheader("📎 Caricamento Documenti Personali e Certificati (Opzionali)")
            
            ci_file = st.file_uploader("Carta d'Identità", type=["pdf", "png", "jpg"])
            ts_file = st.file_uploader("Tessera Sanitaria", type=["pdf", "png", "jpg"])
            pass_file = st.file_uploader("Passaporto", type=["pdf", "png", "jpg"])
            pat_file = st.file_uploader("Patente", type=["pdf", "png", "jpg"])
            sicurezza_file = st.file_uploader("Certificati Corsi sulla Sicurezza", type=["pdf", "png", "jpg"])
            
            if st.form_submit_button("Salva Area Personale"):
                with st.spinner("Salvataggio in corso..."):
                    url_ci = upload_file_to_supabase(ci_file.getvalue(), ci_file.name, "workspaces") if ci_file else dati_personali.get('url_ci')
                    url_ts = upload_file_to_supabase(ts_file.getvalue(), ts_file.name, "workspaces") if ts_file else dati_personali.get('url_ts')
                    url_pass = upload_file_to_supabase(pass_file.getvalue(), pass_file.name, "workspaces") if pass_file else dati_personali.get('url_pass')
                    url_pat = upload_file_to_supabase(pat_file.getvalue(), pat_file.name, "workspaces") if pat_file else dati_personali.get('url_pat')
                    url_sic = upload_file_to_supabase(sicurezza_file.getvalue(), sicurezza_file.name, "workspaces") if sicurezza_file else dati_personali.get('url_sicurezza')
                    
                    aggiornamento = {
                        "telefono": telefono, "data_nascita": data_nascita, "luogo_nascita": luogo_nascita,
                        "codice_fiscale": codice_fiscale, "url_ci": url_ci, "url_ts": url_ts,
                        "url_pass": url_pass, "url_pat": url_pat, "url_sicurezza": url_sic
                    }
                    supabase.table("membri").update(aggiornamento).eq("id", utente['id']).execute()
                    st.success("Dati personali salvati con successo!")
                    time.sleep(1)
                    st.rerun()

        st.divider()
        st.markdown(
            """<div style='background-color: #1e1e1e; padding: 15px; border-radius: 5px; font-size: 13px; color: #b0b0b0;'>
            <b>🔒 Informativa sulla Privacy e Trattamento dei Dati Personali:</b><br>
            I dati anagrafici, i documenti d'identità e i certificati di sicurezza eventualmente caricati all'interno di questa sezione 
            vengono raccolti in conformità al GDPR (Regolamento UE 2016/679) e sono trattati esclusivamente dal Board e dai soggetti autorizzati 
            del team <b>More Modena Racing</b> per fini strettamente connessi all'organizzazione logistica, alla compilazione di documentazione per gare, 
            iscrizioni agli eventi Formula Student e prenotazione di trasferte. I dati non saranno ceduti a terzi né utilizzati per scopi commerciali. 
            Con l'inserimento e il salvataggio dei dati, l'utente acconsente al loro trattamento per le sole finalità istituzionali del team.
            </div>""", 
            unsafe_allow_html=True
        )

    # ==========================================
    # 8. SCADENZE DOCUMENTI
    # ==========================================
    elif menu == "📄 Scadenze Documenti":
        st.title("📄 Gestione Documenti e Scadenze")
        st.write("Le scadenze inserite qui appariranno automaticamente nel Calendario Macchina, incluso un promemoria 15 giorni prima.")
        
        with st.expander("➕ Aggiungi Nuova Scadenza con Template"):
            with st.form("form_scadenza"):
                nome_doc = st.text_input("Nome Documento / Evento")
                data_scad = st.date_input("Data di Scadenza", format="DD/MM/YYYY")
                note_doc = st.text_area("Note / Specifiche")
                file_template_nuovo = st.file_uploader("Carica Template / Documento (Opzionale)", type=["pdf", "doc", "docx", "xls", "xlsx"])
                
                if st.form_submit_button("Crea Scadenza"):
                    if nome_doc:
                        url_temp = None
                        if file_template_nuovo:
                            url_temp = upload_file_to_supabase(file_template_nuovo.getvalue(), file_template_nuovo.name, "workspaces")
                        
                        supabase.table("scadenze_documenti").insert({
                            "nome_documento": nome_doc,
                            "data_scadenza": str(data_scad),
                            "note": note_doc,
                            "url_template": url_temp,
                            "creato_da": utente['username']
                        }).execute()
                        st.success("Scadenza aggiunta con successo!")
                        st.rerun()
                    else:
                        st.error("Inserisci il nome del documento.")
        
        scadenze_esistenti = supabase.table("scadenze_documenti").select("*").order("data_scadenza").execute().data
        if scadenze_esistenti:
            for s in scadenze_esistenti:
                with st.expander(f"🚨 {s['nome_documento']} - Scadenza: {formatta_data_it(s['data_scadenza'])}"):
                    st.write(f"**Note:** {s['note']}")
                    st.write(f"**Creato da:** {s['creato_da']}")
                    
                    if s.get('url_template'):
                        st.markdown(f"📄 **[Scarica Documento/Template Allegato]({s['url_template']})**")
                    else:
                        st.caption("Nessun file o template allegato.")
                    
                    st.divider()
                    st.write("**Aggiungi o Aggiorna il Template / Documento:**")
                    file_up = st.file_uploader("Carica File", key=f"file_scad_{s['id']}")
                    
                    col_s1, col_s2 = st.columns([1, 4])
                    if col_s1.button("💾 Salva File", key=f"btn_scad_{s['id']}"):
                        if file_up:
                            with st.spinner("Caricamento..."):
                                url_f = upload_file_to_supabase(file_up.getvalue(), file_up.name, "workspaces")
                                if url_f:
                                    supabase.table("scadenze_documenti").update({"url_template": url_f}).eq("id", s['id']).execute()
                                    st.success("File aggiunto!")
                                    st.rerun()
                    
                    if col_s2.button("🗑️ Elimina Scadenza", key=f"del_scad_{s['id']}", type="primary"):
                        supabase.table("scadenze_documenti").delete().eq("id", s['id']).execute()
                        st.warning("Scadenza eliminata!")
                        st.rerun()
        else:
            st.info("Non ci sono scadenze documentali attive.")

    # ==========================================
    # 9. DOCUMENTI MEMBRI (RISERVATO AL BOARD)
    # ==========================================
    elif menu == "📂 Documenti Membri":
        st.title("📂 Documenti e Anagrafiche Membri")
        st.write("Sezione riservata al Board: visualizza i dati e i file personali di tutti i membri in ordine alfabetico.")
        
        tutti_membri = supabase.table("membri").select("*").order("cognome").execute().data
        if tutti_membri:
            for m in tutti_membri:
                nome_completo = f"{m['cognome'] or ''} {m['nome'] or ''} ({m['divisione']} - {m['ruolo']})"
                with st.expander(f"👤 {nome_completo}"):
                    c_d1, c_d2 = st.columns(2)
                    c_d1.write(f"**Email:** {m.get('email', '-')}")
                    c_d1.write(f"**Telefono:** {m.get('telefono', 'Non inserito')}")
                    c_d1.write(f"**Data di Nascita:** {m.get('data_nascita', 'Non inserita')}")
                    c_d1.write(f"**Luogo di Nascita:** {m.get('luogo_nascita', 'Non inserito')}")
                    c_d2.write(f"**Codice Fiscale:** {m.get('codice_fiscale', 'Non inserito')}")
                    
                    st.write("**File Allegati:**")
                    links_utili = []
                    if m.get('url_ci'): links_utili.append(f"[Carta d'Identità]({m['url_ci']})")
                    if m.get('url_ts'): links_utili.append(f"[Tessera Sanitaria]({m['url_ts']})")
                    if m.get('url_pass'): links_utili.append(f"[Passaporto]({m['url_pass']})")
                    if m.get('url_pat'): links_utili.append(f"[Patente]({m['url_pat']})")
                    if m.get('url_sicurezza'): links_utili.append(f"[Corsi Sicurezza]({m['url_sicurezza']})")
                    
                    if links_utili:
                        st.markdown(" | ".join(links_utili))
                    else:
                        st.caption("Nessun documento caricato dall'utente.")
        else:
            st.info("Nessun membro registrato.")

    # ==========================================
    # 10. CALENDARI
    # ==========================================
    elif menu == "📅 Calendari":
        st.title("📅 Calendari Team MMR")
        
        scelta_calendario = st.radio("Scegli quale calendario visualizzare:", ["🏎️ Calendario Macchina", "🏫 Prenotazioni Ufficio MO25"], horizontal=True)
        st.divider()
        
        calendar_options = {
            "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"},
            "initialView": "timeGridWeek",
            "slotMinTime": "08:00:00",
            "slotMaxTime": "22:00:00",
            "navLinks": True,
            "height": "700px",
            "locale": "it", 
            "firstDay": 1,
            "buttonText": {"today": "Oggi", "month": "Mese", "week": "Settimana", "day": "Giorno"}
        }

        # --- CALENDARIO MACCHINA ---
        if scelta_calendario == "🏎️ Calendario Macchina":
            st.subheader("Eventi, Impegni Vettura e Scadenze")
            
            if utente['ruolo'] in ["CTO", "Team Leader"] or (utente['ruolo'] == "Division Leader" and utente['divisione'] == "Communication"):
                with st.expander("➕ Aggiungi Evento Macchina"):
                    with st.form("form_macchina"):
                        titolo = st.text_input("Titolo Evento")
                        vettura = st.selectbox("Seleziona Vettura", ["M26-ED (Elettrica)", "M26-LH (Ibrida)", "Ibrida Rossa"])
                        d_inizio = st.date_input("Data Inizio", format="DD/MM/YYYY")
                        d_fine = st.date_input("Data Fine", format="DD/MM/YYYY")
                        
                        tutto_il_giorno = st.checkbox("Evento per l'intera giornata", value=True)
                        c_ora1, c_ora2 = st.columns(2)
                        ora_in = c_ora1.time_input("Ora Inizio (Ignorato se tutto il giorno)")
                        ora_fi = c_ora2.time_input("Ora Fine (Ignorato se tutto il giorno)")
                        
                        furgone = st.checkbox("🚐 Richiedi prenotazione furgone per questo evento")
                        note = st.text_area("Note e Luogo")
                        
                        if st.form_submit_button("Salva Evento"):
                            nuovo_evento = {
                                "titolo": titolo, "vettura": vettura, "data_inizio": str(d_inizio), "data_fine": str(d_fine),
                                "tutto_il_giorno": tutto_il_giorno, "ora_inizio": str(ora_in), "ora_fine": str(ora_fi),
                                "furgone_richiesto": furgone, "stato_furgone": "In attesa" if furgone else "Non richiesto",
                                "note": note, "creatore": utente['username']
                            }
                            supabase.table("calendario_macchina").insert(nuovo_evento).execute()
                            st.success("Evento aggiunto!")
                            st.rerun()
            
            eventi_macchina = supabase.table("calendario_macchina").select("*").order("data_inizio").execute().data
            cal_macchina_events = []
            
            colori_auto = {
                "M26-ED (Elettrica)": "#1d3557",
                "M26-LH (Ibrida)": "#e63946",
                "Ibrida Rossa": "#f77f00"
            }

            if eventi_macchina:
                with st.expander("⚙️ Gestisci / Elimina Eventi Macchina"):
                    for e in eventi_macchina:
                        col_ev1, col_ev2 = st.columns([4,1])
                        data_it = formatta_data_it(e['data_inizio'])
                        col_ev1.write(f"[{e.get('vettura', 'Auto')}] {e['titolo']} ({data_it}) - {e['creatore']}")
                        if is_direttivo or e['creatore'] == utente['username']:
                            if col_ev2.button("🗑️", key=f"del_mac_{e['id']}"):
                                supabase.table("calendario_macchina").delete().eq("id", e['id']).execute()
                                st.rerun()

                for e in eventi_macchina:
                    vettura_scelta = e.get('vettura', 'M26-ED (Elettrica)')
                    colore_vettura = colori_auto.get(vettura_scelta, "#e63946")
                    
                    evento_cal = {
                        "title": f"[{vettura_scelta}] {e['titolo']} ({e['creatore']}) {'🚐' if e['furgone_richiesto'] else ''}",
                        "color": colore_vettura
                    }
                    if e.get("tutto_il_giorno", True):
                        evento_cal["start"] = e['data_inizio']
                        end_date = datetime.strptime(e['data_fine'], "%Y-%m-%d") + timedelta(days=1)
                        evento_cal["end"] = end_date.strftime("%Y-%m-%d")
                        evento_cal["allDay"] = True
                        evento_cal["className"] = "evento-all-day-evidenziato"
                    else:
                        evento_cal["start"] = f"{e['data_inizio']}T{e['ora_inizio']}"
                        evento_cal["end"] = f"{e['data_fine']}T{e['ora_fine']}"
                        evento_cal["allDay"] = False
                        
                    cal_macchina_events.append(evento_cal)
            
            scadenze = supabase.table("scadenze_documenti").select("*").execute().data
            if scadenze:
                for s in scadenze:
                    cal_macchina_events.append({
                        "title": f"🚨 SCADENZA: {s['nome_documento']}",
                        "start": s['data_scadenza'],
                        "end": s['data_scadenza'],
                        "color": "#d90429",
                        "allDay": True,
                        "className": "evento-all-day-evidenziato"
                    })
                    data_scad_obj = datetime.strptime(s['data_scadenza'], "%Y-%m-%d")
                    data_promemoria = (data_scad_obj - timedelta(days=15)).strftime("%Y-%m-%d")
                    cal_macchina_events.append({
                        "title": f"⏳ PROMEMORIA (-15g): {s['nome_documento']}",
                        "start": data_promemoria,
                        "end": data_promemoria,
                        "color": "#ffb703",
                        "allDay": True,
                        "className": "evento-all-day-evidenziato"
                    })

            st.markdown("""
                <style>
                .fc-daygrid-event.evento-all-day-evidenziato, .fc-timegrid-event.evento-all-day-evidenziato {
                    background-color: #d90429 !important;
                    border: 3px solid #ffffff !important;
                    font-size: 14px !important;
                    font-weight: bold !important;
                    padding: 6px 10px !important;
                    border-radius: 6px !important;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.6) !important;
                }
                </style>
            """, unsafe_allow_html=True)

            st.write("🔵 *M26-ED (Blu)* | 🔴 *M26-LH (Rosso)* | 🟠 *Ibrida Rossa (Arancione)*")
            calendar(events=cal_macchina_events, options=calendar_options, key="cal_macchina")

        # --- CALENDARIO MO25 ---
        elif scelta_calendario == "🏫 Prenotazioni Ufficio MO25":
            st.subheader("Prenotazioni Ufficio Hybrid MO25")
            
            with st.expander("➕ Nuova Prenotazione (Aperta a tutti)"):
                c1, c2, c3 = st.columns(3)
                data_pren = c1.date_input("Giorno", min_value=datetime.today(), format="DD/MM/YYYY")
                ora_in = c2.time_input("Ora Inizio")
                ora_fi = c3.time_input("Ora Fine")
                persone = st.number_input("Numero di persone", min_value=1, step=1)
                note_pren = st.text_input("Note (Es. 'Mi unisco alla prenotazione di Marco')")
                settimane = st.number_input("Ripeti per quante settimane? (1 = solo questa)", min_value=1, max_value=10, step=1)
                
                if st.button("Inoltra Richiesta"):
                    for i in range(settimane):
                        data_corrente = data_pren + timedelta(weeks=i)
                        supabase.table("prenotazioni_aule").insert({
                            "richiedente": utente['username'], "divisione": utente['divisione'],
                            "data_prenotazione": str(data_corrente), "ora_inizio": str(ora_in),
                            "ora_fine": str(ora_fi), "num_persone": persone, "note": note_pren, "stato": "In attesa"
                        }).execute()
                    st.success("Richiesta/e inoltrata/e!")
                    st.rerun()

            st.divider()
            pren_mo25 = supabase.table("prenotazioni_aule").select("*").order("data_prenotazione").execute().data
            
            if pren_mo25:
                with st.expander("⚙️ Gestisci / Elimina Prenotazioni MO25"):
                    for p in pren_mo25:
                        col_p1, col_p2 = st.columns([4,1])
                        data_pren_it = formatta_data_it(p['data_prenotazione'])
                        col_p1.write(f"📅 {data_pren_it} | {p['ora_inizio']} - {p['divisione']} ({p['richiedente']})")
                        if is_direttivo or p['richiedente'] == utente['username']:
                            if col_p2.button("🗑️", key=f"del_mo_{p['id']}"):
                                supabase.table("prenotazioni_aule").delete().eq("id", p['id']).execute()
                                st.rerun()

                if is_direttivo:
                    st.write("**Approvazione Prenotazioni Pendenti:**")
                    for p in pren_mo25:
                        if p['stato'] == 'In attesa':
                            if utente['ruolo'] in ["CTO", "Team Leader"] or (utente['ruolo'] == "Division Leader" and utente['divisione'] == p['divisione']):
                                col1, col2 = st.columns([4, 1])
                                data_pren_it_app = formatta_data_it(p['data_prenotazione'])
                                col1.write(f"📅 {data_pren_it_app} | 🕒 {p['ora_inizio']}-{p['ora_fine']} | 🏢 {p['divisione']} ({p['richiedente']}) - {p['num_persone']} pers.")
                                if col2.button("✅ Approva", key=f"app_{p['id']}"):
                                    supabase.table("prenotazioni_aule").update({"stato": "Approvato"}).eq("id", p['id']).execute()
                                    st.rerun()

            colori_divisioni = {
                "Business": "#264653", "Powertrain CV": "#2a9d8f", "Powertrain EV": "#e76f51",
                "Frame and Body": "#457b9d", "Aerodynamics and Thermal Managment": "#1d3557",
                "Vehicle Dynamics": "#f4a261", "Electronics": "#9b5de5", "Actuations": "#f15bb5",
                "Autonomous Driving": "#00bbf9", "Marketing": "#00f5d4", "Manufacturing": "#fee440", "Communication": "#b5179e"
            }

            cal_mo25_events = []
            if pren_mo25:
                for p in pren_mo25:
                    ora_in_str = str(p['ora_inizio'])
                    if len(ora_in_str) == 5: ora_in_str += ":00" 
                    ora_fi_str = str(p['ora_fine'])
                    if len(ora_fi_str) == 5: ora_fi_str += ":00"

                    start_str = f"{p['data_prenotazione']}T{ora_in_str}"
                    end_str = f"{p['data_prenotazione']}T{ora_fi_str}"
                    
                    colore_base = colori_divisioni.get(p['divisione'], "#2e7d32")
                    colore_sfondo = colore_base if p['stato'] == 'Approvato' else "#6c757d"
                    
                    titolo_evento = f"{p['divisione']} ({p['num_persone']}p) - {p['richiedente']} [{p['stato']}]"
                    
                    cal_mo25_events.append({
                        "title": titolo_evento, "start": start_str, "end": end_str,
                        "backgroundColor": colore_sfondo, "borderColor": colore_sfondo
                    })

            st.write("🎨 *Ogni divisione ha il suo colore identificativo. Se grigio, è in attesa di approvazione.*")
            calendar(events=cal_mo25_events, options=calendar_options, key="cal_mo25_view")

    # ==========================================
    # 11. AREE DI LAVORO (FILE MANAGER)
    # ==========================================
    elif menu == "🏢 Aree di Lavoro":
        st.title("🏢 Aree di Lavoro Divisioni")
        
        divisioni_autorizzate = [utente['divisione']]
        if is_direttivo:
            divisioni_mmr = ["Business", "Powertrain CV", "Powertrain EV", "Frame and Body", "Aerodynamics and Thermal Managment", "Vehicle Dynamics", "Electronics", "Actuations", "Autonomous Driving", "Marketing", "Manufacturing", "Communication"]
            divisioni_autorizzate = divisioni_mmr
        else:
            accessi_extra = supabase.table("accessi_divisioni").select("divisione_richiesta").eq("username", utente['username']).eq("stato", "Approvato").execute().data
            for acc in accessi_extra:
                divisioni_autorizzate.append(acc['divisione_richiesta'])

        st.write("Naviga tra le divisioni a cui hai accesso:")
        tabs_divisioni = st.tabs(divisioni_autorizzate)
        
        for i, tab in enumerate(tabs_divisioni):
            current_div = divisioni_autorizzate[i]
            with tab:
                st.subheader(f"Scheda Operativa: {current_div}")
                files_div = supabase.table("file_divisioni").select("*").eq("divisione", current_div).execute().data
                
                autorizzato_upload = utente['ruolo'] in ["CTO", "Team Leader"] or (utente['ruolo'] == "Division Leader" and utente['divisione'] == current_div)
                
                if autorizzato_upload:
                    with st.expander("➕ Crea Cartella / Carica un File"):
                        folders = list(set([f['cartella'] for f in files_div])) if files_div else []
                        if "Generale" not in folders: folders.insert(0, "Generale")
                        
                        selected_folder = st.selectbox("Cartella di destinazione", folders + ["-- Nuova cartella --"], key=f"sel_f_{current_div}")
                        folder_name = selected_folder
                        if selected_folder == "-- Nuova cartella --":
                            folder_name = st.text_input("Nome della nuova cartella", key=f"new_f_{current_div}")
                        
                        uploaded_file = st.file_uploader("Scegli un file", key=f"up_{current_div}")
                        
                        if st.button("Carica File", key=f"btn_up_{current_div}", type="primary"):
                            if uploaded_file and folder_name:
                                with st.spinner("Caricamento in corso..."):
                                    url = upload_file_to_supabase(uploaded_file.getvalue(), uploaded_file.name, "workspaces")
                                    if url:
                                        supabase.table("file_divisioni").insert({
                                            "divisione": current_div, "cartella": folder_name, "nome_file": uploaded_file.name,
                                            "url_file": url, "caricato_da": utente['username']
                                        }).execute()
                                        st.success("File caricato con successo!")
                                        st.rerun()
                            else:
                                st.warning("Seleziona una cartella e un file.")
                
                st.write("**Documenti della Divisione:**")
                if files_div:
                    df_files = pd.DataFrame(files_div)
                    for folder, group in df_files.groupby("cartella"):
                        with st.expander(f"📁 {folder}", expanded=True):
                            for _, row in group.iterrows():
                                st.markdown(f"📄 [{row['nome_file']}]({row['url_file']}) *(Caricato da: {row['caricato_da']})*")
                else:
                    st.info("Nessun documento caricato per questa divisione.")
        
        st.divider()
        col_req, col_app = st.columns(2)
        
        with col_req:
            if not is_direttivo:
                st.subheader("Richiedi nuovi accessi")
                tutte_div = ["Business", "Powertrain CV", "Powertrain EV", "Frame and Body", "Aerodynamics and Thermal Managment", "Vehicle Dynamics", "Electronics", "Actuations", "Autonomous Driving", "Marketing", "Manufacturing", "Communication"]
                div_mancanti = [d for d in tutte_div if d not in divisioni_autorizzate]
                if div_mancanti:
                    div_richiesta = st.selectbox("Seleziona divisione", div_mancanti)
                    if st.button("Invia Richiesta di Accesso"):
                        check = supabase.table("accessi_divisioni").select("*").eq("username", utente['username']).eq("divisione_richiesta", div_richiesta).execute().data
                        if len(check) > 0:
                            st.warning("Hai già una richiesta in corso per questa divisione.")
                        else:
                            supabase.table("accessi_divisioni").insert({"username": utente['username'], "divisione_richiesta": div_richiesta, "stato": "In attesa"}).execute()
                            st.success("Richiesta inviata al DL di riferimento!")
                else:
                    st.success("Hai già accesso a tutte le divisioni!")

        with col_app:
            if is_direttivo:
                st.subheader("Richieste di Accesso Pendenti")
                if utente['ruolo'] == "Division Leader":
                    richieste = supabase.table("accessi_divisioni").select("*").eq("divisione_richiesta", utente['divisione']).eq("stato", "In attesa").execute().data
                else:
                    richieste = supabase.table("accessi_divisioni").select("*").eq("stato", "In attesa").execute().data
                    
                if richieste:
                    for r in richieste:
                        c1, c2 = st.columns([3, 1])
                        c1.write(f"**{r['username']}** ➔ **{r['divisione_richiesta']}**")
                        if c2.button("Approva", key=f"acc_{r['id']}"):
                            supabase.table("accessi_divisioni").update({"stato": "Approvato"}).eq("id", r['id']).execute()
                            st.rerun()
                else:
                    st.info("Nessuna richiesta in sospeso.")

    # ==========================================
    # 12. GESTIONE ACQUISTI
    # ==========================================
    elif menu == "🛒 Gestione Acquisti":
        st.title("🛒 Gestione Acquisti")
        
        if ruolo_display == "CFO (Admin)":
            st.subheader("Pannello di Controllo CFO: Tutte le Richieste")
            richieste = supabase.table("acquisti").select("*").execute().data
            if richieste:
                for req in richieste:
                    with st.expander(f"[{req['divisione']}] {req['oggetto']} ({req['stato']})"):
                        st.write(f"**Richiedente:** {req['richiedente']} | **Azienda:** {req['azienda']}")
                        iva_testo = "Sì (22%)" if req.get('iva_applicabile', True) else "No"
                        st.write(f"**Costo senza IVA:** € {req['costo_no_iva']} | **IVA Applicabile:** {iva_testo}")
                        se_unico = "Sì" if req.get('unica_produttrice') else "No"
                        st.write(f"**Fornitore Unico:** {se_unico}")
                        
                        st.write("**Documenti allegati:**")
                        if req.get('link_preventivo_1'): st.markdown(f"📄 [Scarica Preventivo 1]({req['link_preventivo_1']})")
                        if req.get('link_preventivo_2'): st.markdown(f"📄 [Scarica Preventivo 2]({req['link_preventivo_2']})")
                        if req.get('link_preventivo_3'): st.markdown(f"📄 [Scarica Preventivo 3]({req['link_preventivo_3']})")
                        if req.get('link_dichiarazione_unicita'): st.markdown(f"📄 [Scarica Dichiarazione Unicità]({req['link_dichiarazione_unicita']})")
                        
                        st.divider()
                        c1, c2 = st.columns(2)
                        with c1:
                            nuovo_stato = st.selectbox("Aggiorna Stato", stati_acquisto, index=stati_acquisto.index(req['stato']), key=f"stato_{req['id']}")
                        with c2:
                            nuovo_fondo = st.text_input("Fondo assegnato", value=req['fondo'] if req['fondo'] else "", key=f"fondo_{req['id']}")
                        
                        col_salva, col_elimina = st.columns(2)
                        with col_salva:
                            if st.button("💾 Salva Modifiche", key=f"btn_salva_{req['id']}", use_container_width=True):
                                supabase.table("acquisti").update({"stato": nuovo_stato, "fondo": nuovo_fondo}).eq("id", req['id']).execute()
                                st.success("Richiesta aggiornata con successo!")
                                st.rerun()
                        with col_elimina:
                            if st.button("🗑️ Elimina Richiesta", key=f"btn_elimina_{req['id']}", type="primary", use_container_width=True):
                                supabase.table("acquisti").delete().eq("id", req['id']).execute()
                                st.warning("La richiesta è stata eliminata!")
                                st.rerun()
            else:
                st.info("Non ci sono richieste di acquisto in sospeso.")
            st.divider()
                
        if is_direttivo:
            st.subheader("Inoltra Nuova Richiesta di Acquisto")
            oggetto = st.text_input("Cosa stai acquistando?")
            azienda = st.text_input("Azienda fornitrice")
            costo = st.number_input("Costo totale (Senza IVA)", min_value=0.0, step=1.0)
            iva_applicabile = st.checkbox("Applica IVA (22%)", value=True)
            unica_prod = st.checkbox("L'azienda è l'unica produttrice sul mercato?")
            
            file_p1, file_p2, file_p3, file_dichiarazione = None, None, None, None
            
            if unica_prod:
                st.info("📌 Modalità Fornitore Unico attiva: Richiesto Preventivo e Dichiarazione (opzionali).")
                file_p1 = st.file_uploader("Carica Preventivo 1", type=["pdf"])
                file_dichiarazione = st.file_uploader("Carica Dichiarazione di Unicità", type=["pdf"])
            else:
                file_p1 = st.file_uploader("Carica Preventivo 1", type=["pdf"])
                file_p2 = st.file_uploader("Carica Preventivo 2", type=["pdf"])
                if costo > 5000:
                    st.warning("⚠️ Per acquisti superiori a 5.000€ sono raccomandati 3 preventivi.")
                    file_p3 = st.file_uploader("Carica Preventivo 3", type=["pdf"])
            
            if st.button("📤 Inoltra al CFO", type="primary"):
                if oggetto and azienda and costo > 0:
                    with st.spinner("Caricamento PDF e invio richiesta in corso..."):
                        url_1 = upload_file_to_supabase(file_p1.getvalue(), file_p1.name, "preventivi") if file_p1 else None
                        url_2 = upload_file_to_supabase(file_p2.getvalue(), file_p2.name, "preventivi") if file_p2 else None
                        url_3 = upload_file_to_supabase(file_p3.getvalue(), file_p3.name, "preventivi") if file_p3 else None
                        url_dich = upload_file_to_supabase(file_dichiarazione.getvalue(), file_dichiarazione.name, "preventivi") if file_dichiarazione else None
                        
                        supabase.table("acquisti").insert({
                            "richiedente": utente['username'], "divisione": utente['divisione'], "oggetto": oggetto, "azienda": azienda, "costo_no_iva": costo,
                            "iva_applicabile": iva_applicabile, "unica_produttrice": unica_prod, "link_preventivo_1": url_1, "link_preventivo_2": url_2,
                            "link_preventivo_3": url_3, "link_dichiarazione_unicita": url_dich, "stato": "Inoltrato"
                        }).execute()
                        st.success("Richiesta inviata con successo!")
                        time.sleep(1)
                        st.rerun()
                else: 
                    st.error("Compila i campi Oggetto, Azienda e inserisci un Costo maggiore di zero.")

            st.divider()
            st.subheader(f"Le richieste di: {utente['divisione']}")
            risposta_mie = supabase.table("acquisti").select("*").eq("divisione", utente['divisione']).execute().data
            if risposta_mie:
                df_mie = pd.DataFrame(risposta_mie)[['oggetto', 'azienda', 'costo_no_iva', 'stato', 'fondo']]
                st.dataframe(df_mie, use_container_width=True, hide_index=True)

    # ==========================================
    # 13. BILANCIO BUDGET
    # ==========================================
    elif menu == "📊 Bilancio Budget":
        st.title("📊 Bilancio e Budget Generale")
        risposta_bilancio = supabase.table("acquisti").select("*").in_("stato", ["Buono d'ordine emesso", "Pagato"]).execute().data
        
        if risposta_bilancio:
            df_bilancio = pd.DataFrame(risposta_bilancio)
            df_bilancio['Costo Finanziato'] = df_bilancio.apply(lambda row: row['costo_no_iva'] * 1.22 if row.get('iva_applicabile', True) else row['costo_no_iva'], axis=1)
            totale = df_bilancio['Costo Finanziato'].sum()
            
            st.metric(label="Totale Spese Approvate (IVA inclusa dove applicabile)", value=f"€ {totale:,.2f}")
            df_bilancio['IVA'] = df_bilancio['iva_applicabile'].apply(lambda x: 'Sì' if x else 'No')
            st.dataframe(df_bilancio[['divisione', 'oggetto', 'azienda', 'fondo', 'costo_no_iva', 'IVA', 'Costo Finanziato', 'stato']], use_container_width=True, hide_index=True)
        else: 
            st.info("Nessun acquisto ha ancora raggiunto la fase di emissione buono d'ordine.")

    # ==========================================
    # 14. GESTIONE UTENTI
    # ==========================================
    elif menu == "⚙️ Gestione Utenti":
        st.title("⚙️ Gestione Utenti Avanzata")
        utenti = supabase.table("membri").select("id, nome, cognome, username, email, ruolo, divisione").execute().data
        
        if utenti:
            st.write("Gestione dei ruoli e degli account del team.")
            st.info("ℹ️ Il Team Leader (TL) può modificare tutti. DL e CTO possono rimuovere o gestire solo i Membri.")
            
            ruoli_disponibili = ["Membro", "Division Leader", "CTO", "Team Leader"]
            punteggio_ruoli = {"Membro": 0, "Division Leader": 1, "CTO": 2, "Team Leader": 3}
            
            for u in utenti:
                if u['username'] != utente['username']:
                    with st.container():
                        col_info, col_ruolo, col_salva, col_elimina = st.columns([3, 2, 2, 1])
                        
                        col_info.write(f"**{u['nome']} {u['cognome']}** ({u['username']}) - {u['ruolo']} [{u['divisione']}]")
                        nuovo_ruolo = col_ruolo.selectbox("Cambia ruolo", ruoli_disponibili, index=ruoli_disponibili.index(u['ruolo']), key=f"ruolo_{u['id']}")
                        
                        if col_salva.button("🔄 Aggiorna Ruolo", key=f"aggiorna_{u['id']}_{u['ruolo']}"):
                            is_downgrade = punteggio_ruoli[nuovo_ruolo] < punteggio_ruoli[u['ruolo']]
                            
                            if utente['ruolo'] in ["Division Leader", "CTO"] and u['ruolo'] != "Membro":
                                st.error("❌ Operazione negata: DL e CTO possono gestire/rimuovere solo i Membri.")
                            elif is_downgrade and utente['ruolo'] != "Team Leader":
                                st.error("❌ Operazione negata: Solo il Team Leader può retrocedere di livello un utente.")
                            else:
                                supabase.table("membri").update({"ruolo": nuovo_ruolo}).eq("id", u['id']).execute()
                                st.success("Ruolo aggiornato con successo!")
                                st.rerun()
                                
                        if col_elimina.button("🗑️", key=f"elimina_{u['id']}", help="Elimina utente"):
                            if utente['ruolo'] in ["Division Leader", "CTO"] and u['ruolo'] != "Membro":
                                st.error("❌ Non puoi eliminare account direttivi.")
                            else:
                                supabase.table("membri").delete().eq("id", u['id']).execute()
                                st.warning("Utente eliminato!")
                                st.rerun()
                        st.divider()