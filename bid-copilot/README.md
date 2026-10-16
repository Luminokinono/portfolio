# ⚡ Bid Copilot

Démonstrateur d'outil d'aide à la préparation d'offres pour des projets électriques HTB (postes, liaisons souterraines, raccordements de data centers).

**Le parcours de la démo** : réception d'un appel d'offres → analyse IA du dossier de consultation → premier budget par ratios → contrôle de cohérence → Monte Carlo P50/P80 → génération automatique de la présentation du Comité de Risque (.pptx).

> ⚠️ Toutes les données sont **synthétiques**. Les coûts unitaires sont des ordres de grandeur indicatifs, à recaler sur des sources publiques (annexes « coûts » des S3REnR de RTE, rapports CRE) ou sur des données réelles d'offres.

## Les 4 modules

| Module | Ce qu'il fait | Fichier |
|---|---|---|
| Base de connaissance | 48 projets réalisés : coûts par poste, heures, délais, marges, risques survenus, retours d'expérience | `data/generate_dataset.py` |
| Cost Estimator | Ratios unitaires (médiane, P25, P75) par tension, budget ligne à ligne, 3 projets similaires (k plus proches voisins), détection des lignes sous- ou sur-estimées | `core/estimator.py` |
| Assistant d'appel d'offres | Extraction structurée du dossier : caractéristiques, risques cités, données manquantes, hypothèses, exclusions, questions au client, recommandation go / no-go | `core/ai_analyst.py` |
| Comité de Risque | Présentation de 8 slides : Projet → Chiffres clés → Planning → Risques → Opportunités → Hypothèses → Synthèse financière → Décisions attendues | `core/risk_deck.py` |

L'analyse IA utilise l'API Claude si la variable `ANTHROPIC_API_KEY` est définie. Sinon, elle bascule sur un **mode hors-ligne à base de règles**, pour que la démo fonctionne toujours, même sans réseau.

## Lancer la démo

```bash
cd bid-copilot
pip install -r requirements.txt
python data/generate_dataset.py      # (re)génère data/projects.csv
streamlit run app.py
```

Optionnel, pour l'analyse par Claude :

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Le DCE de démonstration

`data/dce_demo_datacenter.txt` est un faux dossier de consultation pour le raccordement en 225 kV d'un data center. Il contient volontairement des pièges que l'outil doit détecter :

- un délai de 18 mois, incompatible avec la fabrication d'un transformateur (24 à 30 mois) ;
- des pénalités de retard de 0,5 % par jour, sans plafond ;
- des prix fermes et non révisables (exposition au prix du cuivre) ;
- aucune étude de sol, un tracé non figé, des autorisations en cours ;
- le transfert au titulaire du risque lié à l'accord de raccordement.

## Limites et suite

- **Données** : sur de vraies offres, le premier chantier serait de structurer les chiffrages existants (fichiers Excel hétérogènes) dans un format commun.
- **Confidentialité** : des offres à plusieurs dizaines de M€ imposent un LLM hébergé en Europe ou en interne, une traçabilité des sources, et une validation humaine systématique.
- **Similarité** : passer du k plus proches voisins sur les caractéristiques à une recherche sémantique (embeddings) dans les mémoires techniques et les retours d'expérience.
- **Calibration** : ajuster les lois du Monte Carlo à partir des écarts réels entre coûts prévus et coûts constatés.

## Version en ligne (sans serveur)

`index.html` fait tourner l'appli directement dans le navigateur grâce à [stlite](https://github.com/whitphx/stlite) (Streamlit compilé en WebAssembly). Une fois la branche fusionnée dans `main`, elle est accessible via GitHub Pages à l'adresse :

https://luminokinono.github.io/portfolio/bid-copilot/

Dans cette version, l'analyse du DCE tourne en mode hors-ligne (règles). Le premier chargement prend 30 à 60 secondes.
