"""Bid Copilot – démonstrateur pour une Cellule Offres HTB.

Lancer :  streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import ai_analyst, estimator as E
from core.risk_deck import build_deck

ROOT = Path(__file__).parent
st.set_page_config(page_title="Bid Copilot", page_icon="⚡", layout="wide")


@st.cache_data
def load():
    return E.load_projects()


def meur(v):
    return f"{v / 1000:,.1f} M€".replace(",", " ")


df = load()
st.title("⚡ Bid Copilot")
st.caption("Démonstrateur : de la réception d'un appel d'offres à la présentation en Comité de Risque. "
           "Données 100 % synthétiques, ordres de grandeur indicatifs.")

tab_ao, tab_cost, tab_risk, tab_deck, tab_data = st.tabs(
    ["1 · Analyse de l'appel d'offres", "2 · Cost Estimator", "3 · Risques & Monte Carlo", "4 · Comité de Risque", "Base de projets"])

# --- 1. Analyse de l'appel d'offres ------------------------------------------
with tab_ao:
    st.subheader("Analyse automatique du dossier de consultation")
    api_key = st.text_input(
        "Clé API Anthropic (optionnelle)", type="password",
        help="Avec une clé, l'IA lit le dossier et l'analyse quel qu'il soit. Sans clé, l'outil utilise "
             "des règles par mots-clés, limitées aux cas prévus. La clé reste dans votre navigateur.")
    ups = st.file_uploader("Déposer les pièces du DCE (RC, CCAP, CCTP… en .pdf, .txt ou .md)",
                           type=["md", "txt", "pdf"], accept_multiple_files=True)
    if ups:
        from pypdf import PdfReader
        pieces = []
        for up in ups:
            if up.name.lower().endswith(".pdf"):
                txt = "\n".join(p.extract_text() or "" for p in PdfReader(up).pages)
            else:
                txt = up.read().decode("utf-8", errors="replace")
            pieces.append(f"===== PIÈCE : {up.name} =====\n{txt}")
        dce = "\n\n".join(pieces)
        if len(dce.strip()) < 200 * len(ups):
            st.warning("Peu de texte extrait : un PDF scanné (image) ne peut pas être lu sans OCR.")
    else:
        dce = (ROOT / "data" / "dce_demo_datacenter.txt").read_text(encoding="utf-8")
        st.info("Aucun fichier déposé : utilisation du DCE de démonstration (raccordement 225 kV d'un data center).")
    with st.expander(f"Voir le texte du DCE ({len(dce):,} caractères)".replace(",", " ")):
        st.text(dce[:20000] + ("\n[…]" if len(dce) > 20000 else ""))

    if st.button("🔍 Analyser le DCE", type="primary") or "analyse" in st.session_state:
        cle = (dce, api_key)
        if "analyse" not in st.session_state or st.session_state.get("cle") != cle:
            with st.spinner("Analyse en cours… (30 s à 2 min avec l'IA)" if api_key else "Analyse en cours…"):
                st.session_state.analyse, st.session_state.mode = ai_analyst.analyse(dce, api_key or None)
                st.session_state.cle = cle
        a = st.session_state.analyse
        (st.caption if st.session_state.mode.startswith("IA") else st.warning)(f"Mode d'analyse : {st.session_state.mode}")
        st.success(a.resume)
        st.markdown(f"**Recommandation :** {a.recommandation_go_nogo}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tension", f"{a.tension_kv} kV"); c2.metric("Travées", a.nb_travees)
        c3.metric("Puissance", f"{a.puissance_mva} MVA"); c4.metric("Câble", f"{a.km_cable} km")

        st.markdown("#### Risques détectés")
        st.dataframe(pd.DataFrame([r.model_dump() for r in a.risques]), width="stretch", hide_index=True)
        c1, c2 = st.columns(2)
        c1.markdown("#### Données manquantes"); c1.markdown("\n".join(f"- {x}" for x in a.donnees_manquantes))
        c1.markdown("#### Questions au client"); c1.markdown("\n".join(f"- {x}" for x in a.questions_au_client))
        c2.markdown("#### Hypothèses proposées"); c2.markdown("\n".join(f"- {x}" for x in a.hypotheses_proposees))
        c2.markdown("#### Exclusions proposées"); c2.markdown("\n".join(f"- {x}" for x in a.exclusions_proposees))
        c2.markdown("#### Opportunités"); c2.markdown("\n".join(f"- {x}" for x in a.opportunites))

# --- Paramètres du projet (pré-remplis par l'analyse) -------------------------
a = st.session_state.get("analyse")
with st.sidebar:
    st.header("Projet à chiffrer")
    st.caption("Pré-rempli par l'analyse du DCE, modifiable.")
    types = sorted(df["type_projet"].unique())
    ptype = st.selectbox("Type", types, index=types.index(a.type_projet) if a and a.type_projet in types else 0)
    pays_list = list(E.PAYS_COEF)
    pays = st.selectbox("Pays", pays_list, index=pays_list.index(a.pays) if a and a.pays in pays_list else 0)
    tensions = sorted(df["tension_kv"].unique().tolist())
    # Tension de référence la plus proche de celle du dossier
    kv_idx = min(range(len(tensions)), key=lambda i: abs(tensions[i] - a.tension_kv)) if a and a.tension_kv else 0
    kv = st.selectbox("Tension (kV)", tensions, index=kv_idx)
    trav = st.number_input("Nombre de travées", 1, 40, min(max(a.nb_travees, 1), 40) if a else 6)
    mva = st.number_input("Puissance transformateurs (MVA)", 0, 3000, min(max(a.puissance_mva, 0), 3000) if a else 240, step=10)
    km = st.number_input("Longueur de câble (km)", 0.0, 300.0, min(max(float(a.km_cable), 0.0), 300.0) if a else 4.5, step=0.5)
    marge = st.slider("Marge visée (%)", 5, 20, 10)

proj = E.ProjectInput(ptype, pays, int(kv), int(trav), int(mva), float(km))
est = E.estimate(proj, df)
sim = E.similar_projects(proj, df)

# --- 2. Cost Estimator -------------------------------------------------------
with tab_cost:
    st.subheader("Premier budget par ratios des projets de référence")
    c1, c2, c3 = st.columns(3)
    c1.metric("Budget de base", meur(est["estimation"].sum()))
    c2.metric("Fourchette basse (P25)", meur(est["bas"].sum()))
    c3.metric("Fourchette haute (P75)", meur(est["haut"].sum()))
    show = est.assign(**{c: est[c].round(0) for c in ["ratio", "bas", "estimation", "haut"]})
    st.dataframe(show.drop(columns="poste").rename(columns={"estimation": "estimation (k€)", "bas": "bas (k€)", "haut": "haut (k€)"}),
                 width="stretch", hide_index=True)

    st.markdown("#### Projets similaires")
    st.dataframe(sim[["id", "nom", "tension_kv", "nb_travees", "puissance_mva", "km_cable", "cout_total_keur",
                      "retard_mois", "marge_prevue_pct", "marge_reelle_pct", "similarite_pct"]],
                 width="stretch", hide_index=True)
    for _, r in sim.iterrows():
        st.markdown(f"**{r['id']}** – risques survenus : *{r['risques_survenus']}*  \n↳ Retour d'expérience : {r['rex']}")

    st.markdown("#### Contrôle de cohérence d'un chiffrage")
    st.caption("Exemple : chiffrage saisi par un chargé d'offres, avec une erreur volontaire sur les câbles.")
    default = {p: v for p, v in zip(est["poste"], est["estimation"])}
    default["cables"] *= 0.55
    edited = st.data_editor(pd.DataFrame({"poste": est["libelle"], "code": est["poste"],
                                          "chiffrage (k€)": [round(default[p]) for p in est["poste"]]}),
                            column_config={"code": None}, hide_index=True, width="stretch")
    st.dataframe(E.check_consistency(dict(zip(edited["code"], edited["chiffrage (k€)"])), est),
                 width="stretch", hide_index=True)

# --- 3. Risques & Monte Carlo ------------------------------------------------
drivers = E.default_drivers(proj)
sims = E.monte_carlo(est, drivers)
stats = E.summary(sims, est)
with tab_risk:
    st.subheader("Analyse de sensibilité et Monte Carlo (10 000 tirages)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Coût de base", meur(stats["base"])); c2.metric("P50", meur(stats["p50"]))
    c3.metric("P80", meur(stats["p80"])); c4.metric("Provision pour risques", meur(stats["provision_risques"]))
    st.caption(f"Probabilité de dépasser le coût de base : {stats['proba_depassement_base'] * 100:.0f} %")

    fig = px.histogram(x=sims / 1000, nbins=50, labels={"x": "Coût total (M€)"})
    for k, col in [("base", "grey"), ("p50", "#008CC8"), ("p80", "#E67E22")]:
        fig.add_vline(x=stats[k] / 1000, line_color=col, annotation_text=k.upper())
    fig.update_layout(showlegend=False, yaxis_title="Nombre de tirages", height=380)
    st.plotly_chart(fig, width="stretch")

    t = E.tornado(est, drivers)
    fig2 = go.Figure()
    fig2.add_bar(y=t["driver"], x=t["impact_bas"] / 1000, orientation="h", name="Scénario bas", marker_color="#27AE60")
    fig2.add_bar(y=t["driver"], x=t["impact_haut"] / 1000, orientation="h", name="Scénario haut", marker_color="#C0392B")
    fig2.update_layout(barmode="overlay", title="Tornado : impact de chaque facteur sur le coût (M€)", height=380)
    st.plotly_chart(fig2, width="stretch")
    st.dataframe(pd.DataFrame([E.to_dict(d) for d in drivers]), width="stretch", hide_index=True)

# --- 4. Comité de Risque -----------------------------------------------------
with tab_deck:
    st.subheader("Génération de la présentation du Comité de Risque")
    if a is None:
        st.warning("Lance d'abord l'analyse du DCE (onglet 1).")
    else:
        phases = E.planning(proj)
        gantt = pd.DataFrame(phases)
        fig3 = px.bar(gantt, x="duree", y="phase", base="debut", orientation="h", labels={"duree": "Mois"})
        if a.delai_exige_mois:
            fig3.add_vline(x=a.delai_exige_mois, line_color="red", annotation_text=f"Délai client : {a.delai_exige_mois} mois")
        fig3.update_layout(height=320, yaxis={"autorange": "reversed"})
        st.plotly_chart(fig3, width="stretch")

        client = st.text_input("Client", "Hyperion Data Campus (fictif)")
        remise = st.text_input("Date de remise", "15 mars 2027")
        if st.button("📊 Générer le .pptx", type="primary"):
            pptx = build_deck(dict(nom=f"Offre {ptype} {kv} kV", client=client, date_remise=remise,
                                   opportunites=a.opportunites),
                              a, est, stats, sims, phases, sim, marge)
            st.download_button("⬇️ Télécharger la présentation", pptx, "comite_de_risque.pptx",
                               "application/vnd.openxmlformats-officedocument.presentationml.presentation")

# --- Base de projets ---------------------------------------------------------
with tab_data:
    st.subheader(f"Base de connaissance : {len(df)} projets réalisés (synthétiques)")
    st.dataframe(df, width="stretch", hide_index=True)
    st.plotly_chart(px.scatter(df, x="nb_travees", y="cout_total_keur", color="tension_kv", symbol="type_projet",
                               hover_name="nom", labels={"cout_total_keur": "Coût total (k€)"}), width="stretch")
    st.plotly_chart(px.box(df, x="type_projet", y=df["marge_prevue_pct"] - df["marge_reelle_pct"],
                           labels={"y": "Érosion de marge (points)"}, title="Érosion de marge par type de projet"),
                    width="stretch")
