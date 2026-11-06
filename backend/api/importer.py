"""
Module d'import et de normalisation des fichiers de suivi d'avancement (Excel / CSV).
"""
import io
import csv
import logging
from typing import Dict, Any, List
import pandas as pd
from django.db import transaction

from core.models import (
    Module, Groupe, UniteEnseignement,
    VolumeHoraire, UniteGroupe, AnneeScolaire
)

logger = logging.getLogger(__name__)


class FichierAvancementImporter:
    """
    Importe et normalise un fichier CSV ou Excel de suivi des heures / avancement.
    Colonnes attendues (souples) :
    - 'groupe' ou 'code_groupe'
    - 'module' ou 'code_module'
    - 'heures_effectuees' ou 'realise'
    - 'h_presentiel' ou 'prescrit' (optionnel)
    """

    def __init__(self, uploaded_file, annee_scolaire: AnneeScolaire):
        self.file = uploaded_file
        self.annee_scolaire = annee_scolaire

    def importer(self) -> Dict[str, Any]:
        filename = self.file.name.lower()
        content = self.file.read()

        try:
            if filename.endswith('.csv'):
                df = self._lire_csv(content)
            elif filename.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(io.BytesIO(content))
            else:
                return {
                    'succes': False,
                    'message': "Format non supporté. Veuillez importer un fichier .xlsx, .xls ou .csv.",
                    'lignes_traitees': 0,
                    'erreurs': [],
                }
        except Exception as e:
            return {
                'succes': False,
                'message': f"Erreur de lecture du fichier : {str(e)}",
                'lignes_traitees': 0,
                'erreurs': [str(e)],
            }

        return self._traiter_dataframe(df)

    def _lire_csv(self, content: bytes) -> pd.DataFrame:
        """Tente plusieurs encodages pour les fichiers CSV."""
        for encoding in ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']:
            try:
                return pd.read_csv(io.BytesIO(content), encoding=encoding, sep=None, engine='python')
            except Exception:
                continue
        return pd.read_csv(io.BytesIO(content))

    def _normaliser_colonnes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Nettoie et standardise les noms de colonnes."""
        mapping = {}
        for col in df.columns:
            clean = str(col).strip().lower().replace(' ', '_').replace('é', 'e').replace('è', 'e')
            if clean in ('groupe', 'code_groupe', 'nom_groupe', 'id_groupe'):
                mapping[col] = 'groupe'
            elif clean in ('module', 'code_module', 'id_module', 'matiere'):
                mapping[col] = 'module'
            elif clean in ('heures_effectuees', 'realise', 'h_realisees', 'effectue'):
                mapping[col] = 'heures_effectuees'
            elif clean in ('h_presentiel', 'prescrit', 'total_presentiel', 'volume_presentiel'):
                mapping[col] = 'h_presentiel'
            elif clean in ('intitule', 'nom_module', 'titre'):
                mapping[col] = 'intitule'
        return df.rename(columns=mapping)

    def _traiter_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        df = self._normaliser_colonnes(df)
        lignes_traitees = 0
        lignes_ignorees = 0
        erreurs: List[str] = []

        if 'groupe' not in df.columns or 'module' not in df.columns:
            return {
                'succes': False,
                'message': "Colonnes requises manquantes. Le fichier doit contenir les colonnes 'groupe' et 'module'.",
                'lignes_traitees': 0,
                'erreurs': ["Colonnes obligatoires 'groupe' et 'module' introuvables."],
            }

        with transaction.atomic():
            for idx, row in df.iterrows():
                num_ligne = idx + 2
                groupe_code = str(row['groupe']).strip()
                module_code = str(row['module']).strip()

                if not groupe_code or not module_code or groupe_code == 'nan' or module_code == 'nan':
                    lignes_ignorees += 1
                    continue

                groupe = Groupe.objects.filter(code__iexact=groupe_code).first()
                if not groupe:
                    erreurs.append(f"Ligne {num_ligne} : Groupe '{groupe_code}' inexistant en base de données.")
                    lignes_ignorees += 1
                    continue

                module = Module.objects.filter(code__iexact=module_code).first()
                if not module:
                    intitule = str(row.get('intitule', f"Module {module_code}")).strip()
                    module = Module.objects.create(
                        code=module_code,
                        intitule=intitule if intitule != 'nan' else f"Module {module_code}",
                        type_module='technique',
                    )

                # Récupération ou création de l'Unité d'Enseignement
                ue = UniteEnseignement.objects.filter(
                    module=module,
                    annee_scolaire=self.annee_scolaire,
                    unite_groupes__groupe=groupe,
                ).first()

                if not ue:
                    ue = UniteEnseignement.objects.create(
                        module=module,
                        annee_scolaire=self.annee_scolaire,
                    )
                    UniteGroupe.objects.create(unite=ue, groupe=groupe)

                # Mise à jour des heures du volume horaire
                volume, _ = VolumeHoraire.objects.get_or_create(unite=ue)

                if 'heures_effectuees' in row and pd.notna(row['heures_effectuees']):
                    try:
                        volume.heures_effectuees = float(row['heures_effectuees'])
                    except ValueError:
                        erreurs.append(f"Ligne {num_ligne} : Valeur 'heures_effectuees' invalide.")

                if 'h_presentiel' in row and pd.notna(row['h_presentiel']):
                    try:
                        volume.h_presentiel = float(row['h_presentiel'])
                    except ValueError:
                        pass

                volume.save()
                lignes_traitees += 1

        return {
            'succes': True,
            'message': f"Importation terminée : {lignes_traitees} ligne(s) traitée(s) avec succès.",
            'lignes_traitees': lignes_traitees,
            'lignes_ignorees': lignes_ignorees,
            'erreurs': erreurs,
        }

