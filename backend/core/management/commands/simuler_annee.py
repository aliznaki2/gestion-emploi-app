"""
Simulation complète de l'année scolaire 2025/2026 pour GestEmploi.

La commande rend les données de démonstration cohérentes puis génère
l'emploi du temps des 45 semaines :

1. calendrier : 45 semaines (22 en S1, 23 en S2), avec coupures ;
2. unités d'enseignement : un module n'est suivi qu'une fois par groupe ;
3. modules : blocs de 5 h uniquement, volumes officiels 45 h / 90 h ;
4. filières, volumes horaires et besoins d'enseignement ;
5. formateurs : affectation équilibrée module par module, sans surcharge ;
6. passages : calendrier calculé par la phase 0 (2 généraux max en parallèle,
   locaux un par un, régionaux terminés à l'EFM, prérequis respectés) ;
7. disponibilités, indisponibilités et demandes de modification de profil ;
8. génération CP-SAT semaine par semaine.

Exemples :
    python manage.py simuler_annee --reset
    python manage.py simuler_annee --reset --sans-generation
    python manage.py simuler_annee --generer-seulement --depuis 23 --jusqu-a 45
"""
from __future__ import annotations

import math
import re
import time
from collections import defaultdict
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import (
    AffectationEnseignement,
    AnneeScolaire,
    DemandeModificationProfil,
    Disponibilite,
    Filiere,
    Groupe,
    Indisponibilite,
    Journal,
    Module,
    Passage,
    Professeur,
    Seance,
    SeanceGroupe,
    SeanceProfesseur,
    Semaine,
    Semestre,
    TacheGeneration,
    UniteEnseignement,
    UniteGroupe,
    UniteProfesseur,
    Utilisateur,
    VolumeHoraire,
)
from solver.services import GenerateurEmploiDuTemps


NOMBRE_SEMAINES = 45
SEMAINES_S1 = 22
SEMAINES_S2 = 23
DUREE_CRENEAU = 2.5
HORAIRE_HEBDO = 5.0

# Volumes officiels du référentiel : 45 h pour un module général et 90 h
# pour un module technique. Le moteur planifie la somme réelle des modules,
# sans étirement artificiel sur 22/23 semaines.
VOLUME_GENERAL = 45.0
VOLUME_TECHNIQUE = 90.0


def horaire_module(module: Module) -> float:
    """Heures hebdomadaires de repli : 5 h pour tous les modules."""
    return HORAIRE_HEBDO


def volume_module(module: Module) -> float:
    """Volume officiel du module (45 h général, 90 h technique)."""
    if module.type_module == Module.TYPE_GENERAL:
        return VOLUME_GENERAL
    return VOLUME_TECHNIQUE


