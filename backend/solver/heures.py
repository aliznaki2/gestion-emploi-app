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

from django.db.models import Q

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
    professeur_sync_ids: List[int] = field(default_factory=list)
    frac_sync: float = 0.0


class CalculateurHeures:
    """
    Calcule et équilibre le volume horaire pour chaque groupe et unité
    pour une semaine pédagogique donnée.
    """
    OBJECTIF_MIN_HEURES = 15.0   # 3 blocs de 5 h
    OBJECTIF_MAX_HEURES = 25.0   # 5 blocs de 5 h
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

    @staticmethod
    def _heures_restantes(ue, unite_id: int, heures_consommees_unite: Dict[int, float]) -> Optional[float]:
        """Heures présentielles officielles non encore planifiées (None si volume inconnu)."""
        volume = getattr(ue, 'volume_horaire', None)
        if volume is None:
            return None
        return max(
            0.0,
            float(volume.h_presentiel or 0.0)
            - float(volume.heures_effectuees or 0.0)
            - heures_consommees_unite.get(unite_id, 0.0),
        )

    def calculer(self, groupes_cibles: Optional[List[Groupe]] = None,
                 groupes_off_semaine: Optional[set] = None,
                 profs_jours_off: Optional[Dict[int, set]] = None) -> List[UnitePrevision]:
        """Calcule les prévisions à partir des paramètres de l'interface admin.

        Pour chaque groupe, les unités planifiées sont celles qui lui sont
        réellement rattachées (``UniteGroupe``) pour le semestre courant. Les
        heures/semaine viennent du module. Les formateurs sont ceux affectés au
        couple (module, groupe) dans la fiche formateur ; si aucun n'est
        affecté, les séances sont générées sans formateur.

        Un repli sur ``filiere.modules`` reste assuré pour les groupes dont les
        unités n'ont pas encore été créées.
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

        # Volume déjà consommé par chaque unité lors des semaines précédentes.
        # Sans cela, le volume restant serait « réétalé » sur les semaines
        # restantes et les dernières semaines dépasseraient le volume prévu.
        heures_consommees_unite: Dict[int, float] = defaultdict(float)
        for unite_id, duree in Seance.objects.filter(
            semaine__annee_scolaire_id=self.semaine.annee_scolaire_id,
            semaine__numero__lt=num_semaine,
        ).values_list('unite_id', 'creneau__duree_h'):
            heures_consommees_unite[unite_id] += float(duree or self.DUREE_CRENEAU)

        # Unités ayant déjà reçu un EFM dans une autre semaine (évite les doublons).
        unites_avec_efm = set(
            Seance.objects.filter(nature=Seance.NATURE_EXAMEN)
            .exclude(semaine=self.semaine)
            .values_list('unite_id', flat=True)
        )

        # Affectations (module, groupe) → formateurs, chargées en une seule requête.
        groupe_ids_autorises = [g.id for g in groupes]
        profs_par_couple: Dict[tuple, set] = defaultdict(set)
        for module_id, groupe_id, prof_id in AffectationEnseignement.objects.filter(
            professeur__actif=True,
            groupe_id__in=groupe_ids_autorises,
        ).values_list('module_id', 'groupe_id', 'professeur_id'):
            profs_par_couple[(module_id, groupe_id)].add(prof_id)

        # Unités d'enseignement réellement rattachées aux groupes pour le
        # semestre de la semaine. C'est la source de vérité : un groupe ne suit
        # que les UE qui lui sont affectées, et non l'intégralité des modules de
        # sa filière.
        unites_qs = (
            UniteEnseignement.objects.filter(
                annee_scolaire_id=self.semaine.annee_scolaire_id,
                unite_groupes__groupe_id__in=groupe_ids_autorises,
            )
            .select_related('module', 'volume_horaire')
            .prefetch_related(
                'unite_groupes__groupe',
                'unite_professeurs__professeur',
                'passages',
            )
            .distinct()
        )
        if self.semaine.semestre_id:
            unites_qs = unites_qs.filter(
                Q(semestre_id=self.semaine.semestre_id) | Q(semestre__isnull=True)
            )

        # Regrouper les besoins par unité d'enseignement.
        lignes: Dict[int, Dict[str, object]] = {}
        unites_vues = set()
        groupes_couverts = set()
        for ue in unites_qs:
            groupe_ids = sorted({
                ug.groupe_id for ug in ue.unite_groupes.all()
                if ug.groupe_id in groupe_ids_autorises
            })
            if not groupe_ids:
                continue
            # Déduplication : même module, même fusion et mêmes groupes.
            cle = (ue.module_id, ue.code_fusion or '', tuple(groupe_ids))
            if cle in unites_vues:
                continue
            unites_vues.add(cle)
            lignes[ue.id] = {
                'module': ue.module,
                'unite': ue,
                'groupe_ids': set(groupe_ids),
            }
            groupes_couverts.update(groupe_ids)

        # Repli : un groupe sans aucune UE (données incomplètes) conserve les
        # modules déclarés sur sa filière, comme auparavant.
        for groupe in groupes:
            if groupe.id in groupes_couverts or not groupe.filiere_id:
                continue
            for module in groupe.filiere.modules.all():
                ue = self._unite_pour_module(module, groupe)
                if ue is None:
                    continue
                if ue.id not in lignes:
                    lignes[ue.id] = {
                        'module': module,
                        'unite': ue,
                        'groupe_ids': set(),
                    }
                lignes[ue.id]['groupe_ids'].add(groupe.id)

        previsions: List[UnitePrevision] = []
        for unite_id, info in lignes.items():
            module = info['module']
            ue = info['unite']
            groupe_ids = sorted(info['groupe_ids'])
            module_id = module.id

            heures = float(getattr(module, 'heures_hebdomadaires', 0.0) or 0.0)

            # Phase 0 : tous les modules (généraux, régionaux et locaux)
            # suivent leur passage. L'intensité hebdomadaire vient du
            # calendrier calculé ; hors période, aucune heure n'est planifiée.
            est_passage = False
            passages = [p for p in ue.passages.all() if p.actif]
            if passages:
                actif = next(
                    (
                        p for p in passages
                        if p.semaine_debut <= num_semaine <= p.semaine_fin
                    ),
                    None,
                )
                if actif is None:
                    # Passage terminé : si des heures manquent encore (formateur
                    # absent, semaine fermée…), on rattrape au rythme du dernier
                    # passage plutôt que de perdre ces heures définitivement.
                    derniere = max(passages, key=lambda p: p.semaine_fin)
                    if num_semaine <= derniere.semaine_fin:
                        continue          # avant le passage : rien à planifier
                    if unite_id in unites_avec_efm:
                        continue          # l'EFM de fin de module a déjà eu lieu
                    reste_h = self._heures_restantes(ue, unite_id, heures_consommees_unite)
                    if reste_h is None or reste_h <= 0:
                        continue
                    actif = derniere
                est_passage = True
                heures = float(actif.intensite_h or 0.0)

            if heures <= 0:
                continue
            if getattr(module, 'peut_avoir_seance_2_5', False):
                heures = self.round_to_creneau(heures)
            else:
                heures = self.plafond_multiple_de_5(heures)

            # Ne jamais dépasser le volume officiel restant de l'unité.
            volume = getattr(ue, 'volume_horaire', None)
            if volume is not None:
                reste = max(
                    0.0,
                    float(volume.h_presentiel or 0.0)
                    - float(volume.heures_effectuees or 0.0)
                    - heures_consommees_unite.get(unite_id, 0.0),
                )
                heures = min(heures, self.plafond_multiple_de_5(reste))

            heures -= heures_planifiees_unite.get(unite_id, 0.0)
            if heures <= 0:
                continue

            # Formateurs présents sur l'unité elle-même (source de vérité),
            # avec repli sur les besoins (module, groupe) lorsque l'unité
            # n'a aucune affectation explicite.
            prof_ids = sorted({
                up.professeur_id
                for up in ue.unite_professeurs.all()
                if up.mode == 'presentiel' and up.professeur and up.professeur.actif
            })
            if not prof_ids:
                prof_ids = sorted({
                    prof_id
                    for groupe_id in groupe_ids
                    for prof_id in profs_par_couple.get((module_id, groupe_id), ())
                })

            # Formateurs synchrones (distance) et part de synchrone de l'unité.
            prof_sync_ids = sorted({
                up.professeur_id
                for up in ue.unite_professeurs.all()
                if up.mode == 'distance' and up.professeur and up.professeur.actif
            })
            volume = getattr(ue, 'volume_horaire', None)
            frac_sync = 0.0
            if volume:
                denominateur = float(volume.h_presentiel or 0.0) + float(volume.h_synchrone or 0.0)
                if denominateur > 0:
                    frac_sync = max(
                        0.0,
                        min(1.0, float(volume.h_synchrone or 0.0) / denominateur),
                    )

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
                    est_passage=est_passage,
                    derniere_semaine=derniere_semaine,
                    jour_efm=jour_efm,
                    efm_simple=False,
                    professeur_sync_ids=prof_sync_ids,
                    frac_sync=frac_sync,
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
