"""
Service Orchestrateur : GenerateurEmploiDuTemps.
Coordonne le calcul des passages, des heures, le découpage, la résolution
CP-SAT et la persistance.
"""
import logging
import time
import traceback
from collections import defaultdict
from typing import Optional, Dict, Any, List

from django.db import transaction
from django.utils import timezone

from core.models import (
    Semaine, TacheGeneration, Journal, Seance,
    SeanceGroupe, SeanceProfesseur, Creneau, Salle,
    Professeur, Disponibilite, Module, Groupe, Utilisateur
)
from .heures import CalculateurHeures
from .decoupage import DecoupeurSeances
from .placement import ModelePlacement, ResultatPlacement
from .indisponibilites import resoudre_indisponibilites, creneaux_par_jour
from .donnees import Donnees
from .passages import PlanificateurPassages
from .criteres import criteres_par_defaut

logger = logging.getLogger(__name__)


class GenerateurEmploiDuTemps:
    """
    Orchestre la génération automatique d'emplois du temps pour une semaine donnée.

    La façade peut être utilisée de façon synchrone (``executer``) ou via une
    tâche de fond créée par l'API (``tache_id`` déjà existant).
    """

    def __init__(
        self,
        semaine_id: int,
        utilisateur: Optional[Utilisateur] = None,
        tache_id: Optional[int] = None,
    ):
        self.semaine_id = semaine_id
        self.utilisateur = utilisateur
        self.semaine = Semaine.objects.select_related('annee_scolaire', 'semestre').get(id=semaine_id)
        self.tache: Optional[TacheGeneration] = (
            TacheGeneration.objects.filter(pk=tache_id).first() if tache_id else None
        )

    def _log(self, niveau: str, message: str) -> None:
        """Enregistre un événement dans la table Journal."""
        if self.tache:
            Journal.objects.create(
                tache=self.tache,
                niveau=niveau,
                message=message,
            )
        logger.log(getattr(logging, niveau, logging.INFO), message)

    def executer(self, max_time_seconds: int = 60, groupes_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Déroule les phases de génération :
        0. Calendrier des passages des modules généraux
        1. Calcul des prévisions horaires
        2. Découpage en séances atomiques & blocs
        3. Optimisation mathématique CP-SAT
        4. Persistance transactionnelle des séances
        """
        debut_execution = time.time()
        resume: Dict[str, Any] = {}

        # 1. Création ou reprise de la tâche de génération
        if self.tache is None:
            self.tache = TacheGeneration.objects.create(
                semaine=self.semaine,
                semestre=self.semaine.semestre,
                statut=TacheGeneration.STATUT_EN_COURS,
                cree_par=self.utilisateur,
                message=f"Démarrage de la génération pour la semaine {self.semaine.numero}.",
            )
        else:
            self.tache.statut = TacheGeneration.STATUT_EN_COURS
            self.tache.message = f"Démarrage de la génération pour la semaine {self.semaine.numero}."
            self.tache.save(update_fields=['statut', 'message'])

        try:
            self._log(Journal.NIVEAU_INFO, f"Initialisation de la génération pour la Semaine {self.semaine.numero}.")

            # Filtrage des groupes cibles si spécifiés
            groupes_cibles = None
            if groupes_ids:
                groupes_cibles = list(Groupe.objects.filter(id__in=groupes_ids, actif=True))
                self._log(Journal.NIVEAU_INFO, f"{len(groupes_cibles)} groupe(s) ciblé(s) pour la génération.")

            # Indisponibilités (congés / jours libres) de la semaine
            groupes_off_semaine, groupes_jours_off, profs_jours_off = resoudre_indisponibilites(self.semaine)
            if groupes_off_semaine:
                self._log(
                    Journal.NIVEAU_INFO,
                    f"{len(groupes_off_semaine)} groupe(s) entièrement indisponible(s) cette semaine.",
                )

            if groupes_cibles is not None:
                groupes_cibles = [g for g in groupes_cibles if g.id not in groupes_off_semaine]

            # ─── Phase 0 : calendrier des passages ────────────────────────────
            self._log(Journal.NIVEAU_INFO, "Phase 0 : calendrier de passage des modules généraux.")
            donnees = None
            try:
                donnees = Donnees.charger(self.semaine_id, groupes_ids=groupes_ids)
                planificateur = PlanificateurPassages(donnees)
                resultat_passages = planificateur.calculer()
                passages_crees = planificateur.persister(donnees)
                resume['phase0'] = planificateur.resume(resultat_passages)
                resume['phase0']['passages_crees'] = passages_crees
                self._log(Journal.NIVEAU_INFO, f"Phase 0 terminée : {resultat_passages.message}")
                for alerte in resultat_passages.alertes()[:10]:
                    self._log(
                        Journal.NIVEAU_WARNING,
                        f"Passage en retard : {alerte['module_code']} (unité {alerte['unite_id']}) "
                        f"de {alerte['retard']} semaine(s).",
                    )
            except Exception as exc:  # la phase 0 ne doit pas bloquer la génération
                self._log(Journal.NIVEAU_WARNING, f"Phase 0 ignorée : {exc}")
                resume['phase0'] = {'statut': 'ERREUR', 'message': str(exc)}

            # ─── Phase 1 : calcul des heures ─────────────────────────────────
            self._log(Journal.NIVEAU_INFO, "Phase 1 : Calcul des volumes horaires hebdomadaires.")
            calculateur = CalculateurHeures(semaine=self.semaine)
            previsions = calculateur.calculer(
                groupes_cibles=groupes_cibles,
                groupes_off_semaine=groupes_off_semaine,
                profs_jours_off=profs_jours_off,
            )

            resume['phase1'] = self._resume_phase1(previsions, donnees)

            if not previsions:
                msg = (
                    "Aucun module à planifier pour cette semaine. Vérifiez que les "
                    "filières ont des modules cochés et que ces modules ont des "
                    "heures par semaine renseignées."
                )
                self._log(Journal.NIVEAU_WARNING, msg)
                resume.update({
                    'succes': True,
                    'duree_totale_s': round(time.time() - debut_execution, 2),
                    'message': msg,
                })
                self.tache.statut = TacheGeneration.STATUT_TERMINEE
                self.tache.message = msg
                self.tache.resume = resume
                self.tache.date_fin = timezone.now()
                self.tache.save()
                return {
                    'succes': True,
                    'tache_id': self.tache.id,
                    'message': msg,
                    'nb_seances': 0,
                    'resume': resume,
                }

            self._log(Journal.NIVEAU_INFO, f"Phase 1 terminée : {len(previsions)} unité(s) prévue(s).")

            # ─── Phase 2 : découpage en blocs et séances ─────────────────────
            self._log(Journal.NIVEAU_INFO, "Phase 2 : Découpage en blocs de 5h et séances simples de 2.5h.")
            decoupeur = DecoupeurSeances()
            seances_a_placer = decoupeur.decouper(
                previsions,
                semaine_numero=self.semaine.numero,
            )
            resume['phase2'] = self._resume_phase2(seances_a_placer)
            self._log(
                Journal.NIVEAU_INFO,
                f"Phase 2 terminée : {len(seances_a_placer)} séance(s) élémentaire(s) générée(s)."
            )

            # ─── Phase 3 : modèle CP-SAT & placement ─────────────────────────
            self._log(Journal.NIVEAU_INFO, "Phase 3 : Modélisation et résolution CP-SAT (Google OR-Tools).")
            creneaux = list(Creneau.objects.all().order_by('jour', 'numero_seance'))
            salles = list(Salle.objects.filter(actif=True).select_related('type_salle'))
            professeurs = list(Professeur.objects.filter(actif=True).select_related(
                'salle_preferee', 'salle_preferee_matin', 'salle_preferee_apm'
            ))

            # Séances conservées (validées ou verrouillées) : occupation des ressources
            occupations_groupes = set()
            occupations_profs = set()
            occupations_salles = set()
            seances_conservees = Seance.objects.filter(semaine=self.semaine).select_related(
                'creneau'
            ).prefetch_related('seance_groupes')
            for s in seances_conservees:
                if not (s.verrouillee or s.statut == Seance.STATUT_VALIDE):
                    continue
                if s.salle_id:
                    occupations_salles.add((s.creneau_id, s.salle_id))
                if s.professeur_id:
                    occupations_profs.add((s.creneau_id, s.professeur_id))
                for sg in s.seance_groupes.all():
                    occupations_groupes.add((s.creneau_id, sg.groupe_id))

            # Indisponibilités : bloquer les créneaux concernés pour les groupes et formateurs
            creneaux_par_j = creneaux_par_jour(creneaux)
            for gid, jours in groupes_jours_off.items():
                if gid in groupes_off_semaine:
                    for c in creneaux:
                        occupations_groupes.add((c.id, gid))
                    continue
                for j in jours:
                    for cid in creneaux_par_j.get(j, []):
                        occupations_groupes.add((cid, gid))
            for pid, jours in profs_jours_off.items():
                for j in jours:
                    for cid in creneaux_par_j.get(j, []):
                        occupations_profs.add((cid, pid))
            dispos_qs = Disponibilite.objects.select_related('professeur', 'creneau')
            disponibilites_map = {
                (d.professeur_id, d.creneau_id): d.etat
                for d in dispos_qs
            }

            # Salles compatibles par module
            modules_qs = Module.objects.prefetch_related('types_salles_compatibles')
            salles_compatibles_map: Dict[int, List[int]] = {}
            for m in modules_qs:
                types_compatibles_ids = set(m.types_salles_compatibles.values_list('id', flat=True))
                if types_compatibles_ids:
                    salles_compatibles_map[m.id] = [
                        s.id for s in salles if s.type_salle_id in types_compatibles_ids
                    ]

            modele = ModelePlacement(
                seances=seances_a_placer,
                creneaux=creneaux,
                salles=salles,
                professeurs=professeurs,
                disponibilites=disponibilites_map,
                salles_compatibles_map=salles_compatibles_map,
                occupations_groupes=occupations_groupes,
                occupations_profs=occupations_profs,
                occupations_salles=occupations_salles,
            )
            for critere in criteres_par_defaut():
                modele.ajouter_critere(critere)

            resultat: ResultatPlacement = modele.resoudre(max_time_seconds=max_time_seconds)

            # 5. Traitement du résultat du Solver
            if not resultat.succes:
                self._log(Journal.NIVEAU_ERROR, resultat.message)
                resume['phase3'] = {
                    'statut': resultat.statut,
                    'objectif': resultat.score_penalite,
                    'borne': resultat.borne,
                    'seances_placees': 0,
                    'non_placees': len(seances_a_placer),
                    'heures_non_placees': len(seances_a_placer) * 2.5,
                    'temps_resolution_ms': resultat.temps_resolution_ms,
                    'message': resultat.message,
                }
                resume.update({
                    'succes': False,
                    'duree_totale_s': round(time.time() - debut_execution, 2),
                    'message': resultat.message,
                })
                self.tache.statut = TacheGeneration.STATUT_ECHEC
                self.tache.message = resultat.message
                self.tache.temps_resolution_ms = resultat.temps_resolution_ms
                self.tache.score_penalite = resultat.score_penalite
                self.tache.resume = resume
                self.tache.date_fin = timezone.now()
                self.tache.save()
                return {
                    'succes': False,
                    'tache_id': self.tache.id,
                    'message': resultat.message,
                    'temps_resolution_ms': resultat.temps_resolution_ms,
                    'resume': resume,
                }

            resume['phase3'] = self._resume_phase3(resultat, seances_a_placer, creneaux)

            # 6. Persistance des séances en base de données
            self._log(Journal.NIVEAU_INFO, "Phase 4 : Enregistrement des séances et liaisons en base de données.")
            nb_seances_creees = self._persister_seances(resultat)

            resume.update({
                'succes': True,
                'duree_totale_s': round(time.time() - debut_execution, 2),
                'message': resultat.message,
                'nb_seances': nb_seances_creees,
            })

            # Clôture de la tâche avec succès
            self.tache.statut = TacheGeneration.STATUT_TERMINEE
            self.tache.message = resultat.message
            self.tache.temps_resolution_ms = resultat.temps_resolution_ms
            self.tache.score_penalite = resultat.score_penalite
            self.tache.resume = resume
            self.tache.date_fin = timezone.now()
            self.tache.save()

            self._log(
                Journal.NIVEAU_INFO,
                f"Génération terminée avec succès. {nb_seances_creees} séance(s) créées au statut 'brouillon'."
            )

            return {
                'succes': True,
                'tache_id': self.tache.id,
                'message': resultat.message,
                'nb_seances': nb_seances_creees,
                'temps_resolution_ms': resultat.temps_resolution_ms,
                'score_penalite': resultat.score_penalite,
                'resume': resume,
            }

        except Exception as e:
            tb_str = traceback.format_exc()
            error_msg = f"Exception non gérée lors de la génération : {str(e)}"
            self._log(Journal.NIVEAU_ERROR, f"{error_msg}\n{tb_str}")
            resume.update({
                'succes': False,
                'erreur': error_msg,
                'duree_totale_s': round(time.time() - debut_execution, 2),
            })
            if self.tache:
                self.tache.statut = TacheGeneration.STATUT_ECHEC
                self.tache.message = error_msg
                self.tache.resume = resume
                self.tache.date_fin = timezone.now()
                self.tache.save()
            return {
                'succes': False,
                'tache_id': self.tache.id if self.tache else None,
                'message': error_msg,
                'resume': resume,
            }

    # ─── Résumés JSON ────────────────────────────────────────────────────────
    def _resume_phase1(self, previsions, donnees: Optional[Donnees]) -> Dict[str, Any]:
        """Synthèse de la phase 1 (charges, groupes sous/entre/au-dessus)."""
        charges_groupes: Dict[int, float] = defaultdict(float)
        charges_profs: Dict[int, float] = defaultdict(float)
        heures_demandees = 0.0

        for prev in previsions:
            heures_demandees += float(prev.heures_prevues or 0.0)
            for gid in prev.groupe_ids:
                charges_groupes[gid] += float(prev.heures_prevues or 0.0)
            for pid in prev.professeur_ids:
                charges_profs[pid] += float(prev.heures_prevues or 0.0)

        plafond_defaut = (
            donnees.params.plafond_professeur_defaut_h if donnees else 30.0
        )
        professeurs_map = donnees.professeurs_map if donnees else {}
        surcharges = []
        for pid, charge in charges_profs.items():
            prof = professeurs_map.get(pid)
            plafond = (
                donnees.plafond_professeur(prof) if (donnees and prof) else plafond_defaut
            )
            if charge > plafond + 1e-6:
                surcharges.append({
                    'professeur_id': pid,
                    'professeur': getattr(prof, 'nom_complet', str(pid)),
                    'charge': round(charge, 2),
                    'plafond': round(plafond, 2),
                })

        groupes_entre = sum(
            1 for h in charges_groupes.values()
            if 30.0 - 1e-6 <= h <= 35.0 + 1e-6
        )
        groupes_sous = sum(1 for h in charges_groupes.values() if h < 30.0 - 1e-6)
        groupes_sur = sum(1 for h in charges_groupes.values() if h > 35.0 + 1e-6)

        return {
            'unites_planifiees': len(previsions),
            'heures_demandees': round(heures_demandees, 2),
            'professeurs_surcharges_avant': len(surcharges),
            'professeurs_surcharges_apres': len(surcharges),
            'professeurs_surcharges': surcharges[:50],
            'groupes_entre_30_et_35h': groupes_entre,
            'groupes_sous_30h': groupes_sous,
            'groupes_au_dessus_35h': groupes_sur,
            'groupes_charges': len(charges_groupes),
        }

    def _resume_phase2(self, seances) -> Dict[str, Any]:
        """Synthèse de la phase 2 (blocs, séances simples, distance)."""
        blocs = len({s.bloc_id for s in seances if s.bloc_id is not None})
        simples = sum(1 for s in seances if s.nature == 'simple')
        distance = sum(1 for s in seances if s.mode == 'distance')
        sans_professeur = sum(1 for s in seances if not s.professeur_ids)
        return {
            'seances': len(seances),
            'blocs': blocs,
            'simples': simples,
            'a_distance': distance,
            'presentiel': len(seances) - distance,
            'sans_professeur': sans_professeur,
            'heures': round(len(seances) * 2.5, 2),
        }

    def _resume_phase3(self, resultat: ResultatPlacement, seances_a_placer, creneaux) -> Dict[str, Any]:
        """Synthèse de la phase 3 (placement, heures creuses, journées de 10h)."""
        creneaux_map = {c.id: c for c in creneaux}
        occ_groupes: Dict[tuple, set] = defaultdict(set)
        occ_profs: Dict[tuple, set] = defaultdict(set)

        for sp in resultat.seances_placees:
            creneau = creneaux_map.get(sp.creneau_id)
            if creneau is None:
                continue
            for gid in sp.groupe_ids:
                occ_groupes[(gid, creneau.jour)].add(creneau.numero_seance)
            prof_ids = list(sp.professeur_ids)
            if not prof_ids and sp.professeur_id:
                prof_ids = [sp.professeur_id]
            for pid in prof_ids:
                occ_profs[(pid, creneau.jour)].add(creneau.numero_seance)

        def _heures_creuses(occupations: Dict[tuple, set]) -> int:
            trous = 0
            for slots in occupations.values():
                # Séance 2 vide entre la 1 et la 3/4.
                if 1 in slots and (3 in slots or 4 in slots) and 2 not in slots:
                    trous += 1
                # Séance 3 vide entre la 1/2 et la 4.
                if (1 in slots or 2 in slots) and 4 in slots and 3 not in slots:
                    trous += 1
            return trous

        journees_10h = sum(1 for slots in occ_groupes.values() if len(slots) >= 4)
        placees = len(resultat.seances_placees)
        non_placees = max(0, len(seances_a_placer) - placees)

        return {
            'statut': resultat.statut,
            'objectif': resultat.score_penalite,
            'borne': resultat.borne,
            'seances_placees': placees,
            'non_placees': non_placees,
            'heures_non_placees': round(non_placees * 2.5, 2),
            'heures_creuses_groupes': _heures_creuses(occ_groupes),
            'heures_creuses_professeurs': _heures_creuses(occ_profs),
            'journees_10h': journees_10h,
            'temps_resolution_ms': resultat.temps_resolution_ms,
        }

    # ─── Persistance ─────────────────────────────────────────────────────────
    @transaction.atomic
    def _persister_seances(self, resultat: ResultatPlacement) -> int:
        """
        Supprime les anciens brouillons non verrouillés de la semaine et insère les nouvelles séances.
        """
        # Suppression des anciens brouillons modifiables
        Seance.objects.filter(
            semaine=self.semaine,
            statut=Seance.STATUT_BROUILLON,
            verrouillee=False,
        ).delete()

        seances_a_creer: List[Seance] = []
        prof_ids_par_seance: List[List[int]] = []
        for sp in resultat.seances_placees:
            prof_ids = list(sp.professeur_ids)
            if not prof_ids and sp.professeur_id:
                prof_ids = [sp.professeur_id]
            prof_ids = list(dict.fromkeys(prof_ids))
            prof_ids_par_seance.append(prof_ids)
            seance_obj = Seance(
                unite_id=sp.unite_id,
                semaine=self.semaine,
                creneau_id=sp.creneau_id,
                salle_id=sp.salle_id,
                professeur_id=prof_ids[0] if prof_ids else None,
                mode=sp.mode,
                nature=sp.nature,
                bloc_no=sp.bloc_no,
                statut=Seance.STATUT_BROUILLON,
                verrouillee=False,
                tache=self.tache,
            )
            seances_a_creer.append(seance_obj)

        # Insertion groupée des séances
        created_seances = Seance.objects.bulk_create(seances_a_creer)

        # Création des tables de liaison d'unicité SeanceGroupe et SeanceProfesseur
        seance_groupes: List[SeanceGroupe] = []
        seance_profs: List[SeanceProfesseur] = []

        for seance_obj, sp, prof_ids in zip(created_seances, resultat.seances_placees, prof_ids_par_seance):
            # Liaison pour chaque groupe (ex: 2 groupes si fusion)
            for gid in sp.groupe_ids:
                seance_groupes.append(
                    SeanceGroupe(
                        seance=seance_obj,
                        groupe_id=gid,
                        semaine=self.semaine,
                        creneau_id=sp.creneau_id,
                    )
                )

            # Liaison de tous les formateurs (co-enseignement)
            for pid in prof_ids:
                seance_profs.append(
                    SeanceProfesseur(
                        seance=seance_obj,
                        professeur_id=pid,
                        semaine=self.semaine,
                        creneau_id=sp.creneau_id,
                    )
                )

        if seance_groupes:
            SeanceGroupe.objects.bulk_create(seance_groupes)

        if seance_profs:
            SeanceProfesseur.objects.bulk_create(seance_profs)

        return len(created_seances)
