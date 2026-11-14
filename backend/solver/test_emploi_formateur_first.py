"""Tests de la génération « formateur d'abord » (emploi formateurs → stagiaires → salles)."""
from types import SimpleNamespace as NS

from django.test import SimpleTestCase, TestCase

from solver.decoupage import SeanceAPlacer
from solver.emploi_formateurs import EmploiFormateurs
from solver.emploi_stagiaires import compter_trous, verifier_emplois


# ─── Jeux de données légers (sans base de données) ────────────────────────────
def _creneaux(jours=(1, 2)):
    cid = 0
    resultat = []
    for jour in jours:
        for numero in (1, 2, 3, 4):
            cid += 1
            resultat.append(NS(id=cid, jour=jour, numero_seance=numero))
    return resultat


def _prof(pid, heures_max=30):
    return NS(id=pid, nom_complet=f"Formateur {pid}", heures_max_semaine=heures_max)


def _salle(rid, type_id=1):
    return NS(id=rid, actif=True, type_salle_id=type_id, type_salle=NS(code='SC'))


def _seance(sid, groupes, profs, **kw):
    return SeanceAPlacer(
        id=sid, unite_id=sid, module_id=sid, module_code=f"M{sid}", module_type='technique',
        groupe_ids=list(groupes), professeur_ids=list(profs), **kw,
    )


def _resoudre(seances, creneaux, profs, salles=None, dispo=None, occ_profs=None, charges=None):
    salles = salles or [_salle(1), _salle(2), _salle(3)]
    candidats = {s.id: [r for r in salles] for s in seances}
    return EmploiFormateurs(
        seances=seances, creneaux=creneaux,
        professeurs_map={p.id: p for p in profs}, salles=salles, candidats_salles=candidats,
        disponibilites=dispo or {}, occupations_groupes=set(),
        occupations_profs=occ_profs or set(), occupations_salles=set(),
        charges_conservees=charges,
    ).resoudre(temps_max_s=10)


class ComptageDesTrousTest(SimpleTestCase):
    def test_comptage(self):
        self.assertEqual(compter_trous([]), 0)
        self.assertEqual(compter_trous([2]), 0)
        self.assertEqual(compter_trous([1, 2]), 0)
        self.assertEqual(compter_trous([1, 3]), 1)
        self.assertEqual(compter_trous([2, 4]), 1)
        # Deux créneaux vides au milieu : l'ancien modèle ne le pénalisait pas.
        self.assertEqual(compter_trous([1, 4]), 2)
        self.assertEqual(compter_trous([1, 2, 4]), 1)


class EmploiFormateursModeleTest(SimpleTestCase):
    def test_trou_s1_s4_est_evite(self):
        """Deux séances simples d'un formateur sont placées sans créneau vide entre elles."""
        creneaux = _creneaux(jours=(1,))
        seances = [_seance(1, [10], [1], nature='simple'), _seance(2, [11], [1], nature='simple')]
        res = _resoudre(seances, creneaux, [_prof(1)])
        self.assertTrue(res.succes, res.message)
        numeros = [next(c.numero_seance for c in creneaux if c.id == res.creneau_par_seance[s.id])
                   for s in seances]
        self.assertEqual(compter_trous(numeros), 0, numeros)

    def test_un_groupe_jamais_dans_deux_seances_simultanees(self):
        """Deux formateurs différents pour le même groupe ne se chevauchent pas."""
        creneaux = _creneaux(jours=(1,))[:2]
        seances = [_seance(1, [10], [1], nature='simple'), _seance(2, [10], [2], nature='simple')]
        res = _resoudre(seances, creneaux, [_prof(1), _prof(2)])
        self.assertTrue(res.succes, res.message)
        self.assertNotEqual(res.creneau_par_seance[1], res.creneau_par_seance[2])

    def test_bloc_occupe_deux_creneaux_consecutifs(self):
        creneaux = _creneaux(jours=(1, 2))
        seances = [
            _seance(1, [10], [1], bloc_id=7, bloc_part=1),
            _seance(2, [10], [1], bloc_id=7, bloc_part=2),
        ]
        res = _resoudre(seances, creneaux, [_prof(1)])
        c1 = next(c for c in creneaux if c.id == res.creneau_par_seance[1])
        c2 = next(c for c in creneaux if c.id == res.creneau_par_seance[2])
        self.assertEqual(c1.jour, c2.jour)
        self.assertEqual(c2.numero_seance, c1.numero_seance + 1)
        self.assertIn(c1.numero_seance, (1, 3))

    def test_efm_le_plus_proche_de_sa_date(self):
        """Jour d'EFM indisponible : on prend le jour voisin, pas un jour au hasard."""
        creneaux = _creneaux(jours=(1, 5, 6))
        bloque = {c.id for c in creneaux if c.jour == 6}
        occ = {(cid, 1) for cid in bloque}
        seances = [
            _seance(1, [10], [1], bloc_id=1, bloc_part=1),
            _seance(2, [10], [1], bloc_id=1, bloc_part=2, nature='examen', jour_efm=6),
        ]
        res = _resoudre(seances, creneaux, [_prof(1)], occ_profs=occ)
        self.assertTrue(res.succes, res.message)
        jour = next(c.jour for c in creneaux if c.id == res.creneau_par_seance[2])
        self.assertEqual(jour, 5)
        self.assertTrue(res.avertissements, "l'EFM décalé doit être signalé")

    def test_plafond_hebdomadaire_deduit_les_seances_conservees(self):
        creneaux = _creneaux()
        seances = [_seance(i, [10 + i], [1], nature='simple') for i in (1, 2)]
        # Plafond 7,5 h = 3 séances ; 2 déjà conservées (5 h) → une seule possible.
        res = _resoudre(seances, creneaux, [_prof(1, heures_max=7.5)], charges={1: 5.0})
        self.assertFalse(res.succes)
        self.assertIn('plafond', res.message)

    def test_capacite_des_salles_par_type(self):
        """Une seule salle d'un type : deux séances qui n'acceptent que ce type ne coexistent pas."""
        creneaux = _creneaux(jours=(1,))[:2]
        salles = [_salle(1, type_id=1), _salle(2, type_id=2)]
        seances = [_seance(1, [10], [1], nature='simple'), _seance(2, [11], [2], nature='simple')]
        candidats = {1: [salles[0]], 2: [salles[0]]}
        res = EmploiFormateurs(
            seances=seances, creneaux=creneaux,
            professeurs_map={1: _prof(1), 2: _prof(2)}, salles=salles, candidats_salles=candidats,
            disponibilites={}, occupations_groupes=set(), occupations_profs=set(),
            occupations_salles=set(),
        ).resoudre(temps_max_s=10)
        self.assertTrue(res.succes, res.message)
        self.assertNotEqual(res.creneau_par_seance[1], res.creneau_par_seance[2])

    def test_seance_sans_creneau_possible_est_diagnostiquee(self):
        creneaux = _creneaux(jours=(1,))
        dispo = {(1, c.id): 'bloque' for c in creneaux}
        res = _resoudre([_seance(1, [10], [1], nature='simple')], creneaux, [_prof(1)], dispo=dispo)
        self.assertFalse(res.succes)
        self.assertIn('aucun créneau', res.message)


