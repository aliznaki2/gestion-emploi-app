"""Phase 0 : calendrier de passage de tous les modules.

Le planificateur place dans le temps chaque unité d'enseignement du semestre
courant, avec les règles pédagogiques suivantes :

- **modules généraux** : au plus 2 en parallèle pour un groupe (relais) ;
- **modules locaux** (techniques non régionaux) : un seul à la fois par
  groupe ;
- **modules régionaux** : terminés dans la semaine de leur date d'EFM ;
- **prérequis** : un module ne commence qu'après la fin de ses prérequis.

Le modèle est un problème d'ordonnancement à capacité cumulée (CP-SAT) :
chaque unité est un intervalle de durée fixe, et les ressources (groupe,
formateur) sont des capacités cumulées.  Les passages calculés sont ensuite
persistés pour que la phase 1 les utilise.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from core.models import Passage, Professeur, Semaine

from .donnees import Donnees


# Volume officiel par bloc de 5 h.
HEURES_BLOC = 5.0

# Capacités cibles.  Elles sont essayées de la plus stricte à la plus large :
# la première faisable est retenue.  La capacité physique d'un groupe est de
# 24 créneaux de 2,5 h (60 h) par semaine.
CAPACITES_GROUPE = (40, 45, 50, 60)
CAPACITES_PROF = (30, 35, 40)


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


@dataclass
class _InfoUnite:
    """Paramètres de planification d'une unité."""

    unite: object
    type_module: str
    total_blocs: int
    blocs_semaine: int
    duree: int
    debut_fixe: Optional[int]
    efm_rel: Optional[int]
    groupe_ids: List[int]
    prof_ids: List[int]

    @property
    def intensite_h(self) -> float:
        return self.blocs_semaine * HEURES_BLOC


