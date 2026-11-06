"""
Tests unitaires et d'intégration pour le solveur CP-SAT OFPPT.
"""
from django.test import TestCase
from core.models import (
    Semaine, Groupe, Professeur, Salle, Creneau,
    Seance, SeanceGroupe, SeanceProfesseur, TacheGeneration
)
from solver.heures import CalculateurHeures
from solver.decoupage import DecoupeurSeances
from solver.services import GenerateurEmploiDuTemps


class SolverTestCase(TestCase):
    """Vérifie le bon fonctionnement du moteur d'optimisation CP-SAT."""

    fixtures = []

    def setUp(self):
        # Utilise la commande init_data pour charger l'environnement
        from django.core.management import call_command
        call_command('init_data')
        self.semaine_1 = Semaine.objects.get(numero=1)

    def test_01_calculateur_heures(self):
        """Vérifie que le calculateur attribue des volumes cohérents (30h à 35h)."""
        calc = CalculateurHeures(semaine=self.semaine_1)
        previsions = calc.calculer()
        self.assertGreater(len(previsions), 0)

        # Vérifier que les heures prévues sont multiples de 2.5h
        for prev in previsions:
            self.assertEqual(prev.heures_prevues % 2.5, 0.0)

    def test_02_decoupeur_seances(self):
        """Vérifie le découpage en blocs de 5h et séances simples."""
        calc = CalculateurHeures(semaine=self.semaine_1)
        previsions = calc.calculer()
        decoupeur = DecoupeurSeances()
        seances = decoupeur.decouper(previsions)

        self.assertGreater(len(seances), 0)
        # Chaque séance a une durée de 2.5h
        for s in seances:
            self.assertEqual(s.duree_h, 2.5)

        # Les blocs doivent être par paires
        bloc_counts = {}
        for s in seances:
            if s.bloc_id is not None:
                bloc_counts[s.bloc_id] = bloc_counts.get(s.bloc_id, 0) + 1

        for b_id, count in bloc_counts.items():
            self.assertEqual(count, 2, f"Le bloc #{b_id} ne contient pas exactement 2 séances.")

    def test_03_generation_complete_semaine(self):
        """Vérifie la génération complète de l'emploi du temps par le solver CP-SAT."""
        generateur = GenerateurEmploiDuTemps(semaine_id=self.semaine_1.id)
        resultat = generateur.executer(max_time_seconds=30)

        self.assertTrue(resultat['succes'], f"Échec solver : {resultat.get('message')}")
        self.assertGreater(resultat['nb_seances'], 0)

        # Vérifier que la tâche est marquée comme terminée
        tache = TacheGeneration.objects.get(id=resultat['tache_id'])
        self.assertEqual(tache.statut, TacheGeneration.STATUT_TERMINEE)

        # Vérification des Contraintes Dures en base de données :
        # 1. Aucun conflit de groupe sur un même créneau
        seances_groupes = SeanceGroupe.objects.filter(semaine=self.semaine_1)
        groupe_slots = set()
        for sg in seances_groupes:
            key = (sg.groupe_id, sg.creneau_id)
            self.assertNotIn(key, groupe_slots, f"Conflit détecté pour le groupe {sg.groupe_id} au créneau {sg.creneau_id}")
            groupe_slots.add(key)

        # 2. Aucun conflit de formateur sur un même créneau
        seances_profs = SeanceProfesseur.objects.filter(semaine=self.semaine_1)
        prof_slots = set()
        for sp in seances_profs:
            key = (sp.professeur_id, sp.creneau_id)
            self.assertNotIn(key, prof_slots, f"Conflit formateur {sp.professeur_id} au créneau {sp.creneau_id}")
            prof_slots.add(key)

        # 3. Aucun conflit de salle physique
        seances = Seance.objects.filter(semaine=self.semaine_1).exclude(salle__type_salle__code='TEAM')
        salle_slots = set()
        for s in seances:
            if s.salle_id:
                key = (s.salle_id, s.creneau_id)
                self.assertNotIn(key, salle_slots, f"Conflit salle {s.salle_id} au créneau {s.creneau_id}")
                salle_slots.add(key)

        # 4. Formateur vacataire M1004 ne doit pas avoir de cours le samedi (jour=6)
        prof_vac = Professeur.objects.get(matricule="M1004")
        samedi_seances_vac = SeanceProfesseur.objects.filter(
            professeur=prof_vac,
            semaine=self.semaine_1,
            creneau__jour=6,
        ).count()
        self.assertEqual(samedi_seances_vac, 0, "Le formateur vacataire a été placé le Samedi alors qu'il est bloqué.")

