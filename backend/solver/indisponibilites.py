"""Résolution des indisponibilités (congés / jours libres) pour une semaine."""
from datetime import timedelta
from core.models import Indisponibilite, Groupe


def resoudre_indisponibilites(semaine):
    """
    Retourne pour la semaine donnée :
      - groupes_off_semaine : set de groupe_id indisponibles toute la semaine
      - groupes_jours_off  : dict groupe_id -> set de jours (1..6) libres
      - profs_jours_off     : dict prof_id -> set de jours (1..6) libres
    """
    groupes_tous = set(Groupe.objects.filter(actif=True).values_list('id', flat=True))
    groupes_jours_off = {g: set() for g in groupes_tous}
    profs_jours_off = {}

    indis = Indisponibilite.objects.filter(actif=True).select_related(
        'groupe', 'professeur', 'semaine'
    )
    for ind in indis:
        jours = set()
        if ind.type_periode == 'jour':
            if ind.semaine_id == semaine.id and ind.jour:
                jours.add(int(ind.jour))
        elif ind.type_periode == 'semaine':
            if ind.semaine_id == semaine.id:
                jours.update(range(1, 7))
        elif ind.type_periode == 'periode':
            if not ind.date_debut or not ind.date_fin or not semaine.date_debut:
                continue
            for j in range(1, 7):
                d = semaine.date_debut + timedelta(days=j - 1)
                if ind.date_debut <= d <= ind.date_fin:
                    jours.add(j)
        if not jours:
            continue

        if ind.type_cible == 'professeur' and ind.professeur_id:
            profs_jours_off.setdefault(ind.professeur_id, set()).update(jours)
        else:
            if ind.type_cible == 'tous' or ind.groupe_id is None:
                targets = list(groupes_tous)
            else:
                targets = [ind.groupe_id]
            for g in targets:
                groupes_jours_off.setdefault(g, set()).update(jours)

    groupes_off_semaine = {g for g, js in groupes_jours_off.items() if len(js) >= 6}
    return groupes_off_semaine, groupes_jours_off, profs_jours_off


def creneaux_par_jour(creneaux):
    """Map jour -> list of creneau ids."""
    out = {}
    for c in creneaux:
        out.setdefault(c.jour, []).append(c.id)
    return out