# ─── Intégration (base initialisée par init_data) ─────────────────────────────
class PipelineIntegrationTest(TestCase):
    def setUp(self):
        from django.core.management import call_command
        from core.models import Semaine
        call_command('init_data', verbosity=0)
        self.semaine = Semaine.objects.get(numero=1)

    def _generer(self, **kw):
        from solver.services import GenerateurEmploiDuTemps
        return GenerateurEmploiDuTemps(self.semaine.id).executer(max_time_seconds=30, **kw)

    def test_les_trois_emplois_sont_coherents(self):
        from core.models import Seance, Creneau
        from solver.placement import SeancePlacee

        resultat = self._generer()
        self.assertTrue(resultat['succes'], resultat['message'])
        phase3 = resultat['resume']['phase3']
        self.assertEqual(phase3['emploi_stagiaires']['conflits'], 0)
        self.assertEqual(phase3['emploi_salles']['seances_sans_salle'], 0)
        for etape in ('formateurs', 'salles', 'stagiaires'):
            self.assertIn(etape, phase3['etapes'])

        creneaux = {c.id: c for c in Creneau.objects.all()}
        placees = [
            SeancePlacee(
                seance_a_placer_id=s.id, unite_id=s.unite_id, creneau_id=s.creneau_id,
                salle_id=s.salle_id, professeur_id=s.professeur_id,
                groupe_ids=[sg.groupe_id for sg in s.seance_groupes.all()],
                nature=s.nature, bloc_no=s.bloc_no, mode=s.mode,
                professeur_ids=[sp.professeur_id for sp in s.seance_professeurs.all()],
            )
            for s in Seance.objects.filter(semaine=self.semaine)
            .prefetch_related('seance_groupes', 'seance_professeurs')
        ]
        self.assertEqual(verifier_emplois(placees, creneaux), [])

    def test_generation_ciblee_conserve_les_brouillons_des_autres_groupes(self):
        from core.models import Seance, SeanceGroupe, UniteGroupe

        self.assertTrue(self._generer()['succes'])
        groupes = list(
            SeanceGroupe.objects.filter(semaine=self.semaine)
            .values_list('groupe_id', flat=True).distinct()
        )
        self.assertGreaterEqual(len(groupes), 2)
        cible = groupes[0]
        # Les autres groupes qui ne partagent aucune unité avec la cible.
        partage = set(
            UniteGroupe.objects.filter(
                unite_id__in=UniteGroupe.objects.filter(groupe_id=cible).values('unite_id')
            ).values_list('groupe_id', flat=True)
        )
        autres = [g for g in groupes if g not in partage]
        if not autres:
            self.skipTest("Tous les groupes partagent une unité avec la cible.")

        avant = set(
            SeanceGroupe.objects.filter(semaine=self.semaine, groupe_id__in=autres)
            .values_list('seance_id', flat=True)
        )
        resultat = self._generer(groupes_ids=[cible])
        self.assertTrue(resultat['succes'], resultat['message'])
        apres = set(
            SeanceGroupe.objects.filter(semaine=self.semaine, groupe_id__in=autres)
            .values_list('seance_id', flat=True)
        )
        self.assertEqual(avant, apres, "les brouillons des autres groupes ont été supprimés")
        self.assertTrue(Seance.objects.filter(semaine=self.semaine, seance_groupes__groupe_id=cible).exists())
