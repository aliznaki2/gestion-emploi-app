"""Chargement des données de génération (classe ``Donnees``).

Cette classe centralise toutes les lectures faites par le moteur : semaine,
groupes, formateurs, salles, créneaux, unités d'enseignement, volumes horaires,
passages et paramètres.  Elle remplace le chargeur SQL de l'implémentation de
référence par des requêtes ORM Django.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List, Optional, Set, Tuple

from django.db.models import Q

from core.models import (
    Creneau,
    Groupe,
    Indisponibilite,
    Module,
    Passage,
    Professeur,
    Salle,
    Semaine,
    UniteEnseignement,
)


@dataclass
class ParametresDonnees:
    """Paramètres du moteur (valeurs par défaut du document)."""

    heures_groupe_min: float = 30.0
    heures_groupe_max: float = 35.0
    passage_intensite_defaut_h: float = 5.0
    passage_plafond_groupe_h: float = 10.0
    duree_max_solveur_s: int = 60
    plafond_professeur_defaut_h: float = 30.0


@dataclass
class Donnees:
    """Instantané des données nécessaires à une génération de semaine."""

    semaine: Semaine
    semestre: object
    n_sem: int
    creneaux: List[Creneau]
    creneaux_fermes: Set[int]
    groupes: List[Groupe]
    professeurs: List[Professeur]
    salles: List[Salle]
    unites: List[UniteEnseignement]
    passages_actifs: List[Passage]
    types_salle_module: Dict[int, List[str]] = field(default_factory=dict)
    params: ParametresDonnees = field(default_factory=ParametresDonnees)

    # ─── Index ────────────────────────────────────────────────────────────────
    @property
    def creneaux_map(self) -> Dict[int, Creneau]:
        return {c.id: c for c in self.creneaux}

    @property
    def creneaux_par_jour(self) -> Dict[int, List[Creneau]]:
        result: Dict[int, List[Creneau]] = {}
        for c in self.creneaux:
            result.setdefault(c.jour, []).append(c)
        return result

    @property
    def groupes_map(self) -> Dict[int, Groupe]:
        return {g.id: g for g in self.groupes}

    @property
    def professeurs_map(self) -> Dict[int, Professeur]:
        return {p.id: p for p in self.professeurs}

    @property
    def unites_map(self) -> Dict[int, UniteEnseignement]:
        return {u.id: u for u in self.unites}

    # ─── Chargement ──────────────────────────────────────────────────────────
    @classmethod
    def charger(cls, semaine_id: int, groupes_ids: Optional[Iterable[int]] = None) -> "Donnees":
        """Charge toutes les données utiles pour la semaine demandée."""
        semaine = (
            Semaine.objects.select_related('annee_scolaire', 'semestre')
            .get(pk=semaine_id)
        )

        # Nombre de semaines de cours restantes (semaine courante comprise).
        semaines_qs = Semaine.objects.filter(numero__gte=semaine.numero)
        if semaine.semestre_id:
            semaines_qs = semaines_qs.filter(semestre_id=semaine.semestre_id)
        else:
            semaines_qs = semaines_qs.filter(annee_scolaire_id=semaine.annee_scolaire_id)
        n_sem = max(1, semaines_qs.count())

        # Créneaux et jours fermés.
        creneaux = list(Creneau.objects.all().order_by('jour', 'numero_seance'))
        creneaux_fermes = cls._creneaux_fermes(semaine, creneaux)

        # Groupes / formateurs / salles actifs.
        groupes_qs = Groupe.objects.filter(actif=True).select_related('filiere').prefetch_related(
            'filiere__modules'
        )
        if groupes_ids:
            groupes_qs = groupes_qs.filter(id__in=list(groupes_ids))
        groupes = list(groupes_qs)
        groupes.sort(key=lambda g: (g.code or '', g.id))

        professeurs = list(
            Professeur.objects.filter(actif=True).select_related(
                'salle_preferee', 'salle_preferee_matin', 'salle_preferee_apm'
            )
        )
        salles = list(Salle.objects.filter(actif=True).select_related('type_salle'))

        # Unités d'enseignement du semestre (ou non rattachées à un semestre).
        unites_qs = (
            UniteEnseignement.objects.filter(annee_scolaire_id=semaine.annee_scolaire_id)
            .select_related('module', 'volume_horaire')
            .prefetch_related(
                'unite_groupes__groupe',
                'unite_professeurs__professeur',
                'passages',
                'module__prerequis',
            )
        )
        if semaine.semestre_id:
            unites_qs = unites_qs.filter(
                Q(semestre_id=semaine.semestre_id) | Q(semestre__isnull=True)
            )
        unites = list(unites_qs)

        passages_actifs = [
            p for u in unites for p in u.passages.all() if p.actif
        ]

        # Types de salles acceptés par module.
        types_salle_module: Dict[int, List[str]] = {}
        for module in Module.objects.prefetch_related('types_salles_compatibles'):
            codes = [t.code for t in module.types_salles_compatibles.all()]
            if codes:
                types_salle_module[module.id] = codes

        return cls(
            semaine=semaine,
            semestre=semaine.semestre,
            n_sem=n_sem,
            creneaux=creneaux,
            creneaux_fermes=creneaux_fermes,
            groupes=groupes,
            professeurs=professeurs,
            salles=salles,
            unites=unites,
            passages_actifs=passages_actifs,
            types_salle_module=types_salle_module,
        )

    # ─── Helpers métier ──────────────────────────────────────────────────────
    @staticmethod
    def _creneaux_fermes(semaine: Semaine, creneaux: List[Creneau]) -> Set[int]:
        """Créneaux fermés globalement (indisponibilité « tous »)."""
        fermes: Set[int] = set()
        dispos = Indisponibilite.objects.filter(actif=True, type_cible=Indisponibilite.TYPE_CIBLE_TOUS)
        for dispo in dispos:
            if dispo.type_periode == Indisponibilite.TYPE_PERIODE_SEMAINE:
                if dispo.semaine_id == semaine.id:
                    fermes.update(c.id for c in creneaux)
            elif dispo.type_periode == Indisponibilite.TYPE_PERIODE_JOUR:
                if dispo.semaine_id == semaine.id and dispo.jour:
                    fermes.update(c.id for c in creneaux if c.jour == dispo.jour)
            elif dispo.type_periode == Indisponibilite.TYPE_PERIODE_PERIODE:
                if _chevauche(semaine, dispo.date_debut, dispo.date_fin):
                    fermes.update(c.id for c in creneaux)
        return fermes

    def unites_du_groupe(self, groupe_id: int) -> List[UniteEnseignement]:
        """Unités rattachées à un groupe."""
        return [
            u for u in self.unites
            if any(ug.groupe_id == groupe_id for ug in u.unite_groupes.all())
        ]

    def groupes_de_unite(self, unite: UniteEnseignement) -> List[int]:
        return [ug.groupe_id for ug in unite.unite_groupes.all() if ug.groupe_id in self.groupes_map]

    def profs_presentiels(self, unite: UniteEnseignement) -> List[int]:
        return sorted({
            up.professeur_id
            for up in unite.unite_professeurs.all()
            if up.mode == 'presentiel' and up.professeur_id in self.professeurs_map
        })

    def profs_synchrones(self, unite: UniteEnseignement) -> List[int]:
        return sorted({
            up.professeur_id
            for up in unite.unite_professeurs.all()
            if up.mode == 'distance' and up.professeur_id in self.professeurs_map
        })

    def frac_sync(self, unite: UniteEnseignement) -> float:
        """Part d'heures synchrones à distance de l'unité (0 à 1)."""
        volume = getattr(unite, 'volume_horaire', None)
        if volume is None:
            return 0.0
        denominateur = float(volume.h_presentiel or 0.0) + float(volume.h_synchrone or 0.0)
        if denominateur <= 0:
            return 0.0
        return max(0.0, min(1.0, float(volume.h_synchrone or 0.0) / denominateur))

    def heures_restantes(self, unite: UniteEnseignement) -> float:
        """Heures restantes du semestre pour l'unité."""
        volume = getattr(unite, 'volume_horaire', None)
        if volume is not None and float(volume.h_presentiel or 0.0) > 0:
            return max(0.0, float(volume.h_presentiel) - float(volume.heures_effectuees or 0.0))
        heures_hebdo = float(getattr(unite.module, 'heures_hebdomadaires', 0.0) or 0.0)
        return max(0.0, heures_hebdo)

    def intensite_passage(self, unite: UniteEnseignement) -> float:
        """Intensité horaire d'un passage (existante ou paramètre par défaut)."""
        for passage in unite.passages.all():
            if passage.actif and passage.semaine_debut <= self.semaine.numero <= passage.semaine_fin:
                return float(passage.intensite_h or self.params.passage_intensite_defaut_h)
        return float(self.params.passage_intensite_defaut_h)

    def plafond_professeur(self, professeur: Professeur) -> float:
        return float(
            professeur.heures_max_semaine
            or self.params.plafond_professeur_defaut_h
        )

    def types_salle(self, unite: UniteEnseignement) -> List[str]:
        return self.types_salle_module.get(unite.module_id, ['SC'])


def _chevauche(semaine: Semaine, debut: Optional[date], fin: Optional[date]) -> bool:
    """Vrai si la période [debut, fin] chevauche la semaine."""
    if not debut or not fin:
        return False
    s_debut = semaine.date_debut or date.min
    s_fin = semaine.date_fin or semaine.date_debut or date.max
    return debut <= s_fin and fin >= s_debut
