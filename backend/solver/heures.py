"""
Phase 1 : Calculateur du volume horaire hebdomadaire par unité et par groupe.
Application des règles OFPPT pour modules généraux (passages) et techniques.

Le calcul tient compte :
  - des heures déjà planifiées et conservées pour la semaine (séances validées /
    verrouillées) ;
  - du plafond hebdomadaire de chaque formateur (y compris pour les passages) ;
  - de la déduplication des unités identiques ;
  - d'un rééquilibrage par groupe puis par formateur.
"""
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from core.models import (
    Semaine, UniteEnseignement, Groupe, Passage, VolumeHoraire,
    Professeur, Seance, UniteProfesseur
)


@dataclass
class UnitePrevision:
    """Prévision hebdomadaire pour une unité d'enseignement."""
    unite_id: int
    unite: UniteEnseignement
    groupe_ids: List[int]
    professeur_ids: List[int]
    heures_prevues: float
    type_module: str
    code_fusion: Optional[str] = None
    est_passage: bool = False


class CalculateurHeures:
    """
    Calcule et équilibre le volume horaire pour chaque groupe et unité
    pour une semaine pédagogique donnée.
    """
    OBJECTIF_MIN_HEURES = 30.0   # 12 créneaux de 2.5h
    OBJECTIF_MAX_HEURES = 35.0   # 14 créneaux de 2.5h
    DUREE_CRENEAU = 2.5

    def __init__(self, semaine: Semaine, total_semaines_semestre: int = 16):
        self.semaine = semaine
        self.total_semaines = total_semaines_semestre

    @staticmethod
    def round_to_5(val: float) -> float:
        """Arrondi au multiple de 5h le plus proche (ou 2.5h si résidu)."""
        if val <= 0:
            return 0.0
        if val < 3.5:
            return 2.5
        rounded = round(val / 5.0) * 5.0
        return max(5.0, rounded)

    @staticmethod
    def round_to_5_only(val: float) -> float:
        """Arrondi au multiple de 5h le plus proche (2,5 est arrondi vers le haut)."""
        if val <= 0:
            return 0.0
        return max(0.0, math.floor((val + 2.5) / 5.0 + 1e-9) * 5.0)

    @staticmethod
    def plafond_multiple_de_5(val: float) -> float:
        """Plus grand multiple de 5h inférieur ou égal à val."""
        if val <= 0:
            return 0.0
        return math.floor(val / 5.0 + 1e-9) * 5.0

    @staticmethod
    def round_to_creneau(val: float) -> float:
        """Arrondi au multiple de 2.5h le plus proche."""
        if val <= 0:
            return 0.0
        return max(2.5, round(val / 2.5) * 2.5)

    def calculer(self, groupes_cibles: Optional[List[Groupe]] = None,
                 groupes_off_semaine: Optional[set] = None,
                 profs_jours_off: Optional[Dict[int, set]] = None) -> List[UnitePrevision]:
        """
        Calcule les volumes horaires hebdomadaires pour toutes les unités concernées.
        """
        groupes_off_semaine = groupes_off_semaine or set()
        profs_jours_off = profs_jours_off or {}
        num_semaine = self.semaine.numero
        semaines_restantes = max(1, self.total_semaines - num_semaine + 1)

        # 1. Sélectionner les groupes actifs
        if groupes_cibles is None:
            groupes = list(Groupe.objects.filter(actif=True).select_related('filiere'))
        else:
            groupes = list(groupes_cibles)
        groupe_ids_autorises = {g.id for g in groupes}

        # Exclure les groupes entièrement indisponibles cette semaine
        if groupes_off_semaine:
            groupes = [g for g in groupes if g.id not in groupes_off_semaine]
            groupe_ids_autorises = {g.id for g in groupes}

        # 2. Heures déjà planifiées à conserver (séances validées ou verrouillées)
        heures_planifiees_unite: Dict[int, float] = defaultdict(float)
        heures_planifiees_prof: Dict[int, float] = defaultdict(float)
        heures_planifiees_groupe: Dict[int, float] = defaultdict(float)

        seances_existantes = Seance.objects.filter(semaine=self.semaine).select_related(
            'creneau'
        ).prefetch_related('seance_groupes')
        for seance in seances_existantes:
            if not (seance.verrouillee or seance.statut == Seance.STATUT_VALIDE):
                continue
            duree = float(seance.creneau.duree_h or self.DUREE_CRENEAU)
            heures_planifiees_unite[seance.unite_id] += duree
            if seance.professeur_id:
                heures_planifiees_prof[seance.professeur_id] += duree
            for sg in seance.seance_groupes.all():
                heures_planifiees_groupe[sg.groupe_id] += duree

        # 3. Récupérer toutes les unités liées aux groupes actifs pour le semestre
        unites_queryset = UniteEnseignement.objects.filter(
            unite_groupes__groupe__in=groupes,
            annee_scolaire=self.semaine.annee_scolaire,
            semestre=self.semaine.semestre,
        ).select_related('module', 'volume_horaire').prefetch_related(
            'unite_groupes__groupe',
            'unite_professeurs__professeur',
            'passages'
        ).distinct()

        # Dictionnaires de calcul
        unite_heures: Dict[int, float] = {}
        dispo_unite: Dict[int, float] = {}
        unite_obj_map: Dict[int, UniteEnseignement] = {}
        unite_groupes_map: Dict[int, List[int]] = {}
        unite_profs_map: Dict[int, List[int]] = {}
        unite_is_passage_map: Dict[int, bool] = {}

        # Initialisation + déduplication des unités strictement identiques
        profs_actifs = sorted(
            Professeur.objects.filter(actif=True).values_list('id', flat=True)
        )
        profs_actifs_ids = set(profs_actifs)
        module_profs: Dict[int, List[int]] = defaultdict(list)
        for up in UniteProfesseur.objects.filter(
            mode='presentiel', unite__semestre=self.semaine.semestre
        ).select_related('unite'):
            if up.professeur_id in profs_actifs_ids:
                module_profs[up.unite.module_id].append(up.professeur_id)
        for module_id in list(module_profs):
            module_profs[module_id] = sorted(set(module_profs[module_id]))
        attribution_count: Dict[int, int] = defaultdict(int)

        unites_vues = set()
        for ue in unites_queryset:
            unite_id = ue.id
            groupe_ids = sorted({
                ug.groupe_id for ug in ue.unite_groupes.all()
                if ug.groupe_id in groupe_ids_autorises
            })
            if not groupe_ids:
                continue
            prof_ids = sorted({
                up.professeur_id for up in ue.unite_professeurs.all()
                if up.mode == 'presentiel'
            })

            # Certaines unités importées n'ont aucun formateur affecté :
            # on attribue un formateur de secours (même module de préférence).
            if not prof_ids and profs_actifs:
                candidats = module_profs.get(ue.module_id) or profs_actifs
                prof_ids = [
                    min(candidats, key=lambda pid: (attribution_count[pid], pid))
                ]
                attribution_count[prof_ids[0]] += 1

            # Si tous les formateurs de l'unité sont indisponibles toute la semaine,
            # on ne planifie pas cette unité pour cette semaine.
            if prof_ids and profs_jours_off and all(
                len(profs_jours_off.get(pid, ())) >= 6 for pid in prof_ids
            ):
                continue

            # Déduplication : même module, même fusion, mêmes groupes et mêmes profs
            cle = (ue.module_id, ue.code_fusion or '', tuple(groupe_ids), tuple(prof_ids))
            if cle in unites_vues:
                continue
            unites_vues.add(cle)

            unite_obj_map[unite_id] = ue
            unite_groupes_map[unite_id] = groupe_ids
            unite_profs_map[unite_id] = prof_ids
            unite_is_passage_map[unite_id] = False

            volume = getattr(ue, 'volume_horaire', None)
            dispo = 0.0
            if volume:
                dispo = max(
                    0.0,
                    float(volume.heures_restantes) - heures_planifiees_unite.get(unite_id, 0.0),
                )
            dispo_unite[unite_id] = dispo

            if dispo <= 0:
                unite_heures[unite_id] = 0.0
                continue

            module = ue.module
            autorise_2_5 = bool(getattr(module, 'peut_avoir_seance_2_5', False))
            if module.type_module == 'general':
                # Module général : Vérification du Passage actif
                active_passage = ue.passages.filter(
                    actif=True,
                    semaine_debut__lte=num_semaine,
                    semaine_fin__gte=num_semaine
                ).first()

                if active_passage:
                    heures = min(float(active_passage.intensite_h), dispo)
                    if autorise_2_5:
                        unite_heures[unite_id] = self.round_to_creneau(heures)
                    else:
                        unite_heures[unite_id] = min(
                            self.round_to_5_only(heures),
                            self.plafond_multiple_de_5(dispo),
                        )
                    unite_is_passage_map[unite_id] = True
                else:
                    # En dehors de la période de passage
                    unite_heures[unite_id] = 0.0
            else:
                # Module technique : Formule basée sur les semaines restantes
                heures_hebdo_brut = dispo / semaines_restantes
                if autorise_2_5:
                    heures_arrondies = self.round_to_5(heures_hebdo_brut)
                    heures_arrondies = min(heures_arrondies, dispo)
                    # Arrondir au multiple de 2.5h (créneau)
                    unite_heures[unite_id] = self.round_to_creneau(heures_arrondies)
                else:
                    # Séances de 5 h uniquement : multiple de 5 sans dépasser le reste
                    heures_arrondies = self.round_to_5_only(heures_hebdo_brut)
                    heures_arrondies = min(heures_arrondies, self.plafond_multiple_de_5(dispo))
                    unite_heures[unite_id] = heures_arrondies

        # Charges courantes
        charge_prof: Dict[int, float] = defaultdict(float)
        total_groupe: Dict[int, float] = defaultdict(float)
        for pid, heures in heures_planifiees_prof.items():
            charge_prof[pid] += heures
        for gid, heures in heures_planifiees_groupe.items():
            total_groupe[gid] += heures

        for uid, heures in unite_heures.items():
            if heures <= 0:
                continue
            for pid in unite_profs_map[uid]:
                charge_prof[pid] += heures
            for gid in unite_groupes_map[uid]:
                total_groupe[gid] += heures

        prof_max: Dict[int, float] = {
            p.id: float(p.heures_max_semaine)
            for p in Professeur.objects.filter(actif=True)
            if p.heures_max_semaine
        }

        groupe_unites_map: Dict[int, List[int]] = defaultdict(list)
        for uid, gids in unite_groupes_map.items():
            for gid in gids:
                groupe_unites_map[gid].append(uid)

        prof_unites_map: Dict[int, List[int]] = defaultdict(list)
        for uid, pids in unite_profs_map.items():
            for pid in pids:
                prof_unites_map[pid].append(uid)

        # ─── Helpers de capacité ────────────────────────────────────────────────
        def capacite_ok(uid: int, increment: float) -> bool:
            for pid in unite_profs_map.get(uid, []):
                max_h = prof_max.get(pid)
                if max_h and charge_prof[pid] + increment > max_h + 1e-6:
                    return False
            return True

        def ajouter(uid: int, increment: float) -> None:
            unite_heures[uid] += increment
            for pid in unite_profs_map.get(uid, []):
                charge_prof[pid] += increment
            for gid in unite_groupes_map.get(uid, []):
                total_groupe[gid] += increment

        def retirer(uid: int, decrement: float) -> None:
            decrement = min(decrement, unite_heures[uid])
            if decrement <= 0:
                return
            unite_heures[uid] -= decrement
            for pid in unite_profs_map.get(uid, []):
                charge_prof[pid] -= decrement
            for gid in unite_groupes_map.get(uid, []):
                total_groupe[gid] -= decrement

        def pas_min(uid: int) -> float:
            """Pas d'ajustement : 5 h par défaut, 2,5 h si le module l'autorise."""
            module = unite_obj_map[uid].module
            return 2.5 if getattr(module, 'peut_avoir_seance_2_5', False) else 5.0

        def prochain_pas(uid: int, reste: float, besoin: float) -> float:
            """Retourne 0 si aucun ajustement n'est possible, sinon 5 h ou 2,5 h."""
            pas = pas_min(uid)
            if pas >= 5.0 - 1e-6:
                if reste < 5.0 - 1e-6 or besoin < 5.0 - 1e-6:
                    return 0.0
                return 5.0
            if reste < 2.5 - 1e-6 or besoin < 2.5 - 1e-6:
                return 0.0
            if reste >= 5.0 - 1e-6 and besoin >= 5.0 - 1e-6:
                return 5.0
            return 2.5

        # ─── 4. Équilibrage par Groupe (entre 30h et 35h par semaine) ──────────
        for groupe in groupes:
            gid = groupe.id
            uids = groupe_unites_map.get(gid, [])
            if not uids:
                continue

            total_h = total_groupe.get(gid, 0.0)

            # Si en dessous de l'objectif minimal, on augmente les modules techniques
            if total_h < self.OBJECTIF_MIN_HEURES:
                deficit = self.OBJECTIF_MIN_HEURES - total_h
                uids_techniques = [
                    uid for uid in uids
                    if unite_obj_map[uid].module.type_module == 'technique'
                ]
                uids_techniques.sort(
                    key=lambda uid: (dispo_unite.get(uid, 0.0) - unite_heures.get(uid, 0.0)),
                    reverse=True
                )

                for uid in uids_techniques:
                    while deficit >= self.DUREE_CRENEAU - 1e-6:
                        reste = dispo_unite.get(uid, 0.0) - unite_heures.get(uid, 0.0)
                        step = prochain_pas(uid, reste, deficit)
                        if step <= 0:
                            break
                        if not capacite_ok(uid, step) and step > pas_min(uid) + 1e-6:
                            step = pas_min(uid)
                        if not capacite_ok(uid, step):
                            break
                        ajouter(uid, step)
                        deficit -= step

            # Si au-delà de l'objectif maximal, on réduit les modules techniques
            elif total_h > self.OBJECTIF_MAX_HEURES:
                exces = total_h - self.OBJECTIF_MAX_HEURES
                uids_techniques = [
                    uid for uid in uids
                    if unite_obj_map[uid].module.type_module == 'technique'
                    and unite_heures.get(uid, 0.0) > self.DUREE_CRENEAU
                ]
                uids_techniques.sort(key=lambda uid: unite_heures.get(uid, 0.0), reverse=True)

                for uid in uids_techniques:
                    while exces >= self.DUREE_CRENEAU - 1e-6:
                        pas = pas_min(uid)
                        dispo_uid = unite_heures.get(uid, 0.0)
                        if dispo_uid < pas - 1e-6:
                            break
                        # Pour un module en blocs de 5 h, ne pas sur-réduire de 2,5 h.
                        if pas >= 5.0 - 1e-6 and exces < 5.0 - 1e-6:
                            break
                        retirer(uid, pas)
                        exces -= pas

        # ─── 5. Respect du plafond hebdomadaire des formateurs ─────────────────
        # On réduit les unités excédentaires, y compris les passages si nécessaire.
        for pid, uids in prof_unites_map.items():
            max_h = prof_max.get(pid)
            if not max_h:
                continue

            while charge_prof[pid] > max_h + 1e-6:
                candidats = [
                    uid for uid in uids
                    if unite_heures.get(uid, 0.0) >= pas_min(uid) - 1e-6
                ]
                if not candidats:
                    break

                def cle_reduction(uid: int):
                    # Réduire d'abord les modules techniques, puis les groupes
                    # les plus chargés, afin de préserver les groupes fragiles.
                    charge_groupe_max = max(
                        (total_groupe.get(g, 0.0) for g in unite_groupes_map.get(uid, [])),
                        default=0.0,
                    )
                    return (
                        1 if unite_is_passage_map.get(uid, False) else 0,
                        -charge_groupe_max,
                        -unite_heures.get(uid, 0.0),
                    )

                candidats.sort(key=cle_reduction)
                uid = candidats[0]
                pas = pas_min(uid)
                if unite_heures.get(uid, 0.0) < pas - 1e-6:
                    break
                retirer(uid, pas)

        # ─── 6. Rééquilibrage des groupes après réduction des formateurs ──────
        for gid in sorted(groupe_ids_autorises, key=lambda g: total_groupe.get(g, 0.0)):
            deficit = self.OBJECTIF_MIN_HEURES - total_groupe.get(gid, 0.0)
            if deficit < self.DUREE_CRENEAU - 1e-6:
                continue

            uids = [
                uid for uid in groupe_unites_map.get(gid, [])
                if unite_obj_map[uid].module.type_module == 'technique'
            ]
            uids.sort(
                key=lambda uid: (dispo_unite.get(uid, 0.0) - unite_heures.get(uid, 0.0)),
                reverse=True
            )

            for uid in uids:
                while deficit >= self.DUREE_CRENEAU - 1e-6:
                    reste = dispo_unite.get(uid, 0.0) - unite_heures.get(uid, 0.0)
                    step = prochain_pas(uid, reste, deficit)
                    if step <= 0:
                        break

                    # Ne pas dépasser l'objectif maximal d'un groupe desservi
                    if any(
                        total_groupe.get(g, 0.0) + step > self.OBJECTIF_MAX_HEURES
                        for g in unite_groupes_map.get(uid, [])
                    ):
                        step = pas_min(uid)
                        if any(
                            total_groupe.get(g, 0.0) + step > self.OBJECTIF_MAX_HEURES
                            for g in unite_groupes_map.get(uid, [])
                        ):
                            break

                    if not capacite_ok(uid, step) and step > pas_min(uid) + 1e-6:
                        step = pas_min(uid)
                    if not capacite_ok(uid, step):
                        break

                    ajouter(uid, step)
                    deficit -= step

        # ─── 7. Construction des prévisions finales ────────────────────────────
        previsions: List[UnitePrevision] = []
        for uid, heures in unite_heures.items():
            if heures <= 0:
                continue
            ue = unite_obj_map[uid]
            previsions.append(
                UnitePrevision(
                    unite_id=uid,
                    unite=ue,
                    groupe_ids=unite_groupes_map[uid],
                    professeur_ids=unite_profs_map[uid],
                    heures_prevues=heures,
                    type_module=ue.module.type_module,
                    code_fusion=ue.code_fusion,
                    est_passage=unite_is_passage_map[uid],
                )
            )

        return previsions
