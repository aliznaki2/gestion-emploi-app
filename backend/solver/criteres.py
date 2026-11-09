"""Critères de placement (patron de stratégie).

Chaque critère décrit une règle dure ou souple du modèle CP-SAT.  Le
``ModelePlacement`` lit les poids déclarés ici pour construire son objectif et
utilise ``appliquer`` pour les critères qui ajoutent des contraintes
spécifiques.  Les critères non encore programmés restent déclarés avec
``actif = False`` afin de rendre l'écart visible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - uniquement pour les annotations
    from .placement import ModelePlacement


@dataclass
class Critere:
    """Base d'un critère de placement."""

    nom: str
    type: str = 'souple'          # 'dur' | 'souple'
    poids: int = 0
    actif: bool = True
    description: str = ''

    def appliquer(self, modele: "ModelePlacement") -> None:
        """Applique le critère au modèle.  No-op par défaut."""
        return None

    def evaluer(self, modele: "ModelePlacement", resultat: Any) -> int:
        """Évalue le critère sur une solution (diagnostic)."""
        return 0

    def as_dict(self) -> dict:
        return {
            'nom': self.nom,
            'type': self.type,
            'poids': self.poids,
            'actif': self.actif,
            'description': self.description,
        }


class UniciteOccupation(Critere):
    """Au plus une séance par groupe / formateur et par créneau."""

    def __init__(self):
        super().__init__(
            nom='UniciteOccupation',
            type='dur',
            poids=0,
            description="Un groupe et un formateur ne peuvent suivre deux séances au même créneau.",
        )


class DisponibiliteProfesseur(Critere):
    """Interdit les créneaux bloqués d'un formateur."""

    def __init__(self):
        super().__init__(
            nom='DisponibiliteProfesseur',
            type='dur',
            poids=0,
            description="Aucune séance sur un créneau bloqué d'un formateur.",
        )


class ChargeProfesseur(Critere):
    """Respecte le plafond hebdomadaire de chaque formateur."""

    def __init__(self):
        super().__init__(
            nom='ChargeProfesseur',
            type='dur',
            poids=0,
            description="La charge d'un formateur ne dépasse pas son maximum hebdomadaire.",
        )


class CompatibiliteSalle(Critere):
    """Le type de salle choisi doit être accepté par le module."""

    def __init__(self):
        super().__init__(
            nom='CompatibiliteSalle',
            type='dur',
            poids=0,
            description="Chaque séance présentielle utilise une salle d'un type accepté.",
        )


class HeuresCreuses(Critere):
    """Pénalise les trous dans la journée d'un groupe ou d'un formateur."""

    def __init__(self, poids_groupe: int = 30, poids_prof: int = 10):
        super().__init__(
            nom='HeuresCreuses',
            type='souple',
            poids=poids_groupe,
            description="Évite les séances isolées entre deux périodes occupées.",
        )
        self.poids_groupe = poids_groupe
        self.poids_prof = poids_prof

    def as_dict(self) -> dict:
        data = super().as_dict()
        data.update({'poids_groupe': self.poids_groupe, 'poids_prof': self.poids_prof})
        return data


class JourneeDixHeures(Critere):
    """Pénalise les journées de 10 h (4 séances) pour un groupe."""

    def __init__(self, poids: int = 40):
        super().__init__(
            nom='JourneeDixHeures',
            type='souple',
            poids=poids,
            description="Évite de remplir les quatre séances d'une même journée.",
        )


class PreferenceSalle(Critere):
    """Favorise la salle préférée du formateur et les salles spécialisées."""

    def __init__(self, poids: int = 3):
        super().__init__(
            nom='PreferenceSalle',
            type='souple',
            poids=poids,
            description="Préfère la salle habituelle du formateur et les salles SP.",
        )


class PassageActif(Critere):
    """Critère déjà couvert par la phase 0/1 (déclaré pour mémoire)."""

    def __init__(self):
        super().__init__(
            nom='PassageActif',
            type='dur',
            poids=0,
            actif=False,
            description="Un module général n'est planifié que pendant son passage.",
        )


class SeanceExamen(Critere):
    """Place les EFM au jour prévu (critère non encore généralisé)."""

    def __init__(self):
        super().__init__(
            nom='SeanceExamen',
            type='souple',
            poids=5000,
            actif=False,
            description="Place les séances d'examen au jour de l'EFM.",
        )


class EquilibreSalles(Critere):
    """Équilibre l'utilisation des salles (non programmé)."""

    def __init__(self):
        super().__init__(
            nom='EquilibreSalles',
            type='souple',
            poids=0,
            actif=False,
            description="Répartit la charge entre les salles de même type.",
        )


class StabiliteSemaine(Critere):
    """Favorise la stabilité par rapport à la semaine précédente (non programmé)."""

    def __init__(self):
        super().__init__(
            nom='StabiliteSemaine',
            type='souple',
            poids=0,
            actif=False,
            description="Conserve les créneaux de la semaine précédente quand c'est possible.",
        )


class PreferencesProfesseur(Critere):
    """Respecte les créneaux préférés des formateurs (non programmé)."""

    def __init__(self):
        super().__init__(
            nom='PreferencesProfesseur',
            type='souple',
            poids=0,
            actif=False,
            description="Place les séances sur les créneaux marqués « préférés ».",
        )


def criteres_par_defaut() -> list:
    """Liste ordonnée des critères utilisés par la génération."""
    return [
        UniciteOccupation(),
        DisponibiliteProfesseur(),
        ChargeProfesseur(),
        CompatibiliteSalle(),
        HeuresCreuses(),
        JourneeDixHeures(),
        PreferenceSalle(),
        PassageActif(),
        SeanceExamen(),
        EquilibreSalles(),
        StabiliteSemaine(),
        PreferencesProfesseur(),
    ]


def criteres_actifs() -> list:
    return [c for c in criteres_par_defaut() if c.actif]
