"""Étape 1 — Emploi des formateurs.

C'est le point de départ de la génération : on place chaque séance sur un
créneau de la semaine en partant de ce qui contraint le plus directement un
formateur (disponibilités, jours de congé, plafond hebdomadaire, une seule
séance à la fois, blocs de 5 h).  Les emplois des stagiaires et des salles en
sont ensuite *dérivés* (voir ``emploi_stagiaires`` et ``emploi_salles``).

Pourquoi les groupes apparaissent quand même ici
-------------------------------------------------
Une séance relie un formateur *et* des groupes.  Si l'on ignorait les groupes
à cette étape, deux formateurs différents pourraient faire cours au même
groupe au même créneau, et l'emploi du temps du stagiaire déduit serait
impossible.  L'unicité par groupe est donc une contrainte dure de l'étape 1 ;
en revanche **la qualité** de l'emploi des groupes (trous, journées de 10 h…)
passe après celle des formateurs :

* passe A : on minimise les pénalités propres aux formateurs (trous, EFM à
  la bonne date, créneaux préférés) ;
* passe B : on fige ce résultat (``F <= F*``) et, à qualité formateur égale,
  on minimise les pénalités des groupes.

Un emploi de groupe ne peut donc jamais dégrader l'emploi d'un formateur.
"""
from __future__ import annotations

import itertools
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from ortools.sat.python import cp_model

from .parametres import DUREE_SEANCE_H, Poids


@dataclass
class ResultatEmploiFormateurs:
    """Sortie de l'étape 1 : un créneau par séance."""

    succes: bool
    statut: str
    message: str = ""
    creneau_par_seance: Dict[int, int] = field(default_factory=dict)
    objectif_formateurs: int = 0
    objectif_stagiaires: int = 0
    borne: Optional[int] = None
    diagnostics: List[str] = field(default_factory=list)
    avertissements: List[str] = field(default_factory=list)
    temps_ms: int = 0


