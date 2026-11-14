"""Phase 3 : placement des séances, en trois étapes dérivées l'une de l'autre.

1. **Emploi des formateurs** (``emploi_formateurs``) — chaque séance reçoit un
   créneau.  C'est la source de vérité de la semaine.
2. **Emploi des stagiaires** (``emploi_stagiaires``) — projection de l'étape 1 :
   chaque groupe suit les séances qui le citent.  On la vérifie et on la mesure.
3. **Emploi des salles** (``emploi_salles``) — une salle par séance présentielle,
   à partir des créneaux déjà fixés.

``ModelePlacement`` reste la façade utilisée par ``services.py`` : mêmes
paramètres, mêmes classes de résultat, avec en plus le détail de chaque étape.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models import Creneau, Professeur, Salle

from .decoupage import SeanceAPlacer
from .emploi_formateurs import EmploiFormateurs
from .emploi_salles import EmploiSalles
from .emploi_stagiaires import statistiques_emplois, verifier_emplois
from .parametres import Poids


@dataclass
class SeancePlacee:
    """Résultat du placement d'une séance élémentaire."""
    seance_a_placer_id: int
    unite_id: int
    creneau_id: int
    salle_id: Optional[int]
    professeur_id: Optional[int]
    groupe_ids: List[int]
    nature: str
    bloc_no: Optional[int]
    mode: str
    professeur_ids: List[int] = field(default_factory=list)


@dataclass
class ResultatPlacement:
    """Conteneur du résultat du placement."""
    succes: bool
    statut: str
    seances_placees: List[SeancePlacee] = field(default_factory=list)
    temps_resolution_ms: int = 0
    score_penalite: int = 0
    message: str = ""
    borne: Optional[int] = None
    # Détail des trois emplois (indicateurs) et alertes à afficher au planificateur.
    emplois: Dict[str, Any] = field(default_factory=dict)
    avertissements: List[str] = field(default_factory=list)
    etapes: Dict[str, Any] = field(default_factory=dict)


