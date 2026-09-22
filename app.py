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
                        st.error(f"Username {username} esiste già!")
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
    
    opzioni_menu = ["🏠 Home", "📅 Calendari", "🏢 Aree di Lavoro", "👥 Rubrica Contatti"]
    if is_direttivo:
        opzioni_menu.extend(["📄 Scadenze Documenti", "🛒 Gestione Acquisti", "📊 Bilancio Budget", "⚙️ Gestione Utenti"])
        
    menu = st.sidebar.radio("Scegli la sezione:", opzioni_menu)
    stati_acquisto = ["Inoltrato", "Inviato a tecnico responsabile", "Inviato a responsabile dei fondi", "Inviato a Responsabile amministrativo", "Buono d'ordine emesso", "Pagato"]

    # ==========================================
    # 1. HOME CON DASHBOARD AVANZATA
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
                st.subheader("📅 Prossimi Eventi Macchina")
                eventi = supabase.table("calendario_macchina").select("*").order("data_inizio").execute().data
                ev_futuri = [e for e in eventi if datetime.strptime(e['data_inizio'], "%Y-%m-%d").date() >= oggi] if eventi else []
                if ev_futuri:
                    for e in ev_futuri[:5]:
                        st.write(f"🏎️ **{e['titolo']}** - {formatta_data_it(e['data_inizio'])}")
                else:
                    st.write("Nessun evento vettura in programma.")
                    
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
        else:
            st.info("Benvenuto! Usa il menu laterale per navigare tra le sezioni del gestionale.")

    # ==========================================
    # 2. RUBRICA CONTATTI
    # ==========================================
    elif menu == "👥 Rubrica Contatti":
        st.title("👥 Rubrica Contatti")
        df = pd.DataFrame(supabase.table("membri").select("nome, cognome, email, ruolo, divisione").execute().data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ==========================================
    # 3. GESTIONE SCADENZE (NUOVO)
    # ==========================================
    elif menu == "📄 Scadenze Documenti":
        st.title("📄 Gestione Documenti e Scadenze")
        st.write("Le scadenze inserite qui appariranno automaticamente nel Calendario Macchina, incluso un promemoria 15 giorni prima.")
        
        with st.expander("➕ Aggiungi Nuova Scadenza"):
            with st.form("form_scadenza"):
                nome_doc = st.text_input("Nome Documento / Evento")
                data_scad = st.date_input("Data di Scadenza", format="DD/MM/YYYY")
                note_doc = st.text_area("Note / Specifiche")
                if st.form_submit_button("Crea Scadenza"):
                    if nome_doc:
                        supabase.table("scadenze_documenti").insert({
                            "nome_documento": nome_doc,
                            "data_scadenza": str(data_scad),
                            "note": note_doc,
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
                    
                    st.divider()
                    st.write("**Aggiungi o Aggiorna il Template / Documento:**")
                    file_up = st.file_uploader("Carica File (PDF, Word, Excel...)", key=f"file_scad_{s['id']}")
                    
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
    # 4. CALENDARI
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
            "buttonText": {"today": "Oggi", "month": "Mese", "week": "Settimana", "day": "Giorno"}
        }

        # --- CALENDARIO MACCHINA ---
        if scelta_calendario == "🏎️ Calendario Macchina":
            st.subheader("Eventi, Impegni Vettura e Scadenze")
            
            if utente['ruolo'] in ["CTO", "Team Leader"] or (utente['ruolo'] == "Division Leader" and utente['divisione'] == "Communication"):
                with st.expander("➕ Aggiungi Evento Macchina"):
                    with st.form("form_macchina"):
                        titolo = st.text_input("Titolo Evento")
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
                                "titolo": titolo, "data_inizio": str(d_inizio), "data_fine": str(d_fine),
                                "tutto_il_giorno": tutto_il_giorno, "ora_inizio": str(ora_in), "ora_fine": str(ora_fi),
                                "furgone_richiesto": furgone, "stato_furgone": "In attesa" if furgone else "Non richiesto",
                                "note": note, "creatore": utente['username']
                            }
                            supabase.table("calendario_macchina").insert(nuovo_evento).execute()
                            st.success("Evento aggiunto!")
                            st.rerun()
            
            eventi_macchina = supabase.table("calendario_macchina").select("*").order("data_inizio").execute().data
            cal_macchina_events = []
            
            if eventi_macchina:
                with st.expander("⚙️ Gestisci / Elimina Eventi Macchina"):
                    for e in eventi_macchina:
                        col_ev1, col_ev2 = st.columns([4,1])
                        data_it = formatta_data_it(e['data_inizio'])
                        col_ev1.write(f"{e['titolo']} ({data_it}) - {e['creatore']}")
                        if is_direttivo or e['creatore'] == utente['username']:
                            if col_ev2.button("🗑️", key=f"del_mac_{e['id']}"):
                                supabase.table("calendario_macchina").delete().eq("id", e['id']).execute()
                                st.rerun()

                for e in eventi_macchina:
                    evento_cal = {
                        "title": f"{e['titolo']} ({e['creatore']}) {'🚐' if e['furgone_richiesto'] else ''}",
                        "color": "#e63946"
                    }
                    if e.get("tutto_il_giorno", True):
                        evento_cal["start"] = e['data_inizio']
                        end_date = datetime.strptime(e['data_fine'], "%Y-%m-%d") + timedelta(days=1)
                        evento_cal["end"] = end_date.strftime("%Y-%m-%d")
                        evento_cal["allDay"] = True
                    else:
                        evento_cal["start"] = f"{e['data_inizio']}T{e['ora_inizio']}"
                        evento_cal["end"] = f"{e['data_fine']}T{e['ora_fine']}"
                        evento_cal["allDay"] = False
                        
                    cal_macchina_events.append(evento_cal)
            
            # AGGIUNTA SCADENZE DOCUMENTI AL CALENDARIO MACCHINA
            scadenze = supabase.table("scadenze_documenti").select("*").execute().data
            if scadenze:
                for s in scadenze:
                    cal_macchina_events.append({
                        "title": f"🚨 SCADENZA: {s['nome_documento']}",
                        "start": s['data_scadenza'],
                        "end": s['data_scadenza'],
                        "color": "#d90429", # Rosso Scuro
                        "allDay": True
                    })
                    data_scad_obj = datetime.strptime(s['data_scadenza'], "%Y-%m-%d")
                    data_promemoria = (data_scad_obj - timedelta(days=15)).strftime("%Y-%m-%d")
                    cal_macchina_events.append({
                        "title": f"⏳ PROMEMORIA (-15g): {s['nome_documento']}",
                        "start": data_promemoria,
                        "end": data_promemoria,
                        "color": "#ffb703", # Giallo/Arancio
                        "allDay": True
                    })

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

            cal_mo25_events = []
            if pren_mo25:
                for p in pren_mo25:
                    ora_in_str = str(p['ora_inizio'])
                    if len(ora_in_str) == 5: ora_in_str += ":00" 
                    ora_fi_str = str(p['ora_fine'])
                    if len(ora_fi_str) == 5: ora_fi_str += ":00"

                    start_str = f"{p['data_prenotazione']}T{ora_in_str}"
                    end_str = f"{p['data_prenotazione']}T{ora_fi_str}"
                    
                    colore_sfondo = "#2e7d32" if p['stato'] == 'Approvato' else "#9e9e9e"
                    titolo_evento = f"{p['divisione']} ({p['num_persone']}p) - {p['richiedente']}"
                    
                    cal_mo25_events.append({
                        "title": titolo_evento, "start": start_str, "end": end_str,
                        "backgroundColor": colore_sfondo, "borderColor": colore_sfondo
                    })

            st.write("🟢 *Verde: Approvato* | ⚪ *Grigio: In Attesa*")
            calendar(events=cal_mo25_events, options=calendar_options, key="cal_mo25_view")

    # ==========================================
    # 5. AREE DI LAVORO (FILE MANAGER)
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
    # 6. GESTIONE ACQUISTI
    # ==========================================
    elif menu == "🛒 Gestione Acquisti":
        st.title("🛒 Gestione Acquisti")
        
        # PANNELLO CFO
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
                
        # INOLTRO ACQUISTI
        if is_direttivo:
            st.subheader("Inoltra Nuova Richiesta di Acquisto")
            oggetto = st.text_input("Cosa stai acquistando?")
            azienda = st.text_input("Azienda fornitrice")
            costo = st.number_input("Costo totale (Senza IVA)", min_value=0.0, step=1.0)
            iva_applicabile = st.checkbox("Applica IVA (22%)", value=True)
            unica_prod = st.checkbox("L'azienda è l'unica produttrice sul mercato?")
            
            file_p1, file_p2, file_p3, file_dichiarazione = None, None, None, None
            
            if unica_prod:
                st.info("📌 Modalità Fornitore Unico attiva: Richiesto 1 Preventivo e 1 Dichiarazione di Unicità.")
                file_p1 = st.file_uploader("Carica Preventivo 1", type=["pdf"])
                file_dichiarazione = st.file_uploader("Carica Dichiarazione di Unicità", type=["pdf"])
            else:
                file_p1 = st.file_uploader("Carica Preventivo 1", type=["pdf"])
                file_p2 = st.file_uploader("Carica Preventivo 2", type=["pdf"])
                if costo > 5000:
                    st.warning("⚠️ Per acquisti superiori a 5.000€ sono obbligatori 3 preventivi.")
                    file_p3 = st.file_uploader("Carica Preventivo 3", type=["pdf"])
            
            if st.button("📤 Inoltra al CFO", type="primary"):
                valid = False
                if oggetto and azienda and costo > 0:
                    if unica_prod:
                        if file_p1 and file_dichiarazione: valid = True
                        else: st.error("Devi caricare il preventivo e la dichiarazione di unicità.")
                    else:
                        if costo > 5000:
                            if file_p1 and file_p2 and file_p3: valid = True
                            else: st.error("Devi caricare tutti e 3 i preventivi richiesti.")
                        else:
                            if file_p1 and file_p2: valid = True
                            else: st.error("Devi caricare 2 preventivi comparativi.")
                else: 
                    st.error("Compila i campi Oggetto, Azienda e inserisci un Costo maggiore di zero.")
                
                if valid:
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

            st.divider()
            st.subheader(f"Le richieste di: {utente['divisione']}")
            risposta_mie = supabase.table("acquisti").select("*").eq("divisione", utente['divisione']).execute().data
            if risposta_mie:
                df_mie = pd.DataFrame(risposta_mie)[['oggetto', 'azienda', 'costo_no_iva', 'stato', 'fondo']]
                st.dataframe(df_mie, use_container_width=True, hide_index=True)

    # ==========================================
    # 7. BILANCIO BUDGET
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
    # 8. GESTIONE UTENTI
    # ==========================================
    elif menu == "⚙️ Gestione Utenti":
        st.title("⚙️ Gestione Utenti Avanzata")
        utenti = supabase.table("membri").select("id, nome, cognome, username, email, ruolo, divisione").execute().data
        
        if utenti:
            st.write("Come membro del direttivo, puoi aggiornare i ruoli del team o rimuovere account.")
            st.info("⚠️ Solo il Team Leader (TL) può degradare una persona a un ruolo inferiore.")
            
            ruoli_disponibili = ["Membro", "Division Leader", "CTO", "Team Leader"]
            punteggio_ruoli = {"Membro": 0, "Division Leader": 1, "CTO": 2, "Team Leader": 3}
            
            for u in utenti:
                if u['username'] != utente['username']:
                    with st.container():
                        col_info, col_ruolo, col_salva, col_elimina = st.columns([3, 2, 2, 1])
                        
                        col_info.write(f"**{u['nome']} {u['cognome']}** ({u['username']}) - {u['divisione']}")
                        nuovo_ruolo = col_ruolo.selectbox("Cambia ruolo", ruoli_disponibili, index=ruoli_disponibili.index(u['ruolo']), key=f"ruolo_{u['id']}")
                        
                        if col_salva.button("🔄 Aggiorna Ruolo", key=f"aggiorna_{u['id']}"):
                            is_downgrade = punteggio_ruoli[nuovo_ruolo] < punteggio_ruoli[u['ruolo']]
                            if is_downgrade and utente['ruolo'] != "Team Leader":
                                st.error("❌ Operazione negata: Solo il Team Leader può retrocedere di livello un utente.")
                            else:
                                supabase.table("membri").update({"ruolo": nuovo_ruolo}).eq("id", u['id']).execute()
                                st.success("Ruolo aggiornato con successo!")
                                st.rerun()
                                
                        if col_elimina.button("🗑️", key=f"elimina_{u['id']}", help="Elimina utente"):
                            supabase.table("membri").delete().eq("id", u['id']).execute()
                            st.warning("Utente eliminato!")
                            st.rerun()
                        st.divider()