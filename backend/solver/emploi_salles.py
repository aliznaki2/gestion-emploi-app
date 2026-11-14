"""Étape 3 — Emploi des salles, dérivé de l'emploi des formateurs.

Les créneaux sont déjà fixés par l'étape 1.  Il reste à choisir une salle pour
chaque séance présentielle, de façon que :

* **(dur)** une salle ne reçoive qu'une séance par créneau, et pas de salle déjà
  occupée par une séance conservée ;
* **(dur)** la salle soit d'un type accepté par le module ;
* **(souple)** les deux moitiés d'un bloc de 5 h restent dans la même salle ;
* **(souple)** un formateur reste dans sa salle préférée, puis dans la même
  salle pendant toute une période (matin / après-midi) ;
* **(souple)** un groupe garde sa salle pendant une période.

Les séances à distance n'occupent aucune salle.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ortools.sat.python import cp_model

from .parametres import Poids


@dataclass
class ResultatEmploiSalles:
    succes: bool
    statut: str
    message: str = ""
    salle_par_seance: Dict[int, Optional[int]] = field(default_factory=dict)
    objectif: int = 0
    temps_ms: int = 0


class EmploiSalles:
    def __init__(
        self,
        seances,
        creneau_par_seance: Dict[int, int],
        creneaux_map: Dict[int, object],
        candidats_salles: Dict[int, List[object]],
        professeurs_map: Dict[int, object],
        occupations_salles: Set[Tuple[int, int]],
        poids: Optional[Poids] = None,
    ):
        self.seances = list(seances)
        self.creneau_par_seance = creneau_par_seance
        self.creneaux_map = creneaux_map
        self.candidats = candidats_salles
        self.professeurs_map = professeurs_map
        self.occ_salles = occupations_salles
        self.poids = poids or Poids()

    @staticmethod
    def _periode(creneau) -> str:
        return 'matin' if creneau.numero_seance <= 2 else 'apm'

    def _paires_voisines(self, presentiel) -> Dict[Tuple[int, int], int]:
        """Paires de séances consécutives dans une même période, avec leur poids."""
        P = self.poids
        par_slot = defaultdict(list)  # (jour, periode) -> [(numero, seance)]
        for s in presentiel:
            c = self.creneaux_map[self.creneau_par_seance[s.id]]
            par_slot[(c.jour, self._periode(c))].append((c.numero_seance, s))

        poids: Dict[Tuple[int, int], int] = defaultdict(int)
        for liste in par_slot.values():
            liste.sort(key=lambda x: (x[0], x[1].id))
            for i, (n1, s1) in enumerate(liste):
                for n2, s2 in liste[i + 1:]:
                    if n2 - n1 != 1:
                        continue
                    cle = (s1.id, s2.id)
                    if s1.bloc_id is not None and s1.bloc_id == s2.bloc_id:
                        poids[cle] += P.bloc_salles_differentes
                    if set(s1.professeur_ids) & set(s2.professeur_ids):
                        poids[cle] += P.stabilite_formateur
                    if set(s1.groupe_ids) & set(s2.groupe_ids):
                        poids[cle] += P.stabilite_groupe
        return {k: v for k, v in poids.items() if v > 0}

    def resoudre(self, temps_max_s: float = 30.0) -> ResultatEmploiSalles:
        debut = time.time()
        presentiel = [s for s in self.seances if s.mode != 'distance']
        resultat: Dict[int, Optional[int]] = {s.id: None for s in self.seances}
        if not presentiel:
            return ResultatEmploiSalles(True, 'OPTIMAL', "Aucune salle à attribuer.", resultat)

        m = cp_model.CpModel()
        Y: Dict[Tuple[int, int], cp_model.IntVar] = {}
        for s in presentiel:
            cid = self.creneau_par_seance[s.id]
            libres = [r for r in self.candidats.get(s.id, []) if (cid, r.id) not in self.occ_salles]
            if not libres:
                return ResultatEmploiSalles(
                    False, 'INFEASIBLE',
                    f"Aucune salle libre et compatible pour {s.module_code} (séance {s.id}).",
                    temps_ms=int((time.time() - debut) * 1000),
                )
            for r in libres:
                Y[s.id, r.id] = m.NewBoolVar(f"y_{s.id}_{r.id}")
            m.AddExactlyOne([Y[s.id, r.id] for r in libres])

        # Une salle ne reçoit qu'une séance par créneau.
        par_slot_salle: Dict[Tuple[int, int], List[cp_model.IntVar]] = defaultdict(list)
        for (sid, rid), var in Y.items():
            par_slot_salle[(self.creneau_par_seance[sid], rid)].append(var)
        for variables in par_slot_salle.values():
            if len(variables) > 1:
                m.AddAtMostOne(variables)

        P = self.poids
        penalites = []

        # Salle préférée du formateur (selon matin / après-midi).
        for s in presentiel:
            creneau = self.creneaux_map[self.creneau_par_seance[s.id]]
            for pid in s.professeur_ids:
                prof = self.professeurs_map.get(pid)
                if prof is None:
                    continue
                pref = prof.salle_preferee_pour_creneau(creneau)
                if pref is not None and (s.id, pref.id) in Y:
                    penalites.append(P.salle_preferee * (1 - Y[s.id, pref.id]))
                    break

        # Stabilité : blocs, formateurs et groupes qui gardent leur salle.
        for (a, b), poids in self._paires_voisines(presentiel).items():
            communes = [r for (sid, r) in Y if sid == a and (b, r) in Y]
            if not communes:
                penalites.append(poids)
                continue
            memes = []
            for rid in communes:
                z = m.NewBoolVar(f"z_{a}_{b}_{rid}")
                m.Add(z <= Y[a, rid])
                m.Add(z <= Y[b, rid])
                memes.append(z)
            penalites.append(poids * (1 - sum(memes)))

        if penalites:
            m.Minimize(sum(penalites))

        solveur = cp_model.CpSolver()
        solveur.parameters.max_time_in_seconds = max(3.0, float(temps_max_s))
        solveur.parameters.num_workers = 4
        statut = solveur.Solve(m)
        ms = int((time.time() - debut) * 1000)
        if statut not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return ResultatEmploiSalles(
                False, solveur.StatusName(statut),
                "Impossible d'affecter une salle à chaque séance sans conflit. "
                "Vérifiez le nombre de salles actives et leurs types compatibles.",
                temps_ms=ms,
            )

        for (sid, rid), var in Y.items():
            if solveur.Value(var) == 1:
                resultat[sid] = rid
        return ResultatEmploiSalles(
            True, solveur.StatusName(statut), "Emploi des salles établi.",
            resultat, int(round(solveur.ObjectiveValue())) if penalites else 0, ms,
        )
