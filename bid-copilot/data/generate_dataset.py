"""Génère une base synthétique de projets HTB réalisés.

Les coûts unitaires sont des ORDRES DE GRANDEUR indicatifs, à recaler sur des
sources publiques (annexes « coûts » des S3REnR de RTE, rapports CRE) avant
toute utilisation sérieuse. Le but est d'avoir une base plausible pour la démo,
pas de produire des prix réels.
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_PROJECTS = 48
OUT = Path(__file__).parent / "projects.csv"

# Coûts unitaires de référence (k€), par niveau de tension
TRAVEE_KEUR = {63: 900, 90: 1100, 150: 1600, 225: 2200, 400: 3800}
CABLE_KM_KEUR = {63: 1300, 90: 1600, 150: 2400, 225: 3600, 400: 6500}
TRANSFO_KEUR_PAR_MVA = 22
GC_PAR_TRAVEE_KEUR = 450

PROJECT_TYPES = {
    "Poste de raccordement data center": dict(tensions=[63, 90, 225], travees=(4, 10), mva=(80, 400), km=(0.5, 6)),
    "Poste source / extension": dict(tensions=[63, 90, 225], travees=(2, 6), mva=(0, 170), km=(0, 1.5)),
    "Raccordement EnR (solaire/éolien)": dict(tensions=[63, 90, 225], travees=(2, 5), mva=(60, 300), km=(3, 25)),
    "Liaison souterraine HTB": dict(tensions=[63, 90, 225], travees=(2, 4), mva=(0, 0), km=(4, 30)),
    "Interconnexion / poste 400 kV": dict(tensions=[400], travees=(4, 12), mva=(0, 600), km=(0, 10)),
    "Électrification site industriel": dict(tensions=[63, 90, 150], travees=(3, 8), mva=(40, 240), km=(0.5, 8)),
}

PAYS = [("France", 1.00, 0.70), ("Belgique", 1.05, 0.08), ("Maroc", 0.85, 0.07),
        ("Royaume-Uni", 1.20, 0.08), ("Arabie saoudite", 1.10, 0.07)]

RISQUES_TYPES = [
    "Retard livraison transformateur",
    "Sous-estimation génie civil (nature du sol)",
    "Interfaces client tardives",
    "Hausse prix cuivre / câbles",
    "Indisponibilité consignations réseau",
    "Productivité chantier inférieure au prévu",
    "Évolution de périmètre non chiffrée",
    "Pénalités de retard appliquées",
]
REX_PAR_RISQUE = {
    "Retard livraison transformateur": "Commander le transformateur dès la notification ; prévoir 24-30 mois.",
    "Sous-estimation génie civil (nature du sol)": "Exiger une étude géotechnique G2 avant remise de prix.",
    "Interfaces client tardives": "Contractualiser une date limite de gel des données d'entrée.",
    "Hausse prix cuivre / câbles": "Indexer les câbles sur le LME cuivre ou obtenir un prix ferme fournisseur.",
    "Indisponibilité consignations réseau": "Faire valider le planning de consignations par le gestionnaire de réseau.",
    "Productivité chantier inférieure au prévu": "Appliquer un coefficient de productivité de 0,85 sur sites contraints.",
    "Évolution de périmètre non chiffrée": "Lister les exclusions de façon exhaustive dans l'offre.",
    "Pénalités de retard appliquées": "Plafonner les pénalités à 10 % du montant du contrat.",
}


def tension_class(kv: int) -> str:
    return f"{kv} kV"


def generate(seed: int = SEED, n: int = N_PROJECTS) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    pays_names = [p[0] for p in PAYS]
    pays_coef = {p[0]: p[1] for p in PAYS}
    pays_prob = np.array([p[2] for p in PAYS])
    pays_prob = pays_prob / pays_prob.sum()
    types = list(PROJECT_TYPES)

    rows = []
    for i in range(n):
        ptype = types[i % len(types)] if i < len(types) else rng.choice(types)
        spec = PROJECT_TYPES[ptype]
        kv = int(rng.choice(spec["tensions"]))
        travees = int(rng.integers(spec["travees"][0], spec["travees"][1] + 1))
        mva = 0 if spec["mva"][1] == 0 else int(round(rng.uniform(*spec["mva"]) / 10) * 10)
        km = round(float(rng.uniform(*spec["km"])), 1)
        pays = str(rng.choice(pays_names, p=pays_prob))
        annee = int(rng.integers(2018, 2026))
        coef = pays_coef[pays] * (1 + 0.04 * (annee - 2018))  # inflation simple

        noise = lambda: float(rng.lognormal(0, 0.12))  # noqa: E731
        cout_postes = TRAVEE_KEUR[kv] * travees * coef * noise()
        cout_transfo = TRANSFO_KEUR_PAR_MVA * mva * coef * noise()
        cout_cables = CABLE_KM_KEUR[kv] * km * coef * noise()
        cout_gc = GC_PAR_TRAVEE_KEUR * travees * coef * noise() * (1.4 if rng.random() < 0.15 else 1.0)
        directs = cout_postes + cout_transfo + cout_cables + cout_gc
        cout_ing = directs * rng.uniform(0.07, 0.12)
        total = directs + cout_ing

        heures_ing = int(cout_ing * 1000 / rng.uniform(85, 105))
        heures_chantier = int((cout_postes + cout_gc) * 1000 * rng.uniform(0.25, 0.35) / 65)
        delai_transfo = int(rng.integers(14, 32)) if mva else 0
        duree = int(max(12, delai_transfo + rng.integers(4, 10), 10 + travees * 1.5 + km * 0.4))
        retard = int(max(0, rng.normal(1.5, 3)))

        n_risques = int(rng.integers(1, 4))
        risques = list(rng.choice(RISQUES_TYPES, size=n_risques, replace=False))
        if delai_transfo > 24 and "Retard livraison transformateur" not in risques:
            risques[0] = "Retard livraison transformateur"
        marge_prevue = rng.uniform(0.07, 0.12)
        derive = sum(rng.uniform(0.005, 0.025) for _ in risques)
        marge_reelle = marge_prevue - derive

        rows.append(dict(
            id=f"OMX-{annee}-{i + 1:03d}",
            nom=f"{ptype} – {pays} #{i + 1}",
            type_projet=ptype,
            pays=pays,
            annee=annee,
            tension_kv=kv,
            nb_travees=travees,
            puissance_mva=mva,
            km_cable=km,
            cout_postes_keur=round(cout_postes),
            cout_transfo_keur=round(cout_transfo),
            cout_cables_keur=round(cout_cables),
            cout_genie_civil_keur=round(cout_gc),
            cout_ingenierie_keur=round(cout_ing),
            cout_total_keur=round(total),
            heures_ingenierie=heures_ing,
            heures_chantier=heures_chantier,
            delai_transfo_mois=delai_transfo,
            duree_mois=duree,
            retard_mois=retard,
            marge_prevue_pct=round(marge_prevue * 100, 1),
            marge_reelle_pct=round(marge_reelle * 100, 1),
            risques_survenus="; ".join(risques),
            rex="; ".join(REX_PAR_RISQUE[r] for r in risques),
        ))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate()
    df.to_csv(OUT, index=False)
    print(f"{len(df)} projets écrits dans {OUT}")
