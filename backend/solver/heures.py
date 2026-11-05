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
    Professeur, Seance, UniteProfesseur, AffectationEnseignement, UniteGroupe,
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
    derniere_semaine: bool = False
    jour_efm: Optional[int] = None
    efm_simple: bool = False


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
        """Calcule les prévisions à partir des paramètres de l'interface admin.

        Pour chaque groupe, les modules planifiés sont ceux cochés dans sa
        filière, avec les heures/semaine définies sur le module. Les formateurs
        sont ceux affectés au couple (module, groupe) dans la fiche formateur ;
        si aucun n'est affecté, les séances sont générées sans formateur.
        """
        groupes_off_semaine = groupes_off_semaine or set()
        profs_jours_off = profs_jours_off or {}

        if groupes_cibles is None:
            groupes = list(
                Groupe.objects.filter(actif=True)
                .select_related('filiere')
                .prefetch_related('filiere__modules')
            )
        else:
            ids = [g.id for g in groupes_cibles]
            groupes = list(
                Groupe.objects.filter(id__in=ids, actif=True)
                .select_related('filiere')
                .prefetch_related('filiere__modules')
            )
        groupes = [g for g in groupes if g.id not in groupes_off_semaine]
        if not groupes:
            return []

        num_semaine = self.semaine.numero

        # Calendrier des semaines pour situer la date de l'EFM d'un module.
        semaines_dates = list(
            Semaine.objects.filter(annee_scolaire=self.semaine.annee_scolaire)
            .exclude(date_debut__isnull=True)
            .exclude(date_fin__isnull=True)
            .values_list('numero', 'date_debut', 'date_fin')
        )

        def semaine_de(date_efm) -> Optional[int]:
            for numero, debut, fin in semaines_dates:
                if debut <= date_efm <= fin:
                    return numero
            return None

        # Heures déjà planifiées et conservées pour la semaine.
        heures_planifiees_unite: Dict[int, float] = defaultdict(float)
        for seance in Seance.objects.filter(semaine=self.semaine).select_related('creneau'):
            if not (seance.verrouillee or seance.statut == Seance.STATUT_VALIDE):
                continue
            heures_planifiees_unite[seance.unite_id] += float(
                seance.creneau.duree_h or self.DUREE_CRENEAU
            )

        # Unités ayant déjà reçu un EFM dans une autre semaine (évite les doublons).
        unites_avec_efm = set(
            Seance.objects.filter(nature=Seance.NATURE_EXAMEN)
            .exclude(semaine=self.semaine)
            .values_list('unite_id', flat=True)
        )

        # Regrouper les besoins par (module, unité d'enseignement).
        lignes: Dict[tuple, Dict[str, object]] = {}
        for groupe in groupes:
            if not groupe.filiere_id:
                continue
            for module in groupe.filiere.modules.all():
                ue = self._unite_pour_module(module, groupe)
                if ue is None:
                    continue
                cle = (module.id, ue.id)
                if cle not in lignes:
                    lignes[cle] = {
                        'module': module,
                        'unite': ue,
                        'groupe_ids': set(),
                    }
                lignes[cle]['groupe_ids'].add(groupe.id)

        previsions: List[UnitePrevision] = []
        for (module_id, unite_id), info in lignes.items():
            module = info['module']
            ue = info['unite']
            groupe_ids = sorted(info['groupe_ids'])

            heures = float(getattr(module, 'heures_hebdomadaires', 0.0) or 0.0)
            if heures <= 0:
                continue
            if getattr(module, 'peut_avoir_seance_2_5', False):
                heures = self.round_to_creneau(heures)
            else:
                heures = self.plafond_multiple_de_5(heures)
            heures -= heures_planifiees_unite.get(unite_id, 0.0)
            if heures <= 0:
                continue

            prof_ids = sorted({
                a.professeur_id
                for a in AffectationEnseignement.objects.filter(
                    module_id=module_id,
                    groupe_id__in=groupe_ids,
                    professeur__actif=True,
                )
            })

            # Tous les formateurs affectés sont indisponibles toute la semaine.
            if prof_ids and profs_jours_off and all(
                len(profs_jours_off.get(pid, ())) >= 6 for pid in prof_ids
            ):
                continue

            date_efm = getattr(module, 'date_efm', None)
            semaine_efm = semaine_de(date_efm) if date_efm else None
            est_semaine_efm = semaine_efm is not None and semaine_efm == num_semaine
            efm_actif = (
                bool(getattr(module, 'efm_fin_module', False))
                and semaine_efm is not None
            )

            derniere_semaine = False
            if unite_id not in unites_avec_efm and efm_actif:
                derniere_semaine = num_semaine >= semaine_efm

            jour_efm = None
            if est_semaine_efm and date_efm and self.semaine.date_debut:
                jour = (date_efm - self.semaine.date_debut).days + 1
                if 1 <= jour <= 6:
                    jour_efm = jour

            previsions.append(
                UnitePrevision(
                    unite_id=unite_id,
                    unite=ue,
                    groupe_ids=groupe_ids,
                    professeur_ids=prof_ids,
                    heures_prevues=heures,
                    type_module=module.type_module,
                    code_fusion=ue.code_fusion,
                    est_passage=False,
                    derniere_semaine=derniere_semaine,
                    jour_efm=jour_efm,
                    efm_simple=False,
                )
            )

        return previsions

    def _unite_pour_module(self, module, groupe) -> Optional[UniteEnseignement]:
        """Retourne l'unité (module, groupe) existante, ou la crée.

        L'unité sert uniquement de support aux séances générées ; les volumes
        horaires ne sont plus utilisés, les heures venant du module.
        """
        base = UniteEnseignement.objects.filter(
            module=module,
            annee_scolaire=self.semaine.annee_scolaire,
            unite_groupes__groupe=groupe,
        ).distinct()
        ue = base.filter(semestre=self.semaine.semestre).order_by('id').first()
        if ue is None:
            ue = base.order_by('id').first()
        if ue is not None:
            return ue

        ue = UniteEnseignement.objects.create(
            module=module,
            annee_scolaire=self.semaine.annee_scolaire,
            semestre=self.semaine.semestre,
        )
        UniteGroupe.objects.get_or_create(unite=ue, groupe=groupe)
        return ue

    def _calculer_par_unites(self, groupes_cibles: Optional[List[Groupe]] = None,
                 groupes_off_semaine: Optional[set] = None,
                 profs_jours_off: Optional[Dict[int, set]] = None) -> List[UnitePrevision]:
        """
        Calcule les volumes horaires hebdomadaires pour toutes les unités concernées.
        """
        groupes_off_semaine = groupes_off_semaine or set()
        profs_jours_off = profs_jours_off or {}
        num_semaine = self.semaine.numero
        semaines_restantes = max(1, self.total_semaines - num_semaine + 1)

        # Calendrier des semaines pour situer la date de l'EFM d'un module.
        semaines_dates = list(
            Semaine.objects.filter(annee_scolaire=self.semaine.annee_scolaire)
            .exclude(date_debut__isnull=True)
            .exclude(date_fin__isnull=True)
            .values_list('numero', 'date_debut', 'date_fin')
        )

        def semaine_de(date_efm) -> Optional[int]:
            """Numéro de la semaine pédagogique contenant une date donnée."""
            for numero, debut, fin in semaines_dates:
                if debut <= date_efm <= fin:
                    return numero
            return None

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
        unite_est_semaine_efm: Dict[int, bool] = {}
        unite_jour_efm: Dict[int, Optional[int]] = {}
        unite_efm_simple: Dict[int, bool] = {}
        plafond_unite: Dict[int, float] = {}

        # Unités ayant déjà reçu un EFM dans une autre semaine (évite les doublons).
        unites_avec_efm = set(
            Seance.objects.filter(nature=Seance.NATURE_EXAMEN)
            .exclude(semaine=self.semaine)
            .values_list('unite_id', flat=True)
        )

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

        # Complément : modules déclarés directement sur la fiche formateur.
        # Ils servent uniquement de secours quand aucune unité d'enseignement
        # n'explicite déjà les formateurs du module.
        for prof_id, module_id in (
            Professeur.modules.through.objects
            .filter(professeur__actif=True)
            .values_list('professeur_id', 'module_id')
        ):
            if module_id not in module_profs:
                module_profs[module_id] = []
            if prof_id not in module_profs[module_id]:
                module_profs[module_id].append(prof_id)
        for module_id in module_profs:
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

            # Période d'étude : si une date d'EFM est fixée, le module doit être
            # terminé dans la semaine qui contient cette date.
            date_efm = getattr(module, 'date_efm', None)
            semaine_efm = semaine_de(date_efm) if date_efm else None
            est_semaine_efm = semaine_efm is not None and semaine_efm == num_semaine
            efm_actif = bool(getattr(module, 'efm_fin_module', False)) and semaine_efm is not None

            if semaine_efm is not None and num_semaine < semaine_efm:
                # Semaines d'enseignement restantes avant la semaine de l'EFM.
                semaines_pour_module = max(1, semaine_efm - num_semaine)
            elif semaine_efm is not None:
                semaines_pour_module = 1
            else:
                semaines_pour_module = semaines_restantes

            # Plafond : on réserve de quoi planifier l'EFM dans sa semaine afin
            # que le module ne se termine pas avant la date prévue.
            plafond = dispo
            if efm_actif and num_semaine < semaine_efm:
                if autorise_2_5:
                    reserve = self.DUREE_CRENEAU
                    pas = self.DUREE_CRENEAU
                    disponible_enseignement = max(0.0, dispo - reserve)
                    plafond = (disponible_enseignement // pas) * pas
                else:
                    # Module en blocs de 5 h uniquement : on réserve un bloc
                    # complet (5 h) pour la semaine de l'EFM. Aucun résidu de
                    # 2,5 h ne doit être planifié avant ou pendant l'EFM.
                    disponible_enseignement = max(0.0, dispo - 5.0)
                    plafond = self.plafond_multiple_de_5(disponible_enseignement)
            plafond_unite[unite_id] = plafond

            unite_est_semaine_efm[unite_id] = est_semaine_efm
            jour_efm = None
            if est_semaine_efm and date_efm and self.semaine.date_debut:
                jour = (date_efm - self.semaine.date_debut).days + 1
                if 1 <= jour <= 6:
                    jour_efm = jour
            unite_jour_efm[unite_id] = jour_efm

            if module.type_module == 'general':
                # Module général : Vérification du Passage actif
                active_passage = ue.passages.filter(
                    actif=True,
                    semaine_debut__lte=num_semaine,
                    semaine_fin__gte=num_semaine
                ).first()

                if active_passage:
                    heures = min(float(active_passage.intensite_h), plafond)
                    if autorise_2_5:
                        unite_heures[unite_id] = self.round_to_creneau(heures)
                    else:
                        unite_heures[unite_id] = min(
                            self.round_to_5_only(heures),
                            self.plafond_multiple_de_5(plafond),
                        )
                    unite_is_passage_map[unite_id] = True
                else:
                    # En dehors de la période de passage
                    unite_heures[unite_id] = 0.0
            else:
                # Module technique : Formule basée sur les semaines restantes
                heures_hebdo_brut = plafond / semaines_pour_module
                if autorise_2_5:
                    heures_arrondies = self.round_to_5(heures_hebdo_brut)
                    heures_arrondies = min(heures_arrondies, plafond)
                    # Arrondir au multiple de 2.5h (créneau)
                    unite_heures[unite_id] = self.round_to_creneau(heures_arrondies)
                else:
                    # Séances de 5 h uniquement : multiple de 5 sans dépasser le reste
                    heures_arrondies = self.round_to_5_only(heures_hebdo_brut)
                    heures_arrondies = min(heures_arrondies, self.plafond_multiple_de_5(plafond))
                    unite_heures[unite_id] = heures_arrondies

                    # Semaine de l'EFM : on termine le module en blocs de 5 h.
                    # Un éventuel résidu de 2,5 h n'est pas planifié : aucune
                    # séance isolée de 2,5 h pour un module qui ne l'autorise pas.
                    if est_semaine_efm and efm_actif:
                        unite_heures[unite_id] = self.plafond_multiple_de_5(dispo)

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

        def ajouter(uid: int, increment: float) -> float:
            plafond = plafond_unite.get(uid)
            if plafond is not None:
                increment = min(increment, plafond - unite_heures.get(uid, 0.0))
            if increment <= 1e-6:
                return 0.0
            unite_heures[uid] += increment
            for pid in unite_profs_map.get(uid, []):
                charge_prof[pid] += increment
            for gid in unite_groupes_map.get(uid, []):
                total_groupe[gid] += increment
            return increment

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
                        reste = plafond_unite.get(uid, dispo_unite.get(uid, 0.0)) - unite_heures.get(uid, 0.0)
                        step = prochain_pas(uid, reste, deficit)
                        if step <= 0:
                            break
                        if not capacite_ok(uid, step) and step > pas_min(uid) + 1e-6:
                            step = pas_min(uid)
                        if not capacite_ok(uid, step):
                            break
                        ajoute = ajouter(uid, step)
                        if ajoute <= 0:
                            break
                        deficit -= ajoute

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
                    reste = plafond_unite.get(uid, dispo_unite.get(uid, 0.0)) - unite_heures.get(uid, 0.0)
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

                    ajoute = ajouter(uid, step)
                    if ajoute <= 0:
                        break
                    deficit -= ajoute

        # ─── 7. Construction des prévisions finales ────────────────────────────
        previsions: List[UnitePrevision] = []
        for uid, heures in unite_heures.items():
            if heures <= 0:
                continue
            ue = unite_obj_map[uid]
            dispo_initiale = dispo_unite.get(uid, 0.0)
            semaine_efm = None
            date_efm = getattr(ue.module, 'date_efm', None)
            if date_efm:
                semaine_efm = semaine_de(date_efm)

            if uid in unites_avec_efm:
                # Un EFM existe déjà pour cette unité dans une autre semaine.
                derniere_semaine = False
            elif semaine_efm is not None:
                # Avec une date d'EFM, l'examen n'est marqué que dans la
                # semaine de l'EFM (ou après si le module est en retard).
                derniere_semaine = num_semaine >= semaine_efm
            else:
                # Sans date : le module se termine cette semaine s'il ne reste
                # au plus qu'un créneau de 2,5 h (résidu éventuel de l'EFM).
                derniere_semaine = (
                    dispo_initiale > 0
                    and (dispo_initiale - heures) <= self.DUREE_CRENEAU + 1e-6
                )

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
                    derniere_semaine=derniere_semaine,
                    jour_efm=unite_jour_efm.get(uid),
                    efm_simple=unite_efm_simple.get(uid, False),
                )
            )

        return previsions
