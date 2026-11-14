"""Façade du moteur de génération d'emplois du temps.

Le pseudo-code d'origine nomme cette façade ``GenerateurEmploiDuTemps``.  Elle
reste implémentée dans :mod:`solver.services` pour préserver les imports
existants ; ce module expose le point d'entrée officiel ainsi que les classes
de chaque phase.
"""
from .services import GenerateurEmploiDuTemps
from .donnees import Donnees, ParametresDonnees
from .passages import PlanificateurPassages, PassagePlan, ResultatPassages
from .heures import CalculateurHeures, UnitePrevision
from .decoupage import DecoupeurSeances, SeanceAPlacer
from .placement import ModelePlacement, ResultatPlacement, SeancePlacee
from .criteres import (
    Critere,
    UniciteOccupation,
    DisponibiliteProfesseur,
    ChargeProfesseur,
    CompatibiliteSalle,
    HeuresCreuses,
    JourneeDixHeures,
    PreferenceSalle,
    criteres_par_defaut,
)

__all__ = [
    'GenerateurEmploiDuTemps',
    'Donnees',
    'ParametresDonnees',
    'PlanificateurPassages',
    'PassagePlan',
    'ResultatPassages',
    'CalculateurHeures',
    'UnitePrevision',
    'DecoupeurSeances',
    'SeanceAPlacer',
    'ModelePlacement',
    'ResultatPlacement',
    'SeancePlacee',
    'Critere',
    'UniciteOccupation',
    'DisponibiliteProfesseur',
    'ChargeProfesseur',
    'CompatibiliteSalle',
    'HeuresCreuses',
    'JourneeDixHeures',
    'PreferenceSalle',
    'criteres_par_defaut',
]
