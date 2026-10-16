"""Analyse d'un dossier de consultation (DCE).

Deux modes :
- Claude (avec une clé API) : lecture du dossier par l'IA et extraction structurée
  en JSON. Fonctionne sur n'importe quel dossier, en local comme dans le navigateur ;
- hors-ligne : règles par mots-clés, pour que la démo marche sans clé ni réseau.
"""
import json
import os
import re
import sys
from typing import Literal

from pydantic import BaseModel, Field

MODEL = "claude-opus-5-5"
API_URL = "https://api.anthropic.com/v1/messages"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_CHARS = 2_000_000  # ~500 000 tokens, largement sous la fenêtre de contexte

TYPES_PROJET = (
    "Poste de raccordement data center",
    "Poste source / extension",
    "Raccordement EnR (solaire/éolien)",
    "Liaison souterraine HTB",
    "Interconnexion / poste 400 kV",
    "Électrification site industriel",
)


class Risque(BaseModel):
    titre: str
    categorie: Literal["Planning", "Contractuel", "Technique", "Financier", "Interfaces", "Administratif"]
    gravite: Literal["Critique", "Élevée", "Moyenne", "Faible"]
    extrait_dce: str = Field(description="Citation courte et exacte du DCE qui justifie le risque")
    mitigation: str


class Analyse(BaseModel):
    resume: str
    type_projet: Literal[TYPES_PROJET]  # type: ignore[valid-type]
    tension_kv: int = Field(description="Tension la plus élevée des ouvrages, en kV ; 0 si absente")
    nb_travees: int = Field(description="Nombre de travées HTB du poste ; 0 si absent")
    puissance_mva: int = Field(description="Puissance totale de transformation installée, en MVA ; 0 si absente")
    km_cable: float = Field(description="Longueur totale de liaison à construire, en km ; 0 si absente")
    pays: str
    delai_exige_mois: int = Field(description="Délai de mise en service exigé, en mois après notification ; 0 si absent")
    risques: list[Risque]
    donnees_manquantes: list[str]
    hypotheses_proposees: list[str]
    exclusions_proposees: list[str]
    questions_au_client: list[str]
    opportunites: list[str] = Field(description="Opportunités commerciales ou techniques pour le titulaire")
    recommandation_go_nogo: str = Field(description="Commence par GO, GO SOUS CONDITIONS ou NO GO, puis une phrase de justification")


SYSTEM = """Tu es ingénieur d'offres senior dans une entreprise de travaux électriques HTB \
(postes, liaisons souterraines et aériennes, raccordements). Tu analyses un dossier de \
consultation, qui peut comporter plusieurs pièces (règlement de consultation, CCAP, CCTP, \
bordereau de prix…), pour préparer le Comité de Risque qui décidera de répondre ou non.

Sois factuel : chaque risque cite un extrait exact du dossier. Classe la gravité selon \
l'impact potentiel sur la marge et le délai. Regarde en particulier :
- le planning, comparé aux délais réels des fournisseurs (transformateurs de puissance : \
24 à 30 mois ; appareillage HTB : 12 à 18 mois) ;
- les pénalités (plafond, assiette, cumul), les garanties, la révision des prix ;
- les données d'entrée manquantes (sol, tracé, autorisations, interfaces) ;
- les transferts de responsabilité vers le titulaire et les exigences de performance.

Ne signale pas une clause bien encadrée (pénalités plafonnées, prix révisables…) comme un \
risque. Les quantités viennent du document ; si une donnée est absente, mets 0. \
Réponds en français."""


def _request(dce_text: str) -> dict:
    return {
        "model": MODEL,
        "max_tokens": 16000,
        "system": SYSTEM,
        "thinking": {"type": "adaptive"},
        "output_config": {
            "effort": "medium",
            "format": {"type": "json_schema", "schema": _strict_schema(Analyse.model_json_schema())},
        },
        # Si le modèle refuse la requête, l'API la relance sur un modèle de repli.
        "fallbacks": "default",
        "messages": [{"role": "user", "content": f"Analyse ce dossier de consultation :\n\n<dce>\n{dce_text}\n</dce>"}],
    }


