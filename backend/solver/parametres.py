"""Paramètres communs aux trois étapes du placement.

Le placement se fait dans cet ordre :

1. **Emploi des formateurs** (``emploi_formateurs.py``) : chaque séance reçoit
   un créneau.  C'est la source de vérité de la semaine.
2. **Emploi des stagiaires** (``emploi_stagiaires.py``) : dérivé de l'emploi des
   formateurs (chaque séance porte ses groupes), vérifié et mesuré.
3. **Emploi des salles** (``emploi_salles.py``) : une salle est choisie pour
   chaque séance présentielle, à partir des créneaux déjà fixés.

Les poids ci-dessous sont les pénalités des contraintes souples.  Quand un
critère (``solver.criteres``) est enregistré dans le modèle, son poids
remplace la valeur par défaut.
"""
from __future__ import annotations

from dataclasses import dataclass

DUREE_SEANCE_H = 2.5


@dataclass(frozen=True)
class Poids:
    """Pénalités des contraintes souples (plus c'est grand, plus c'est évité)."""

    # ── Emploi des formateurs (étape 1, passe A) ──────────────────────────
    trou_formateur: int = 10      # créneau vide entre deux séances d'un formateur
    efm_par_jour: int = 5000      # par jour d'écart entre l'EFM placé et sa date
    preference: int = 80          # bonus (coût négatif) : créneau « préféré »

    # ── Emploi des stagiaires (étape 1, passe B) ──────────────────────────
    trou_groupe: int = 30         # créneau vide entre deux séances d'un groupe
    journee_10h: int = 40         # journée complète de 4 séances pour un groupe
    surcharge: int = 80           # par séance au-delà de 2 dans la même journée
    jour_vide: int = 200          # jour ouvrable (lun-ven) sans séance

    # ── Emploi des salles (étape 3) ───────────────────────────────────────
    salle_preferee: int = 3       # salle différente de la salle préférée
    stabilite_formateur: int = 2  # un formateur change de salle dans la période
    stabilite_groupe: int = 1     # un groupe change de salle dans la période
    bloc_salles_differentes: int = 1000  # deux moitiés d'un bloc en salles différentes
