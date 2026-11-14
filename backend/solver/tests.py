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


# ─── Tests des briques ajoutées (intégration progressive du pseudo-code) ──────
class DonneesEtPassagesTestCase(TestCase):
    """Vérifie le chargement ORM et la phase 0."""

    def setUp(self):
        from django.core.management import call_command
        call_command('init_data', verbosity=0)
        from core.models import Semaine
        self.semaine = Semaine.objects.order_by('numero').first()

    def test_donnees_charge(self):
        from solver.donnees import Donnees
        d = Donnees.charger(self.semaine.id)
        self.assertGreaterEqual(d.n_sem, 1)
        self.assertEqual(len(d.creneaux), 24)
        self.assertGreater(len(d.groupes), 0)
        self.assertGreater(len(d.professeurs), 0)
        self.assertGreater(len(d.salles), 0)
        self.assertEqual(d.params.passage_intensite_defaut_h, 5.0)
        self.assertIn('n_sem', d.__dict__)

    def test_planificateur_passages_calcule_et_persiste(self):
        from core.models import (
            AnneeScolaire, Groupe, Module, Passage, Semestre,
            UniteEnseignement, UniteGroupe, VolumeHoraire,
        )
        from solver.donnees import Donnees
        from solver.passages import PlanificateurPassages

        annee = AnneeScolaire.objects.first()
        semestre = self.semaine.semestre or Semestre.objects.first()
        groupe = Groupe.objects.filter(actif=True).first()
        module, _ = Module.objects.get_or_create(
            code='EGTS_TEST_PHASE0',
            defaults={'intitule': 'Module général de test', 'type_module': 'general'},
        )
        module.type_module = 'general'
        module.heures_hebdomadaires = 5.0
        module.save(update_fields=['type_module', 'heures_hebdomadaires'])

        unite = UniteEnseignement.objects.create(
            module=module,
            annee_scolaire=annee,
            semestre=semestre,
        )
        UniteGroupe.objects.create(unite=unite, groupe=groupe)
        VolumeHoraire.objects.create(
            unite=unite, h_total=40.0, h_presentiel=40.0, heures_effectuees=0.0,
        )

        d = Donnees.charger(self.semaine.id)
        planificateur = PlanificateurPassages(d)
        resultat = planificateur.calculer(duree_max_s=10)
        plans = [p for p in resultat.plans if p.unite_id == unite.id]
        self.assertEqual(
            len(plans), 1,
            f"statut={resultat.statut} message={resultat.message}",
        )
        self.assertEqual(plans[0].source, 'calcule')
        self.assertGreaterEqual(plans[0].duree, 1)
        self.assertGreaterEqual(plans[0].retard, 0)

        planificateur.persister(d)
        self.assertTrue(
            Passage.objects.filter(unite=unite, actif=True).exists(),
            "Le passage calculé doit être enregistré pour la phase 1.",
        )

    def test_criteres_poids_du_document(self):
        from solver.criteres import (
            HeuresCreuses, JourneeDixHeures, PreferenceSalle, criteres_par_defaut,
        )
        self.assertEqual(HeuresCreuses().poids_groupe, 30)
        self.assertEqual(HeuresCreuses().poids_prof, 10)
        self.assertEqual(JourneeDixHeures().poids, 40)
        self.assertEqual(PreferenceSalle().poids, 3)
        noms = [c.nom for c in criteres_par_defaut()]
        self.assertIn('UniciteOccupation', noms)
        self.assertIn('DisponibiliteProfesseur', noms)
        self.assertIn('ChargeProfesseur', noms)
        self.assertIn('CompatibiliteSalle', noms)