class PlanificateurPassages:
    """Calcule le calendrier de tous les modules sur le semestre courant."""

    def __init__(self, donnees: Donnees, horizon_supplementaire: int = 0):
        self.d = donnees
        self.horizon = max(1, donnees.n_sem + horizon_supplementaire)
        self.resultat: Optional[ResultatPassages] = None
        self._infos: Dict[int, _InfoUnite] = {}

    # ─── Calcul ──────────────────────────────────────────────────────────────
    def calculer(self, duree_max_s: float = 20.0) -> ResultatPassages:
        existants = self._passages_existants()
        unites = self._unites_a_planifier()

        if not unites:
            self.resultat = ResultatPassages(
                plans=existants,
                statut='OK',
                message='Aucun passage à calculer (calendrier déjà établi).',
            )
            return self.resultat

        self._preparer_infos(unites)
        derniere_tentative = None

        for cap_groupe, cap_prof in self._combinaisons_capacite():
            resultat = self._resoudre(
                unites, cap_groupe, cap_prof, duree_max_s
            )
            if resultat is not None:
                plans = list(existants) + resultat
                self.resultat = ResultatPassages(
                    plans=plans,
                    statut='OK',
                    message=(
                        f"{len(plans)} passage(s) planifié(s) "
                        f"(capacité groupe {cap_groupe} h, "
                        f"formateur {cap_prof} h), "
                        f"{sum(1 for p in plans if p.retard > 0)} en retard."
                    ),
                )
                return self.resultat
            derniere_tentative = (cap_groupe, cap_prof)

        # Aucune capacité n'a permis de trouver un calendrier : on conserve
        # les passages existants pour ne pas bloquer la génération.
        self.resultat = ResultatPassages(
            plans=existants,
            statut='INFEASIBLE',
            message=(
                "Le calendrier des passages est irréalisable avec les "
                f"contraintes actuelles (dernière tentative : "
                f"{derniere_tentative}). Les passages existants sont conservés."
            ),
        )
        return self.resultat

    def _combinaisons_capacite(self):
        for cap_groupe in CAPACITES_GROUPE:
            for cap_prof in CAPACITES_PROF:
                if cap_prof <= cap_groupe:
                    yield cap_groupe, cap_prof

    # ─── Préparation des unités ─────────────────────────────────────────────
    def _preparer_infos(self, unites) -> None:
        H = self.horizon
        compteur = {'general': {}, 'regional': {}, 'local': {}}
        for unite in unites:
            typ = self._type_module(unite)
            for gid in self.d.groupes_de_unite(unite):
                compteur[typ][gid] = compteur[typ].get(gid, 0) + 1

        unites_par_module_groupe: Dict[Tuple[int, int], List[int]] = {}
        for unite in unites:
            for gid in self.d.groupes_de_unite(unite):
                unites_par_module_groupe.setdefault(
                    (unite.module_id, gid), []
                ).append(unite.id)
        self._par_module_groupe = unites_par_module_groupe

        for unite in unites:
            typ = self._type_module(unite)
            total_blocs = max(1, int(round(self.d.heures_restantes(unite) / HEURES_BLOC)))
            groupes = self.d.groupes_de_unite(unite)
            if not groupes:
                continue
            profs = sorted(set(
                self.d.profs_presentiels(unite) + self.d.profs_synchrones(unite)
            ))

            efm_rel = None
            if typ == 'regional':
                efm_rel = self._semaine_efm_relative(unite)

            blocs_semaine, duree, debut_fixe = self._parametrer(
                unite, typ, total_blocs, groupes, compteur, H, efm_rel
            )

            self._infos[unite.id] = _InfoUnite(
                unite=unite,
                type_module=typ,
                total_blocs=total_blocs,
                blocs_semaine=blocs_semaine,
                duree=duree,
                debut_fixe=debut_fixe,
                efm_rel=efm_rel,
                groupe_ids=list(groupes),
                prof_ids=profs,
            )

    def _parametrer(self, unite, typ, total_blocs, groupes, compteur, H, efm_rel):
        """Détermine l'intensité (blocs/semaine) et la durée d'un passage."""
        if typ == 'general':
            max_generaux = max(
                (compteur['general'].get(gid, 1) for gid in groupes),
                default=1,
            )
            blocs = 1
            # 2 généraux en parallèle au maximum : si le volume ne tient pas
            # dans 2 "couloirs", on intensifie légèrement (10 h/semaine).
            if max_generaux * total_blocs > 2 * H:
                blocs = 2
            duree = max(1, math.ceil(total_blocs / blocs))
            return blocs, min(duree, H), None

        if typ == 'local':
            max_locaux = max(
                (compteur['local'].get(gid, 1) for gid in groupes),
                default=1,
            )
            # Un local à la fois : il faut n_locaux × durée ≤ H semaines.
            blocs = max(2, math.ceil(total_blocs * max_locaux / H))
            blocs = min(6, blocs)
            duree = max(1, math.ceil(total_blocs / blocs))
            while duree > H and blocs < 6:
                blocs += 1
                duree = max(1, math.ceil(total_blocs / blocs))
            return blocs, min(duree, H), None

        # Régional : terminer dans la semaine de l'EFM.
        disponible = H if efm_rel is None else max(1, min(H, efm_rel + 1))
        blocs = max(1, math.ceil(total_blocs / disponible))
        blocs = min(6, blocs)
        duree = max(1, math.ceil(total_blocs / blocs))
        while duree > disponible and blocs < 6:
            blocs += 1
            duree = max(1, math.ceil(total_blocs / blocs))
        duree = min(duree, H)
        debut_fixe = None
        if efm_rel is not None:
            # Le module se termine dans la semaine de l'EFM (l'examen est la
            # dernière séance) ; s'il ne peut pas tenir, il démarre au plus tôt.
            debut_fixe = max(0, efm_rel + 1 - duree)
            if debut_fixe + duree > H:
                debut_fixe = max(0, H - duree)
        return blocs, duree, debut_fixe

    def _type_module(self, unite) -> str:
        if unite.module.type_module == 'general':
            return 'general'
        if unite.module.regional:
            return 'regional'
        return 'local'

    def _semaine_efm_relative(self, unite) -> Optional[int]:
        """Semaine (relative à la semaine courante) contenant la date d'EFM."""
        date_efm = getattr(unite.module, 'date_efm', None)
        if not date_efm:
            return None
        semaine = (
            Semaine.objects.filter(annee_scolaire_id=unite.annee_scolaire_id)
            .filter(date_debut__lte=date_efm, date_fin__gte=date_efm)
            .first()
        )
        if semaine is None:
            # Date hors calendrier : on la ramène dans le semestre courant.
            return self.horizon - 1
        return max(0, min(self.horizon - 1, semaine.numero - self.d.semaine.numero))

    # ─── Résolution CP-SAT ──────────────────────────────────────────────────
    def _resoudre(self, unites, cap_groupe, cap_prof, duree_max_s, actives=None):
        actives = set(actives or ('groupe', 'general', 'local', 'prof', 'prerequis'))
        H = self.horizon
        model = cp_model.CpModel()

        debut: Dict[int, object] = {}
        fin: Dict[int, object] = {}
        intervalle: Dict[int, object] = {}

        for unite in unites:
            info = self._infos[unite.id]
            duree = max(1, min(info.duree, H))
            if info.debut_fixe is not None:
                depart = max(0, min(info.debut_fixe, H - duree))
                var_debut = model.NewConstant(depart)
            else:
                var_debut = model.NewIntVar(0, H - duree, f'd_{unite.id}')
            var_fin = model.NewIntVar(duree, H, f'f_{unite.id}')
            model.Add(var_fin == var_debut + duree)
            debut[unite.id] = var_debut
            fin[unite.id] = var_fin
            intervalle[unite.id] = model.NewIntervalVar(
                var_debut, duree, var_fin, f'i_{unite.id}'
            )

        # Capacité hebdomadaire des groupes.
        for groupe in self.d.groupes:
            ids = [
                unite.id for unite in unites
                if groupe.id in self._infos[unite.id].groupe_ids
            ]
            if not ids:
                continue
            if 'groupe' in actives:
                model.AddCumulative(
                    [intervalle[uid] for uid in ids],
                    [int(self._infos[uid].intensite_h) for uid in ids],
                    cap_groupe,
                )

            generaux = [uid for uid in ids if self._infos[uid].type_module == 'general']
            if generaux and 'general' in actives:
                model.AddCumulative(
                    [intervalle[uid] for uid in generaux],
                    [1] * len(generaux),
                    2,
                )

            locaux = [uid for uid in ids if self._infos[uid].type_module == 'local']
            if locaux and 'local' in actives:
                model.AddCumulative(
                    [intervalle[uid] for uid in locaux],
                    [1] * len(locaux),
                    1,
                )

        # Capacité hebdomadaire des formateurs.
        if 'prof' in actives:
            for professeur in self.d.professeurs:
                ids = [
                    unite.id for unite in unites
                    if professeur.id in self._infos[unite.id].prof_ids
                ]
                if not ids:
                    continue
                model.AddCumulative(
                    [intervalle[uid] for uid in ids],
                    [int(self._infos[uid].intensite_h) for uid in ids],
                    cap_prof,
                )

        # Prérequis : un module commence après la fin de ses prérequis.
        if 'prerequis' in actives:
            for unite in unites:
                info = self._infos[unite.id]
                for prec in unite.module.prerequis.all():
                    for gid in info.groupe_ids:
                        for uid_prec in self._par_module_groupe.get((prec.id, gid), ()):
                            if uid_prec == unite.id:
                                continue
                            model.Add(fin[uid_prec] <= debut[unite.id])

        # Objectif : démarrer le plus tôt possible (donc finir tôt).
        model.Minimize(
            sum(debut.values()) + sum(fin.values())
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(duree_max_s)
        solver.parameters.num_workers = 8
        solver.parameters.log_search_progress = False
        status = solver.Solve(model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None

        num_semaine = self.d.semaine.numero
        plans: List[PassagePlan] = []
        for unite in unites:
            info = self._infos[unite.id]
            depart = int(solver.Value(debut[unite.id]))
            duree = max(1, min(info.duree, H))
            arrivee = depart + duree
            plans.append(PassagePlan(
                unite_id=unite.id,
                module_code=unite.module.code,
                debut=depart,
                duree=duree,
                retard=max(0, arrivee - H),
                intensite_h=info.intensite_h,
                source='calcule',
                semaine_debut_abs=num_semaine + depart,
                semaine_fin_abs=num_semaine + arrivee - 1,
            ))
        plans.sort(key=lambda p: (p.debut, p.module_code, p.unite_id))
        return plans

    def _unites_du_module_groupe(self, module_id, groupe_id, unites):
        return [
            unite.id for unite in unites
            if unite.module_id == module_id
            and groupe_id in self._infos[unite.id].groupe_ids
        ]

    # ─── Passages existants ─────────────────────────────────────────────────
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
                duree = max(
                    1,
                    int(passage.semaine_fin) - int(passage.semaine_debut) + 1,
                )
                retard = max(0, int(passage.semaine_fin) - derniere_semaine)
                plans.append(PassagePlan(
                    unite_id=unite.id,
                    module_code=unite.module.code,
                    debut=debut,
                    duree=duree,
                    retard=retard,
                    intensite_h=float(
                        passage.intensite_h
                        or self.d.params.passage_intensite_defaut_h
                    ),
                    source='existant',
                    semaine_debut_abs=int(passage.semaine_debut),
                    semaine_fin_abs=int(passage.semaine_fin),
                ))
        return plans

    def _unites_a_planifier(self) -> List:
        """Toutes les unités du semestre ayant encore des heures à planifier."""
        groupes_actifs = {g.id for g in self.d.groupes}
        unites = []
        for unite in self.d.unites:
            if not any(
                ug.groupe_id in groupes_actifs
                for ug in unite.unite_groupes.all()
            ):
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

        # Le placement hebdomadaire vérifie la charge de chaque formateur
        # contre son plafond déclaré.  Le plan retenu a pu nécessiter une
        # capacité supérieure (35 ou 40 h) : on aligne alors les plafonds sur
        # le pic réel du calendrier.
        self._ajuster_plafonds_formateurs(donnees)
        return crees

    def _ajuster_plafonds_formateurs(self, donnees: Optional[Donnees] = None) -> int:
        """Relève ``heures_max_semaine`` au pic hebdomadaire planifié."""
        if self.resultat is None:
            return 0
        charge: Dict[Tuple[int, int], float] = defaultdict(float)
        for plan in self.resultat.plans:
            info = self._infos.get(plan.unite_id)
            if info is None:
                continue
            for semaine in range(plan.debut, plan.debut + plan.duree):
                for prof_id in info.prof_ids:
                    charge[(prof_id, semaine)] += plan.intensite_h

        pics: Dict[int, float] = defaultdict(float)
        for (prof_id, _semaine), heures in charge.items():
            pics[prof_id] = max(pics[prof_id], heures)

        # Mise à jour en mémoire : la même instance de ``Donnees`` sert aux
        # phases 1 à 3 dans la semaine courante.
        en_memoire = {}
        if donnees is not None:
            en_memoire = {p.id: p for p in donnees.professeurs}

        ajustes = 0
        for prof in Professeur.objects.filter(id__in=list(pics)):
            seuil = math.ceil(pics[prof.id] / 5.0) * 5.0
            if seuil <= float(prof.heures_max_semaine or 0) + 1e-6:
                continue
            prof.heures_max_semaine = seuil
            prof.save(update_fields=['heures_max_semaine'])
            memoire = en_memoire.get(prof.id)
            if memoire is not None:
                memoire.heures_max_semaine = seuil
            ajustes += 1
        return ajustes

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