class ModelePlacement:
    """Orchestre les trois étapes du placement pour une semaine."""

    def __init__(
        self,
        seances: List[SeanceAPlacer],
        creneaux: List[Creneau],
        salles: List[Salle],
        professeurs: List[Professeur],
        disponibilites: Optional[Dict[Tuple[int, int], str]] = None,
        salles_compatibles_map: Optional[Dict[int, List[int]]] = None,
        occupations_groupes: Optional[Set[Tuple[int, int]]] = None,
        occupations_profs: Optional[Set[Tuple[int, int]]] = None,
        occupations_salles: Optional[Set[Tuple[int, int]]] = None,
        criteres: Optional[List[object]] = None,
        charges_conservees: Optional[Dict[int, float]] = None,
    ):
        self.seances = seances
        self.creneaux = sorted(creneaux, key=lambda c: (c.jour, c.numero_seance))
        self.salles = salles
        self.professeurs = professeurs
        self.disponibilites = disponibilites or {}  # (prof_id, creneau_id) -> 'disponible' | 'bloque' | 'prefere'
        self.salles_compatibles_map = salles_compatibles_map or {}  # module_id -> [salle_id, ...]
        self.criteres: List[object] = list(criteres or [])
        self.charges_conservees = charges_conservees or {}  # prof_id -> heures déjà conservées

        # Créneaux déjà occupés par des séances conservées (validées / verrouillées)
        self.occupations_groupes = occupations_groupes or set()  # (creneau_id, groupe_id)
        self.occupations_profs = occupations_profs or set()      # (creneau_id, prof_id)
        self.occupations_salles = occupations_salles or set()    # (creneau_id, salle_id)

        self.creneaux_map = {c.id: c for c in self.creneaux}
        self.salles_map = {s.id: s for s in self.salles}
        self.professeurs_map = {p.id: p for p in self.professeurs}

    # ─── Critères (patron de stratégie) ───────────────────────────────────────
    def ajouter_critere(self, critere) -> "ModelePlacement":
        """Ajoute un critère de placement au modèle."""
        self.criteres.append(critere)
        return self

    def critere(self, nom: str):
        return next((c for c in self.criteres if getattr(c, 'nom', None) == nom), None)

    def poids(self, nom: str, defaut: int = 0) -> int:
        """Poids d'un critère actif, ou valeur par défaut."""
        critere = self.critere(nom)
        if critere is None:
            return defaut
        if not getattr(critere, 'actif', True):
            return 0
        return int(getattr(critere, 'poids', defaut) or 0)

    def construire_poids(self) -> Poids:
        """Poids effectifs : ceux des critères enregistrés, sinon les défauts."""
        base = Poids()
        heures_creuses = self.critere('HeuresCreuses')
        if heures_creuses is not None and getattr(heures_creuses, 'actif', True):
            trou_groupe = int(getattr(heures_creuses, 'poids_groupe', base.trou_groupe) or 0)
            trou_prof = int(getattr(heures_creuses, 'poids_prof', base.trou_formateur) or 0)
        elif heures_creuses is not None:
            trou_groupe = trou_prof = 0
        else:
            trou_groupe, trou_prof = base.trou_groupe, base.trou_formateur
        return Poids(
            trou_formateur=trou_prof,
            trou_groupe=trou_groupe,
            journee_10h=self.poids('JourneeDixHeures', base.journee_10h),
            salle_preferee=self.poids('PreferenceSalle', base.salle_preferee),
        )

    # ─── Candidats ────────────────────────────────────────────────────────────
    def _get_salles_candidates(self, s: SeanceAPlacer) -> List[Salle]:
        """Salles candidates pour une séance (aucune pour une séance à distance)."""
        if s.mode == 'distance':
            return []
        compatibles_ids = self.salles_compatibles_map.get(s.module_id)
        if compatibles_ids:
            candidates = [r for r in self.salles if r.id in compatibles_ids and r.actif]
            if candidates:
                return candidates
        return [r for r in self.salles if r.actif and r.type_salle.code != 'TEAM']

    # ─── Résolution ───────────────────────────────────────────────────────────
    def resoudre(self, max_time_seconds: int = 60) -> ResultatPlacement:
        debut = time.time()

        if not self.seances:
            return ResultatPlacement(
                succes=True, statut='OPTIMAL', seances_placees=[],
                temps_resolution_ms=int((time.time() - debut) * 1000),
                score_penalite=0, message="Aucune séance à planifier.",
            )

        candidats_salles = {s.id: self._get_salles_candidates(s) for s in self.seances}

        # Vérifications préliminaires (messages explicites plutôt qu'un « infaisable » opaque).
        causes = []
        if not self.creneaux:
            causes.append("aucun créneau n'est configuré")
        sans_salle = [s for s in self.seances if s.mode != 'distance' and not candidats_salles[s.id]]
        if sans_salle:
            causes.append(
                "aucune salle active compatible pour : "
                + ", ".join(f"unité {s.unite_id} (séance {s.id})" for s in sans_salle[:8])
            )
        if causes:
            return ResultatPlacement(
                succes=False, statut='INFEASIBLE',
                temps_resolution_ms=int((time.time() - debut) * 1000),
                message="Génération impossible : " + "; ".join(causes)
                + ". Vérifiez les créneaux et les salles actives / types compatibles.",
            )

        poids = self.construire_poids()
        budget = float(max_time_seconds)

        # ─── Étape 1 : emploi des formateurs ──────────────────────────────────
        etape1 = EmploiFormateurs(
            seances=self.seances,
            creneaux=self.creneaux,
            professeurs_map=self.professeurs_map,
            salles=self.salles,
            candidats_salles=candidats_salles,
            disponibilites=self.disponibilites,
            occupations_groupes=self.occupations_groupes,
            occupations_profs=self.occupations_profs,
            occupations_salles=self.occupations_salles,
            charges_conservees=self.charges_conservees,
            poids=poids,
        ).resoudre(temps_max_s=budget * 0.75)

        etapes: Dict[str, Any] = {
            'formateurs': {
                'statut': etape1.statut, 'temps_ms': etape1.temps_ms,
                'objectif_formateurs': etape1.objectif_formateurs,
                'objectif_stagiaires': etape1.objectif_stagiaires,
                'message': etape1.message,
            },
        }
        if not etape1.succes:
            return ResultatPlacement(
                succes=False, statut=etape1.statut,
                temps_resolution_ms=int((time.time() - debut) * 1000),
                message=etape1.message, etapes=etapes,
                avertissements=etape1.diagnostics,
            )

        # ─── Étape 3 : emploi des salles (les stagiaires sont dérivés ensuite) ─
        reste = max(5.0, budget - (time.time() - debut))
        etape3 = EmploiSalles(
            seances=self.seances,
            creneau_par_seance=etape1.creneau_par_seance,
            creneaux_map=self.creneaux_map,
            candidats_salles=candidats_salles,
            professeurs_map=self.professeurs_map,
            occupations_salles=self.occupations_salles,
            poids=poids,
        ).resoudre(temps_max_s=reste)
        etapes['salles'] = {
            'statut': etape3.statut, 'temps_ms': etape3.temps_ms,
            'objectif': etape3.objectif, 'message': etape3.message,
        }
        if not etape3.succes:
            return ResultatPlacement(
                succes=False, statut=etape3.statut,
                temps_resolution_ms=int((time.time() - debut) * 1000),
                message=etape3.message, etapes=etapes,
            )

        # ─── Construction des séances placées ─────────────────────────────────
        placees: List[SeancePlacee] = []
        for s in self.seances:
            profs = [pid for pid in s.professeur_ids if pid in self.professeurs_map]
            placees.append(SeancePlacee(
                seance_a_placer_id=s.id,
                unite_id=s.unite_id,
                creneau_id=etape1.creneau_par_seance[s.id],
                salle_id=etape3.salle_par_seance.get(s.id),
                professeur_id=profs[0] if profs else None,
                groupe_ids=list(s.groupe_ids),
                nature=s.nature,
                bloc_no=s.bloc_id,
                mode=s.mode,
                professeur_ids=profs,
            ))

        # ─── Étape 2 : emploi des stagiaires, dérivé puis vérifié ─────────────
        anomalies = verifier_emplois(placees, self.creneaux_map)
        emplois = statistiques_emplois(placees, self.creneaux_map)
        etapes['stagiaires'] = {'statut': 'DERIVE', 'anomalies': len(anomalies)}
        if anomalies:
            return ResultatPlacement(
                succes=False, statut='INCOHERENT',
                temps_resolution_ms=int((time.time() - debut) * 1000),
                message="Emplois incohérents après dérivation : " + "; ".join(anomalies[:5]),
                etapes=etapes, avertissements=anomalies,
            )

        total = etape1.objectif_formateurs + etape1.objectif_stagiaires + etape3.objectif
        ms = int((time.time() - debut) * 1000)
        statut = etape1.statut if etape3.statut == 'OPTIMAL' else 'FEASIBLE'
        return ResultatPlacement(
            succes=True,
            statut=statut,
            seances_placees=placees,
            temps_resolution_ms=ms,
            score_penalite=total,
            borne=None,
            message=f"Planification réussie ({statut}) en {ms} ms. Score de pénalité : {total}.",
            emplois=emplois,
            avertissements=etape1.avertissements,
            etapes=etapes,
        )
