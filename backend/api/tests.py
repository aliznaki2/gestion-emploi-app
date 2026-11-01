"""
Tests unitaires et d'API REST pour les endpoints DRF.
"""
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from core.models import Utilisateur, Semaine, Seance
from solver.services import GenerateurEmploiDuTemps


class ApiTimetableTestCase(APITestCase):

    def setUp(self):
        from django.core.management import call_command
        call_command('init_data')

        self.admin_user = Utilisateur.objects.get(username='admin')
        self.prof_user = Utilisateur.objects.get(username='prof_alami')
        self.stagiaire_user = Utilisateur.objects.get(username='stagiaire_dev101')
        self.semaine_1 = Semaine.objects.get(numero=1)

    def test_01_authentification_jwt(self):
        """Vérifie l'authentification et l'obtention du token JWT."""
        url = reverse('token_obtain_pair')
        response = self.client.post(url, {'username': 'admin', 'password': 'admin123'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_02_generation_endpoint(self):
        """Vérifie le déclenchement de la génération via l'API REST."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('generation_list_create')
        data = {
            'semaine_id': self.semaine_1.id,
            'max_time_seconds': 30,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['succes'])
        self.assertGreater(response.data['nb_seances'], 0)

    def test_03_permissions_seances(self):
        """
        Vérifie que les formateurs et stagiaires ne voient que les séances validées.
        """
        # Générer des séances au statut brouillon
        generateur = GenerateurEmploiDuTemps(semaine_id=self.semaine_1.id)
        generateur.executer(max_time_seconds=30)

        # L'admin voit les brouillons
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('seance-list')
        resp_admin = self.client.get(f"{url}?semaine={self.semaine_1.id}")
        self.assertEqual(resp_admin.status_code, status.HTTP_200_OK)
        count_admin = len(resp_admin.data.get('results', resp_admin.data))
        self.assertGreater(count_admin, 0)

        # Le formateur ne voit aucun brouillon
        self.client.force_authenticate(user=self.prof_user)
        resp_prof = self.client.get(f"{url}?semaine={self.semaine_1.id}")
        self.assertEqual(resp_prof.status_code, status.HTTP_200_OK)
        count_prof = len(resp_prof.data.get('results', resp_prof.data))
        self.assertEqual(count_prof, 0, "Le formateur ne doit pas voir les séances au statut brouillon.")

        # L'admin valide la semaine
        self.client.force_authenticate(user=self.admin_user)
        valider_url = reverse('valider_semaine', kwargs={'semaine_id': self.semaine_1.id})
        resp_val = self.client.post(valider_url, {'confirmer': True})
        self.assertEqual(resp_val.status_code, status.HTTP_200_OK)
        self.assertTrue(resp_val.data['succes'])

        # Après validation, le formateur Alami voit ses séances validées
        self.client.force_authenticate(user=self.prof_user)
        resp_prof_after = self.client.get(f"{url}?semaine={self.semaine_1.id}")
        count_prof_after = len(resp_prof_after.data.get('results', resp_prof_after.data))
        self.assertGreater(count_prof_after, 0, "Le formateur doit voir ses séances validées.")