class DecoupageDistanceTestCase(TestCase):
    """Le découpage respecte la part de synchrone et reste déterministe."""

    def test_distance_deterministe(self):
        from types import SimpleNamespace
        from solver.decoupage import DecoupeurSeances
        from solver.heures import UnitePrevision

        module = SimpleNamespace(
            id=999,
            code='TEST_DIST',
            type_module='technique',
            peut_avoir_seance_2_5=False,
            efm_fin_module=False,
        )
        prev = UnitePrevision(
            unite_id=999,
            unite=SimpleNamespace(module=module),
            groupe_ids=[1],
            professeur_ids=[],
            heures_prevues=10.0,
            type_module='technique',
            frac_sync=1.0,
        )
        seances_1 = DecoupeurSeances().decouper([prev], semaine_numero=1)
        seances_2 = DecoupeurSeances().decouper([prev], semaine_numero=1)

        self.assertEqual(len(seances_1), 4)
        self.assertTrue(all(s.mode == 'distance' for s in seances_1))
        self.assertEqual(
            [(s.mode, s.nature, s.bloc_id) for s in seances_1],
            [(s.mode, s.nature, s.bloc_id) for s in seances_2],
        )


class PersistanceMultiFormateursTestCase(TestCase):
    """Chaque formateur de la séance est rattaché (co-enseignement)."""

    def setUp(self):
        from django.core.management import call_command
        call_command('init_data', verbosity=0)

    def test_persistance_deux_formateurs(self):
        from core.models import (
            Creneau, Groupe, Professeur, Semaine, SeanceProfesseur, TacheGeneration,
            UniteEnseignement,
        )
        from solver.placement import ResultatPlacement, SeancePlacee
        from solver.services import GenerateurEmploiDuTemps

        semaine = Semaine.objects.order_by('numero').first()
        unite = UniteEnseignement.objects.first()
        creneau = Creneau.objects.order_by('jour', 'numero_seance').first()
        groupe = Groupe.objects.filter(actif=True).first()
        profs = list(Professeur.objects.all()[:2])
        self.assertEqual(len(profs), 2)

        tache = TacheGeneration.objects.create(
            semaine=semaine,
            semestre=semaine.semestre,
            statut=TacheGeneration.STATUT_EN_COURS,
        )
        generateur = GenerateurEmploiDuTemps(semaine.id, tache_id=tache.id)
        resultat = ResultatPlacement(
            succes=True,
            statut='OPTIMAL',
            seances_placees=[
                SeancePlacee(
                    seance_a_placer_id=1,
                    unite_id=unite.id,
                    creneau_id=creneau.id,
                    salle_id=None,
                    professeur_id=profs[0].id,
                    groupe_ids=[groupe.id],
                    nature='simple',
                    bloc_no=None,
                    mode='distance',
                    professeur_ids=[p.id for p in profs],
                )
            ],
        )

        nb = generateur._persister_seances(resultat)
        self.assertEqual(nb, 1)
        self.assertEqual(
            SeanceProfesseur.objects.filter(seance__tache=tache).count(),
            2,
        )
        seance = tache.seances.first()
        self.assertIsNone(seance.salle_id)
        self.assertEqual(seance.mode, 'distance')


class ApiGenerationTestCase(TestCase):
    """Vérifie le contrat HTTP : 202, 409 et endpoint passages."""

    def setUp(self):
        from django.core.management import call_command
        from core.models import Semaine, Utilisateur
        call_command('init_data', verbosity=0)
        self.semaine = Semaine.objects.order_by('numero').first()
        self.admin = Utilisateur.objects.get(username='admin')
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_generation_202_puis_409(self):
        from unittest.mock import patch
        with patch('api.views._executer_generation_en_tache'):
            r1 = self.client.post('/api/generation/', {'semaine': self.semaine.id}, format='json')
            self.assertEqual(r1.status_code, 202, r1.content)
            self.assertIn('resume', r1.json())
            r2 = self.client.post('/api/generation/', {'semaine': self.semaine.id}, format='json')
            self.assertEqual(r2.status_code, 409, r2.content)

    def test_passages_calculer(self):
        r = self.client.post('/api/passages/calculer/', {'semaine': self.semaine.id}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertIn('passages', data)
        self.assertIn('alertes', data)
        self.assertIn('resume', data)
        self.assertIn('statut', data['resume'])

