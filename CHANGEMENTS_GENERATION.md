# Génération « formateur d'abord » — changements

## Nouvel ordre de génération (phase 3)
1. **Emploi des formateurs** — `solver/emploi_formateurs.py`
   Place chaque séance sur un créneau. Passe A : on minimise les pénalités des formateurs
   (trous, EFM à la bonne date). Passe B : on fige ce résultat et, à qualité égale,
   on optimise les groupes (trous, journées de 10 h, surcharge, jours vides, créneaux préférés).
2. **Emploi des stagiaires** — `solver/emploi_stagiaires.py`
   Dérivé de l'étape 1 (chaque séance porte ses groupes), puis vérifié : aucun groupe,
   formateur ou salle en double. Calcule aussi les indicateurs des trois emplois.
3. **Emploi des salles** — `solver/emploi_salles.py`
   Salle par séance à partir des créneaux fixés : salle préférée du formateur, même salle
   pour un bloc de 5 h, stabilité par période pour formateurs et groupes.

`solver/placement.py` reste la façade (`ModelePlacement`) : même API pour `services.py`.
Poids : `solver/parametres.py`. Le détail des trois emplois est dans `resume['phase3']`
(`emploi_formateurs`, `emploi_stagiaires`, `emploi_salles`, `etapes`, `efm_hors_date`).

## Erreurs corrigées
| Problème | Correction |
|---|---|
| EFM hors date : pénalité fixe, jour de repli arbitraire (lun-ven) | Pénalité proportionnelle à l'écart en jours + alerte avec la cause |
| Heures perdues quand un formateur est absent (EGTS101 : 40 h / 45 h) | Rattrapage après la fin du passage (`heures.py`) |
| Trou S1+S4 (5 h de vide) jamais pénalisé | Détection de trous correcte pour tout créneau vide entre deux occupés |
| Capacité des salles vérifiée seulement en total | Condition de Hall par types de salles : l'étape salles a toujours une solution |
| Génération ciblée (`groupes_ids`) supprimait les brouillons des autres groupes | Seuls les brouillons des groupes régénérés sont supprimés ; groupes fusionnés inclus |
| Séances conservées : seul le 1er formateur était bloqué | Tous les formateurs de la séance sont comptés, plafond hebdo déduit |
| Passages : échec total si le semestre est trop chargé (« retard » jamais atteint) | Repli avec horizon rallongé, passages signalés « en retard » |
| Indicateurs phase 1 comparés à 30-35 h alors que le calculateur vise 15-25 h | Indicateurs alignés (anciennes clés conservées) |
| Code mort `_calculer_par_unites` (variable non définie) | Supprimé |
| `/api/emploi-du-temps` : 1 requête SQL par séance (`.first()` sur prefetch) | Utilise le prefetch |
| 2 tests en échec | Test API adapté au 202 asynchrone ; phase 0 corrigée |

## Panneau admin : les trois emplois
Onglet « Emploi du temps » du tableau de bord, trois vues dans l'ordre de génération :
1. **Emploi des formateurs** (vue par défaut) : une ligne par formateur (groupe / module / salle), charge en heures,
   jours de présence, trous, conflits éventuels.
2. **Emploi des stagiaires** : la vue par groupe existante.
3. **Emploi des salles** : une ligne par salle (groupe / module / formateur), taux d'occupation.

Après « Générer l'emploi », un panneau récapitule les trois étapes (statut, temps, indicateurs) et liste les EFM
qui n'ont pas pu être placés à leur date. Fichiers : `frontend/src/components/Dashboard/EmploiRessources.jsx` (nouveau)
et `Dashboard.jsx` (modifié).

## À savoir
- La passe B est limitée à 5 s (`EmploiFormateurs.BUDGET_MAX_PASSE_B_S`) : ~9 s par semaine
  contre ~2 s avant. Augmentez-la pour de meilleurs emplois de groupes.
- Données : certains formateurs ont 4-5 EFM le même samedi alors qu'un jour ne contient que
  2 blocs de 5 h. Le générateur place alors ces EFM au plus près de leur date et les signale.
- Les endpoints `compat_views` (générer / valider / vider) n'ont aucune authentification.