def _post_from_browser(body: dict, api_key: str, fallback: bool) -> dict:
    """Appel HTTP depuis le navigateur (stlite/Pyodide), où le SDK Python ne peut pas tourner.

    Le code Python de stlite s'exécute dans un web worker, où une requête synchrone est permise.
    """
    from js import XMLHttpRequest  # noqa: PLC0415

    xhr = XMLHttpRequest.new()
    xhr.open("POST", API_URL, False)
    headers = {
        "content-type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true",
    }
    if fallback:
        headers["anthropic-beta"] = FALLBACK_BETA
    for k, v in headers.items():
        xhr.setRequestHeader(k, v)
    xhr.send(json.dumps(body))
    if xhr.status != 200:
        raise RuntimeError(f"API {xhr.status} : {str(xhr.responseText)[:300]}")
    return json.loads(xhr.responseText)


def _call(body: dict, api_key: str, fallback: bool) -> tuple[str | None, list[str]]:
    if sys.platform == "emscripten":
        data = _post_from_browser(body, api_key, fallback)
        return data.get("stop_reason"), [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    import anthropic  # noqa: PLC0415

    client = anthropic.Anthropic(api_key=api_key)
    response = client.beta.messages.create(betas=[FALLBACK_BETA], **body) if fallback else client.messages.create(**body)
    return response.stop_reason, [b.text for b in response.content if b.type == "text"]


def analyse_with_claude(dce_text: str, api_key: str) -> Analyse:
    if len(dce_text) > MAX_CHARS:
        raise ValueError(f"Dossier trop volumineux ({len(dce_text):,} caractères) : analyser les pièces séparément.")
    body = _request(dce_text)
    try:
        stop_reason, texts = _call(body, api_key, fallback=True)
    except Exception as e:
        if "fallback" not in str(e).lower():
            raise
        # Compte non éligible aux modèles de repli : on relance sans.
        body.pop("fallbacks")
        stop_reason, texts = _call(body, api_key, fallback=False)
    if stop_reason == "refusal":
        raise RuntimeError("Le modèle a refusé la requête.")
    if stop_reason == "max_tokens":
        raise RuntimeError("Réponse tronquée (limite de longueur atteinte).")
    return Analyse.model_validate(json.loads(texts[0]))


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


def _opportunites(dce: str) -> list[str]:
    t = dce.lower()
    ops = []
    if "extension future" in t or "tranche" in t:
        ops.append("Extension future prévue : position privilégiée pour la tranche suivante")
    if "data center" in t:
        ops.append("Data centers : segment en forte croissance, référence vitrine")
    if re.search(r"solaire|photovolta|éolien", t):
        ops.append("Raccordements EnR : marché récurrent, référence réutilisable pour d'autres parcs")
    if re.search(r"\bais\b|isolé dans l.air", t):
        ops.append("Variante GIS (poste sous enveloppe métallique) : emprise réduite, argument technique")
    ops.append("Achats groupés câbles et appareillage avec les autres affaires en cours")
    return ops


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
        opportunites=_opportunites(dce),
        recommandation_go_nogo=reco)


def analyse(dce_text: str, api_key: str | None = None) -> tuple[Analyse, str]:
    """Retourne (analyse, mode). Sans clé, ou si l'API échoue, bascule sur le mode hors-ligne."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if key:
        try:
            return analyse_with_claude(dce_text, key), "IA (Claude)"
        except Exception as e:  # démo : on ne bloque jamais
            return analyse_offline(dce_text), f"hors-ligne – l'appel à l'IA a échoué ({type(e).__name__} : {str(e)[:200]})"
    return analyse_offline(dce_text), "hors-ligne (règles) – ajoutez une clé API pour analyser n'importe quel dossier"
