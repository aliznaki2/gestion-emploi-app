"""
Phase 1 : Calculateur du volume horaire hebdomadaire par unité et par groupe.
Application des règles OFPPT pour modules généraux (passages) et techniques.
"""
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from core.models import Semaine, UniteEnseignement, Groupe, Passage, VolumeHoraire


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
    def round_to_creneau(val: float) -> float:
        """Arrondi au multiple de 2.5h le plus proche."""
        if val <= 0:
            return 0.0
        return max(2.5, round(val / 2.5) * 2.5)

    def calculer(self, groupes_cibles: Optional[List[Groupe]] = None) -> List[UnitePrevision]:
        """
        Calcule les volumes horaires hebdomadaires pour toutes les unités concernées.
        """
        num_semaine = self.semaine.numero
        semaines_restantes = max(1, self.total_semaines - num_semaine + 1)

        # 1. Sélectionner les groupes actifs
        if groupes_cibles is None:
            groupes = list(Groupe.objects.filter(actif=True).select_related('filiere'))
        else:
            groupes = list(groupes_cibles)

        # 2. Récupérer toutes les unités liées aux groupes actifs
        unites_queryset = UniteEnseignement.objects.filter(
            unite_groupes__groupe__in=groupes,
            annee_scolaire=self.semaine.annee_scolaire,
        ).select_related('module', 'volume_horaire').prefetch_related(
            'unite_groupes__groupe',
            'unite_professeurs__professeur',
            'passages'
        ).distinct()

        # Dictionnaires de calcul
        # unite_id -> volume calculé
        unite_heures: Dict[int, float] = {}
        unite_obj_map: Dict[int, UniteEnseignement] = {}
        unite_groupes_map: Dict[int, List[int]] = {}
        unite_profs_map: Dict[int, List[int]] = {}
        unite_is_passage_map: Dict[int, bool] = {}

        # Initialisation
        for ue in unites_queryset:
            unite_id = ue.id
            unite_obj_map[unite_id] = ue
            unite_groupes_map[unite_id] = [ug.groupe_id for ug in ue.unite_groupes.all()]
            unite_profs_map[unite_id] = [up.professeur_id for up in ue.unite_professeurs.filter(mode='presentiel')]
            unite_is_passage_map[unite_id] = False

            volume = getattr(ue, 'volume_horaire', None)
            if not volume:
                unite_heures[unite_id] = 0.0
                continue

            heures_restantes = volume.heures_restantes
            if heures_restantes <= 0:
                unite_heures[unite_id] = 0.0
                continue

            module = ue.module
            if module.type_module == 'general':
                # Module général : Vérification du Passage actif
                active_passage = ue.passages.filter(
                    actif=True,
                    semaine_debut__lte=num_semaine,
                    semaine_fin__gte=num_semaine
                ).first()

                if active_passage:
                    heures = min(active_passage.intensite_h, heures_restantes)
                    unite_heures[unite_id] = self.round_to_creneau(heures)
                    unite_is_passage_map[unite_id] = True
                else:
                    # En dehors de la période de passage
                    unite_heures[unite_id] = 0.0
            else:
                # Module technique : Formule basée sur les semaines restantes
                heures_hebdo_brut = heures_restantes / semaines_restantes
                heures_arrondies = self.round_to_5(heures_hebdo_brut)
                heures_arrondies = min(heures_arrondies, heures_restantes)
                # Arrondir au multiple de 2.5h (créneau)
                unite_heures[unite_id] = self.round_to_creneau(heures_arrondies)

        # 3. Équilibrage par Groupe (entre 30h et 35h par semaine)
        groupe_unites_map: Dict[int, List[int]] = {}
        for uid, gids in unite_groupes_map.items():
            for gid in gids:
                groupe_unites_map.setdefault(gid, []).append(uid)

        for groupe in groupes:
            gid = groupe.id
            uids = groupe_unites_map.get(gid, [])
            if not uids:
                continue

            total_h = sum(unite_heures.get(uid, 0.0) for uid in uids)

            # Si en dessous de l'objectif minimal (30h), on essaie d'augmenter les modules techniques
            if total_h < self.OBJECTIF_MIN_HEURES:
                deficit = self.OBJECTIF_MIN_HEURES - total_h
                # Trier les unités techniques par heures restantes décroissantes
                uids_techniques = [
                    uid for uid in uids
                    if unite_obj_map[uid].module.type_module == 'technique'
                ]
                uids_techniques.sort(
                    key=lambda uid: (
                        getattr(unite_obj_map[uid], 'volume_horaire', None).heures_restantes - unite_heures.get(uid, 0.0)
                        if getattr(unite_obj_map[uid], 'volume_horaire', None) else 0.0
                    ),
                    reverse=True
                )

                for uid in uids_techniques:
                    if deficit <= 0:
                        break
                    vol = getattr(unite_obj_map[uid], 'volume_horaire', None)
                    if not vol:
                        continue
                    dispo = vol.heures_restantes - unite_heures[uid]
                    if dispo >= 2.5:
                        increment = 5.0 if dispo >= 5.0 and deficit >= 4.0 else 2.5
                        increment = min(increment, dispo)
                        unite_heures[uid] += increment
                        deficit -= increment

            # Si au-delà de l'objectif maximal (35h), on réduit les modules techniques
            elif total_h > self.OBJECTIF_MAX_HEURES:
                exces = total_h - self.OBJECTIF_MAX_HEURES
                uids_techniques = [
                    uid for uid in uids
                    if unite_obj_map[uid].module.type_module == 'technique' and unite_heures.get(uid, 0.0) > 2.5
                ]
                uids_techniques.sort(key=lambda uid: unite_heures.get(uid, 0.0), reverse=True)

                for uid in uids_techniques:
                    if exces <= 0:
                        break
                    actuel = unite_heures[uid]
                    reduction = min(exces, 2.5 if actuel - 2.5 >= 2.5 else 0.0)
                    if reduction > 0:
                        unite_heures[uid] -= reduction
                        exces -= reduction

        # 4. Construction des prévisions finales
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

