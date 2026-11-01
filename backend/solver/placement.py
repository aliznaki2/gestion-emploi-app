"""
Phase 3 : Modèle d'optimisation mathématique CP-SAT (Google OR-Tools).
Placement sous contraintes dures et souples d'emplois du temps OFPPT.
"""
import time
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from ortools.sat.python import cp_model

from core.models import Creneau, Salle, Professeur
from .decoupage import SeanceAPlacer


@dataclass
class SeancePlacee:
    """Résultat du placement d'une séance élémentaire."""
    seance_a_placer_id: int
    unite_id: int
    creneau_id: int
    salle_id: Optional[int]
    professeur_id: Optional[int]
    groupe_ids: List[int]
    nature: str
    bloc_no: Optional[int]
    mode: str


@dataclass
class ResultatPlacement:
    """Conteneur du résultat renvoyé par le solveur CP-SAT."""
    succes: bool
    statut: str
    seances_placees: List[SeancePlacee] = field(default_factory=list)
    temps_resolution_ms: int = 0
    score_penalite: int = 0
    message: str = ""


class ModelePlacement:
    """
    Formulation et résolution du problème de planification via Google OR-Tools CP-SAT.
    """
    # Pénalités des contraintes souples (Soft Constraints)
    P_SALLE_PREF = 10       # Salle attribuée non préférée
    P_10H = 1000            # Journée de 10h (4 créneaux) pour un groupe
    P_JOUR_VIDE = 200       # Journée vide pour un groupe actif
    P_SURCHARGE = 80        # Dépassement de 2 créneaux (5h) par jour pour un groupe
    P_TROU_GROUPE = 60      # Heure creuse (trou) dans l'emploi du temps d'un groupe
    P_TROU_PROF = 40        # Heure creuse pour un formateur

    def __init__(
        self,
        seances: List[SeanceAPlacer],
        creneaux: List[Creneau],
        salles: List[Salle],
        professeurs: List[Professeur],
        disponibilites: Optional[Dict[Tuple[int, int], str]] = None,
        salles_compatibles_map: Optional[Dict[int, List[int]]] = None,
    ):
        self.seances = seances
        self.creneaux = sorted(creneaux, key=lambda c: (c.jour, c.numero_seance))
        self.salles = salles
        self.professeurs = professeurs
        self.disponibilites = disponibilites or {}  # (prof_id, creneau_id) -> 'disponible' | 'bloque' | 'prefere'
        self.salles_compatibles_map = salles_compatibles_map or {}  # module_id -> [salle_id, ...]

        # Indexations rapides
        self.creneaux_map = {c.id: c for c in self.creneaux}
        self.salles_map = {s.id: s for s in self.salles}
        self.professeurs_map = {p.id: p for p in self.professeurs}

        # Structuration par jour & période
        # jour (1 à 6) -> [creneaux...]
        self.creneaux_par_jour: Dict[int, List[Creneau]] = {}
        for c in self.creneaux:
            self.creneaux_par_jour.setdefault(c.jour, []).append(c)

        # Créneaux consécutifs pour les blocs de 5h:
        # matin: (S1, S2), après-midi: (S3, S4)
        self.paires_blocs: List[Tuple[int, int]] = []
        for jour, cr_list in self.creneaux_par_jour.items():
            s1 = next((c for c in cr_list if c.numero_seance == 1), None)
            s2 = next((c for c in cr_list if c.numero_seance == 2), None)
            s3 = next((c for c in cr_list if c.numero_seance == 3), None)
            s4 = next((c for c in cr_list if c.numero_seance == 4), None)
            if s1 and s2:
                self.paires_blocs.append((s1.id, s2.id))
            if s3 and s4:
                self.paires_blocs.append((s3.id, s4.id))

    def _get_salles_candidates(self, s: SeanceAPlacer) -> List[Salle]:
        """Détermine les salles candidates pour une séance donnée."""
        if s.mode == 'distance':
            team_rooms = [r for r in self.salles if r.type_salle.code == 'TEAM']
            return team_rooms if team_rooms else self.salles[:1]

        compatibles_ids = self.salles_compatibles_map.get(s.module_id)
        if compatibles_ids:
            candidates = [r for r in self.salles if r.id in compatibles_ids and r.actif]
            if candidates:
                return candidates

        # Salles physiques actives par défaut
        physiques = [r for r in self.salles if r.actif and r.type_salle.code != 'TEAM']
        return physiques if physiques else self.salles

    def _get_profs_candidates(self, s: SeanceAPlacer) -> List[Professeur]:
        """Détermine les professeurs éligibles pour cette séance."""
        if s.professeur_ids:
            return [self.professeurs_map[pid] for pid in s.professeur_ids if pid in self.professeurs_map]
        return self.professeurs

    def resoudre(self, max_time_seconds: int = 60) -> ResultatPlacement:
        """
        Construit et résout le modèle CP-SAT.
        """
        start_time = time.time()
        model = cp_model.CpModel()

        if not self.seances:
            return ResultatPlacement(
                succes=True,
                statut='OPTIMAL',
                seances_placees=[],
                temps_resolution_ms=int((time.time() - start_time) * 1000),
                score_penalite=0,
                message="Aucune séance à planifier.",
            )

        # ─── 1. Groupement des séances en blocs ────────────────────────────────
        blocs_map: Dict[int, List[SeanceAPlacer]] = {}
        seances_simples: List[SeanceAPlacer] = []
        for s in self.seances:
            if s.bloc_id is not None:
                blocs_map.setdefault(s.bloc_id, []).append(s)
            else:
                seances_simples.append(s)

        # ─── 2. Variables de décision ─────────────────────────────────────────
        # X[s_id, c_id] : Booléen séance s au créneau c
        # Y[s_id, r_id] : Booléen séance s dans la salle r
        # Z[s_id, p_id] : Booléen séance s avec le professeur p
        # W[s_id, c_id, r_id] : Booléen séance s au créneau c dans la salle r (pour conflit de salle)
        X: Dict[Tuple[int, int], cp_model.IntVar] = {}
        Y: Dict[Tuple[int, int], cp_model.IntVar] = {}
        Z: Dict[Tuple[int, int], cp_model.IntVar] = {}
        W: Dict[Tuple[int, int, int], cp_model.IntVar] = {}

        seance_candidates_salles: Dict[int, List[Salle]] = {}
        seance_candidates_profs: Dict[int, List[Professeur]] = {}

        for s in self.seances:
            cand_salles = self._get_salles_candidates(s)
            cand_profs = self._get_profs_candidates(s)
            seance_candidates_salles[s.id] = cand_salles
            seance_candidates_profs[s.id] = cand_profs

            # Variables créneaux
            for c in self.creneaux:
                X[s.id, c.id] = model.NewBoolVar(f"x_{s.id}_{c.id}")

            # Variables salles
            for r in cand_salles:
                Y[s.id, r.id] = model.NewBoolVar(f"y_{s.id}_{r.id}")

            # Variables professeurs
            for p in cand_profs:
                Z[s.id, p.id] = model.NewBoolVar(f"z_{s.id}_{p.id}")

            # Variables couplées (séance, créneau, salle) pour l'unicité de la salle
            for c in self.creneaux:
                for r in cand_salles:
                    W[s.id, c.id, r.id] = model.NewBoolVar(f"w_{s.id}_{c.id}_{r.id}")
                    # Linéarisation : W <= X et W <= Y et W >= X + Y - 1
                    model.Add(W[s.id, c.id, r.id] <= X[s.id, c.id])
                    model.Add(W[s.id, c.id, r.id] <= Y[s.id, r.id])
                    model.Add(W[s.id, c.id, r.id] >= X[s.id, c.id] + Y[s.id, r.id] - 1)

        # ─── 3. Contraintes Dures (Hard Constraints) ──────────────────────────

        # C1 : Placement Unique pour chaque séance
        for s in self.seances:
            cand_salles = seance_candidates_salles[s.id]
            cand_profs = seance_candidates_profs[s.id]

            # Exactement 1 créneau
            model.Add(sum(X[s.id, c.id] for c in self.creneaux) == 1)
            # Exactement 1 salle
            model.Add(sum(Y[s.id, r.id] for r in cand_salles) == 1)
            # Exactement 1 professeur (si des professeurs candidats existent)
            if cand_profs:
                model.Add(sum(Z[s.id, p.id] for p in cand_profs) == 1)

        # C7 : Structure des Blocs de 5h
        # Chaque bloc (s1, s2) doit occuper l'une des paires consécutives autorisées
        for b_id, pair in blocs_map.items():
            if len(pair) == 2:
                s1, s2 = pair[0], pair[1]

                # Même salle pour les 2 séances du bloc
                cand_salles = seance_candidates_salles[s1.id]
                for r in cand_salles:
                    if (s2.id, r.id) in Y:
                        model.Add(Y[s1.id, r.id] == Y[s2.id, r.id])

                # Même professeur pour les 2 séances du bloc
                cand_profs = seance_candidates_profs[s1.id]
                for p in cand_profs:
                    if (s2.id, p.id) in Z:
                        model.Add(Z[s1.id, p.id] == Z[s2.id, p.id])

                # Variable booléenne d'activation par paire de créneaux (c_a, c_b)
                pair_vars = []
                for idx, (ca_id, cb_id) in enumerate(self.paires_blocs):
                    pv = model.NewBoolVar(f"bloc_{b_id}_pair_{idx}")
                    pair_vars.append(pv)
                    # Si la paire est choisie, s1 est sur ca_id et s2 sur cb_id
                    model.Add(X[s1.id, ca_id] == pv)
                    model.Add(X[s2.id, cb_id] == pv)

                # Exactement 1 paire consécutive choisie pour le bloc
                model.Add(sum(pair_vars) == 1)

                # Interdiction de placer s1 ou s2 sur des créneaux hors des paires
                creneaux_dans_paires_1 = {ca for ca, _ in self.paires_blocs}
                creneaux_dans_paires_2 = {cb for _, cb in self.paires_blocs}
                for c in self.creneaux:
                    if c.id not in creneaux_dans_paires_1:
                        model.Add(X[s1.id, c.id] == 0)
                    if c.id not in creneaux_dans_paires_2:
                        model.Add(X[s2.id, c.id] == 0)

        # C2 : Unicité Groupe (au plus 1 séance par créneau)
        # Collecter tous les groupes distincts
        tous_les_groupes: Set[int] = set()
        groupe_seances_map: Dict[int, List[int]] = {}
        for s in self.seances:
            for gid in s.groupe_ids:
                tous_les_groupes.add(gid)
                groupe_seances_map.setdefault(gid, []).append(s.id)

        for gid in tous_les_groupes:
            s_ids = groupe_seances_map.get(gid, [])
            for c in self.creneaux:
                model.Add(sum(X[sid, c.id] for sid in s_ids) <= 1)

        # C3 : Unicité & Disponibilité Formateur
        prof_seances_map: Dict[int, List[int]] = {}
        for s in self.seances:
            for p in seance_candidates_profs[s.id]:
                prof_seances_map.setdefault(p.id, []).append(s.id)

        for p in self.professeurs:
            s_ids = prof_seances_map.get(p.id, [])
            if not s_ids:
                continue

            for c in self.creneaux:
                etat_dispo = self.disponibilites.get((p.id, c.id), 'disponible')
                assigned_vars = []
                for sid in s_ids:
                    # Variable indicatrice : séance sid attribuée au prof p sur le créneau c
                    # Si p est le seul candidat, Z=1 donc indicatrice = X
                    cand_profs = seance_candidates_profs[sid]
                    if len(cand_profs) == 1 and cand_profs[0].id == p.id:
                        assigned_vars.append(X[sid, c.id])
                    else:
                        v = model.NewBoolVar(f"prof_{p.id}_s_{sid}_c_{c.id}")
                        model.Add(v <= X[sid, c.id])
                        model.Add(v <= Z[sid, p.id])
                        model.Add(v >= X[sid, c.id] + Z[sid, p.id] - 1)
                        assigned_vars.append(v)

                if etat_dispo == 'bloque':
                    # Interdiction absolue
                    model.Add(sum(assigned_vars) == 0)
                else:
                    # Au plus 1 séance
                    model.Add(sum(assigned_vars) <= 1)

            # Plafond hebdomadaire du professeur (heures_max_semaine)
            if p.heures_max_semaine:
                max_seances_prof = int(float(p.heures_max_semaine) / 2.5)
                # Somme des Z[sid, p.id] pour toutes les séances
                prof_active_seances = [Z[sid, p.id] for sid in s_ids if (sid, p.id) in Z]
                if prof_active_seances:
                    model.Add(sum(prof_active_seances) <= max_seances_prof)

        # C4 : Unicité Salle (pour les salles physiques non virtuelles)
        salles_physiques = [r for r in self.salles if r.type_salle.code != 'TEAM' and r.actif]
        for r in salles_physiques:
            for c in self.creneaux:
                salles_occupations = [
                    W[s.id, c.id, r.id]
                    for s in self.seances
                    if (s.id, c.id, r.id) in W
                ]
                if salles_occupations:
                    model.Add(sum(salles_occupations) <= 1)

        # ─── 4. Contraintes Souples & Fonction Objectif ────────────────────────
        penalites = []

        # S1 : Salle préférée du formateur
        for s in self.seances:
            cand_profs = seance_candidates_profs[s.id]
            cand_salles = seance_candidates_salles[s.id]
            for p in cand_profs:
                if p.salle_preferee_id:
                    pref_id = p.salle_preferee_id
                    for r in cand_salles:
                        if r.id != pref_id and (s.id, r.id) in Y:
                            # Pénalité si le prof est affecté et la salle non préférée est choisie
                            if len(cand_profs) == 1:
                                penalites.append(self.P_SALLE_PREF * Y[s.id, r.id])
                            else:
                                diff_var = model.NewBoolVar(f"diff_pref_s{s.id}_p{p.id}_r{r.id}")
                                model.Add(diff_var <= Y[s.id, r.id])
                                model.Add(diff_var <= Z[s.id, p.id])
                                penalites.append(self.P_SALLE_PREF * diff_var)

        # S2, S3 & S4 : Équilibrage des journées pour les groupes
        for gid in tous_les_groupes:
            s_ids = groupe_seances_map.get(gid, [])

            # Variables de présence par jour
            day_active_vars = []
            for jour, cr_list in self.creneaux_par_jour.items():
                day_slots = [c.id for c in cr_list]
                # Nombre de séances du groupe sur ce jour
                day_sum_var = model.NewIntVar(0, 4, f"g_{gid}_day_{jour}_sum")
                model.Add(day_sum_var == sum(X[sid, cid] for sid in s_ids for cid in day_slots))

                # Variable booléenne jour actif (au moins 1 séance dans la journée)
                is_day_active = model.NewBoolVar(f"g_{gid}_day_{jour}_active")
                model.Add(day_sum_var >= is_day_active)
                model.Add(day_sum_var <= 4 * is_day_active)
                day_active_vars.append(is_day_active)

                # Pénalité Journée de 10h (4 créneaux)
                is_10h = model.NewBoolVar(f"g_{gid}_day_{jour}_10h")
                model.Add(day_sum_var >= 4 * is_10h)
                penalites.append(self.P_10H * is_10h)

                # Pénalité Surcharge (> 2 créneaux = 5h par jour)
                surcharge = model.NewIntVar(0, 2, f"g_{gid}_day_{jour}_surcharge")
                model.Add(surcharge >= day_sum_var - 2)
                penalites.append(self.P_SURCHARGE * surcharge)

                # Minimisation des heures creuses (trous)
                # Slots 1, 2, 3, 4 du jour
                s_cr_map = {c.numero_seance: c.id for c in cr_list}
                if 1 in s_cr_map and 2 in s_cr_map and 3 in s_cr_map:
                    # Trou sur S2 : S1 occupé, S3 occupé, S2 libre
                    c1_occ = sum(X[sid, s_cr_map[1]] for sid in s_ids)
                    c2_occ = sum(X[sid, s_cr_map[2]] for sid in s_ids)
                    c3_occ = sum(X[sid, s_cr_map[3]] for sid in s_ids)
                    hole_s2 = model.NewBoolVar(f"g_{gid}_hole_s2_j{jour}")
                    # hole_s2 = 1 => c1=1, c2=0, c3=1
                    model.Add(c1_occ + c3_occ - c2_occ <= 1 + hole_s2)
                    penalites.append(self.P_TROU_GROUPE * hole_s2)

                if 2 in s_cr_map and 3 in s_cr_map and 4 in s_cr_map:
                    # Trou sur S3 : S2 occupé, S4 occupé, S3 libre
                    c2_occ = sum(X[sid, s_cr_map[2]] for sid in s_ids)
                    c3_occ = sum(X[sid, s_cr_map[3]] for sid in s_ids)
                    c4_occ = sum(X[sid, s_cr_map[4]] for sid in s_ids)
                    hole_s3 = model.NewBoolVar(f"g_{gid}_hole_s3_j{jour}")
                    model.Add(c2_occ + c4_occ - c3_occ <= 1 + hole_s3)
                    penalites.append(self.P_TROU_GROUPE * hole_s3)

            # Pénalité Journée Vide pour les groupes actifs (Lundi à Vendredi)
            # Samedi peut être vide si l'effectif hebdomadaire le permet
            for j_idx, jour in enumerate(sorted(self.creneaux_par_jour.keys())):
                if jour <= 5:  # Jours ouvrés standards
                    day_empty = model.NewBoolVar(f"g_{gid}_day_{jour}_empty")
                    model.Add(day_empty == 1 - day_active_vars[j_idx])
                    penalites.append(self.P_JOUR_VIDE * day_empty)

        # Objectif : Minimiser le cumul des pénalités
        model.Minimize(sum(penalites))

        # ─── 5. Exécution du Solveur CP-SAT ───────────────────────────────────
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(max_time_seconds)
        solver.parameters.num_workers = 4
        solver.parameters.log_search_progress = False

        status = solver.Solve(model)
        elapsed_ms = int((time.time() - start_time) * 1000)

        status_name = solver.StatusName(status)
        succes = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        if not succes:
            return ResultatPlacement(
                succes=False,
                statut=status_name,
                temps_resolution_ms=elapsed_ms,
                score_penalite=int(solver.ObjectiveValue()) if status == cp_model.FEASIBLE else 0,
                message=f"Le solveur n'a pas pu trouver de solution faisable (Statut : {status_name}). "
                        f"Vérifiez la disponibilité des formateurs et la capacité des salles.",
            )

        # ─── 6. Extraction des résultats ──────────────────────────────────────
        seances_placees: List[SeancePlacee] = []
        for s in self.seances:
            cand_salles = seance_candidates_salles[s.id]
            cand_profs = seance_candidates_profs[s.id]

            # Créneau sélectionné
            chosen_creneau_id = next(
                (c.id for c in self.creneaux if solver.Value(X[s.id, c.id]) == 1),
                self.creneaux[0].id
            )

            # Salle sélectionnée
            chosen_salle_id = next(
                (r.id for r in cand_salles if solver.Value(Y[s.id, r.id]) == 1),
                cand_salles[0].id if cand_salles else None
            )

            # Professeur sélectionné
            chosen_prof_id = None
            if cand_profs:
                chosen_prof_id = next(
                    (p.id for p in cand_profs if solver.Value(Z[s.id, p.id]) == 1),
                    cand_profs[0].id
                )

            seances_placees.append(
                SeancePlacee(
                    seance_a_placer_id=s.id,
                    unite_id=s.unite_id,
                    creneau_id=chosen_creneau_id,
                    salle_id=chosen_salle_id,
                    professeur_id=chosen_prof_id,
                    groupe_ids=list(s.groupe_ids),
                    nature=s.nature,
                    bloc_no=s.bloc_id,
                    mode=s.mode,
                )
            )

        objective_score = int(solver.ObjectiveValue())
        return ResultatPlacement(
            succes=True,
            statut=status_name,
            seances_placees=seances_placees,
            temps_resolution_ms=elapsed_ms,
            score_penalite=objective_score,
            message=f"Planification réussie ({status_name}) en {elapsed_ms} ms. Score de pénalité : {objective_score}.",
        )

