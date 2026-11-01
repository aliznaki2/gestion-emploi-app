"""
Service Orchestrateur : GenerateurEmploiDuTemps.
Coordonne le calcul des heures, le découpage, la résolution CP-SAT et la persistance.
"""
import logging
import traceback
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

logger = logging.getLogger(__name__)


class GenerateurEmploiDuTemps:
    """
    Orchestre la génération automatique d'emplois du temps pour une semaine donnée.
    """

    def __init__(self, semaine_id: int, utilisateur: Optional[Utilisateur] = None):
        self.semaine_id = semaine_id
        self.utilisateur = utilisateur
        self.semaine = Semaine.objects.select_related('annee_scolaire', 'semestre').get(id=semaine_id)
        self.tache: Optional[TacheGeneration] = None

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
        1. Initialisation de la tâche
        2. Calcul des prévisions horaires (Phase 1)
        3. Découpage en séances atomiques & blocs (Phase 2)
        4. Optimisation mathématique CP-SAT (Phase 3)
        5. Persistance transactionnelle des séances
        """
        # 1. Création de la tâche de génération
        self.tache = TacheGeneration.objects.create(
            semaine=self.semaine,
            semestre=self.semaine.semestre,
            statut=TacheGeneration.STATUT_EN_COURS,
            cree_par=self.utilisateur,
            message=f"Démarrage de la génération pour la semaine {self.semaine.numero}.",
        )

        try:
            self._log(Journal.NIVEAU_INFO, f"Initialisation de la génération pour la Semaine {self.semaine.numero}.")

            # Filtrage des groupes cibles si spécifiés
            groupes_cibles = None
            if groupes_ids:
                groupes_cibles = list(Groupe.objects.filter(id__in=groupes_ids, actif=True))
                self._log(Journal.NIVEAU_INFO, f"{len(groupes_cibles)} groupe(s) ciblé(s) pour la génération.")

            # 2. Phase 1 : Calcul des heures
            self._log(Journal.NIVEAU_INFO, "Phase 1 : Calcul des volumes horaires hebdomadaires.")
            calculateur = CalculateurHeures(semaine=self.semaine)
            previsions = calculateur.calculer(groupes_cibles=groupes_cibles)

            if not previsions:
                msg = "Aucun module ou volume horaire restant à planifier pour cette semaine."
                self._log(Journal.NIVEAU_WARNING, msg)
                self.tache.statut = TacheGeneration.STATUT_TERMINEE
                self.tache.message = msg
                self.tache.date_fin = timezone.now()
                self.tache.save()
                return {
                    'succes': True,
                    'tache_id': self.tache.id,
                    'message': msg,
                    'nb_seances': 0,
                }

            self._log(Journal.NIVEAU_INFO, f"Phase 1 terminée : {len(previsions)} unité(s) prévues.")

            # 3. Phase 2 : Découpage en blocs et séances
            self._log(Journal.NIVEAU_INFO, "Phase 2 : Découpage en blocs de 5h et séances simples de 2.5h.")
            decoupeur = DecoupeurSeances()
            seances_a_placer = decoupeur.decouper(previsions)
            self._log(
                Journal.NIVEAU_INFO,
                f"Phase 2 terminée : {len(seances_a_placer)} séance(s) élémentaire(s) générée(s)."
            )

            # 4. Phase 3 : Modèle CP-SAT & Placement
            self._log(Journal.NIVEAU_INFO, "Phase 3 : Modélisation et résolution CP-SAT (Google OR-Tools).")
            creneaux = list(Creneau.objects.all().order_by('jour', 'numero_seance'))
            salles = list(Salle.objects.filter(actif=True).select_related('type_salle'))
            professeurs = list(Professeur.objects.filter(actif=True))

            # Disponibilités formateurs
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
            )

            resultat: ResultatPlacement = modele.resoudre(max_time_seconds=max_time_seconds)

            # 5. Traitement du résultat du Solver
            if not resultat.succes:
                self._log(Journal.NIVEAU_ERROR, resultat.message)
                self.tache.statut = TacheGeneration.STATUT_ECHEC
                self.tache.message = resultat.message
                self.tache.temps_resolution_ms = resultat.temps_resolution_ms
                self.tache.score_penalite = resultat.score_penalite
                self.tache.date_fin = timezone.now()
                self.tache.save()
                return {
                    'succes': False,
                    'tache_id': self.tache.id,
                    'message': resultat.message,
                    'temps_resolution_ms': resultat.temps_resolution_ms,
                }

            # 6. Persistance des séances en base de données
            self._log(Journal.NIVEAU_INFO, "Phase 4 : Enregistrement des séances et liaisons en base de données.")
            nb_seances_creees = self._persister_seances(resultat)

            # Clôture de la tâche avec succès
            self.tache.statut = TacheGeneration.STATUT_TERMINEE
            self.tache.message = resultat.message
            self.tache.temps_resolution_ms = resultat.temps_resolution_ms
            self.tache.score_penalite = resultat.score_penalite
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
            }

        except Exception as e:
            tb_str = traceback.format_exc()
            error_msg = f"Exception non gérée lors de la génération : {str(e)}"
            self._log(Journal.NIVEAU_ERROR, f"{error_msg}\n{tb_str}")
            if self.tache:
                self.tache.statut = TacheGeneration.STATUT_ECHEC
                self.tache.message = error_msg
                self.tache.date_fin = timezone.now()
                self.tache.save()
            return {
                'succes': False,
                'tache_id': self.tache.id if self.tache else None,
                'message': error_msg,
            }

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
        for sp in resultat.seances_placees:
            seance_obj = Seance(
                unite_id=sp.unite_id,
                semaine=self.semaine,
                creneau_id=sp.creneau_id,
                salle_id=sp.salle_id,
                professeur_id=sp.professeur_id,
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

        for seance_obj, sp in zip(created_seances, resultat.seances_placees):
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

            # Liaison formateur
            if sp.professeur_id:
                seance_profs.append(
                    SeanceProfesseur(
                        seance=seance_obj,
                        professeur_id=sp.professeur_id,
                        semaine=self.semaine,
                        creneau_id=sp.creneau_id,
                    )
                )

        if seance_groupes:
            SeanceGroupe.objects.bulk_create(seance_groupes)

        if seance_profs:
            SeanceProfesseur.objects.bulk_create(seance_profs)

        return len(created_seances)