class EmploiFormateurs:
    """Construit et résout l'emploi des formateurs (CP-SAT)."""

    # Tolérance (en points de pénalité) accordée à la passe B sur la qualité
    # de l'emploi des formateurs obtenue en passe A.  0 = ne jamais dégrader.
    TOLERANCE_FORMATEURS = 0

    # Écart relatif toléré avec la borne pour arrêter la passe B (2 % ≈ quelques
    # dizaines de points de pénalité) : évite de passer des dizaines de secondes
    # à prouver l'optimalité d'un emploi déjà excellent.
    ECART_RELATIF_PASSE_B = 0.02

    # Durée maximale de la passe B (en secondes) : la solution est généralement
    # trouvée en quelques secondes, la fin du temps ne sert qu'à la prouver optimale.
    BUDGET_MAX_PASSE_B_S = 5.0

    def __init__(
        self,
        seances,
        creneaux,
        professeurs_map: Dict[int, object],
        salles,
        candidats_salles: Dict[int, List[object]],
        disponibilites: Dict[Tuple[int, int], str],
        occupations_groupes: Set[Tuple[int, int]],
        occupations_profs: Set[Tuple[int, int]],
        occupations_salles: Set[Tuple[int, int]],
        charges_conservees: Optional[Dict[int, float]] = None,
        poids: Optional[Poids] = None,
    ):
        self.seances = list(seances)
        self.creneaux = sorted(creneaux, key=lambda c: (c.jour, c.numero_seance))
        self.professeurs_map = professeurs_map
        self.salles = salles
        self.candidats_salles = candidats_salles
        self.disponibilites = disponibilites
        self.occ_groupes = occupations_groupes
        self.occ_profs = occupations_profs
        self.occ_salles = occupations_salles
        self.charges_conservees = charges_conservees or {}
        self.poids = poids or Poids()

        self.creneaux_map = {c.id: c for c in self.creneaux}
        self.par_jour: Dict[int, Dict[int, object]] = defaultdict(dict)
        for c in self.creneaux:
            self.par_jour[c.jour][c.numero_seance] = c

        # Paires de créneaux consécutifs d'un bloc de 5 h : (S1,S2) et (S3,S4).
        self.paires_blocs: List[Tuple[int, int]] = []
        for jour, slots in self.par_jour.items():
            for debut in (1, 3):
                if debut in slots and debut + 1 in slots:
                    self.paires_blocs.append((slots[debut].id, slots[debut + 1].id))

        self.blocs: Dict[int, List[object]] = defaultdict(list)
        for s in self.seances:
            if s.bloc_id is not None:
                self.blocs[s.bloc_id].append(s)
        for b in self.blocs.values():
            b.sort(key=lambda s: (s.bloc_part or 0, s.id))

        # Index séances ↔ ressources
        self.seances_par_groupe: Dict[int, List[int]] = defaultdict(list)
        self.seances_par_prof: Dict[int, List[int]] = defaultdict(list)
        for s in self.seances:
            for gid in s.groupe_ids:
                self.seances_par_groupe[gid].append(s.id)
            for pid in s.professeur_ids:
                if pid in self.professeurs_map:
                    self.seances_par_prof[pid].append(s.id)
        self.seance_par_id = {s.id: s for s in self.seances}

        self.autorises: Dict[int, List[int]] = {}
        self.X: Dict[Tuple[int, int], cp_model.IntVar] = {}

    # ─── Créneaux autorisés (pré-filtrage) ────────────────────────────────
    def _creneau_libre_pour(self, s, c) -> bool:
        for gid in s.groupe_ids:
            if (c.id, gid) in self.occ_groupes:
                return False
        for pid in s.professeur_ids:
            if pid not in self.professeurs_map:
                continue
            if (c.id, pid) in self.occ_profs:
                return False
            if self.disponibilites.get((pid, c.id)) == 'bloque':
                return False
        return True

    def _calculer_autorises(self) -> None:
        for s in self.seances:
            self.autorises[s.id] = [c.id for c in self.creneaux if self._creneau_libre_pour(s, c)]

        # Propagation des blocs : une moitié n'est possible que si l'autre
        # moitié peut occuper le créneau voisin.
        for pair in self.blocs.values():
            if len(pair) != 2:
                continue
            s1, s2 = pair
            ok1, ok2 = set(self.autorises[s1.id]), set(self.autorises[s2.id])
            valides = [(a, b) for a, b in self.paires_blocs if a in ok1 and b in ok2]
            self.autorises[s1.id] = sorted({a for a, _ in valides})
            self.autorises[s2.id] = sorted({b for _, b in valides})

    # ─── Diagnostics ──────────────────────────────────────────────────────
    def diagnostiquer(self) -> List[str]:
        """Explications lisibles quand le problème est impossible."""
        messages: List[str] = []

        def libelle(s) -> str:
            return f"{s.module_code} (groupes {list(s.groupe_ids)}, formateurs {list(s.professeur_ids)})"

        sans = [s for s in self.seances if not self.autorises.get(s.id)]
        if sans:
            messages.append(
                "séance(s) sans aucun créneau possible : "
                + " ; ".join(libelle(s) for s in sans[:6])
                + (" …" if len(sans) > 6 else "")
            )

        for pid, sids in self.seances_par_prof.items():
            libres = {cid for sid in sids for cid in self.autorises[sid]}
            if len(sids) > len(libres):
                nom = getattr(self.professeurs_map[pid], 'nom_complet', pid)
                messages.append(
                    f"formateur {nom} : {len(sids)} séance(s) à placer pour "
                    f"{len(libres)} créneau(x) disponible(s)"
                )
        for gid, sids in self.seances_par_groupe.items():
            libres = {cid for sid in sids for cid in self.autorises[sid]}
            if len(sids) > len(libres):
                messages.append(
                    f"groupe {gid} : {len(sids)} séance(s) à placer pour "
                    f"{len(libres)} créneau(x) disponible(s)"
                )
        return messages

    def depassements_plafond(self) -> List[str]:
        """Formateurs dont la charge à placer dépasse le plafond hebdomadaire.

        Chaque séance est placée exactement une fois, la charge d'un formateur
        est donc connue avant la résolution : c'est une vérification, pas une
        contrainte du modèle.  Les séances déjà conservées sont déduites.
        """
        messages = []
        for pid, sids in self.seances_par_prof.items():
            plafond_h = getattr(self.professeurs_map[pid], 'heures_max_semaine', None)
            if not plafond_h:
                continue
            reste_h = float(plafond_h) - float(self.charges_conservees.get(pid, 0.0))
            max_seances = max(0, int((reste_h + 1e-9) / DUREE_SEANCE_H))
            if len(sids) > max_seances:
                nom = getattr(self.professeurs_map[pid], 'nom_complet', pid)
                messages.append(
                    f"plafond hebdomadaire dépassé pour {nom} : {len(sids)} séance(s) "
                    f"demandée(s), {max_seances} possible(s) ({float(plafond_h):g} h max)"
                )
        return messages

    # ─── Modèle ───────────────────────────────────────────────────────────
    def _occ(self, ids: Iterable[int], cid: int):
        """Somme des variables ``X[s, c]`` de ces séances (ou None si aucune)."""
        termes = [self.X[sid, cid] for sid in ids if (sid, cid) in self.X]
        return sum(termes) if termes else None

    def _ajouter_variables_et_contraintes(self, m: cp_model.CpModel) -> None:
        for s in self.seances:
            for cid in self.autorises[s.id]:
                self.X[s.id, cid] = m.NewBoolVar(f"x_{s.id}_{cid}")
            m.AddExactlyOne([self.X[s.id, cid] for cid in self.autorises[s.id]])

        # Blocs : les deux séances occupent S1+S2 ou S3+S4 du même jour.
        for pair in self.blocs.values():
            if len(pair) != 2:
                continue
            s1, s2 = pair
            partenaire = {a: b for a, b in self.paires_blocs}
            for cid in self.autorises[s1.id]:
                m.Add(self.X[s1.id, cid] == self.X[s2.id, partenaire[cid]])

        # Un groupe ne suit qu'une séance à la fois.
        for gid, sids in self.seances_par_groupe.items():
            for c in self.creneaux:
                variables = [self.X[sid, c.id] for sid in sids if (sid, c.id) in self.X]
                if len(variables) > 1:
                    m.AddAtMostOne(variables)

        # Un formateur n'enseigne qu'une séance à la fois.
        for pid, sids in self.seances_par_prof.items():
            for c in self.creneaux:
                variables = [self.X[sid, c.id] for sid in sids if (sid, c.id) in self.X]
                if len(variables) > 1:
                    m.AddAtMostOne(variables)

        self._ajouter_capacite_salles(m)

    def _ajouter_capacite_salles(self, m: cp_model.CpModel) -> None:
        """Garantit que l'étape 3 (salles) aura toujours une solution.

        Condition de Hall sur les types de salles : pour tout ensemble ``T`` de
        types, les séances qui ne peuvent aller que dans ``T`` ne dépassent
        jamais le nombre de salles libres de ces types, à chaque créneau.
        Les salles d'un même type étant interchangeables, c'est exact.
        """
        physiques = [r for r in self.salles if r.actif and r.type_salle.code != 'TEAM']
        types_present = sorted({r.type_salle_id for r in physiques})
        presentiel = [s for s in self.seances if s.mode == 'presentiel']
        if not presentiel or not types_present:
            return

        types_candidats = {
            s.id: frozenset(r.type_salle_id for r in self.candidats_salles.get(s.id, []))
            for s in presentiel
        }
        libres: Dict[Tuple[int, int], int] = {}
        for c in self.creneaux:
            for t in types_present:
                libres[c.id, t] = sum(
                    1 for r in physiques
                    if r.type_salle_id == t and (c.id, r.id) not in self.occ_salles
                )

        deja: Set[Tuple[int, ...]] = set()
        for taille in range(1, len(types_present) + 1):
            for sous_ensemble in itertools.combinations(types_present, taille):
                T = frozenset(sous_ensemble)
                confinees = [
                    s.id for s in presentiel
                    if types_candidats[s.id] and types_candidats[s.id] <= T
                ]
                if not confinees:
                    continue
                signature = tuple(sorted(confinees))
                if signature in deja:
                    continue
                deja.add(signature)
                for c in self.creneaux:
                    variables = [self.X[sid, c.id] for sid in confinees if (sid, c.id) in self.X]
                    if not variables:
                        continue
                    capacite = sum(libres[c.id, t] for t in T)
                    if len(variables) > capacite:
                        m.Add(sum(variables) <= capacite)

    # ─── Pénalités ────────────────────────────────────────────────────────
    def _termes_trous(self, m, occ_par_numero: Dict[int, object], poids: int, nom: str) -> list:
        """Pénalise chaque créneau vide situé entre deux créneaux occupés.

        Pour un créneau intermédiaire ``j`` et deux créneaux ``i < j < k`` :
        ``occ_i + occ_k - occ_j - 1 <= trou_j``.  Cela couvre aussi le cas
        S1 + S4 (deux créneaux vides au milieu), que l'ancien modèle ignorait.
        """
        numeros = sorted(occ_par_numero)
        termes = []
        for idx in range(1, len(numeros) - 1):
            j = numeros[idx]
            trou = None
            for i in numeros[:idx]:
                for k in numeros[idx + 1:]:
                    if occ_par_numero[i] is None or occ_par_numero[k] is None:
                        continue
                    if trou is None:
                        trou = m.NewBoolVar(f"trou_{nom}_{j}")
                    milieu = occ_par_numero[j] if occ_par_numero[j] is not None else 0
                    m.Add(occ_par_numero[i] + occ_par_numero[k] - milieu - 1 <= trou)
            if trou is not None:
                termes.append(poids * trou)
        return termes

    def _penalites_formateurs(self, m) -> list:
        termes = []
        P = self.poids

        # EFM : le plus près possible de la date prévue (écart en jours).
        for s in self.seances:
            if s.nature == 'examen' and s.jour_efm:
                for cid in self.autorises[s.id]:
                    ecart = abs(self.creneaux_map[cid].jour - s.jour_efm)
                    if ecart:
                        termes.append(P.efm_par_jour * ecart * self.X[s.id, cid])

        # Trous dans la journée d'un formateur.
        for pid, sids in self.seances_par_prof.items():
            for jour, slots in self.par_jour.items():
                occ = {n: self._occ(sids, c.id) for n, c in slots.items()}
                termes += self._termes_trous(m, occ, P.trou_formateur, f"p{pid}_j{jour}")
        return termes

    def _bonus_preferences(self) -> list:
        """Créneaux « préférés » des formateurs (coût négatif, jamais bloquant)."""
        termes = []
        for pid, sids in self.seances_par_prof.items():
            for c in self.creneaux:
                if self.disponibilites.get((pid, c.id)) == 'prefere':
                    occ = self._occ(sids, c.id)
                    if occ is not None:
                        termes.append(-self.poids.preference * occ)
        return termes

    def _penalites_groupes(self, m) -> list:
        termes = []
        P = self.poids
        for gid, sids in self.seances_par_groupe.items():
            jours_actifs: Dict[int, object] = {}
            for jour, slots in self.par_jour.items():
                occ = {n: self._occ(sids, c.id) for n, c in slots.items()}
                termes += self._termes_trous(m, occ, P.trou_groupe, f"g{gid}_j{jour}")

                presentes = [v for v in occ.values() if v is not None]
                if not presentes:
                    continue
                total = sum(presentes)
                nb = len(slots)

                actif = m.NewBoolVar(f"g{gid}_j{jour}_actif")
                m.Add(total >= actif)
                m.Add(total <= nb * actif)
                jours_actifs[jour] = actif

                if nb >= 4:
                    complet = m.NewBoolVar(f"g{gid}_j{jour}_10h")
                    m.Add(total >= 4 * complet)
                    termes.append(P.journee_10h * complet)

                surcharge = m.NewIntVar(0, max(0, nb - 2), f"g{gid}_j{jour}_surcharge")
                m.Add(surcharge >= total - 2)
                termes.append(P.surcharge * surcharge)

            for jour in self.par_jour:
                if jour <= 5:
                    actif = jours_actifs.get(jour)
                    if actif is not None:
                        termes.append(P.jour_vide * (1 - actif))
        return termes

    # ─── Résolution ───────────────────────────────────────────────────────
    def resoudre(self, temps_max_s: float = 60.0) -> ResultatEmploiFormateurs:
        debut = time.time()
        self._calculer_autorises()

        diagnostics = self.depassements_plafond() + self.diagnostiquer()
        if diagnostics and (
            any(not self.autorises.get(s.id) for s in self.seances)
            or any(d.startswith('plafond hebdomadaire') for d in diagnostics)
        ):
            return ResultatEmploiFormateurs(
                succes=False,
                statut='INFEASIBLE',
                message="Emploi des formateurs impossible : " + "; ".join(diagnostics[:5]),
                diagnostics=diagnostics,
                temps_ms=int((time.time() - debut) * 1000),
            )

        m = cp_model.CpModel()
        self._ajouter_variables_et_contraintes(m)
        F = sum(self._penalites_formateurs(m))
        G = sum(self._penalites_groupes(m)) + sum(self._bonus_preferences())

        # ── Passe A : qualité de l'emploi des formateurs ─────────────────
        budget_a = max(3.0, 0.35 * float(temps_max_s))
        m.Minimize(F)
        solveur = cp_model.CpSolver()
        solveur.parameters.max_time_in_seconds = budget_a
        solveur.parameters.num_workers = 4
        statut_a = solveur.Solve(m)
        nom_a = solveur.StatusName(statut_a)

        if statut_a not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            ms = int((time.time() - debut) * 1000)
            if statut_a == cp_model.UNKNOWN:
                message = f"Délai de {budget_a:.0f}s dépassé pendant l'emploi des formateurs."
            else:
                message = (
                    "Aucun emploi des formateurs ne respecte toutes les contraintes"
                    + (" : " + "; ".join(diagnostics[:5]) if diagnostics else ".")
                )
            return ResultatEmploiFormateurs(
                succes=False, statut=nom_a, message=message,
                diagnostics=diagnostics, temps_ms=ms,
            )

        creneau_a = self._extraire(solveur)
        self.temps_passe_a_ms = int((time.time() - debut) * 1000)
        f_etoile = int(round(solveur.ObjectiveValue()))
        borne_a = int(solveur.BestObjectiveBound())

        # ── Passe B : emploi des groupes, sans dégrader celui des formateurs ──
        creneau_final, g_val, statut_final = creneau_a, 0, nom_a
        reste = min(self.BUDGET_MAX_PASSE_B_S, max(3.0, float(temps_max_s) - (time.time() - debut)))
        if not isinstance(F, int):
            m.Add(F <= f_etoile + self.TOLERANCE_FORMATEURS)
        m.Minimize(G)
        m.ClearHints()
        for (sid, cid), var in self.X.items():
            m.AddHint(var, 1 if creneau_a[sid] == cid else 0)
        solveur_b = cp_model.CpSolver()
        solveur_b.parameters.max_time_in_seconds = reste
        solveur_b.parameters.num_workers = 4
        solveur_b.parameters.relative_gap_limit = self.ECART_RELATIF_PASSE_B
        statut_b = solveur_b.Solve(m)
        if statut_b in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            creneau_final = self._extraire(solveur_b)
            g_val = int(round(solveur_b.ObjectiveValue()))
            statut_final = solveur_b.StatusName(statut_b)

        return ResultatEmploiFormateurs(
            succes=True,
            statut=statut_final if statut_final == 'OPTIMAL' and nom_a == 'OPTIMAL' else 'FEASIBLE',
            message="Emploi des formateurs établi.",
            creneau_par_seance=creneau_final,
            objectif_formateurs=f_etoile,
            objectif_stagiaires=g_val,
            borne=borne_a,
            diagnostics=diagnostics,
            avertissements=self._avertissements_efm(creneau_final),
            temps_ms=int((time.time() - debut) * 1000),
        )

    def _extraire(self, solveur) -> Dict[int, int]:
        resultat: Dict[int, int] = {}
        for (sid, cid), var in self.X.items():
            if solveur.Value(var) == 1:
                resultat[sid] = cid
        return resultat

    def _avertissements_efm(self, creneau_par_seance: Dict[int, int]) -> List[str]:
        """EFM qui n'ont pas pu être placés à leur date, avec la cause probable."""
        alertes: List[str] = []
        for s in self.seances:
            if s.nature != 'examen' or not s.jour_efm:
                continue
            c = self.creneaux_map[creneau_par_seance[s.id]]
            if c.jour == s.jour_efm:
                continue
            causes = []
            for pid in s.professeur_ids:
                prof = self.professeurs_map.get(pid)
                if prof is None:
                    continue
                ce_jour = [
                    t for t in self.seances_par_prof[pid]
                    if t != s.id and (self.seance_par_id[t].nature == 'examen'
                                      and self.seance_par_id[t].jour_efm == s.jour_efm)
                ]
                if len(ce_jour) + 1 > len(self.par_jour.get(s.jour_efm, {})) // 2:
                    causes.append(
                        f"{prof.nom_complet} a {len(ce_jour) + 1} EFM le même jour"
                    )
            alertes.append(
                f"EFM {s.module_code} (groupes {list(s.groupe_ids)}) prévu le jour {s.jour_efm}, "
                f"placé le jour {c.jour}"
                + (" — " + ", ".join(causes) if causes else " — jour saturé ou indisponible")
            )
        return alertes