class Command(BaseCommand):
    help = "Remplit les données CRUD et simule l'emploi du temps des 45 semaines."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help="Supprime les séances, tâches et journaux avant de reconstruire.",
        )
        parser.add_argument(
            '--sans-generation',
            action='store_true',
            help="Prépare uniquement les données, sans lancer le solveur.",
        )
        parser.add_argument(
            '--generer-seulement',
            action='store_true',
            help="Ne touche pas aux données et génère seulement les semaines demandées.",
        )
        parser.add_argument(
            '--depuis', type=int, default=1,
            help="Première semaine à générer (défaut : 1).",
        )
        parser.add_argument(
            '--jusqu-a', type=int, default=NOMBRE_SEMAINES,
            help=f"Dernière semaine à générer (défaut : {NOMBRE_SEMAINES}).",
        )
        parser.add_argument(
            '--temps-max', type=float, default=30.0,
            help="Temps maximal du solveur par semaine, en secondes (défaut : 30).",
        )
        parser.add_argument(
            '--continuer-en-cas-d-echec',
            action='store_true',
            help="Continue la génération malgré l'échec d'une semaine.",
        )

    # ─── Point d'entrée ──────────────────────────────────────────────────────
    def handle(self, *args, **options):
        try:
            annee = AnneeScolaire.objects.get(libelle='2025/2026')
        except AnneeScolaire.DoesNotExist as exc:
            raise CommandError(
                "L'année 2025/2026 est introuvable. Lancez d'abord « python manage.py init_data »."
            ) from exc

        debut = time.time()
        if not options['generer_seulement']:
            self.preparer_donnees(annee, reset=options['reset'])

        if not options['sans_generation']:
            self.generer(
                annee,
                depuis=options['depuis'],
                jusqu_a=options['jusqu_a'],
                temps_max=options['temps_max'],
                continuer=options['continuer_en_cas_d_echec'],
            )
            self.verifier(annee)

        self.stdout.write(self.style.SUCCESS(
            f"Simulation terminée en {time.time() - debut:.1f} s."
        ))

    # ─── 1. Préparation des données ─────────────────────────────────────────
    @transaction.atomic
    def preparer_donnees(self, annee: AnneeScolaire, reset: bool = False):
        if reset:
            self.stdout.write("Suppression des séances et tâches existantes…")
            Seance.objects.all().delete()
            TacheGeneration.objects.all().delete()
            Journal.objects.all().delete()

        s1, s2 = self._calendrier(annee)
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Calendrier : {NOMBRE_SEMAINES} semaines "
            f"(S1 = 1–{SEMAINES_S1}, S2 = {SEMAINES_S1 + 1}–{NOMBRE_SEMAINES})."
        ))

        prerequis = self._seed_prerequis()
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Prérequis : {prerequis} dépendance(s) module -> module."
        ))

        unites = list(
            UniteEnseignement.objects.filter(annee_scolaire=annee)
            .select_related('module', 'volume_horaire', 'semestre')
            .prefetch_related(
                'unite_groupes__groupe',
                'unite_professeurs',
                'module__prerequis',
            )
        )
        if not unites:
            raise CommandError("Aucune unité d'enseignement pour l'année 2025/2026.")

        # Un module doit être enseigné une seule fois par groupe : on supprime
        # les unités dupliquées entre S1 et S2 (même module, même fusion,
        # mêmes groupes) avant d'affecter les semestres.
        unites = self._dedupliquer_unites(annee, unites)
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Unités : {len(unites)} unités uniques."
        ))

        # Le semestre est décidé au niveau du MODULE (et non de l'unité) afin
        # que sa date d'EFM soit cohérente pour tous les groupes.
        semestre_par_unite = self._repartir_semestres(unites)
        module_semestre = {
            ue.module_id: semestre_par_unite[ue.id] for ue in unites
        }
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Unités : {len(unites)} réparties entre S1 ({s1.numero}) et S2 ({s2.numero})."
        ))

        self._regler_modules(annee, module_semestre)
        self.stdout.write(self.style.SUCCESS(
            "[OK] Modules : blocs de 5 h uniquement ; volumes officiels 45 h (général) / 90 h (technique)."
        ))

        unites_par_groupe = defaultdict(list)
        for ue in unites:
            for ug in ue.unite_groupes.all():
                unites_par_groupe[ug.groupe_id].append(ue)

        self._remplir_filieres(unites_par_groupe)
        self.stdout.write(self.style.SUCCESS("[OK] Filières : modules renseignés depuis les unités des groupes."))

        self._remplir_volumes(unites)
        self.stdout.write(self.style.SUCCESS(
            "[OK] Volumes horaires : somme officielle des modules (45 h / 90 h)."
        ))

        charges = self._affecter_formateurs(annee, unites, semestre_par_unite)
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Formateurs : {len(charges)} affectations unité -> formateur."
        ))

        # Phase 0 calcule les passages (2 généraux max, locaux un par un,
        # régionaux avant l'EFM, prérequis). On repart d'un calendrier vide.
        self._creer_passages(annee, unites, semestre_par_unite)
        self.stdout.write(self.style.SUCCESS(
            "[OK] Passages : calendrier calculé par le moteur (phase 0)."
        ))

        self._remplir_disponibilites(annee, charges)
        self._remplir_indisponibilites(annee, charges)
        self._remplir_demandes()
        self.stdout.write(self.style.SUCCESS(
            "[OK] Disponibilités, indisponibilités et demandes de profil renseignées."
        ))

    def _calendrier(self, annee: AnneeScolaire):
        s1, _ = Semestre.objects.get_or_create(
            annee_scolaire=annee, numero=1,
            defaults={'date_debut': date(2025, 9, 8), 'date_fin': date(2026, 2, 21)},
        )
        s2, _ = Semestre.objects.get_or_create(
            annee_scolaire=annee, numero=2,
            defaults={'date_debut': date(2026, 3, 2), 'date_fin': date(2026, 8, 15)},
        )

        # Coupures : vacances d'hiver (2 semaines), intersemestre (1 semaine)
        # et vacances de printemps (1 semaine).
        coupures = {
            date(2025, 12, 22),
            date(2025, 12, 29),
            date(2026, 2, 23),
            date(2026, 4, 6),
        }

        courant = date(2025, 9, 8)
        semaines = {}
        for numero in range(1, NOMBRE_SEMAINES + 1):
            while courant in coupures:
                courant += timedelta(weeks=1)
            fin = courant + timedelta(days=5)
            semestre = s1 if numero <= SEMAINES_S1 else s2
            semaine, _ = Semaine.objects.update_or_create(
                annee_scolaire=annee,
                numero=numero,
                defaults={
                    'semestre': semestre,
                    'date_debut': courant,
                    'date_fin': fin,
                    'active': True,
                },
            )
            semaines[numero] = semaine
            courant += timedelta(weeks=1)

        # Nettoyer d'éventuelles semaines au-delà de l'année simulée.
        Semaine.objects.filter(annee_scolaire=annee).exclude(
            numero__lte=NOMBRE_SEMAINES
        ).delete()

        s1.date_debut = semaines[1].date_debut
        s1.date_fin = semaines[SEMAINES_S1].date_fin
        s1.save(update_fields=['date_debut', 'date_fin'])

        s2.date_debut = semaines[SEMAINES_S1 + 1].date_debut
        s2.date_fin = semaines[NOMBRE_SEMAINES].date_fin
        s2.save(update_fields=['date_debut', 'date_fin'])
        return s1, s2

    # ─── Prérequis ──────────────────────────────────────────────────────────
    def _seed_prerequis(self) -> int:
        """Initialise les prérequis module -> module (éditables dans le CRUD).

        Deux familles de dépendances sont amorcées :
        - la même matière d'une année sur l'autre : ``M2yy`` -> ``M1yy`` et
          ``M3yy`` -> ``M2yy`` ;
        - la progression dans l'année pour les modules locaux :
          ``Mx(yy)`` -> ``Mx(yy-1)``. Les modules régionaux sont exclus de
          cette chaîne : ils doivent pouvoir être menés en parallèle avant
          leur date d'EFM.

        Les dépendances déjà saisies dans l'interface sont conservées.
        """
        modules = list(Module.objects.prefetch_related('prerequis'))
        par_code = {m.code: m for m in modules}
        par_id = {m.id: m for m in modules}
        paires = set()

        for code, module in par_code.items():
            trouve = re.match(r'^M([123])(\d{2})$', code)
            if not trouve:
                continue
            annee = int(trouve.group(1))
            numero = int(trouve.group(2))

            if annee > 1:
                prec = par_code.get(f"M{annee - 1}{numero:02d}")
                if prec is not None:
                    paires.add((module.id, prec.id))

            if numero > 1:
                prec = par_code.get(f"M{annee}{numero - 1:02d}")
                if (
                    prec is not None
                    and prec.type_module == Module.TYPE_TECHNIQUE
                    and module.type_module == Module.TYPE_TECHNIQUE
                    and not prec.regional
                    and not module.regional
                ):
                    paires.add((module.id, prec.id))

        crees = 0
        for module_id, prec_id in paires:
            module = par_id[module_id]
            if not any(p.id == prec_id for p in module.prerequis.all()):
                module.prerequis.add(prec_id)
                crees += 1
        return crees

    # ─── Unités & semestres ─────────────────────────────────────────────────
    def _dedupliquer_unites(self, annee, unites):
        """Supprime les unités identiques (module, fusion, groupes).

        Un module ne doit être suivi qu'une fois par groupe : les doublons
        créés par les anciennes répartitions S1/S2 sont supprimés.
        """
        vus, doublons = {}, []
        for ue in sorted(unites, key=lambda u: u.id):
            cle = (
                ue.module_id,
                (ue.code_fusion or '').strip().upper(),
                tuple(sorted(ug.groupe_id for ug in ue.unite_groupes.all())),
            )
            if cle in vus:
                doublons.append(ue.id)
            else:
                vus[cle] = ue
        if doublons:
            UniteEnseignement.objects.filter(id__in=doublons).delete()
        return list(vus.values())

    @staticmethod
    def _ordre_topologique(module_ids, prerequis):
        """Trie les modules pour que chaque prérequis précède ses dépendants."""
        ids = set(module_ids)
        dependants = defaultdict(set)
        indegree = {mid: 0 for mid in ids}
        for mid in ids:
            for prec in prerequis.get(mid, ()):
                if prec in ids:
                    indegree[mid] += 1
                    dependants[prec].add(mid)

        file = sorted(mid for mid, degre in indegree.items() if degre == 0)
        ordre = []
        while file:
            mid = file.pop(0)
            ordre.append(mid)
            for suivant in sorted(dependants.get(mid, ())):
                indegree[suivant] -= 1
                if indegree[suivant] == 0:
                    file.append(suivant)
        if len(ordre) < len(ids):
            # Cycle résiduel : on conserve un ordre stable pour ne pas bloquer.
            ordre.extend(sorted(ids - set(ordre)))
        return ordre

    def _repartir_semestres(self, unites):
        """Affecte chaque module à un seul semestre en équilibrant les groupes.

        Règles :
        - toutes les unités d'un module partagent le même semestre, pour que
          sa date d'EFM globale reste cohérente ;
        - un module régional dont la date d'EFM est saisie dans le CRUD est
          placé dans le semestre qui contient cette date ;
        - un prérequis est planifié au plus tard dans le semestre de son
          dépendant ;
        - les charges sont équilibrées par groupe, avec des plafonds souples
          par type (2 généraux en parallèle, locaux un par un, régionaux
          avant l'EFM).
        """
        semestre_1 = Semestre.objects.get(
            annee_scolaire=unites[0].annee_scolaire, numero=1
        )
        semestre_2 = Semestre.objects.get(
            annee_scolaire=unites[0].annee_scolaire, numero=2
        )

        volume, type_module, codes = {}, {}, {}
        groupes_du_module = defaultdict(set)
        modules_du_groupe = defaultdict(set)
        prerequis = {}
        forces = {}

        for ue in unites:
            module = ue.module
            mid = module.id
            volume[mid] = volume_module(module)
            codes[mid] = module.code
            if module.type_module == Module.TYPE_GENERAL:
                type_module[mid] = 'general'
            elif module.regional:
                type_module[mid] = 'regional'
            else:
                type_module[mid] = 'local'
            for ug in ue.unite_groupes.all():
                groupes_du_module[mid].add(ug.groupe_id)
                modules_du_groupe[ug.groupe_id].add(mid)
            prerequis[mid] = set(module.prerequis.values_list('id', flat=True))
            if module.regional and module.date_efm:
                forces[mid] = 1 if module.date_efm <= semestre_1.date_fin else 2

        dependants = defaultdict(set)
        for mid, pres in prerequis.items():
            for prec in pres:
                if prec in volume:
                    dependants[prec].add(mid)

        # Les modules les plus partagés sont placés en premier, mais toujours
        # dans l'ordre des prérequis.
        ordre = self._ordre_topologique(volume.keys(), prerequis)
        rang = {mid: index for index, mid in enumerate(ordre)}
        ordre.sort(key=lambda mid: (-len(groupes_du_module[mid]), rang[mid]))

        heures = defaultdict(lambda: {1: 0.0, 2: 0.0})
        compte = defaultdict(lambda: {
            1: defaultdict(int), 2: defaultdict(int)
        })
        cible = {
            gid: sum(volume[mid] for mid in mids) / 2.0
            for gid, mids in modules_du_groupe.items()
        }
        plafonds = {'general': 5, 'regional': 3, 'local': 5}
        sem = {}

        def cout(mid, semestre):
            total = 0.0
            typ = type_module[mid]
            for gid in groupes_du_module[mid]:
                charge = heures[gid][semestre] + volume[mid]
                total += (charge - cible[gid]) ** 2
                if compte[gid][semestre][typ] + 1 > plafonds[typ]:
                    total += 1e7
            for prec in prerequis.get(mid, ()):
                if prec in sem and sem[prec] > semestre:
                    total += 1e9
            return total

        for mid in ordre:
            force = forces.get(mid)
            if force:
                choisi = force
            else:
                choisi = 1 if cout(mid, 1) <= cout(mid, 2) else 2
            sem[mid] = choisi
            for gid in groupes_du_module[mid]:
                heures[gid][choisi] += volume[mid]
                compte[gid][choisi][type_module[mid]] += 1

        # Réparation : déplacer un module d'un semestre à l'autre lorsque les
        # plafonds sont dépassés, sans casser les prérequis.
        def deplacer_possible(mid, vers):
            for prec in prerequis.get(mid, ()):
                if prec in sem and sem[prec] > vers:
                    return False
            for suivant in dependants.get(mid, ()):
                if suivant in sem and vers > sem[suivant]:
                    return False
            return True

        for _ in range(40):
            deplace = False
            for gid, mids in modules_du_groupe.items():
                for source in (1, 2):
                    cible_sem = 3 - source
                    for typ, plafond in plafonds.items():
                        if compte[gid][source][typ] <= plafond:
                            continue
                        candidats = sorted(
                            (
                                mid for mid in mids
                                if sem[mid] == source and type_module[mid] == typ
                            ),
                            key=lambda mid: (
                                len(groupes_du_module[mid]),
                                -volume[mid],
                                codes[mid],
                            ),
                        )
                        for mid in candidats:
                            if not deplacer_possible(mid, cible_sem):
                                continue
                            if any(
                                compte[g][cible_sem][typ] + 1 > plafond
                                for g in groupes_du_module[mid]
                            ):
                                continue
                            for g in groupes_du_module[mid]:
                                heures[g][source] -= volume[mid]
                                compte[g][source][typ] -= 1
                                heures[g][cible_sem] += volume[mid]
                                compte[g][cible_sem][typ] += 1
                            sem[mid] = cible_sem
                            deplace = True
                            break
                        if deplace:
                            break
                    if deplace:
                        break
                if deplace:
                    break
            if not deplace:
                break

        # Équilibrage final : déplacer un module vers le semestre le moins
        # chargé tant que cela réduit l'écart aux cibles, sans casser les
        # prérequis ni les plafonds.
        for _ in range(200):
            meilleur = None
            meilleur_delta = -1e-6
            for mid in sem:
                source = sem[mid]
                cible_sem = 3 - source
                if not deplacer_possible(mid, cible_sem):
                    continue
                if any(
                    compte[g][cible_sem][type_module[mid]] + 1 > plafonds[type_module[mid]]
                    for g in groupes_du_module[mid]
                ):
                    continue
                delta = 0.0
                poids = volume[mid]
                for gid in groupes_du_module[mid]:
                    avant_s = heures[gid][source]
                    avant_c = heures[gid][cible_sem]
                    delta += (
                        (avant_s - poids - cible[gid]) ** 2
                        - (avant_s - cible[gid]) ** 2
                    )
                    delta += (
                        (avant_c + poids - cible[gid]) ** 2
                        - (avant_c - cible[gid]) ** 2
                    )
                if delta < meilleur_delta:
                    meilleur_delta = delta
                    meilleur = (mid, source, cible_sem)
            if meilleur is None:
                break
            mid, source, cible_sem = meilleur
            typ = type_module[mid]
            for gid in groupes_du_module[mid]:
                heures[gid][source] -= volume[mid]
                compte[gid][source][typ] -= 1
                heures[gid][cible_sem] += volume[mid]
                compte[gid][cible_sem][typ] += 1
            sem[mid] = cible_sem

        depassements = sum(
            1 for gid, mids in modules_du_groupe.items()
            for source in (1, 2)
            for typ, plafond in plafonds.items()
            if compte[gid][source][typ] > plafond
        )
        if depassements:
            self.stdout.write(self.style.WARNING(
                f"  {depassements} plafond(s) de type dépassé(s) ; le moteur "
                "ajustera l'intensité des passages."
            ))

        semestre_par_unite = {}
        for ue in unites:
            source = sem[ue.module_id]
            ue.semestre = semestre_1 if source == 1 else semestre_2
            semestre_par_unite[ue.id] = source
        UniteEnseignement.objects.bulk_update(unites, ['semestre'])
        return semestre_par_unite

    def _regler_modules(self, annee, module_semestre=None):
        """Règle les paramètres de tous les modules.

        - blocs de 5 h uniquement ;
        - modules régionaux : EFM en fin de module, date EFM conservée si elle
          a été saisie dans le CRUD, sinon positionnée sur la dernière semaine
          du semestre affecté ;
        - autres modules : pas d'EFM.
        """
        module_semestre = module_semestre or {}
        semaines = {
            s.numero: s for s in Semaine.objects.filter(annee_scolaire=annee)
        }
        modules = list(Module.objects.all())
        for module in modules:
            module.seances_2_5_autorisees = False
            module.heures_hebdomadaires = HORAIRE_HEBDO
            if module.regional:
                module.efm_fin_module = True
                if not module.date_efm:
                    source = module_semestre.get(module.id, 1)
                    numero = SEMAINES_S1 if source == 1 else NOMBRE_SEMAINES
                    semaine = semaines.get(numero)
                    if semaine is not None:
                        module.date_efm = semaine.date_fin
            else:
                module.efm_fin_module = False
                module.date_efm = None
        Module.objects.bulk_update(
            modules,
            ['seances_2_5_autorisees', 'heures_hebdomadaires',
             'efm_fin_module', 'date_efm'],
        )

    def _remplir_filieres(self, unites_par_groupe):
        for filiere in Filiere.objects.all():
            module_ids = set()
            for groupe in filiere.groupes.all():
                for ue in unites_par_groupe.get(groupe.id, []):
                    module_ids.add(ue.module_id)
            filiere.modules.set(module_ids)

    def _remplir_volumes(self, unites):
        existants = {
            v.unite_id: v
            for v in VolumeHoraire.objects.filter(unite_id__in=[u.id for u in unites])
        }
        a_creer = []
        a_mettre_a_jour = []
        for ue in unites:
            # Volume officiel du référentiel : 45 h (général) / 90 h (technique).
            total = volume_module(ue.module)
            volume = existants.get(ue.id)
            if volume is None:
                a_creer.append(VolumeHoraire(
                    unite=ue,
                    h_total=total,
                    h_presentiel=total,
                    h_synchrone=0.0,
                    h_asynchrone=0.0,
                    heures_effectuees=0.0,
                ))
            else:
                volume.h_total = total
                volume.h_presentiel = total
                volume.h_synchrone = 0.0
                volume.h_asynchrone = 0.0
                volume.heures_effectuees = 0.0
                a_mettre_a_jour.append(volume)
        if a_creer:
            VolumeHoraire.objects.bulk_create(a_creer)
        if a_mettre_a_jour:
            VolumeHoraire.objects.bulk_update(
                a_mettre_a_jour,
                ['h_total', 'h_presentiel', 'h_synchrone', 'h_asynchrone', 'heures_effectuees'],
            )

    # ─── 2. Affectation des formateurs ──────────────────────────────────────
    def _affecter_formateurs(self, annee, unites, semestre_par_unite):
        """Affecte chaque unité à un formateur sans surcharge.

        La charge d'un formateur est exprimée en **heures du volume officiel**
        du module (45 h / 90 h) et comparée à sa capacité réelle sur le
        semestre (``heures_max_semaine × nombre de semaines``).  Une marge de
        15 % est conservée pour que la phase 0 puisse placer les modules en
        parallèle sans dépasser le plafond hebdomadaire.
        """
        professeurs = list(Professeur.objects.filter(actif=True))
        if not professeurs:
            raise CommandError("Aucun formateur actif : impossible de planifier.")

        semaines_semestre = {
            numero: max(
                1,
                Semaine.objects.filter(
                    annee_scolaire=annee, semestre__numero=numero
                ).count(),
            )
            for numero in (1, 2)
        }
        if not any(semaines_semestre.values()):
            raise CommandError("Aucune semaine de cours : impossible de planifier.")

        capacite = {
            p.id: min(float(p.heures_max_semaine or 30.0), 30.0)
            for p in professeurs
        }
        # Objectif de charge hebdomadaire : 85 % du plafond nominal de 30 h.
        objectif = {pid: capacite[pid] * 0.85 for pid in capacite}

        # Compétences : module -> formateurs qui l'ont déjà enseigné.
        module_pool = defaultdict(set)
        for module_id, prof_id in UniteProfesseur.objects.filter(
            unite__annee_scolaire=annee
        ).values_list('unite__module_id', 'professeur_id'):
            module_pool[module_id].add(prof_id)

        # Les anciens liens (présentiel et distance) sont remplacés : ils
        # concentraient les unités sur quelques formateurs et rendaient la
        # planification irréalisable.
        UniteProfesseur.objects.filter(unite__annee_scolaire=annee).delete()

        affectations = {}
        nouveaux = defaultdict(int)

        for semestre in (1, 2):
            unites_semestre = [
                ue for ue in unites if semestre_par_unite[ue.id] == semestre
            ]
            if not unites_semestre:
                continue

            semaines = semaines_semestre[semestre]
            restant = {pid: objectif[pid] * semaines for pid in capacite}

            demande = defaultdict(float)
            for ue in unites_semestre:
                demande[ue.module_id] += volume_module(ue.module)

            def candidats_module(module_id):
                pool = {
                    pid for pid in module_pool[module_id] if pid in capacite
                }
                # Aucun formateur référencé pour ce module : on puise dans
                # l'ensemble des formateurs actifs plutôt que de créer une
                # fiche inutile.
                return pool or set(capacite)

            # Traiter d'abord les modules dont le vivier est le plus étroit
            # par rapport à leur volume, afin de ne pas les bloquer.
            ordre = sorted(
                demande,
                key=lambda mid: (
                    len(candidats_module(mid)) / max(1.0, demande[mid]),
                    -demande[mid],
                    mid,
                ),
            )

            for module_id in ordre:
                module = next(
                    ue.module for ue in unites_semestre
                    if ue.module_id == module_id
                )
                unites_module = sorted(
                    (ue for ue in unites_semestre if ue.module_id == module_id),
                    key=lambda u: (-len(u.unite_groupes.all()), u.id),
                )
                for ue in unites_module:
                    besoin = volume_module(ue.module)
                    candidats = sorted(
                        candidats_module(module_id),
                        key=lambda pid: (-restant.get(pid, 0.0), pid),
                    )
                    choisi = next(
                        (
                            pid for pid in candidats
                            if restant.get(pid, 0.0) + 1e-6 >= besoin
                        ),
                        None,
                    )

                    if choisi is None:
                        # Tous les formateurs du module sont saturés : on crée
                        # un formateur dédié pour la simulation.
                        nouveaux[module_id] += 1
                        prof = self._nouveau_formateur(
                            module, nouveaux[module_id]
                        )
                        capacite[prof.id] = min(
                            float(prof.heures_max_semaine or 30.0), 30.0
                        )
                        objectif[prof.id] = capacite[prof.id] * 0.85
                        restant[prof.id] = objectif[prof.id] * semaines
                        module_pool[module_id].add(prof.id)
                        choisi = prof.id

                    restant[choisi] -= besoin
                    affectations[ue.id] = choisi

        manquantes = [ue for ue in unites if ue.id not in affectations]
        if manquantes:
            raise CommandError(
                f"{len(manquantes)} unité(s) sans formateur après affectation."
            )

        # Remplacer tous les liens de l'année par l'affectation recalculée.
        UniteProfesseur.objects.bulk_create([
            UniteProfesseur(
                unite_id=unite_id,
                professeur_id=prof_id,
                mode='presentiel',
            )
            for unite_id, prof_id in affectations.items()
        ], ignore_conflicts=True)

        # Reconstruire les besoins (module, groupe).
        AffectationEnseignement.objects.all().delete()
        besoins = set()
        for ue in unites:
            prof_id = affectations[ue.id]
            for ug in ue.unite_groupes.all():
                besoins.add((prof_id, ue.module_id, ug.groupe_id))
        AffectationEnseignement.objects.bulk_create([
            AffectationEnseignement(
                professeur_id=prof_id,
                module_id=module_id,
                groupe_id=groupe_id,
                statut=AffectationEnseignement.STATUT_AFFECTE,
            )
            for prof_id, module_id, groupe_id in besoins
        ], ignore_conflicts=True)

        # Aligner la fiche formateur sur ses besoins réels.
        for prof in Professeur.objects.filter(actif=True):
            module_ids = set(
                AffectationEnseignement.objects.filter(professeur=prof)
                .values_list('module_id', flat=True)
            )
            prof.modules.set(Module.objects.filter(id__in=module_ids))

        return affectations

    def _nouveau_formateur(self, module: Module, index: int) -> Professeur:
        matricule = f"SIM-{module.code}-{index}"
        prof, cree = Professeur.objects.get_or_create(
            matricule=matricule,
            defaults={
                'nom_complet': f"Formateur {module.code} {index}",
                'email': f"{module.code.lower()}.{index}@gestemploi.ma",
                'statut': Professeur.STATUT_PERMANENT,
                'heures_max_semaine': 30.0,
                'actif': True,
            },
        )
        if cree:
            prof.modules.add(module)
        return prof

    # ─── 3. Passages (calculés par la phase 0) ──────────────────────────────
    def _creer_passages(self, annee, unites, semestre_par_unite):
        """Vide le calendrier : la phase 0 planifie tous les modules.

        Le planificateur CP-SAT applique les règles pédagogiques (2 généraux
        maximum en parallèle, modules locaux un par un, régionaux terminés
        avant l'EFM, prérequis) puis persiste les passages.
        """
        Passage.objects.filter(unite__annee_scolaire=annee).delete()

    # ─── 4. Disponibilités / indisponibilités / demandes ────────────────────
    def _remplir_disponibilites(self, annee, affectations):
        from core.models import Creneau

        Disponibilite.objects.all().delete()
        creneaux = list(Creneau.objects.order_by('jour', 'numero_seance'))
        if not creneaux:
            return

        # Charge hebdomadaire moyenne d'un formateur sur l'un des semestres.
        semaines_semestre = {
            numero: max(
                1,
                Semaine.objects.filter(
                    annee_scolaire=annee, semestre__numero=numero
                ).count(),
            )
            for numero in (1, 2)
        }
        unites_map = {
            ue.id: ue
            for ue in UniteEnseignement.objects.filter(
                id__in=affectations.keys()
            ).select_related('module', 'semestre')
        }
        charge = defaultdict(float)
        for unite_id, prof_id in affectations.items():
            ue = unites_map.get(unite_id)
            if ue is None:
                continue
            semestre = ue.semestre.numero if ue.semestre else 1
            charge[(prof_id, semestre)] += volume_module(ue.module)
        charge_max = defaultdict(float)
        for (prof_id, semestre), heures in charge.items():
            semaines = semaines_semestre.get(semestre, 22)
            charge_max[prof_id] = max(
                charge_max[prof_id], heures / max(1, semaines)
            )

        profs = list(Professeur.objects.filter(actif=True))
        lignes = []
        vus = set()
        for index, prof in enumerate(profs):
            # Deux créneaux préférés stables par formateur.
            for decalage in (index * 3, index * 7 + 1):
                creneau = creneaux[decalage % len(creneaux)]
                cle = (prof.id, creneau.id)
                if cle in vus:
                    continue
                vus.add(cle)
                lignes.append(Disponibilite(
                    professeur=prof, creneau=creneau,
                    etat=Disponibilite.ETAT_PREFERE,
                ))

            # Un créneau bloqué uniquement pour les formateurs ayant de la marge,
            # afin de ne jamais rendre la semaine irréalisable.
            plafond = float(prof.heures_max_semaine or 30.0)
            if charge_max.get(prof.id, 0.0) <= plafond * 0.6:
                creneau = creneaux[-(index % len(creneaux)) - 1]
                cle = (prof.id, creneau.id)
                if cle not in vus:
                    vus.add(cle)
                    lignes.append(Disponibilite(
                        professeur=prof, creneau=creneau,
                        etat=Disponibilite.ETAT_BLOQUE,
                    ))

        Disponibilite.objects.bulk_create(lignes, ignore_conflicts=True)

    def _remplir_indisponibilites(self, annee, affectations):
        Indisponibilite.objects.all().delete()
        semaines = {
            s.numero: s for s in Semaine.objects.filter(annee_scolaire=annee)
        }
        groupes = list(Groupe.objects.filter(actif=True).order_by('code'))

        charge = defaultdict(float)
        unites_map = {
            ue.id: ue
            for ue in UniteEnseignement.objects.filter(
                id__in=affectations.keys()
            ).select_related('module')
        }
        for unite_id, prof_id in affectations.items():
            ue = unites_map.get(unite_id)
            if ue is not None:
                charge[prof_id] += volume_module(ue.module)

        lignes = []
        # Journée libre pour une partie des groupes, répartie sur l'année.
        for index, groupe in enumerate(groupes):
            if index % 5 != 0:
                continue
            numero = [5, 10, 15, 22, 28, 34][(index // 5) % 6]
            semaine = semaines.get(numero)
            if semaine is None:
                continue
            lignes.append(Indisponibilite(
                type_cible=Indisponibilite.TYPE_CIBLE_GROUPE,
                groupe=groupe,
                type_periode=Indisponibilite.TYPE_PERIODE_JOUR,
                semaine=semaine,
                jour=(index % 5) + 1,
                motif="Journée pédagogique",
                actif=True,
            ))

        # Journée libre pour les formateurs les moins chargés.
        profs = sorted(
            Professeur.objects.filter(actif=True),
            key=lambda p: (charge.get(p.id, 0.0), p.id),
        )
        for index, prof in enumerate(profs[:12]):
            semaine = semaines.get([7, 12, 17, 24, 30, 35][index % 6])
            if semaine is None:
                continue
            lignes.append(Indisponibilite(
                type_cible=Indisponibilite.TYPE_CIBLE_PROFESSEUR,
                professeur=prof,
                type_periode=Indisponibilite.TYPE_PERIODE_JOUR,
                semaine=semaine,
                jour=(index % 5) + 1,
                motif="Formation continue",
                actif=True,
            ))

        # Deux absences de plusieurs jours pour des formateurs peu chargés.
        # La période couvre le lundi -> samedi (6 jours) : le moteur considère
        # alors le formateur absent toute la semaine et reporte ses unités,
        # au lieu de tenter de les caser dans les rares créneaux restants
        # (ce qui rendait la semaine infaisable).
        for index, prof in enumerate(profs[12:14]):
            debut = date(2026, 3, 9 + index * 7)
            lignes.append(Indisponibilite(
                type_cible=Indisponibilite.TYPE_CIBLE_PROFESSEUR,
                professeur=prof,
                type_periode=Indisponibilite.TYPE_PERIODE_PERIODE,
                date_debut=debut,
                date_fin=debut + timedelta(days=5),
                motif="Congé exceptionnel",
                actif=True,
            ))

        Indisponibilite.objects.bulk_create(lignes)

    def _remplir_demandes(self):
        from api.compat_views import _appliquer_donnees_profil, _valeurs_profil

        DemandeModificationProfil.objects.all().delete()
        admin = Utilisateur.objects.filter(role=Utilisateur.ROLE_ADMIN).first()
        profs = list(Professeur.objects.filter(actif=True).order_by('nom_complet'))
        if len(profs) < 6:
            return

        approuvee = DemandeModificationProfil.STATUT_APPROUVEE
        en_attente = DemandeModificationProfil.STATUT_EN_ATTENTE
        refusee = DemandeModificationProfil.STATUT_REFUSEE

        modeles = [
            (profs[0], {'telephone': '0661-000-101'}, approuvee,
             "Mise à jour de mon numéro de téléphone.", "Modification validée."),
            (profs[1], {'email': 'formateur.updated@gestemploi.ma'}, approuvee,
             "Mon adresse e-mail professionnelle a changé.", "Adresse mise à jour."),
            (profs[2], {'salle_preferee_id': None}, en_attente,
             "Je souhaite retirer ma salle préférée.", "Demande en cours d'examen."),
            (profs[3], {'telephone': '0661-000-104'}, approuvee,
             "Nouveau numéro joignable en journée.", "Numéro enregistré."),
            (profs[4], {'heures_max_semaine': 35}, refusee,
             "Demande d'heures supplémentaires.", "Refusée : plafond hebdomadaire maintenu."),
            (profs[5], {'email': 'nouvelle.adresse@gestemploi.ma'}, en_attente,
             "Changement d'adresse e-mail personnel.", "En attente de justificatif."),
            (profs[6] if len(profs) > 6 else profs[0], {'statut': 'vacataire'}, approuvee,
             "Passage au statut vacataire.", "Statut mis à jour."),
            (profs[7] if len(profs) > 7 else profs[1], {'telephone': '0661-000-108'}, en_attente,
             "Correction du numéro affiché.", "En attente de validation."),
        ]

        for prof, donnees, statut, commentaire, reponse in modeles:
            traite = statut in (approuvee, refusee)
            DemandeModificationProfil.objects.create(
                professeur=prof,
                donnees=donnees,
                donnees_avant=_valeurs_profil(prof),
                statut=statut,
                commentaire_formateur=commentaire,
                commentaire_admin=reponse,
                traite_par=admin if traite else None,
                date_traitement=timezone.now() if traite else None,
            )
            if statut == approuvee:
                _appliquer_donnees_profil(prof, donnees)

    # ─── 5. Génération ───────────────────────────────────────────────────────
    def generer(self, annee, depuis, jusqu_a, temps_max, continuer=False):
        if depuis < 1 or jusqu_a > NOMBRE_SEMAINES or depuis > jusqu_a:
            raise CommandError("Plage de semaines invalide.")

        admin = Utilisateur.objects.filter(role=Utilisateur.ROLE_ADMIN).first()
        semaines = {
            s.numero: s
            for s in Semaine.objects.filter(
                annee_scolaire=annee, numero__gte=depuis, numero__lte=jusqu_a
            ).order_by('numero')
        }

        echecs = []
        for numero in range(depuis, jusqu_a + 1):
            semaine = semaines.get(numero)
            if semaine is None:
                continue
            self.stdout.write(f"\n— Semaine {numero} ({semaine.date_debut} -> {semaine.date_fin}) —")
            generateur = GenerateurEmploiDuTemps(
                semaine_id=semaine.id,
                utilisateur=admin,
            )
            resultat = generateur.executer(max_time_seconds=temps_max)
            if resultat.get('succes'):
                self.stdout.write(self.style.SUCCESS(
                    f"  OK : {resultat.get('nb_seances', 0)} séance(s) — "
                    f"{resultat.get('message', '')}"
                ))
            else:
                echecs.append((numero, resultat.get('message', 'échec')))
                self.stdout.write(self.style.ERROR(
                    f"  ÉCHEC : {resultat.get('message', 'inconnu')}"
                ))
                if not continuer:
                    break

        if echecs:
            details = '; '.join(f"S{num}: {msg}" for num, msg in echecs)
            raise CommandError(f"Génération incomplète : {details}")

    # ─── 6. Vérifications ────────────────────────────────────────────────────
    def verifier(self, annee):
        from django.db.models import Count

        self.stdout.write("\n=== Vérification ===")
        self.stdout.write(f"Séances : {Seance.objects.count()}")
        self.stdout.write(f"Affectations : {AffectationEnseignement.objects.count()}")
        self.stdout.write(f"Passages : {Passage.objects.count()}")

        par_semaine = list(
            Semaine.objects.filter(annee_scolaire=annee)
            .annotate(nb=Count('seances'))
            .order_by('numero')
            .values_list('numero', 'nb')
        )
        sans_seances = [num for num, nb in par_semaine if nb == 0]
        self.stdout.write(f"Semaines sans séance : {sans_seances or 'aucune'}")

        # Conflits de groupe, de formateur et de salle.
        conflits = defaultdict(int)
        for sg in SeanceGroupe.objects.select_related('seance__creneau'):
            cle = (sg.semaine_id, sg.groupe_id, sg.creneau_id)
            conflits[('groupe',) + cle] += 1
        for sp in SeanceProfesseur.objects.select_related('seance__creneau'):
            cle = (sp.semaine_id, sp.professeur_id, sp.creneau_id)
            conflits[('prof',) + cle] += 1
        for seance in Seance.objects.exclude(salle__isnull=True):
            cle = (seance.semaine_id, seance.salle_id, seance.creneau_id)
            conflits[('salle',) + cle] += 1
        doublons = {cle: nb for cle, nb in conflits.items() if nb > 1}
        self.stdout.write(f"Conflits détectés : {len(doublons)}")
        if doublons:
            apercu = list(doublons.items())[:5]
            self.stdout.write(self.style.WARNING(f"  Aperçu : {apercu}"))
