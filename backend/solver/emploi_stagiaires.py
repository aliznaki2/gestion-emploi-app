"""Étape 2 — Emploi des stagiaires, dérivé de l'emploi des formateurs.

Une séance placée à l'étape 1 porte déjà la liste de ses groupes : l'emploi
d'un groupe est donc simplement l'ensemble des séances qui le citent.  Ce
module construit cette projection, **vérifie** qu'elle est cohérente (aucun
groupe, formateur ou salle utilisé deux fois au même créneau) et calcule les
indicateurs de qualité des trois emplois (trous, journées de 10 h, charges).

Les mêmes fonctions servent à l'audit : on peut les rejouer sur n'importe
quelle semaine déjà générée.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Set, Tuple

from .parametres import DUREE_SEANCE_H


def _profs_de(sp) -> List[int]:
    ids = list(getattr(sp, 'professeur_ids', None) or [])
    if not ids and getattr(sp, 'professeur_id', None):
        ids = [sp.professeur_id]
    return list(dict.fromkeys(ids))


def compter_trous(numeros_occupes: Iterable[int]) -> int:
    """Nombre de créneaux vides situés entre le premier et le dernier occupé."""
    occupes = sorted(set(numeros_occupes))
    if len(occupes) < 2:
        return 0
    return (occupes[-1] - occupes[0] + 1) - len(occupes)


@dataclass
class EmploiStagiaires:
    """Projection de l'emploi des formateurs sur les groupes."""

    par_groupe: Dict[int, Dict[int, List[int]]] = field(default_factory=dict)
    conflits: List[str] = field(default_factory=list)
    heures_par_groupe: Dict[int, float] = field(default_factory=dict)
    trous: int = 0
    journees_10h: int = 0

    @property
    def coherent(self) -> bool:
        return not self.conflits


def deriver_emploi_stagiaires(seances_placees, creneaux_map: Dict[int, Any]) -> EmploiStagiaires:
    """Construit l'emploi de chaque groupe à partir des séances placées."""
    emploi = EmploiStagiaires()
    par_groupe: Dict[int, Dict[int, List[int]]] = defaultdict(lambda: defaultdict(list))
    numeros_par_jour: Dict[Tuple[int, int], Set[int]] = defaultdict(set)

    for sp in seances_placees:
        creneau = creneaux_map[sp.creneau_id]
        for gid in sp.groupe_ids:
            par_groupe[gid][sp.creneau_id].append(sp.seance_a_placer_id)
            numeros_par_jour[(gid, creneau.jour)].add(creneau.numero_seance)

    for gid, slots in par_groupe.items():
        for cid, ids in slots.items():
            if len(ids) > 1:
                emploi.conflits.append(
                    f"groupe {gid} a {len(ids)} séances au créneau {cid} : {ids}"
                )
        emploi.heures_par_groupe[gid] = len(slots) * DUREE_SEANCE_H

    for numeros in numeros_par_jour.values():
        emploi.trous += compter_trous(numeros)
        if len(numeros) >= 4:
            emploi.journees_10h += 1

    emploi.par_groupe = {g: dict(s) for g, s in par_groupe.items()}
    return emploi


def verifier_emplois(seances_placees, creneaux_map: Dict[int, Any]) -> List[str]:
    """Contrôle croisé des trois emplois ; retourne la liste des anomalies."""
    anomalies: List[str] = []
    profs: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    salles: Dict[Tuple[int, int], List[int]] = defaultdict(list)

    for sp in seances_placees:
        for pid in _profs_de(sp):
            profs[(pid, sp.creneau_id)].append(sp.seance_a_placer_id)
        if sp.salle_id:
            salles[(sp.salle_id, sp.creneau_id)].append(sp.seance_a_placer_id)
        if sp.mode == 'distance' and sp.salle_id:
            anomalies.append(f"séance {sp.seance_a_placer_id} à distance mais avec une salle")
        if sp.mode == 'presentiel' and not sp.salle_id:
            anomalies.append(f"séance présentielle {sp.seance_a_placer_id} sans salle")

    anomalies += deriver_emploi_stagiaires(seances_placees, creneaux_map).conflits
    for (pid, cid), ids in profs.items():
        if len(ids) > 1:
            anomalies.append(f"formateur {pid} a {len(ids)} séances au créneau {cid} : {ids}")
    for (rid, cid), ids in salles.items():
        if len(ids) > 1:
            anomalies.append(f"salle {rid} utilisée {len(ids)} fois au créneau {cid} : {ids}")
    return anomalies


def statistiques_emplois(seances_placees, creneaux_map: Dict[int, Any]) -> Dict[str, Any]:
    """Indicateurs de qualité des trois emplois d'une semaine."""
    occ_profs: Dict[Tuple[int, int], Set[int]] = defaultdict(set)
    charge_profs: Dict[int, int] = defaultdict(int)
    salles_par_jour: Dict[int, Set[int]] = defaultdict(set)
    changements_salle_prof = 0
    derniere_salle: Dict[Tuple[int, int, str], int] = {}

    ordonnees = sorted(
        seances_placees,
        key=lambda sp: (creneaux_map[sp.creneau_id].jour, creneaux_map[sp.creneau_id].numero_seance),
    )
    for sp in ordonnees:
        c = creneaux_map[sp.creneau_id]
        for pid in _profs_de(sp):
            occ_profs[(pid, c.jour)].add(c.numero_seance)
            charge_profs[pid] += 1
            if sp.salle_id:
                cle = (pid, c.jour, 'matin' if c.numero_seance <= 2 else 'apm')
                if cle in derniere_salle and derniere_salle[cle] != sp.salle_id:
                    changements_salle_prof += 1
                derniere_salle[cle] = sp.salle_id
        if sp.salle_id:
            salles_par_jour[c.jour].add(sp.salle_id)

    stagiaires = deriver_emploi_stagiaires(seances_placees, creneaux_map)
    return {
        'formateurs': {
            'formateurs_planifies': len(charge_profs),
            'heures_max': max(charge_profs.values(), default=0) * DUREE_SEANCE_H,
            'trous': sum(compter_trous(n) for n in occ_profs.values()),
            'jours_de_presence': len(occ_profs),
            'changements_de_salle': changements_salle_prof,
        },
        'stagiaires': {
            'groupes_planifies': len(stagiaires.par_groupe),
            'trous': stagiaires.trous,
            'journees_10h': stagiaires.journees_10h,
            'heures_min': min(stagiaires.heures_par_groupe.values(), default=0.0),
            'heures_max': max(stagiaires.heures_par_groupe.values(), default=0.0),
            'conflits': len(stagiaires.conflits),
        },
        'salles': {
            'salles_utilisees': len({sp.salle_id for sp in seances_placees if sp.salle_id}),
            'seances_sans_salle': sum(
                1 for sp in seances_placees if sp.mode == 'presentiel' and not sp.salle_id
            ),
        },
    }
