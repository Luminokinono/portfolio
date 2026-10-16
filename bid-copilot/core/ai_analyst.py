"""Analyse d'un dossier de consultation (DCE).

Deux modes :
- Claude (si ANTHROPIC_API_KEY est défini) : extraction structurée en JSON ;
- hors-ligne : règles par mots-clés, pour que la démo marche sans clé ni réseau.
"""
import json
import os
import re
from typing import Literal

from pydantic import BaseModel, Field

MODEL = "claude-opus-5-5"


class Risque(BaseModel):
    titre: str
    categorie: Literal["Planning", "Contractuel", "Technique", "Financier", "Interfaces", "Administratif"]
    gravite: Literal["Critique", "Élevée", "Moyenne", "Faible"]
    extrait_dce: str = Field(description="Citation courte du DCE qui justifie le risque")
    mitigation: str


class Analyse(BaseModel):
    resume: str
    type_projet: str
    tension_kv: int
    nb_travees: int
    puissance_mva: int
    km_cable: float
    pays: str
    delai_exige_mois: int
    risques: list[Risque]
    donnees_manquantes: list[str]
    hypotheses_proposees: list[str]
    exclusions_proposees: list[str]
    questions_au_client: list[str]
    recommandation_go_nogo: str


SYSTEM = """Tu es ingénieur d'offres senior dans une entreprise de travaux électriques HTB \
(postes, liaisons souterraines, raccordements). Tu analyses un dossier de consultation pour \
préparer le Comité de Risque. Sois factuel : chaque risque doit citer un extrait du DCE. \
Repère en priorité : incohérences de planning (délais fournisseurs transformateurs de 24 à \
30 mois), pénalités non plafonnées, prix fermes sur longue durée, données d'entrée manquantes \
(sol, tracé, autorisations), transferts de responsabilité vers le titulaire. \
Les montants et quantités doivent venir du document ; s'ils sont absents, mets 0. \
Réponds en français."""


def analyse_with_claude(dce_text: str) -> Analyse:
    import anthropic  # noqa: PLC0415

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": _strict_schema(Analyse.model_json_schema())},
        },
        # Si le modèle refuse la requête, l'API bascule automatiquement sur un modèle de repli.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": f"Analyse ce dossier de consultation :\n\n<dce>\n{dce_text}\n</dce>"}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Le modèle a refusé la requête.")
    text = next(b.text for b in response.content if b.type == "text")
    return Analyse.model_validate(json.loads(text))


def _strict_schema(schema: dict) -> dict:
    """Ajoute additionalProperties=false et inline les $defs (exigé par le format JSON strict)."""
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(dict(defs[node["$ref"].split("/")[-1]]))
            node = {k: walk(v) for k, v in node.items() if k not in ("title", "default")}
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            return node
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(schema)


# --- Mode hors-ligne -------------------------------------------------------

