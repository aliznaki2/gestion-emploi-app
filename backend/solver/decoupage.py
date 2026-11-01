"""
Phase 2 : Découpeur de volumes horaires en séances atomiques de 2.5h.
Organisation en Blocs de 5h (2 créneaux consécutifs) et Séances simples.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from .heures import UnitePrevision


@dataclass
class SeanceAPlacer:
    """Représente une séance atomique de 2.5h à positionner par le solver CP-SAT."""
    id: int                              # Identifiant séquentiel dans le modèle CP-SAT
    unite_id: int
    module_id: int
    module_code: str
    module_type: str
    groupe_ids: List[int]
    professeur_ids: List[int]
    duree_h: float = 2.5
    nature: str = 'bloc'                 # 'bloc', 'simple', 'examen'
    bloc_id: Optional[int] = None        # Identifiant commun pour les 2 séances d'un bloc de 5h
    bloc_part: Optional[int] = None      # 1 (première séance) ou 2 (seconde séance consécutive)
    mode: str = 'presentiel'
    est_fusion: bool = False
    code_fusion: Optional[str] = None


class DecoupeurSeances:
    """
    Transforme les prévisions de volume horaire hebdomadaire en une liste
    de séances atomiques de 2.5h avec identification stricte des blocs de 5h.
    """
    DUREE_SEANCE = 2.5
    DUREE_BLOC = 5.0

    def __init__(self):
        self._seance_counter = 0
        self._bloc_counter = 0

    def decouper(self, previsions: List[UnitePrevision]) -> List[SeanceAPlacer]:
        """
        Découpe toutes les unités prévues en séances élémentaires de 2.5h.
        """
        seances: List[SeanceAPlacer] = []

        for prev in previsions:
            heures_a_traiter = prev.heures_prevues
            unite = prev.unite
            module = unite.module
            est_fusion = bool(prev.code_fusion)

            # Découpage par tranche de 5h (Blocs)
            while heures_a_traiter >= self.DUREE_BLOC:
                self._bloc_counter += 1
                b_id = self._bloc_counter

                # Séance 1 du bloc
                self._seance_counter += 1
                s1 = SeanceAPlacer(
                    id=self._seance_counter,
                    unite_id=prev.unite_id,
                    module_id=module.id,
                    module_code=module.code,
                    module_type=module.type_module,
                    groupe_ids=list(prev.groupe_ids),
                    professeur_ids=list(prev.professeur_ids),
                    duree_h=self.DUREE_SEANCE,
                    nature='bloc',
                    bloc_id=b_id,
                    bloc_part=1,
                    mode='presentiel',
                    est_fusion=est_fusion,
                    code_fusion=prev.code_fusion,
                )
                seances.append(s1)

                # Séance 2 du bloc
                self._seance_counter += 1
                s2 = SeanceAPlacer(
                    id=self._seance_counter,
                    unite_id=prev.unite_id,
                    module_id=module.id,
                    module_code=module.code,
                    module_type=module.type_module,
                    groupe_ids=list(prev.groupe_ids),
                    professeur_ids=list(prev.professeur_ids),
                    duree_h=self.DUREE_SEANCE,
                    nature='bloc',
                    bloc_id=b_id,
                    bloc_part=2,
                    mode='presentiel',
                    est_fusion=est_fusion,
                    code_fusion=prev.code_fusion,
                )
                seances.append(s2)

                heures_a_traiter -= self.DUREE_BLOC

            # Séance simple résiduelle de 2.5h
            if heures_a_traiter >= self.DUREE_SEANCE:
                self._seance_counter += 1
                s_simple = SeanceAPlacer(
                    id=self._seance_counter,
                    unite_id=prev.unite_id,
                    module_id=module.id,
                    module_code=module.code,
                    module_type=module.type_module,
                    groupe_ids=list(prev.groupe_ids),
                    professeur_ids=list(prev.professeur_ids),
                    duree_h=self.DUREE_SEANCE,
                    nature='simple',
                    bloc_id=None,
                    bloc_part=None,
                    mode='presentiel',
                    est_fusion=est_fusion,
                    code_fusion=prev.code_fusion,
                )
                seances.append(s_simple)
                heures_a_traiter -= self.DUREE_SEANCE

        return seances

