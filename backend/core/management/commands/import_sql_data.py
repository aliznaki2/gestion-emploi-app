"""
Commande de chargement complet du jeu de données officiel OFPPT (592 lignes).
Importe l'intégralité des 44 groupes, filières, formateurs, modules et volumes
depuis le fichier backend/data/02_import_donnees.sql dans l'ORM Django.
"""
import os
import re
from datetime import date, time, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings

from core.models import (
    Utilisateur, Secteur, Filiere, Groupe, TypeSalle, Salle,
    Module, AnneeScolaire, Semestre, Semaine, Professeur,
    Creneau, Disponibilite, UniteEnseignement, UniteGroupe,
    VolumeHoraire, UniteProfesseur, Passage
)


class Command(BaseCommand):
    help = "Charge toutes les données réelles OFPPT (44 groupes, formateurs, modules) depuis 02_import_donnees.sql"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Lecture du fichier data/02_import_donnees.sql..."))

        sql_path = os.path.join(settings.BASE_DIR, 'data', '02_import_donnees.sql')
        if not os.path.exists(sql_path):
            self.stdout.write(self.style.ERROR(f"Fichier non trouvé : {sql_path}"))
            return

        with open(sql_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extraction des tuples d'insertion
        raw_tuples = self._extraire_tuples(content)
        self.stdout.write(self.style.NOTICE(f"{len(raw_tuples)} lignes extraites du fichier SQL."))

        parsed_rows = []
        for t_str in raw_tuples:
            vals = self._parse_sql_tuple(t_str)
            if len(vals) >= 48:
                parsed_rows.append(vals)

        self.stdout.write(self.style.NOTICE(f"{len(parsed_rows)} lignes normalisées avec succès."))

        with transaction.atomic():
            self._importer_donnees(parsed_rows)

        self.stdout.write(self.style.SUCCESS(
            "\n[SUCCES] L'intégralité des données officielles OFPPT (44 groupes) a été importée dans Django !"
        ))

    def _extraire_tuples(self, sql_content: str):
        """Extrait les blocs de tuples dans les requêtes INSERT INTO stg_avancement."""
        insert_blocks = re.findall(
            r'INSERT INTO stg_avancement\s*\([^)]+\)\s*VALUES\s*(.*?);',
            sql_content,
            re.DOTALL | re.IGNORECASE
        )
        tuples = []
        for block in insert_blocks:
            pos = 0
            n = len(block)
            while pos < n:
                start = block.find('(', pos)
                if start == -1:
                    break
                in_quote = False
                i = start + 1
                while i < n:
                    ch = block[i]
                    if ch == "'":
                        if in_quote and i + 1 < n and block[i + 1] == "'":
                            i += 1
                        else:
                            in_quote = not in_quote
                    elif ch == ')' and not in_quote:
                        break
                    i += 1
                end = i
                tuples.append(block[start + 1:end])
                pos = end + 1
        return tuples

    def _parse_sql_tuple(self, tuple_str: str):
        """Découpe les valeurs d'un tuple SQL en tenant compte des chaînes entre apostrophes."""
        values = []
        cur = []
        in_quote = False
        i = 0
        n = len(tuple_str)

        while i < n:
            ch = tuple_str[i]
            if ch == "'":
                if in_quote and i + 1 < n and tuple_str[i + 1] == "'":
                    cur.append("'")
                    i += 1
                else:
                    in_quote = not in_quote
            elif ch == ',' and not in_quote:
                val = ''.join(cur).strip()
                values.append(self._nettoyer_val(val))
                cur = []
            else:
                cur.append(ch)
            i += 1

        if cur:
            val = ''.join(cur).strip()
            values.append(self._nettoyer_val(val))

        return values

    def _nettoyer_val(self, val: str):
        if val.upper() == 'NULL':
            return None
        if val.startswith("'") and val.endswith("'"):
            return val[1:-1].strip()
        try:
            if '.' in val:
                return float(val)
            return int(val)
        except ValueError:
            return val

    def _importer_donnees(self, rows):
        """Insère les données normalisées dans les modèles Django."""
        self.stdout.write(self.style.NOTICE("Nettoyage des anciennes sessions et unités..."))
        from core.models import SeanceProfesseur, SeanceGroupe, Seance
        SeanceProfesseur.objects.all().delete()
        SeanceGroupe.objects.all().delete()
        Seance.objects.all().delete()
        Passage.objects.all().delete()
        VolumeHoraire.objects.all().delete()
        UniteProfesseur.objects.all().delete()
        UniteGroupe.objects.all().delete()
        UniteEnseignement.objects.all().delete()

        # 1. Année scolaire et semestres
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

        # 16 Semaines pédagogiques
        debut_base = date(2025, 9, 8)
        for num in range(1, 17):
            deb = debut_base + timedelta(weeks=num - 1)
            fin = deb + timedelta(days=5)
            Semaine.objects.get_or_create(
                annee_scolaire=annee,
                numero=num,
                defaults={'semestre': s1, 'date_debut': deb, 'date_fin': fin, 'active': True}
            )

        # 2. Créneaux (Lundi=1 à Samedi=6, 4 créneaux)
        horaires = [
            (1, time(8, 30), time(11, 0)),
            (2, time(11, 0), time(13, 30)),
            (3, time(13, 30), time(16, 0)),
            (4, time(16, 0), time(18, 30)),
        ]
        for jour in range(1, 7):
            for num_s, h_deb, h_fin in horaires:
                Creneau.objects.get_or_create(
                    jour=jour,
                    numero_seance=num_s,
                    defaults={'heure_debut': h_deb, 'heure_fin': h_fin, 'duree_h': 2.5}
                )

        # 3. Types de Salles et Salles
        ts_sc, _ = TypeSalle.objects.get_or_create(code="SC", defaults={'libelle': "Salle de Cours"})
        ts_sp, _ = TypeSalle.objects.get_or_create(code="SP", defaults={'libelle': "Salle Pratique Informatique"})
        ts_lab, _ = TypeSalle.objects.get_or_create(code="LABO", defaults={'libelle': "Laboratoire Réseau & Systèmes"})
        ts_sem, _ = TypeSalle.objects.get_or_create(code="SEM", defaults={'libelle': "Salle de Séminaire"})
        ts_team, _ = TypeSalle.objects.get_or_create(code="TEAM", defaults={'libelle': "Virtuelle Microsoft Teams"})

        salles_config = [
            ("SP1", ts_sp, 30), ("SP2", ts_sp, 30), ("SP3", ts_sp, 30),
            ("SP4", ts_sp, 30), ("SP5", ts_sp, 30), ("SP6", ts_sp, 30),
            ("SP7", ts_sp, 30), ("SP8", ts_sp, 30), ("SP9", ts_sp, 30),
            ("SC1", ts_sc, 30), ("SC2", ts_sc, 30), ("SC3", ts_sc, 30),
            ("SC4", ts_sc, 30), ("SC5", ts_sc, 30), ("SC6", ts_sc, 30),
            ("SC7", ts_sc, 30), ("SC8", ts_sc, 30), ("SC9", ts_sc, 30),
            ("SC10", ts_sc, 30),
            ("LABO1", ts_lab, 26), ("LABO2", ts_lab, 26),
            ("SEM1", ts_sem, 40),
            ("Teams Distanciel 1", ts_team, 200),
            ("Teams Distanciel 2", ts_team, 200),
        ]
        salles_map = {}
        for nom, ts, cap in salles_config:
            s_obj, _ = Salle.objects.get_or_create(
                nom=nom,
                defaults={'type_salle': ts, 'capacite': cap, 'actif': True}
            )
            salles_map[nom] = s_obj

        # 4. Secteurs et Filières
        secteurs_map = {}
        filieres_map = {}
        modules_map = {}
        profs_map = {}
        groupes_map = {}

        # Dictionnaires pour regrouper les unités d'enseignement
        # cle_unite -> list of rows
        unites_dict = {}

        for row in rows:
            # Indices selon l'ordre du INSERT :
            # 3: secteur, 4: code_filiere, 5: filiere, 8: groupe, 9: effectif_groupe,
            # 13: code_fusion, 14: annee_formation, 15: mode_formation, 16: code_module, 17: module,
            # 18: regional, 19: mle_present, 20: formateur_present, 21: mle_syn, 22: formateur_syn,
            # 23: mhp_s1, 24: mhsyn_s1, 37: mh_real_present
            secteur_nom = str(row[3]).strip() if row[3] else "Général"
            code_filiere = str(row[4]).strip()
            filiere_nom = str(row[5]).strip() if row[5] else code_filiere
            niveau = str(row[2]).strip() if row[2] else "TS"
            groupe_code = str(row[8]).strip()
            effectif = int(row[9]) if row[9] else 25
            code_fusion = str(row[13]).strip() if row[13] and str(row[13]).strip() not in ('0', 'None', '') else None
            annee_form = int(row[14]) if row[14] else 1
            mode_form = str(row[15]).strip().lower() if row[15] else 'presentiel'
            code_module = str(row[16]).strip()
            module_nom = str(row[17]).strip() if row[17] else code_module
            is_regional = (str(row[18]).strip().upper() == 'O')
            mle_pres = str(row[19]).strip() if row[19] else None
            nom_pres = str(row[20]).strip() if row[20] else None
            mle_syn = str(row[21]).strip() if row[21] else None
            nom_syn = str(row[22]).strip() if row[22] else None

            hp_s1 = float(row[23]) if row[23] else 0.0
            hsyn_s1 = float(row[24]) if row[24] else 0.0
            hasyn_s1 = float(row[25]) if len(row) > 25 and row[25] else 0.0

            hp_s2 = float(row[27]) if len(row) > 27 and row[27] else 0.0
            hsyn_s2 = float(row[28]) if len(row) > 28 and row[28] else 0.0
            hasyn_s2 = float(row[29]) if len(row) > 29 and row[29] else 0.0

            h_real_s1 = float(row[38]) if len(row) > 38 and row[38] else 0.0

            # Secteur
            if secteur_nom not in secteurs_map:
                sec_obj, _ = Secteur.objects.get_or_create(
                    code=secteur_nom[:20].upper(),
                    defaults={'intitule': secteur_nom}
                )
                secteurs_map[secteur_nom] = sec_obj

            # Filière
            if code_filiere not in filieres_map:
                fil_obj, _ = Filiere.objects.get_or_create(
                    code=code_filiere,
                    defaults={
                        'intitule': filiere_nom,
                        'secteur': secteurs_map[secteur_nom],
                        'niveau': niveau,
                    }
                )
                filieres_map[code_filiere] = fil_obj

            # Groupe
            if groupe_code not in groupes_map:
                grp_obj, _ = Groupe.objects.get_or_create(
                    code=groupe_code,
                    defaults={
                        'filiere': filieres_map[code_filiere],
                        'annee_etude': annee_form,
                        'effectif': effectif,
                        'mode_formation': 'presentiel',
                        'actif': True,
                    }
                )
                groupes_map[groupe_code] = grp_obj

            # Module
            mod_key = code_module
            if mod_key not in modules_map:
                t_mod = 'general' if code_module.startswith('EGTS') else 'technique'
                mod_obj, _ = Module.objects.get_or_create(
                    code=code_module,
                    defaults={
                        'intitule': module_nom,
                        'type_module': t_mod,
                        'regional': is_regional,
                    }
                )
                if t_mod == 'general':
                    mod_obj.types_salles_compatibles.set([ts_sc])
                else:
                    mod_obj.types_salles_compatibles.set([ts_sp, ts_sc])
                modules_map[mod_key] = mod_obj

            # Professeur présentiel
            if mle_pres and nom_pres and mle_pres not in profs_map:
                prof_obj, _ = Professeur.objects.get_or_create(
                    matricule=mle_pres,
                    defaults={
                        'nom_complet': nom_pres,
                        'statut': 'permanent',
                        'heures_max_semaine': 30.0,
                        'actif': True,
                    }
                )
                profs_map[mle_pres] = prof_obj

            # Professeur synchrone
            if mle_syn and nom_syn and mle_syn not in profs_map:
                prof_obj, _ = Professeur.objects.get_or_create(
                    matricule=mle_syn,
                    defaults={
                        'nom_complet': nom_syn,
                        'statut': 'permanent',
                        'heures_max_semaine': 30.0,
                        'actif': True,
                    }
                )
                profs_map[mle_syn] = prof_obj

            # Clé de regroupement pour les fusions
            if code_fusion:
                cle_u = f"FUSION|{code_fusion}|{code_module}"
            else:
                cle_u = f"SOLO|{groupe_code}|{code_module}"

            # Semestre 1 : si des heures sont prévues au S1
            if hp_s1 + hsyn_s1 + hasyn_s1 > 0:
                unites_dict.setdefault((cle_u, 1), []).append({
                    'groupe': groupe_code,
                    'module': code_module,
                    'code_fusion': code_fusion,
                    'mle_pres': mle_pres,
                    'mle_syn': mle_syn,
                    'hp': hp_s1,
                    'hsyn': hsyn_s1,
                    'hasyn': hasyn_s1,
                    'h_real': h_real_s1,
                    'sem': 1,
                })

            # Semestre 2 : si des heures sont prévues au S2
            if hp_s2 + hsyn_s2 + hasyn_s2 > 0:
                unites_dict.setdefault((cle_u, 2), []).append({
                    'groupe': groupe_code,
                    'module': code_module,
                    'code_fusion': code_fusion,
                    'mle_pres': mle_pres,
                    'mle_syn': mle_syn,
                    'hp': hp_s2,
                    'hsyn': hsyn_s2,
                    'hasyn': hasyn_s2,
                    'h_real': 0.0,
                    'sem': 2,
                })

        self.stdout.write(self.style.SUCCESS(f"-> {len(groupes_map)} groupes identifiés et enregistrés."))
        self.stdout.write(self.style.SUCCESS(f"-> {len(profs_map)} professeurs identifiés et enregistrés."))
        self.stdout.write(self.style.SUCCESS(f"-> {len(modules_map)} modules identifiés et enregistrés."))

        # 5. Création des Unités d'Enseignement et Volumes par Semestre
        nb_unites_creees = 0
        for (cle_u, sem_num), items in unites_dict.items():
            first = items[0]
            module_obj = modules_map[first['module']]
            code_fusion = first['code_fusion']
            sem_obj = s1 if sem_num == 1 else s2

            ue = UniteEnseignement.objects.create(
                module=module_obj,
                annee_scolaire=annee,
                semestre=sem_obj,
                code_fusion=code_fusion,
            )
            nb_unites_creees += 1

            # Affecter les groupes (sans doublon)
            seen_grp = set()
            for item in items:
                grp = groupes_map.get(item['groupe'])
                if grp and grp.id not in seen_grp:
                    UniteGroupe.objects.create(unite=ue, groupe=grp)
                    seen_grp.add(grp.id)

            # Affecter les formateurs (sans doublon)
            seen_profs = set()
            for item in items:
                if item['mle_pres'] and item['mle_pres'] in profs_map:
                    prof_obj = profs_map[item['mle_pres']]
                    if (prof_obj.id, 'presentiel') not in seen_profs:
                        UniteProfesseur.objects.create(
                            unite=ue,
                            professeur=prof_obj,
                            mode='presentiel'
                        )
                        seen_profs.add((prof_obj.id, 'presentiel'))
                if item['mle_syn'] and item['mle_syn'] in profs_map:
                    prof_obj = profs_map[item['mle_syn']]
                    if (prof_obj.id, 'distance') not in seen_profs:
                        UniteProfesseur.objects.create(
                            unite=ue,
                            professeur=prof_obj,
                            mode='distance'
                        )
                        seen_profs.add((prof_obj.id, 'distance'))

            # Volume horaire exact du semestre selon stg_avancement
            hp = max(item['hp'] for item in items)
            hs = max(item['hsyn'] for item in items)
            ha = max(item['hasyn'] for item in items)
            hr = max(item['h_real'] for item in items)

            VolumeHoraire.objects.create(
                unite=ue,
                h_total=hp + hs + ha,
                h_presentiel=hp,
                h_synchrone=hs,
                h_asynchrone=ha,
                heures_effectuees=min(hr, hp),
            )

            # Passages pour les modules généraux
            if module_obj.type_module == 'general':
                # Alternance pédagogique :
                # Les premiers modules généraux (Arabe, Français, PIE) en semaines 1 à 8 (première moitié)
                # Les suivants (Anglais, Soft Skills, Culture Numérique) en semaines 9 à 16 (deuxième moitié)
                code_up = module_obj.code.upper()
                is_first_block = any(k in code_up for k in ['101', '102', '108', '201', '202', '301', '302'])
                sem_deb = 1 if is_first_block else 9
                sem_fin = 8 if is_first_block else 16

                Passage.objects.create(
                    unite=ue,
                    semaine_debut=sem_deb,
                    semaine_fin=sem_fin,
                    intensite_h=5.0,
                    actif=True,
                )

        self.stdout.write(self.style.SUCCESS(f"-> {nb_unites_creees} unités d'enseignement configurées."))
