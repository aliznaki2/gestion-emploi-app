"""
Commande Django pour initialiser la base de données avec des données types OFPPT :
- Créneaux horaires officiels (Lundi à Samedi, 4 séances de 2.5h)
- Types de salles et salles (SC, SP, LABO, TEAM)
- Année scolaire, semestres et 16 semaines
- Secteurs, filières et groupes
- Modules techniques et généraux
- Formateurs avec disponibilités et salles préférées
- Unités d'enseignement, volumes horaires et modules en passage
- Utilisateurs de test avec les 3 rôles (Admin, Formateur, Stagiaire)
"""
from datetime import time, date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Utilisateur, Secteur, Filiere, Groupe, TypeSalle, Salle,
    Module, AnneeScolaire, Semestre, Semaine, Professeur,
    Creneau, Disponibilite, UniteEnseignement, UniteGroupe,
    VolumeHoraire, UniteProfesseur, Passage
)


class Command(BaseCommand):
    help = "Initialise les données de test représentatives d'un établissement OFPPT."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Démarrage du peuplement des données OFPPT..."))

        with transaction.atomic():
            # 1. Utilisateurs
            admin_user, _ = Utilisateur.objects.get_or_create(
                username='admin',
                defaults={
                    'email': 'admin@ofppt.ma',
                    'first_name': 'Responsable',
                    'last_name': 'Pédagogique',
                    'role': Utilisateur.ROLE_ADMIN,
                    'is_staff': True,
                    'is_superuser': True,
                }
            )
            admin_user.set_password('admin123')
            admin_user.save()

            prof_user, _ = Utilisateur.objects.get_or_create(
                username='prof_alami',
                defaults={
                    'email': 'm.alami@ofppt.ma',
                    'first_name': 'Mohammed',
                    'last_name': 'Alami',
                    'role': Utilisateur.ROLE_PROFESSEUR,
                }
            )
            prof_user.set_password('prof123')
            prof_user.save()

            stagiaire_user, _ = Utilisateur.objects.get_or_create(
                username='stagiaire_dev101',
                defaults={
                    'email': 'stagiaire@ofppt.ma',
                    'first_name': 'Youssef',
                    'last_name': 'Bennani',
                    'role': Utilisateur.ROLE_STAGIAIRE,
                }
            )
            stagiaire_user.set_password('stagiaire123')
            stagiaire_user.save()

            self.stdout.write(self.style.SUCCESS("[OK] Utilisateurs crees (admin, prof_alami, stagiaire_dev101)."))

            # 2. Créneaux Horaires (Lundi=1 à Samedi=6, 4 séances par jour)
            horaires = [
                (1, time(8, 30), time(11, 0)),
                (2, time(11, 0), time(13, 30)),
                (3, time(13, 30), time(16, 0)),
                (4, time(16, 0), time(18, 30)),
            ]
            creneaux_crees = 0
            for jour in range(1, 7):
                for num_s, h_deb, h_fin in horaires:
                    _, created = Creneau.objects.get_or_create(
                        jour=jour,
                        numero_seance=num_s,
                        defaults={
                            'heure_debut': h_deb,
                            'heure_fin': h_fin,
                            'duree_h': 2.5,
                        }
                    )
                    if created:
                        creneaux_crees += 1

            self.stdout.write(self.style.SUCCESS("[OK] Creneaux configures (24 creneaux de 2.5h)."))

            # 3. Année Scolaire, Semestres & Semaines
            annee, _ = AnneeScolaire.objects.get_or_create(
                libelle="2025/2026",
                defaults={
                    'date_debut': date(2025, 9, 8),
                    'date_fin': date(2026, 6, 30),
                    'active': True,
                }
            )

            s1, _ = Semestre.objects.get_or_create(
                annee_scolaire=annee,
                numero=1,
                defaults={'date_debut': date(2025, 9, 8), 'date_fin': date(2026, 1, 31)}
            )
            s2, _ = Semestre.objects.get_or_create(
                annee_scolaire=annee,
                numero=2,
                defaults={'date_debut': date(2026, 2, 9), 'date_fin': date(2026, 6, 30)}
            )

            # 16 Semaines pédagogiques pour le Semestre 1
            debut_base = date(2025, 9, 8)
            for num in range(1, 17):
                deb = debut_base + timedelta(weeks=num - 1)
                fin = deb + timedelta(days=5)
                Semaine.objects.get_or_create(
                    annee_scolaire=annee,
                    numero=num,
                    defaults={'semestre': s1, 'date_debut': deb, 'date_fin': fin, 'active': True}
                )

            self.stdout.write(self.style.SUCCESS("[OK] Annee 2025/2026 et 16 semaines initialisees."))

            # 4. Types de Salles et Salles
            ts_sc, _ = TypeSalle.objects.get_or_create(code="SC", defaults={'libelle': "Salle de Cours"})
            ts_sp, _ = TypeSalle.objects.get_or_create(code="SP", defaults={'libelle': "Salle Pratique Informatique"})
            ts_lab, _ = TypeSalle.objects.get_or_create(code="LABO", defaults={'libelle': "Laboratoire Reseau & Systemes"})
            ts_team, _ = TypeSalle.objects.get_or_create(code="TEAM", defaults={'libelle': "Virtuelle Microsoft Teams"})

            salles_data = [
                ("Salle 101", ts_sc, 30),
                ("Salle 102", ts_sc, 30),
                ("Salle 103", ts_sc, 30),
                ("Lab Info 1", ts_sp, 28),
                ("Lab Info 2", ts_sp, 28),
                ("Lab Info 3", ts_sp, 28),
                ("Lab Reseau", ts_lab, 24),
                ("Teams Distanciel", ts_team, 100),
            ]
            salles_dict = {}
            for nom, ts, cap in salles_data:
                s_obj, _ = Salle.objects.get_or_create(nom=nom, defaults={'type_salle': ts, 'capacite': cap, 'actif': True})
                salles_dict[nom] = s_obj

            self.stdout.write(self.style.SUCCESS("[OK] Salles physiques et virtuelles configurees."))

            # 5. Formateurs
            profs_data = [
                ("M1001", "Mohammed Alami", prof_user, "permanent", 30.0, salles_dict["Lab Info 1"]),
                ("M1002", "Fatima Zahra Mansouri", None, "permanent", 30.0, salles_dict["Lab Info 2"]),
                ("M1003", "Hassan El Idrissi", None, "permanent", 30.0, salles_dict["Salle 101"]),
                ("M1004", "Khadija Benali", None, "vacataire", 20.0, salles_dict["Salle 102"]),
                ("M1005", "Rachid Tahiri", None, "permanent", 30.0, salles_dict["Lab Reseau"]),
            ]
            profs_dict = {}
            for mat, nom, user_obj, stat, hmax, spref in profs_data:
                p_obj, _ = Professeur.objects.get_or_create(
                    matricule=mat,
                    defaults={
                        'nom_complet': nom,
                        'utilisateur': user_obj,
                        'statut': stat,
                        'heures_max_semaine': hmax,
                        'salle_preferee': spref,
                        'actif': True,
                    }
                )
                profs_dict[mat] = p_obj

            # Indisponibilités : Professeur vacataire bloqué le Samedi
            samedi_creneaux = Creneau.objects.filter(jour=6)
            for c in samedi_creneaux:
                Disponibilite.objects.get_or_create(
                    professeur=profs_dict["M1004"],
                    creneau=c,
                    defaults={'etat': Disponibilite.ETAT_BLOQUE}
                )

            # Vendredi après-midi bloqué pour Hassan El Idrissi
            vendredi_apm = Creneau.objects.filter(jour=5, numero_seance__in=[3, 4])
            for c in vendredi_apm:
                Disponibilite.objects.get_or_create(
                    professeur=profs_dict["M1003"],
                    creneau=c,
                    defaults={'etat': Disponibilite.ETAT_BLOQUE}
                )

            self.stdout.write(self.style.SUCCESS("[OK] Formateurs et contraintes de disponibilite initialises."))

            # 6. Secteur, Filières & Groupes
            sec_ntic, _ = Secteur.objects.get_or_create(code="NTIC", defaults={'intitule': "Technologies de l'Information"})
            fil_dev, _ = Filiere.objects.get_or_create(
                code="DEVOWFS",
                defaults={'intitule': "Développement Digital option Web Full Stack", 'secteur': sec_ntic, 'niveau': 'TS'}
            )
            fil_id, _ = Filiere.objects.get_or_create(
                code="IDOSR",
                defaults={'intitule': "Infrastructure Digitale option Systèmes & Réseaux", 'secteur': sec_ntic, 'niveau': 'TS'}
            )

            g_dev101, _ = Groupe.objects.get_or_create(code="DEV101", defaults={'filiere': fil_dev, 'annee_etude': 1, 'effectif': 28})
            g_dev102, _ = Groupe.objects.get_or_create(code="DEV102", defaults={'filiere': fil_dev, 'annee_etude': 1, 'effectif': 27})
            g_id101, _ = Groupe.objects.get_or_create(code="ID101", defaults={'filiere': fil_id, 'annee_etude': 1, 'effectif': 26})

            self.stdout.write(self.style.SUCCESS("[OK] Secteurs, filieres et groupes configures."))

            # 7. Modules
            mod_python, _ = Module.objects.get_or_create(code="M102", defaults={'intitule': "Programmation Python", 'type_module': 'technique'})
            mod_poo, _ = Module.objects.get_or_create(code="M103", defaults={'intitule': "POO & Conception UML", 'type_module': 'technique'})
            mod_web, _ = Module.objects.get_or_create(code="M104", defaults={'intitule': "Technologies Web HTML/CSS/JS", 'type_module': 'technique'})
            mod_soft, _ = Module.objects.get_or_create(code="EGTS101", defaults={'intitule': "Soft Skills & Communication", 'type_module': 'general'})
            mod_anglais, _ = Module.objects.get_or_create(code="EGTS102", defaults={'intitule': "Anglais Technique", 'type_module': 'general'})

            mod_python.types_salles_compatibles.set([ts_sp])
            mod_poo.types_salles_compatibles.set([ts_sp, ts_sc])
            mod_web.types_salles_compatibles.set([ts_sp])
            mod_soft.types_salles_compatibles.set([ts_sc])
            mod_anglais.types_salles_compatibles.set([ts_sc])

            # 8. Unités d'Enseignement et Volumes
            def creer_ue(module, groupe, prof, h_pres, fusion=None, passage_intensite=None):
                if fusion:
                    ue = UniteEnseignement.objects.filter(
                        module=module,
                        annee_scolaire=annee,
                        semestre=s1,
                        code_fusion=fusion,
                    ).first()
                    if not ue:
                        ue = UniteEnseignement.objects.create(
                            module=module,
                            annee_scolaire=annee,
                            semestre=s1,
                            code_fusion=fusion,
                        )
                else:
                    ue = UniteEnseignement.objects.filter(
                        module=module,
                        annee_scolaire=annee,
                        semestre=s1,
                        code_fusion__isnull=True,
                        unite_groupes__groupe=groupe,
                    ).first()
                    if not ue:
                        ue = UniteEnseignement.objects.create(
                            module=module,
                            annee_scolaire=annee,
                            semestre=s1,
                        )

                UniteGroupe.objects.get_or_create(unite=ue, groupe=groupe)
                UniteProfesseur.objects.get_or_create(unite=ue, professeur=prof, mode='presentiel')
                vol, _ = VolumeHoraire.objects.get_or_create(
                    unite=ue,
                    defaults={'h_total': h_pres, 'h_presentiel': h_pres, 'heures_effectuees': 0.0}
                )
                if passage_intensite:
                    Passage.objects.get_or_create(
                        unite=ue,
                        semaine_debut=1,
                        semaine_fin=8,
                        defaults={'intensite_h': passage_intensite, 'actif': True}
                    )
                return ue

            # DEV101 Modules
            creer_ue(mod_python, g_dev101, profs_dict["M1001"], 80.0)
            creer_ue(mod_poo, g_dev101, profs_dict["M1002"], 80.0)
            creer_ue(mod_web, g_dev101, profs_dict["M1001"], 75.0)
            creer_ue(mod_soft, g_dev101, profs_dict["M1004"], 40.0, passage_intensite=5.0)
            creer_ue(mod_anglais, g_dev101, profs_dict["M1004"], 30.0, passage_intensite=5.0)

            # DEV102 Modules
            creer_ue(mod_python, g_dev102, profs_dict["M1002"], 80.0)
            creer_ue(mod_poo, g_dev102, profs_dict["M1003"], 80.0)
            creer_ue(mod_web, g_dev102, profs_dict["M1002"], 75.0)
            creer_ue(mod_soft, g_dev102, profs_dict["M1004"], 40.0, passage_intensite=5.0)

            # Unité Fusionnée entre DEV101 et DEV102 pour une conférence commune
            ue_fusion, _ = UniteEnseignement.objects.get_or_create(
                module=mod_anglais,
                annee_scolaire=annee,
                semestre=s1,
                code_fusion="FUSION_DEV101_102_ANG",
            )
            UniteGroupe.objects.get_or_create(unite=ue_fusion, groupe=g_dev101)
            UniteGroupe.objects.get_or_create(unite=ue_fusion, groupe=g_dev102)
            UniteProfesseur.objects.get_or_create(unite=ue_fusion, professeur=profs_dict["M1004"], mode='presentiel')
            VolumeHoraire.objects.get_or_create(
                unite=ue_fusion,
                defaults={'h_total': 30.0, 'h_presentiel': 30.0, 'heures_effectuees': 0.0}
            )
            Passage.objects.get_or_create(
                unite=ue_fusion,
                semaine_debut=1,
                semaine_fin=6,
                defaults={'intensite_h': 5.0, 'actif': True}
            )

            self.stdout.write(self.style.SUCCESS("[OK] Unites d enseignement, volumes et passages configures."))

        self.stdout.write(self.style.SUCCESS("\n==> Donnees OFPPT creees avec succes ! Pret pour le solveur CP-SAT."))
