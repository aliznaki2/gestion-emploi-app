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
    jour_efm: Optional[int] = None       # Jour précis (1-6) où placer l'EFM


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

    def decouper(self, previsions: List[UnitePrevision], semaine_numero: int = 1) -> List[SeanceAPlacer]:
        """
        Découpe toutes les unités prévues en séances élémentaires de 2.5h.

        La part de séances à distance suit la part d'heures synchrones de
        l'unité (``frac_sync``) avec un tirage pseudo-aléatoire stable.
        """
        seances: List[SeanceAPlacer] = []

        for prev in previsions:
            heures_a_traiter = prev.heures_prevues
            unite = prev.unite
            module = unite.module
            est_fusion = bool(prev.code_fusion)
            autorise_2_5 = bool(getattr(module, 'peut_avoir_seance_2_5', False))
            nb_avant = len(seances)
            k = 0

            def mode_et_profs():
                """Choisit le mode et les formateurs d'une session."""
                nonlocal k
                frac = float(prev.frac_sync or 0.0)
                distance = frac > 0 and self._alea(prev.unite_id, semaine_numero, k) < frac
                k += 1
                if distance:
                    profs = list(prev.professeur_sync_ids) or list(prev.professeur_ids)
                    return 'distance', profs
                return 'presentiel', list(prev.professeur_ids)

            # Découpage par tranche de 5h (Blocs)
            while heures_a_traiter >= self.DUREE_BLOC:
                self._bloc_counter += 1
                b_id = self._bloc_counter
                mode, profs = mode_et_profs()

                # Séance 1 du bloc
                self._seance_counter += 1
                s1 = SeanceAPlacer(
                    id=self._seance_counter,
                    unite_id=prev.unite_id,
                    module_id=module.id,
                    module_code=module.code,
                    module_type=module.type_module,
                    groupe_ids=list(prev.groupe_ids),
                    professeur_ids=list(profs),
                    duree_h=self.DUREE_SEANCE,
                    nature='bloc',
                    bloc_id=b_id,
                    bloc_part=1,
                    mode=mode,
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
                    professeur_ids=list(profs),
                    duree_h=self.DUREE_SEANCE,
                    nature='bloc',
                    bloc_id=b_id,
                    bloc_part=2,
                    mode=mode,
                    est_fusion=est_fusion,
                    code_fusion=prev.code_fusion,
                )
                seances.append(s2)

                heures_a_traiter -= self.DUREE_BLOC

            # Séance simple résiduelle de 2.5h — strictement réservée aux modules
            # qui autorisent les séances de 2,5 h. Un module décoché ne doit
            # jamais produire de séance isolée de 2,5 h (y compris pour l'EFM).
            if autorise_2_5 and heures_a_traiter >= self.DUREE_SEANCE:
                mode, profs = mode_et_profs()
                self._seance_counter += 1
                s_simple = SeanceAPlacer(
                    id=self._seance_counter,
                    unite_id=prev.unite_id,
                    module_id=module.id,
                    module_code=module.code,
                    module_type=module.type_module,
                    groupe_ids=list(prev.groupe_ids),
                    professeur_ids=list(profs),
                    duree_h=self.DUREE_SEANCE,
                    nature='simple',
                    bloc_id=None,
                    bloc_part=None,
                    mode=mode,
                    est_fusion=est_fusion,
                    code_fusion=prev.code_fusion,
                )
                seances.append(s_simple)
                heures_a_traiter -= self.DUREE_SEANCE

            # EFM : la dernière séance du module (lors de sa dernière semaine)
            # est marquée comme examen afin que les stagiaires la repèrent.
            if (
                prev.derniere_semaine
                and getattr(module, 'efm_fin_module', False)
                and len(seances) > nb_avant
            ):
                seances[-1].nature = 'examen'
                seances[-1].jour_efm = prev.jour_efm

        return seances

    @staticmethod
    def _alea(unite_id: int, semaine: int, k: int) -> float:
        """Nombre pseudo-aléatoire stable dans [0, 1)."""
        return ((unite_id * 7919 + semaine * 104729 + k * 1299709) % 1000) / 1000.0

