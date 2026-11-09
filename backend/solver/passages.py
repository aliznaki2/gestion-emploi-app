"""Phase 0 : calendrier de passage des modules généraux.

Le planificateur réutilise les ``Passage`` déjà saisis comme des intervalles
fixes et ne calcule que les passages manquants avec CP-SAT.  Les passages
calculés peuvent ensuite être persistés pour que la phase 1 les utilise.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ortools.sat.python import cp_model

from core.models import Passage

from .donnees import Donnees


@dataclass
class PassagePlan:
    """Passage calculé ou existant, exprimé relativement à la semaine courante."""

    unite_id: int
    module_code: str
    debut: int                 # 0 = semaine à générer
    duree: int                 # en semaines
    retard: int                # semaines après la fin du semestre
    intensite_h: float
    source: str                # 'existant' | 'calcule'
    semaine_debut_abs: int = 0
    semaine_fin_abs: int = 0

    @property
    def fin(self) -> int:
        return self.debut + self.duree

    @property
    def actif_cette_semaine(self) -> bool:
        return self.debut <= 0 < self.fin

    def as_dict(self) -> Dict[str, object]:
        return {
            'unite_id': self.unite_id,
            'module_code': self.module_code,
            'debut': self.debut,
            'duree': self.duree,
            'retard': self.retard,
            'intensite_h': self.intensite_h,
            'source': self.source,
            'semaine_debut': self.semaine_debut_abs,
            'semaine_fin': self.semaine_fin_abs,
            'actif_cette_semaine': self.actif_cette_semaine,
        }


@dataclass
class ResultatPassages:
    plans: List[PassagePlan] = field(default_factory=list)
    statut: str = 'OK'
    message: str = ''

    def par_unite(self) -> Dict[int, PassagePlan]:
        return {p.unite_id: p for p in self.plans}

    def alertes(self) -> List[Dict[str, object]]:
        return [p.as_dict() for p in self.plans if p.retard > 0]


class PlanificateurPassages:
    """Calcule le calendrier des modules généraux sur un horizon élargi."""

    def __init__(self, donnees: Donnees, horizon_supplementaire: int = 8):
        self.d = donnees
        self.horizon = max(1, donnees.n_sem + horizon_supplementaire)
        self.resultat: Optional[ResultatPassages] = None

    # ─── Calcul ──────────────────────────────────────────────────────────────
    def calculer(self, duree_max_s: float = 20.0) -> ResultatPassages:
        """Calcule les passages manquants et conserve les passages existants."""
        existants = self._passages_existants()
        unites = self._unites_a_planifier()

        if not unites:
            self.resultat = ResultatPassages(
                plans=existants,
                statut='OK',
                message='Aucun passage manquant à calculer.',
            )
            return self.resultat

        model = cp_model.CpModel()
        num_semaine = self.d.semaine.numero
        # CP-SAT travaille avec des entiers : on exprime les heures en
        # demi-heures pour rester exact avec des intensités de 2,5 h.
        echelle = 2
        plafond_groupe = int(round(float(self.d.params.passage_plafond_groupe_h) * echelle))
        intensite = int(round(float(self.d.params.passage_intensite_defaut_h) * echelle))
        intensite_h = float(self.d.params.passage_intensite_defaut_h)

        variables: Dict[int, Dict[str, object]] = {}
        actifs: Dict[tuple, object] = {}

        for unite in unites:
            restantes = self.d.heures_restantes(unite)
            duree = max(1, int(math.ceil(restantes / intensite_h))) if intensite_h > 0 else 1
            duree = min(duree, self.horizon)
            debut = model.NewIntVar(0, self.horizon - duree, f'd_{unite.id}')
            fin = model.NewIntVar(duree, self.horizon, f'f_{unite.id}')
            model.Add(fin == debut + duree)
            retard = model.NewIntVar(0, self.horizon, f'r_{unite.id}')
            model.Add(retard >= fin - self.d.n_sem)
            model.Add(retard >= 0)
            variables[unite.id] = {
                'unite': unite,
                'debut': debut,
                'fin': fin,
                'retard': retard,
                'duree': duree,
                'intensite': intensite_h,
            }

            # Variables d'activité semaine par semaine.
            # Trois états exclusifs : avant (fin <= semaine), pendant
            # (debut <= semaine < fin) ou après (debut >= semaine + 1).
            # L'encodage précédent imposait deux bornes contradictoires au
            # cas inactif et rendait le modèle irréalisable.
            for semaine in range(self.horizon):
                avant = model.NewBoolVar(f'av_{unite.id}_{semaine}')
                apres = model.NewBoolVar(f'ap_{unite.id}_{semaine}')
                model.Add(fin <= semaine).OnlyEnforceIf(avant)
                model.Add(fin >= semaine + 1).OnlyEnforceIf(avant.Not())
                model.Add(debut >= semaine + 1).OnlyEnforceIf(apres)
                model.Add(debut <= semaine).OnlyEnforceIf(apres.Not())
                a = model.NewBoolVar(f'a_{unite.id}_{semaine}')
                model.Add(a + avant + apres == 1)
                actifs[(unite.id, semaine)] = a

        # Capacités souples : un dépassement est pénalisé mais n'empêche pas
        # la génération (les passages en retard restent des alertes, pas des
        # erreurs bloquantes).  Cela évite un INFEASIBLE dès qu'un groupe ou
        # un formateur a plus de volume qu'un plafond hebdomadaire strict.
        depassements: List[object] = []

        # Capacité par groupe et par semaine.
        for groupe in self.d.groupes:
            for semaine in range(self.horizon):
                demande = []
                for unite_id, info in variables.items():
                    if groupe.id in self.d.groupes_de_unite(info['unite']):
                        demande.append(intensite * actifs[(unite_id, semaine)])
                if not demande:
                    continue
                marge_max = intensite * len(demande)
                depassement = model.NewIntVar(
                    0, marge_max, f'dep_g_{groupe.id}_{semaine}'
                )
                model.Add(sum(demande) <= plafond_groupe + depassement)
                depassements.append(depassement)

        # Capacité par professeur et par semaine.
        for professeur in self.d.professeurs:
            plafond = int(round(self.d.plafond_professeur(professeur) * echelle))
            for semaine in range(self.horizon):
                demande = []
                for unite_id, info in variables.items():
                    unite = info['unite']
                    profs = self.d.profs_presentiels(unite) + self.d.profs_synchrones(unite)
                    if professeur.id in profs:
                        demande.append(intensite * actifs[(unite_id, semaine)])
                if not demande:
                    continue
                marge_max = intensite * len(demande)
                depassement = model.NewIntVar(
                    0, marge_max, f'dep_p_{professeur.id}_{semaine}'
                )
                model.Add(sum(demande) <= plafond + depassement)
                depassements.append(depassement)

        # Objectif : finir tôt, éviter les retards puis les dépassements.
        model.Minimize(
            sum(info['fin'] for info in variables.values())
            + 1000 * sum(info['retard'] for info in variables.values())
            + 200 * sum(depassements)
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(duree_max_s)
        solver.parameters.num_workers = 8
        solver.parameters.log_search_progress = False
        status = solver.Solve(model)
        statut = solver.StatusName(status)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if status == cp_model.INFEASIBLE:
                message = (
                    "Le calendrier des passages est irréalisable avec les "
                    "contraintes actuelles. Les passages existants sont conservés."
                )
            else:
                message = (
                    "Le calendrier des passages n'a pas pu être calculé dans le "
                    "délai. Les passages existants sont conservés."
                )
            self.resultat = ResultatPassages(
                plans=existants,
                statut=statut,
                message=message,
            )
            return self.resultat

        plans = list(existants)
        for unite_id, info in variables.items():
            debut = int(solver.Value(info['debut']))
            duree = int(info['duree'])
            retard = int(solver.Value(info['retard']))
            unite = info['unite']
            plans.append(
                PassagePlan(
                    unite_id=unite_id,
                    module_code=unite.module.code,
                    debut=debut,
                    duree=duree,
                    retard=retard,
                    intensite_h=float(info['intensite']),
                    source='calcule',
                    semaine_debut_abs=num_semaine + debut,
                    semaine_fin_abs=num_semaine + debut + duree - 1,
                )
            )

        plans.sort(key=lambda p: (p.debut, p.module_code, p.unite_id))
        message = (
            f"{len(plans)} passage(s) planifié(s), "
            f"{sum(1 for p in plans if p.retard > 0)} en retard."
        )
        self.resultat = ResultatPassages(plans=plans, statut=statut, message=message)
        return self.resultat

    def _passages_existants(self) -> List[PassagePlan]:
        """Passages déjà saisis et encore utiles (actifs ou futurs)."""
        plans: List[PassagePlan] = []
        num_semaine = self.d.semaine.numero
        derniere_semaine = num_semaine + self.d.n_sem - 1
        for unite in self.d.unites:
            for passage in unite.passages.all():
                if not passage.actif:
                    continue
                if passage.semaine_fin < num_semaine:
                    continue
                debut = int(passage.semaine_debut) - num_semaine
                duree = max(1, int(passage.semaine_fin) - int(passage.semaine_debut) + 1)
                retard = max(0, int(passage.semaine_fin) - derniere_semaine)
                plans.append(
                    PassagePlan(
                        unite_id=unite.id,
                        module_code=unite.module.code,
                        debut=debut,
                        duree=duree,
                        retard=retard,
                        intensite_h=float(passage.intensite_h or self.d.params.passage_intensite_defaut_h),
                        source='existant',
                        semaine_debut_abs=int(passage.semaine_debut),
                        semaine_fin_abs=int(passage.semaine_fin),
                    )
                )
        return plans

    def _unites_a_planifier(self) -> List:
        """Modules généraux sans aucun passage actif, rattachés aux groupes chargés."""
        groupes_actifs = {g.id for g in self.d.groupes}
        unites = []
        for unite in self.d.unites:
            if unite.module.type_module != 'general':
                continue
            if not any(ug.groupe_id in groupes_actifs for ug in unite.unite_groupes.all()):
                continue
            if any(p.actif for p in unite.passages.all()):
                continue
            if self.d.heures_restantes(unite) <= 0:
                continue
            unites.append(unite)
        unites.sort(key=lambda u: (u.module.code, u.id))
        return unites

    # ─── Persistance & résumé ────────────────────────────────────────────────
    def persister(self, donnees: Optional[Donnees] = None) -> int:
        """Enregistre les passages calculés (idempotent)."""
        if self.resultat is None:
            return 0
        d = donnees or self.d
        crees = 0
        for plan in self.resultat.plans:
            if plan.source != 'calcule':
                continue
            if plan.semaine_fin_abs < plan.semaine_debut_abs:
                continue
            existe = Passage.objects.filter(
                unite_id=plan.unite_id,
                semaine_debut=plan.semaine_debut_abs,
                semaine_fin=plan.semaine_fin_abs,
            ).first()
            if existe:
                if not existe.actif:
                    existe.actif = True
                    existe.save(update_fields=['actif'])
                continue
            Passage.objects.create(
                unite_id=plan.unite_id,
                semaine_debut=plan.semaine_debut_abs,
                semaine_fin=plan.semaine_fin_abs,
                intensite_h=plan.intensite_h,
                actif=True,
            )
            crees += 1
        return crees

    def resume(self, resultat: Optional[ResultatPassages] = None) -> Dict[str, object]:
        resultat = resultat or self.resultat
        if resultat is None:
            return {'statut': 'NON_CALCULE', 'nombre_passages': 0}
        return {
            'statut': resultat.statut,
            'message': resultat.message,
            'nombre_passages': len(resultat.plans),
            'passages_calcules': sum(1 for p in resultat.plans if p.source == 'calcule'),
            'passages_existants': sum(1 for p in resultat.plans if p.source == 'existant'),
            'passages_actifs_cette_semaine': sum(1 for p in resultat.plans if p.actif_cette_semaine),
            'passages_en_retard': len(resultat.alertes()),
            'alertes': resultat.alertes()[:50],
        }