def _find(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(0).strip(" -•*#:") if m else None


def _num(pattern: str, text: str, cast=float, default=0):
    m = re.search(pattern, text, re.IGNORECASE)
    return cast(m.group(1).replace(",", ".")) if m else default


def _type_projet(dce: str) -> str:
    t = dce.lower()
    if "data center" in t:
        return "Poste de raccordement data center"
    if re.search(r"solaire|photovolta|éolien", t):
        return "Raccordement EnR (solaire/éolien)"
    if "400 kv" in t or "interconnexion" in t:
        return "Interconnexion / poste 400 kV"
    return "Poste source / extension"


def analyse_offline(dce: str) -> Analyse:
    dce = re.sub(r"\s+", " ", dce)  # les PDF coupent les phrases en fin de ligne
    kv = _num(r"(\d{2,3})\s*/\s*\d+\s*kV", dce, int) or _num(r"(\d{2,3})\s*kV", dce, int)
    travees = _num(r"(\d+)\s*travées", dce, int)
    n_tr = _num(r"(\d+)\s*transformateurs?\b", dce, int, 1)
    mva_unit = _num(r"(\d+)\s*MVA", dce, int)
    mva_total = _num(r"soit\s*(\d+)\s*MVA", dce, int, n_tr * mva_unit)
    km = _num(r"(\d+(?:[.,]\d+)?)\s*km", dce)
    delai = _num(r"(\d+)\s*mois\*?\*?\s*après la notification", dce, int)

    risques, manquantes, hyp, excl, questions = [], [], [], [], []

    if mva_total and delai and delai < 24:
        risques.append(Risque(
            titre=f"Délai de {delai} mois incompatible avec la fabrication des transformateurs",
            categorie="Planning", gravite="Critique",
            extrait_dce=_find(r"[^.]*\d+\s*mois\*?\*?\s*après la notification[^.]*", dce) or "",
            mitigation="Proposer un planning à 28-30 mois ou un transformateur provisoire ; réserver un créneau usine dès la remise de l'offre."))
        hyp.append("Planning basé sur un délai de fabrication transformateur de 26 mois à compter de la commande.")
        questions.append(f"Le délai de {delai} mois peut-il être recalé sur un délai réaliste de fabrication transformateur ?")
    pen = _find(r"[^.]*pénalités[^.]*par jour[^.]*", dce)
    pen_bloc = _find(r"pénalités[^.]*\.", dce) or ""
    if pen and not re.search(r"plafon|limitées à|dans la limite", pen_bloc, re.IGNORECASE):
        risques.append(Risque(titre="Pénalités de retard non plafonnées", categorie="Contractuel", gravite="Critique",
                              extrait_dce=pen, mitigation="Demander un plafond global à 10 % du montant du marché."))
        questions.append("Les pénalités de retard peuvent-elles être plafonnées à 10 % du montant du marché ?")
    if re.search(r"fermes et non révisables|aucune\.?\s*les prix", dce, re.IGNORECASE):
        risques.append(Risque(titre=f"Prix fermes et non révisables sur {delai or 'plus de 18'} mois", categorie="Financier", gravite="Élevée",
                              extrait_dce=_find(r"[^.]*non révisables[^.]*", dce) or "",
                              mitigation="Indexer les câbles sur le LME cuivre ou figer les prix fournisseurs à la commande."))
    sol = r"(études? de sols?|études? géotechniques?)[^.]*(si nécessaire|à la charge du titulaire|non fournie|pas été réalisée)"
    if re.search(sol, dce, re.IGNORECASE):
        risques.append(Risque(titre="Aucune étude géotechnique fournie", categorie="Technique", gravite="Élevée",
                              extrait_dce=_find(r"[^.]*" + sol + r"[^.]*", dce) or "",
                              mitigation="Chiffrer sur hypothèse de sol standard ; fondations spéciales en option."))
        manquantes.append("Étude géotechnique (G2 AVP) du terrain du poste")
        questions.append("Une étude géotechnique (même partielle) est-elle disponible pour le terrain du poste ?")
        hyp.append("Sol de portance standard, sans fondations profondes ni pollution.")
        excl.append("Fondations spéciales, dépollution et rabattement de nappe")
    trace = r"tracé[^.]*(à confirmer|reste|non arrêté|pressenti)"
    if re.search(trace, dce, re.IGNORECASE):
        risques.append(Risque(titre="Tracé de la liaison souterraine non figé", categorie="Technique", gravite="Élevée",
                              extrait_dce=_find(r"[^.]*" + trace + r"[^.]*", dce) or "",
                              mitigation="Prix au mètre linéaire au-delà de la longueur de référence."))
        manquantes.append("Tracé définitif de la liaison et longueur exacte")
        questions.append("À quelle date le tracé définitif de la liaison sera-t-il arrêté ?")
        hyp.append(f"Longueur de liaison de {km} km ; variation facturée au mètre linéaire.")
    if re.search(r"autorisations[^.]*en cours", dce, re.IGNORECASE):
        risques.append(Risque(titre="Autorisations administratives non obtenues", categorie="Administratif", gravite="Élevée",
                              extrait_dce=_find(r"[^.]*autorisations administratives[^.]*", dce) or "",
                              mitigation="Faire démarrer le délai contractuel à l'obtention des autorisations."))
        manquantes.append("Calendrier d'obtention des autorisations (tracé, voirie)")
    if re.search(r"responsable de toute adaptation", dce, re.IGNORECASE):
        risques.append(Risque(titre="Transfert du risque d'accord de raccordement au titulaire", categorie="Interfaces", gravite="Élevée",
                              extrait_dce=_find(r"[^.]*responsable de toute adaptation[^.]*", dce) or "",
                              mitigation="Exclure les évolutions imposées par le gestionnaire de réseau après la remise de l'offre."))
        excl.append("Modifications imposées par le gestionnaire de réseau après la remise de l'offre")
    if re.search(r"consignations[^.]*titulaire", dce, re.IGNORECASE):
        risques.append(Risque(titre="Consignations réseau à la charge du titulaire", categorie="Planning", gravite="Moyenne",
                              extrait_dce=_find(r"[^.]*consignations[^.]*", dce) or "",
                              mitigation="Faire valider le planning de consignations par le gestionnaire de réseau avant signature."))
    if re.search(r"99[,.]99", dce):
        risques.append(Risque(titre="Garantie de disponibilité de 99,99 % sur 24 mois", categorie="Contractuel", gravite="Moyenne",
                              extrait_dce=_find(r"[^.\n]*99[,.]99[^.\n]*", dce) or "",
                              mitigation="Limiter la garantie au périmètre du titulaire et définir les cas exclus."))
    if re.search(r"Natura 2000|zone humide|espèces protégées", dce, re.IGNORECASE):
        risques.append(Risque(titre="Contraintes environnementales sur le tracé", categorie="Administratif", gravite="Élevée",
                              extrait_dce=_find(r"[^.]*(Natura 2000|zone humide|espèces protégées)[^.]*", dce) or "",
                              mitigation="Prévoir un écologue, des fenêtres de travaux hors nidification et un forage dirigé en option."))
        hyp.append("Travaux en zone sensible réalisés hors période de nidification (septembre à février).")
        excl.append("Mesures compensatoires environnementales et suivi écologique post-travaux")
        questions.append("Les prescriptions environnementales (périodes de travaux, forage dirigé) sont-elles déjà connues ?")
    if re.search(r"garantie à première demande", dce, re.IGNORECASE):
        risques.append(Risque(titre="Garantie à première demande exigée", categorie="Financier", gravite="Moyenne",
                              extrait_dce=_find(r"[^.]*garantie à première demande[^.]*", dce) or "",
                              mitigation="Négocier une caution bancaire classique ou réduire le montant garanti."))
    if re.search(r"extension future", dce, re.IGNORECASE):
        manquantes.append("Périmètre exact des réservations pour l'extension à 4 transformateurs")
        questions.append("Quelles réservations sont attendues pour l'extension future (génie civil seul, ou travées équipées) ?")
    excl += ["Travaux dans le poste RTE existant", "Frais de raccordement facturés par le gestionnaire de réseau"]

    critiques = sum(r.gravite == "Critique" for r in risques)
    reco = ("GO SOUS CONDITIONS : " if critiques else "GO : ") + (
        f"{critiques} risque(s) critique(s) à lever par réserves ou questions avant la remise." if critiques
        else "pas de point bloquant détecté.")

    return Analyse(
        resume=f"Poste {kv} kV de {travees} travées, {mva_total} MVA, liaison souterraine de {km} km, "
               + (f"délai exigé de {delai} mois. " if delai else "délai non précisé. ")
               + ("Contrat à prix ferme et non révisable." if re.search(r"non révisables", dce, re.I) else "Prix révisables."),
        type_projet=_type_projet(dce),
        tension_kv=kv, nb_travees=travees, puissance_mva=mva_total, km_cable=km, pays="France",
        delai_exige_mois=delai, risques=risques, donnees_manquantes=manquantes,
        hypotheses_proposees=hyp, exclusions_proposees=excl, questions_au_client=questions,
        recommandation_go_nogo=reco)


def analyse(dce_text: str) -> tuple[Analyse, str]:
    """Retourne (analyse, mode). Bascule en hors-ligne si Claude n'est pas disponible."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return analyse_with_claude(dce_text), "Claude"
        except Exception as e:  # démo : on ne bloque jamais
            return analyse_offline(dce_text), f"hors-ligne (erreur API : {type(e).__name__})"
    return analyse_offline(dce_text), "hors-ligne (règles)"
