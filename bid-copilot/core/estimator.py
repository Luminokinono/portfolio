"""Cost Estimator : ratios issus des références, projets similaires,
contrôle de cohérence, Monte Carlo et sensibilité."""
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "projects.csv"

POSTES = ["postes", "transfo", "cables", "genie_civil", "ingenierie"]
LIBELLES = {
    "postes": "Équipements postes (travées)",
    "transfo": "Transformateurs",
    "cables": "Câbles / liaisons",
    "genie_civil": "Génie civil",
    "ingenierie": "Ingénierie & études",
}
PAYS_COEF = {"France": 1.00, "Belgique": 1.05, "Maroc": 0.85, "Royaume-Uni": 1.20, "Arabie saoudite": 1.10}


@dataclass
class ProjectInput:
    type_projet: str
    pays: str
    tension_kv: int
    nb_travees: int
    puissance_mva: int
    km_cable: float
    annee: int = 2026


def load_projects(path: Path = DATA) -> pd.DataFrame:
    if not path.exists():
        from data.generate_dataset import generate  # noqa: PLC0415
        generate().to_csv(path, index=False)
    return pd.read_csv(path)


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Ramène les coûts historiques en euros France 2026 (pays + inflation)."""
    out = df.copy()
    coef = out["pays"].map(PAYS_COEF) * (1 + 0.04 * (out["annee"] - 2018))
    target = 1 + 0.04 * (2026 - 2018)
    for p in POSTES:
        out[f"cout_{p}_keur"] = out[f"cout_{p}_keur"] / coef * target
    out["cout_total_keur"] = out[[f"cout_{p}_keur" for p in POSTES]].sum(axis=1)
    return out


def unit_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Ratios unitaires (k€ France 2026) : médiane, P25, P75 par tension."""
    n = _normalise(df)
    rows = []
    for kv, g in n.groupby("tension_kv"):
        series = {
            "postes": g["cout_postes_keur"] / g["nb_travees"],
            "genie_civil": g["cout_genie_civil_keur"] / g["nb_travees"],
            "cables": (g["cout_cables_keur"] / g["km_cable"])[g["km_cable"] > 0],
        }
        for p, s in series.items():
            rows.append(dict(tension_kv=kv, poste=p, p25=s.quantile(.25), mediane=s.median(), p75=s.quantile(.75), n=len(s)))
    tr = n[n["puissance_mva"] > 0]
    tr_ratio = tr["cout_transfo_keur"] / tr["puissance_mva"]
    ing_ratio = n["cout_ingenierie_keur"] / n[[f"cout_{p}_keur" for p in POSTES[:-1]]].sum(axis=1)
    for kv in sorted(n["tension_kv"].unique()):
        rows.append(dict(tension_kv=kv, poste="transfo", p25=tr_ratio.quantile(.25), mediane=tr_ratio.median(), p75=tr_ratio.quantile(.75), n=len(tr_ratio)))
        rows.append(dict(tension_kv=kv, poste="ingenierie", p25=ing_ratio.quantile(.25), mediane=ing_ratio.median(), p75=ing_ratio.quantile(.75), n=len(ing_ratio)))
    return pd.DataFrame(rows)


def _quantities(p: ProjectInput) -> dict:
    return {"postes": p.nb_travees, "genie_civil": p.nb_travees, "cables": p.km_cable, "transfo": p.puissance_mva}


UNITES = {"postes": "k€/travée", "genie_civil": "k€/travée", "cables": "k€/km", "transfo": "k€/MVA", "ingenierie": "% des directs"}


def estimate(p: ProjectInput, df: pd.DataFrame) -> pd.DataFrame:
    """Budget ligne à ligne = quantité × ratio médian × coefficient pays."""
    r = unit_ratios(df)
    r = r[r["tension_kv"] == p.tension_kv].set_index("poste")
    coef = PAYS_COEF.get(p.pays, 1.0) * (1 + 0.04 * (p.annee - 2026))
    q = _quantities(p)
    lines = []
    for poste in POSTES[:-1]:
        ratio = r.loc[poste]
        lines.append(dict(poste=poste, libelle=LIBELLES[poste], quantite=q[poste], unite=UNITES[poste],
                          ratio=ratio.mediane, bas=q[poste] * ratio.p25 * coef,
                          estimation=q[poste] * ratio.mediane * coef, haut=q[poste] * ratio.p75 * coef))
    directs = sum(l["estimation"] for l in lines)
    ing = r.loc["ingenierie"]
    lines.append(dict(poste="ingenierie", libelle=LIBELLES["ingenierie"], quantite=1, unite=UNITES["ingenierie"],
                      ratio=ing.mediane, bas=directs * ing.p25, estimation=directs * ing.mediane, haut=directs * ing.p75))
    return pd.DataFrame(lines)


def similar_projects(p: ProjectInput, df: pd.DataFrame, k: int = 3) -> pd.DataFrame:
    """k plus proches voisins sur les caractéristiques techniques normalisées."""
    feats = ["tension_kv", "nb_travees", "puissance_mva", "km_cable"]
    X = df[feats].astype(float)
    mu, sd = X.mean(), X.std().replace(0, 1)
    Z = (X - mu) / sd
    z = (pd.Series({f: float(getattr(p, f)) for f in feats}) - mu) / sd
    dist = np.sqrt(((Z - z) ** 2).sum(axis=1))
    dist = dist + np.where(df["type_projet"] == p.type_projet, 0, 1.0)
    out = df.assign(distance=dist).nsmallest(k, "distance").copy()
    out["similarite_pct"] = (100 / (1 + out["distance"])).round(0)
    return out


