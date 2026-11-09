"""
Phase 3 : Modèle d'optimisation mathématique CP-SAT (Google OR-Tools).
Placement sous contraintes dures et souples d'emplois du temps OFPPT.
Architecture à résolution décomposée hautement performante (Créneaux/Formateurs puis Salles).
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
    professeur_ids: List[int] = field(default_factory=list)


@dataclass
class ResultatPlacement:
    """Conteneur du résultat renvoyé par le solveur CP-SAT."""
    succes: bool
    statut: str
    seances_placees: List[SeancePlacee] = field(default_factory=list)
    temps_resolution_ms: int = 0
    score_penalite: int = 0
    message: str = ""
    borne: Optional[int] = None


class ModelePlacement:
    """
    Formulation et résolution du problème de planification via Google OR-Tools CP-SAT.
    Utilise une décomposition en 2 étapes mathématiquement exactes pour garantir un temps
    de résolution inférieur à quelques secondes, même pour plus de 40 groupes et 60 formateurs.
    """
    # Pénalités des contraintes souples (Soft Constraints)
    P_SALLE_PREF = 10       # Salle attribuée non préférée
    P_10H = 1000            # Journée de 10h (4 créneaux) pour un groupe
    P_JOUR_VIDE = 200       # Journée vide pour un groupe actif (Lundi-Vendredi)
    P_SURCHARGE = 80        # Dépassement de 2 créneaux (5h) par jour pour un groupe
    P_TROU_GROUPE = 700     # Heure creuse (trou) dans l'emploi du temps d'un groupe
    P_TROU_PROF = 150       # Heure creuse pour un formateur
    P_EFM_JOUR = 5000       # EFM placé hors de la date d'EFM prévue
    P_PREF = 80             # Bonus (coût négatif) pour un créneau préféré honoré

    def __init__(
        self,
        seances: List[SeanceAPlacer],
        creneaux: List[Creneau],
        salles: List[Salle],
        professeurs: List[Professeur],
        disponibilites: Optional[Dict[Tuple[int, int], str]] = None,
        salles_compatibles_map: Optional[Dict[int, List[int]]] = None,
        occupations_groupes: Optional[Set[Tuple[int, int]]] = None,
        occupations_profs: Optional[Set[Tuple[int, int]]] = None,
        occupations_salles: Optional[Set[Tuple[int, int]]] = None,
        criteres: Optional[List[object]] = None,
    ):
        self.seances = seances
        self.creneaux = sorted(creneaux, key=lambda c: (c.jour, c.numero_seance))
        self.salles = salles
        self.professeurs = professeurs
        self.disponibilites = disponibilites or {}  # (prof_id, creneau_id) -> 'disponible' | 'bloque' | 'prefere'
        self.salles_compatibles_map = salles_compatibles_map or {}  # module_id -> [salle_id, ...]
        self.criteres: List[object] = list(criteres or [])

        # Créneaux déjà occupés par des séances conservées (validées / verrouillées)
        self.occupations_groupes = occupations_groupes or set()  # (creneau_id, groupe_id)
        self.occupations_profs = occupations_profs or set()      # (creneau_id, prof_id)
        self.occupations_salles = occupations_salles or set()    # (creneau_id, salle_id)

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

    # ─── Critères (patron de stratégie) ───────────────────────────────────────
    def ajouter_critere(self, critere) -> "ModelePlacement":
        """Ajoute un critère de placement au modèle."""
        self.criteres.append(critere)
        return self

    def critere(self, nom: str):
        return next((c for c in self.criteres if getattr(c, 'nom', None) == nom), None)

    def poids(self, nom: str, defaut: int = 0) -> int:
        """Poids d'un critère actif, ou valeur par défaut."""
        critere = self.critere(nom)
        if critere is None or not getattr(critere, 'actif', True):
            return defaut
        return int(getattr(critere, 'poids', defaut) or defaut)

    def _poids_heures_creuses(self, ressource: str) -> int:
        critere = self.critere('HeuresCreuses')
        if critere is None or not getattr(critere, 'actif', True):
            return self.P_TROU_GROUPE if ressource == 'groupe' else self.P_TROU_PROF
        attribut = 'poids_groupe' if ressource == 'groupe' else 'poids_prof'
        return int(getattr(critere, attribut, 0) or 0)

    def _get_salles_candidates(self, s: SeanceAPlacer) -> List[Salle]:
        """Détermine les salles candidates pour une séance donnée."""
        if s.mode == 'distance':
            # Une séance à distance n'occupe pas de salle physique.
            return []

        compatibles_ids = self.salles_compatibles_map.get(s.module_id)
        if compatibles_ids:
            candidates = [r for r in self.salles if r.id in compatibles_ids and r.actif]
            if candidates:
                return candidates

        # Salles physiques actives par défaut
        return [r for r in self.salles if r.actif and r.type_salle.code != 'TEAM']

    def _get_profs_candidates(self, s: SeanceAPlacer) -> List[Professeur]:
        """Détermine les professeurs éligibles pour cette séance."""
        if s.professeur_ids:
            return [self.professeurs_map[pid] for pid in s.professeur_ids if pid in self.professeurs_map]
        return []

    def resoudre(self, max_time_seconds: int = 60) -> ResultatPlacement:
        """
        Construit et résout le modèle CP-SAT en deux phases complémentaires :
        Phase 1 : Placement des créneaux temporels, gestion des conflits groupes/profs et blocs 5h.
        Phase 2 : Affectation des salles aux créneaux déterminés avec respect des blocs et préférences.
        """
        start_time = time.time()

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
        for s in self.seances:
            if s.bloc_id is not None:
                blocs_map.setdefault(s.bloc_id, []).append(s)

        seance_candidates_salles: Dict[int, List[Salle]] = {}
        seance_candidates_profs: Dict[int, List[Professeur]] = {}

        for s in self.seances:
            seance_candidates_salles[s.id] = self._get_salles_candidates(s)
            seance_candidates_profs[s.id] = self._get_profs_candidates(s)

        # ─── 2. Vérifications Préliminaires de Faisabilité ────────────────────
        sans_creneaux = not self.creneaux
        sans_salle = [
            s for s in self.seances
            if s.mode != 'distance' and not seance_candidates_salles[s.id]
        ]
        profs_surcharges = []
        for prof in self.professeurs:
            max_heures = float(prof.heures_max_semaine or 0)
            if max_heures <= 0:
                continue
            seances_obligatoires = [
                s for s in self.seances
                if len(seance_candidates_profs[s.id]) == 1
                and seance_candidates_profs[s.id][0].id == prof.id
            ]
            max_seances = int(max_heures / 2.5)
            if len(seances_obligatoires) > max_seances:
                profs_surcharges.append((prof, len(seances_obligatoires), max_seances))

        if sans_creneaux or sans_salle or profs_surcharges:
            causes = []
            if sans_creneaux:
                causes.append("aucun créneau n'est configuré")
            if sans_salle:
                causes.append(
                    "aucune salle active compatible pour : "
                    + ", ".join(f"unité {s.unite_id} (séance {s.id})" for s in sans_salle[:8])
                )
            if profs_surcharges:
                causes.append(
                    "plafond hebdomadaire dépassé pour : "
                    + ", ".join(
                        f"{prof.nom_complet} ({nb} séances demandées, plafond {max_nb})"
                        for prof, nb, max_nb in profs_surcharges[:8]
                    )
                )
            return ResultatPlacement(
                succes=False,
                statut='INFEASIBLE',
                temps_resolution_ms=int((time.time() - start_time) * 1000),
                message="Génération impossible : " + "; ".join(causes) + ". Vérifiez les créneaux, les salles actives/types compatibles et les affectations/plafonds des formateurs.",
            )

        # ─── 3. ÉTAPE 1 : Affectation des Créneaux Temporels ──────────────────
        time_limit_st1 = max(5.0, float(max_time_seconds) * 0.75)
        model_time = cp_model.CpModel()

        # Variables de décision temporelles : X[s_id, c_id]
        X: Dict[Tuple[int, int], cp_model.IntVar] = {}
        for s in self.seances:
            for c in self.creneaux:
                X[s.id, c.id] = model_time.NewBoolVar(f"x_{s.id}_{c.id}")

        # C1 : Chaque séance est attribuée à exactly 1 créneau
        for s in self.seances:
            model_time.Add(sum(X[s.id, c.id] for c in self.creneaux) == 1)

        # C7 : Blocs de 5h sur 2 créneaux consécutifs (Matin S1+S2 ou Après-midi S3+S4)
        for b_id, pair in blocs_map.items():
            if len(pair) == 2:
                s1, s2 = pair[0], pair[1]

                pair_vars = []
                for idx, (ca_id, cb_id) in enumerate(self.paires_blocs):
                    pv = model_time.NewBoolVar(f"b_{b_id}_p_{idx}")
                    pair_vars.append(pv)
                    model_time.Add(X[s1.id, ca_id] == pv)
                    model_time.Add(X[s2.id, cb_id] == pv)

                model_time.Add(sum(pair_vars) == 1)

        # C2 : Unicité Groupe (au plus 1 séance par créneau)
        tous_les_groupes: Set[int] = set()
        groupe_seances_map: Dict[int, List[int]] = {}
        for s in self.seances:
            for gid in s.groupe_ids:
                tous_les_groupes.add(gid)
                groupe_seances_map.setdefault(gid, []).append(s.id)

        for gid in tous_les_groupes:
            s_ids = groupe_seances_map.get(gid, [])
            for c in self.creneaux:
                model_time.Add(sum(X[sid, c.id] for sid in s_ids) <= 1)
                if (c.id, gid) in self.occupations_groupes:
                    model_time.Add(sum(X[sid, c.id] for sid in s_ids) == 0)

        # C3 : Unicité & Disponibilité Formateur.
        # Tous les formateurs rattachés à une séance (co-enseignement) sont
        # considérés occupés : le document demande de rattacher chaque
        # formateur de l'unité à chaque séance.
        prof_seances_map: Dict[int, List[int]] = {}
        for s in self.seances:
            for p in seance_candidates_profs[s.id]:
                prof_seances_map.setdefault(p.id, []).append(s.id)

        prof_occ: Dict[Tuple[int, int], object] = {}

        for p in self.professeurs:
            s_ids = prof_seances_map.get(p.id, [])
            if not s_ids:
                continue

            for c in self.creneaux:
                etat_dispo = self.disponibilites.get((p.id, c.id), 'disponible')
                assigned_vars = [X[sid, c.id] for sid in s_ids]

                if (c.id, p.id) in self.occupations_profs or etat_dispo == 'bloque':
                    model_time.Add(sum(assigned_vars) == 0)
                else:
                    model_time.Add(sum(assigned_vars) <= 1)
                prof_occ[(p.id, c.id)] = sum(assigned_vars) if assigned_vars else 0

            # Plafond hebdomadaire du professeur (toutes affectations confondues)
            if p.heures_max_semaine:
                max_seances_prof = int(float(p.heures_max_semaine) / 2.5)
                prof_assign_vars = [
                    sum(X[sid, c.id] for c in self.creneaux)
                    for sid in s_ids
                ]
                if prof_assign_vars:
                    model_time.Add(sum(prof_assign_vars) <= max_seances_prof)

        # C4-Capacité : La somme des séances présentielles par créneau ne peut dépasser les salles physiques
        salles_physiques = [r for r in self.salles if r.type_salle.code != 'TEAM' and r.actif]
        nb_salles_physiques = len(salles_physiques)

        for c in self.creneaux:
            presentiel_seances = [s for s in self.seances if s.mode == 'presentiel']
            if presentiel_seances:
                salles_occupees = sum(
                    1 for r in salles_physiques if (c.id, r.id) in self.occupations_salles
                )
                capacite_libre = max(0, nb_salles_physiques - salles_occupees)
                model_time.Add(sum(X[s.id, c.id] for s in presentiel_seances) <= capacite_libre)

        # C4-Sous-capacités pour types de salles spécifiques si restreints (ex: LABO)
        types_salles_ids = set(r.type_salle_id for r in salles_physiques)
        for t_id in types_salles_ids:
            salles_ce_type = [r for r in salles_physiques if r.type_salle_id == t_id]
            # Séances qui ne peuvent aller QUE dans ce type
            seances_strictes_t = []
            for s in self.seances:
                if s.mode == 'presentiel':
                    cand_ids = set(r.type_salle_id for r in seance_candidates_salles[s.id])
                    if cand_ids == {t_id}:
                        seances_strictes_t.append(s)
            if seances_strictes_t:
                for c in self.creneaux:
                    occupees = sum(
                        1 for r in salles_ce_type if (c.id, r.id) in self.occupations_salles
                    )
                    model_time.Add(
                        sum(X[s.id, c.id] for s in seances_strictes_t)
                        <= max(0, len(salles_ce_type) - occupees)
                    )

        # Soft Constraints Temporelles : Équilibrage journalier et Heures creuses
        penalites_temps = []

        # L'EFM doit être placé le jour précis de sa date (pénalité très forte).
        for s in self.seances:
            if s.nature == 'examen' and s.jour_efm:
                for c in self.creneaux:
                    if c.jour != s.jour_efm:
                        penalites_temps.append(self.P_EFM_JOUR * X[s.id, c.id])
        for gid in tous_les_groupes:
            s_ids = groupe_seances_map.get(gid, [])
            day_active_vars = []

            for jour, cr_list in self.creneaux_par_jour.items():
                day_slots = [c.id for c in cr_list]
                day_sum_var = model_time.NewIntVar(0, 4, f"g_{gid}_j_{jour}_sum")
                model_time.Add(day_sum_var == sum(X[sid, cid] for sid in s_ids for cid in day_slots))

                is_day_active = model_time.NewBoolVar(f"g_{gid}_j_{jour}_act")
                model_time.Add(day_sum_var >= is_day_active)
                model_time.Add(day_sum_var <= 4 * is_day_active)
                day_active_vars.append(is_day_active)

                # Pénalité 10h
                is_10h = model_time.NewBoolVar(f"g_{gid}_j_{jour}_10h")
                model_time.Add(day_sum_var >= 4 * is_10h)
                penalites_temps.append(self.poids('JourneeDixHeures', self.P_10H) * is_10h)

                # Pénalité Surcharge (> 2 créneaux)
                surcharge = model_time.NewIntVar(0, 2, f"g_{gid}_j_{jour}_surch")
                model_time.Add(surcharge >= day_sum_var - 2)
                penalites_temps.append(self.P_SURCHARGE * surcharge)

                # Minimisation des trous
                s_cr_map = {c.numero_seance: c.id for c in cr_list}
                if 1 in s_cr_map and 2 in s_cr_map and 3 in s_cr_map:
                    c1_occ = sum(X[sid, s_cr_map[1]] for sid in s_ids)
                    c2_occ = sum(X[sid, s_cr_map[2]] for sid in s_ids)
                    c3_occ = sum(X[sid, s_cr_map[3]] for sid in s_ids)
                    hole_s2 = model_time.NewBoolVar(f"g_{gid}_hole_s2_j{jour}")
                    model_time.Add(c1_occ + c3_occ - c2_occ <= 1 + hole_s2)
                    penalites_temps.append(self._poids_heures_creuses('groupe') * hole_s2)

                if 2 in s_cr_map and 3 in s_cr_map and 4 in s_cr_map:
                    c2_occ = sum(X[sid, s_cr_map[2]] for sid in s_ids)
                    c3_occ = sum(X[sid, s_cr_map[3]] for sid in s_ids)
                    c4_occ = sum(X[sid, s_cr_map[4]] for sid in s_ids)
                    hole_s3 = model_time.NewBoolVar(f"g_{gid}_hole_s3_j{jour}")
                    model_time.Add(c2_occ + c4_occ - c3_occ <= 1 + hole_s3)
                    penalites_temps.append(self._poids_heures_creuses('groupe') * hole_s3)

            # Pénalité Journée Vide (Lundi à Vendredi)
            for j_idx, jour in enumerate(sorted(self.creneaux_par_jour.keys())):
                if jour <= 5:
                    day_empty = model_time.NewBoolVar(f"g_{gid}_j_{jour}_empty")
                    model_time.Add(day_empty == 1 - day_active_vars[j_idx])
                    penalites_temps.append(self.P_JOUR_VIDE * day_empty)

        # Heures creuses des formateurs (poids plus faible que les groupes)
        for p in self.professeurs:
            s_ids = prof_seances_map.get(p.id, [])
            if not s_ids:
                continue
            for jour, cr_list in self.creneaux_par_jour.items():
                s_cr_map = {c.numero_seance: c.id for c in cr_list}

                def occ(num):
                    cid = s_cr_map.get(num)
                    return prof_occ.get((p.id, cid), 0) if cid else 0

                if all(k in s_cr_map for k in (1, 2, 3)):
                    hole_s2 = model_time.NewBoolVar(f"p_{p.id}_hole_s2_j{jour}")
                    model_time.Add(occ(1) + occ(3) - occ(2) <= 1 + hole_s2)
                    penalites_temps.append(self._poids_heures_creuses('prof') * hole_s2)

                if all(k in s_cr_map for k in (2, 3, 4)):
                    hole_s3 = model_time.NewBoolVar(f"p_{p.id}_hole_s3_j{jour}")
                    model_time.Add(occ(2) + occ(4) - occ(3) <= 1 + hole_s3)
                    penalites_temps.append(self._poids_heures_creuses('prof') * hole_s3)

        # Bonus pour les créneaux préférés des formateurs.
        # Un coût négatif dans l'objectif encourage le solveur à y placer des
        # séances, sans jamais rendre une solution infaisable (contrainte souple).
        for p in self.professeurs:
            s_ids = prof_seances_map.get(p.id, [])
            if not s_ids:
                continue
            for c in self.creneaux:
                if self.disponibilites.get((p.id, c.id)) == 'prefere':
                    penalites_temps.append(
                        -self.P_PREF * prof_occ.get((p.id, c.id), 0)
                    )

        model_time.Minimize(sum(penalites_temps))

        solver_time = cp_model.CpSolver()
        solver_time.parameters.max_time_in_seconds = float(time_limit_st1)
        solver_time.parameters.num_workers = 4
        solver_time.parameters.log_search_progress = False

        status_time = solver_time.Solve(model_time)
        status_name = solver_time.StatusName(status_time)
        succes_time = status_time in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        if not succes_time:
            elapsed_ms = int((time.time() - start_time) * 1000)
            if status_time == cp_model.UNKNOWN:
                message = f"Le solveur a dépassé le délai de {time_limit_st1}s lors de la planification temporelle."
            else:
                message = "Aucune solution temporelle faisable avec les contraintes actuelles."
            return ResultatPlacement(
                succes=False,
                statut=status_name,
                temps_resolution_ms=elapsed_ms,
                score_penalite=0,
                message=message,
            )

        # Extraction des créneaux assignés
        assigned_creneau: Dict[int, int] = {}
        for s in self.seances:
            for c in self.creneaux:
                if solver_time.Value(X[s.id, c.id]) == 1:
                    assigned_creneau[s.id] = c.id
                    break

        # Tous les formateurs rattachés à la séance (co-enseignement).
        assigned_profs: Dict[int, List[int]] = {}
        for s in self.seances:
            assigned_profs[s.id] = [p.id for p in seance_candidates_profs[s.id]]
        assigned_prof: Dict[int, Optional[int]] = {
            sid: (ids[0] if ids else None) for sid, ids in assigned_profs.items()
        }

        score_st1 = int(solver_time.ObjectiveValue())
        borne_st1 = int(solver_time.BestObjectiveBound())

        # ─── 4. ÉTAPE 2 : Affectation des Salles ──────────────────────────────
        remaining_time = max(5.0, float(max_time_seconds) - (time.time() - start_time))
        model_room = cp_model.CpModel()

        Y: Dict[Tuple[int, int], cp_model.IntVar] = {}
        for s in self.seances:
            if s.mode == 'distance':
                continue
            cand_salles = seance_candidates_salles[s.id]
            for r in cand_salles:
                Y[s.id, r.id] = model_room.NewBoolVar(f"y_{s.id}_{r.id}")
            if cand_salles:
                model_room.Add(sum(Y[s.id, r.id] for r in cand_salles) == 1)

        # Même salle pour les Blocs de 5h
        for b_id, pair in blocs_map.items():
            if len(pair) == 2:
                s1, s2 = pair[0], pair[1]
                cand_salles = seance_candidates_salles[s1.id]
                for r in cand_salles:
                    if (s2.id, r.id) in Y:
                        model_room.Add(Y[s1.id, r.id] == Y[s2.id, r.id])

        # Unicité de la salle physique par créneau + respect des salles occupées
        for c in self.creneaux:
            seances_du_creneau = [s for s in self.seances if assigned_creneau[s.id] == c.id and s.mode != 'distance']
            for r in salles_physiques:
                occupations = [Y[s.id, r.id] for s in seances_du_creneau if (s.id, r.id) in Y]
                if occupations:
                    if (c.id, r.id) in self.occupations_salles:
                        model_room.Add(sum(occupations) == 0)
                    else:
                        model_room.Add(sum(occupations) <= 1)

        # Pénalité Salle préférée du formateur (selon la période AM / PM)
        penalites_salles = []
        for s in self.seances:
            p_id = assigned_prof.get(s.id)
            if p_id and p_id in self.professeurs_map:
                prof = self.professeurs_map[p_id]
                creneau = self.creneaux_map.get(assigned_creneau.get(s.id))
                pref = prof.salle_preferee_pour_creneau(creneau) if hasattr(
                    prof, 'salle_preferee_pour_creneau'
                ) else getattr(prof, 'salle_preferee', None)
                pref_id = getattr(pref, 'id', None)
                if pref_id and (s.id, pref_id) in Y:
                    penalites_salles.append(
                        self.poids('PreferenceSalle', self.P_SALLE_PREF) * (1 - Y[s.id, pref_id])
                    )

        if penalites_salles:
            model_room.Minimize(sum(penalites_salles))

        solver_room = cp_model.CpSolver()
        solver_room.parameters.max_time_in_seconds = float(remaining_time)
        solver_room.parameters.num_workers = 4
        solver_room.parameters.log_search_progress = False

        status_room = solver_room.Solve(model_room)
        succes_room = status_room in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        if not succes_room:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return ResultatPlacement(
                succes=False,
                statut=solver_room.StatusName(status_room),
                temps_resolution_ms=elapsed_ms,
                score_penalite=0,
                message=(
                    "Impossible d'affecter une salle à chaque séance sans conflit. "
                    "Vérifiez le nombre de salles actives et leurs types compatibles."
                ),
            )

        score_st2 = int(solver_room.ObjectiveValue()) if penalites_salles else 0

        # Extraction des salles assignées
        assigned_salle: Dict[int, Optional[int]] = {}
        for s in self.seances:
            if s.mode == 'distance':
                assigned_salle[s.id] = None
                continue
            cand_salles = seance_candidates_salles[s.id]
            if not cand_salles:
                assigned_salle[s.id] = None
                continue
            chosen_r = next(
                (r.id for r in cand_salles if solver_room.Value(Y[s.id, r.id]) == 1),
                cand_salles[0].id,
            )
            assigned_salle[s.id] = chosen_r

        elapsed_ms = int((time.time() - start_time) * 1000)

        # ─── 5. Construction de la Liste des Séances Placées ──────────────────
        seances_placees: List[SeancePlacee] = []
        for s in self.seances:
            seances_placees.append(
                SeancePlacee(
                    seance_a_placer_id=s.id,
                    unite_id=s.unite_id,
                    creneau_id=assigned_creneau[s.id],
                    salle_id=assigned_salle[s.id],
                    professeur_id=assigned_prof.get(s.id),
                    groupe_ids=list(s.groupe_ids),
                    nature=s.nature,
                    bloc_no=s.bloc_id,
                    mode=s.mode,
                    professeur_ids=list(assigned_profs.get(s.id, [])),
                )
            )

        total_penalty = score_st1 + score_st2
        return ResultatPlacement(
            succes=True,
            statut=status_name,
            seances_placees=seances_placees,
            temps_resolution_ms=elapsed_ms,
            score_penalite=total_penalty,
            borne=borne_st1 + score_st2,
            message=f"Planification réussie ({status_name}) en {elapsed_ms} ms. Score de pénalité : {total_penalty}.",
        )