def check_consistency(proposed: dict, est: pd.DataFrame, tolerance: float = 0.15) -> pd.DataFrame:
    """Compare un chiffrage proposé à la fourchette P25-P75 des références."""
    rows = []
    for _, l in est.iterrows():
        val = proposed.get(l["poste"], l["estimation"])
        if val < l["bas"] * (1 - tolerance):
            statut, msg = "🔴 Sous-estimé", f"{(1 - val / l['estimation']) * 100:.0f} % sous la médiane des références"
        elif val > l["haut"] * (1 + tolerance):
            statut, msg = "🟠 Sur-estimé", f"{(val / l['estimation'] - 1) * 100:.0f} % au-dessus de la médiane"
        else:
            statut, msg = "🟢 Cohérent", "Dans la fourchette des références"
        rows.append(dict(poste=l["libelle"], propose_keur=round(val), reference_keur=round(l["estimation"]),
                         fourchette=f"{l['bas']:,.0f} – {l['haut']:,.0f}".replace(",", " "), statut=statut, commentaire=msg))
    return pd.DataFrame(rows)


# --- Risques chiffrés -------------------------------------------------------

@dataclass
class RiskDriver:
    nom: str
    bas: float      # multiplicateur ou montant bas
    mode: float
    haut: float
    cible: str      # poste impacté, ou "total"
    description: str


def default_drivers(p: ProjectInput) -> list[RiskDriver]:
    d = [
        RiskDriver("Prix cuivre / câbles", 0.92, 1.0, 1.25, "cables", "Volatilité LME cuivre sur la durée du projet"),
        RiskDriver("Productivité chantier", 0.95, 1.0, 1.20, "genie_civil", "Site contraint, météo, coactivité"),
        RiskDriver("Nature du sol (génie civil)", 1.0, 1.05, 1.40, "genie_civil", "Absence d'étude géotechnique G2"),
        RiskDriver("Prix équipements HTB", 0.95, 1.0, 1.12, "postes", "Tension sur le marché des appareillages"),
        RiskDriver("Heures d'ingénierie", 0.9, 1.0, 1.25, "ingenierie", "Données d'entrée client tardives"),
    ]
    if p.puissance_mva:
        d.append(RiskDriver("Retard transformateur (pénalités)", 0.0, 0.0, 0.06, "total",
                            "Délai fournisseur 24-30 mois ; pénalités en % du contrat"))
    return d


def monte_carlo(est: pd.DataFrame, drivers: list[RiskDriver], n: int = 10_000, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = est.set_index("poste")["estimation"]
    sims = {poste: np.full(n, v) for poste, v in base.items()}
    total_extra = np.zeros(n)
    for d in drivers:
        draw = rng.triangular(d.bas, d.mode, d.haut, n) if d.haut > d.bas else np.full(n, d.mode)
        if d.cible == "total":
            total_extra += draw  # fraction du total
        else:
            sims[d.cible] = sims[d.cible] * draw
    total = sum(sims.values())
    return total * (1 + total_extra)


def tornado(est: pd.DataFrame, drivers: list[RiskDriver]) -> pd.DataFrame:
    base = est.set_index("poste")["estimation"]
    base_total = base.sum()
    rows = []
    for d in drivers:
        if d.cible == "total":
            lo, hi = base_total * d.bas, base_total * d.haut
        else:
            lo = base[d.cible] * (d.bas - d.mode)
            hi = base[d.cible] * (d.haut - d.mode)
        rows.append(dict(driver=d.nom, impact_bas=lo, impact_haut=hi, amplitude=hi - lo))
    return pd.DataFrame(rows).sort_values("amplitude")


def summary(sims: np.ndarray, est: pd.DataFrame) -> dict:
    base = est["estimation"].sum()
    p50, p80, p90 = np.percentile(sims, [50, 80, 90])
    return dict(base=base, p50=p50, p80=p80, p90=p90, provision_risques=p80 - base,
                proba_depassement_base=float((sims > base).mean()))


def planning(p: ProjectInput, delai_transfo: int = 26) -> list[dict]:
    """Planning macro indicatif (mois depuis la notification)."""
    etudes = 6 + (2 if p.tension_kv >= 225 else 0)
    gc_start, gc_dur = etudes - 1, 5 + p.nb_travees // 2
    montage_start = gc_start + gc_dur - 1
    montage_dur = 4 + p.nb_travees // 2
    phases = [
        dict(phase="Études & approvisionnements", debut=0, duree=etudes),
        dict(phase="Génie civil", debut=gc_start, duree=gc_dur),
        dict(phase="Montage électromécanique", debut=montage_start, duree=montage_dur),
    ]
    if p.km_cable:
        phases.append(dict(phase="Pose des câbles", debut=gc_start + 1, duree=max(3, int(p.km_cable * 0.8))))
    if p.puissance_mva:
        phases.insert(1, dict(phase="Fabrication transformateur", debut=1, duree=delai_transfo))
    fin = max(ph["debut"] + ph["duree"] for ph in phases)
    phases.append(dict(phase="Essais & mise en service", debut=fin, duree=3))
    return phases


def to_dict(obj) -> dict:
    return asdict(obj)
