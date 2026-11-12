"""Contrôle de cohérence de la simulation annuelle (script temporaire)."""
import os
import django
from collections import defaultdict, Counter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import (
    AnneeScolaire, Groupe, Module, Passage, Professeur, Seance, Semaine,
    UniteEnseignement, UniteGroupe, VolumeHoraire,
)

annee = AnneeScolaire.objects.get(libelle='2025/2026')
semaines = list(Semaine.objects.filter(annee_scolaire=annee).order_by('numero'))

# 1. Semaines générées
avec = set(Seance.objects.values_list('semaine__numero', flat=True))
manquantes = [s.numero for s in semaines if s.numero not in avec]
print(f"Semaines : {len(avec)}/45 avec séances ; manquantes={manquantes}")

# 2. Conflits (un groupe / un formateur sur un même créneau d'une semaine)
conflits_groupes = 0
vus = set()
for gid, semaine_id, creneau_id in (
    Seance.objects.values_list(
        'seance_groupes__groupe_id', 'seance_groupes__semaine_id',
        'seance_groupes__creneau_id',
    )
):
    if gid is None:
        continue
    cle = (gid, semaine_id, creneau_id)
    if cle in vus:
        conflits_groupes += 1
    vus.add(cle)
conflits_profs = 0
vus = set()
for pid, semaine_id, creneau_id in (
    Seance.objects.values_list(
        'seance_professeurs__professeur_id', 'seance_professeurs__semaine_id',
        'seance_professeurs__creneau_id',
    )
):
    if pid is None:
        continue
    cle = (pid, semaine_id, creneau_id)
    if cle in vus:
        conflits_profs += 1
    vus.add(cle)
print(f"Conflits : groupes={conflits_groupes}, formateurs={conflits_profs}")

# 3. Blocs de 5 h uniquement
natures = Counter(Seance.objects.values_list('nature', flat=True))
durees = Counter(
    round(float(d), 2)
    for d in Seance.objects.values_list('creneau__duree_h', flat=True)
)
print(f"Natures : {dict(natures)} ; durées : {dict(durees)}")

# 4. Volumes consommés = volumes officiels
heures_unite = defaultdict(float)
for uid, duree in Seance.objects.values_list('unite_id', 'creneau__duree_h'):
    heures_unite[uid] += float(duree or 2.5)
volumes = {v.unite_id: float(v.h_total) for v in VolumeHoraire.objects.all()}
ecarts = []
for uid, total in heures_unite.items():
    attendu = volumes.get(uid)
    if attendu is None:
        continue
    if abs(total - attendu) > 1e-6:
        ecarts.append((uid, total, attendu))
print(
    f"Volumes : {len(heures_unite)} unités planifiées, "
    f"{len(ecarts)} écart(s) au volume officiel"
)
for uid, total, attendu in ecarts[:10]:
    ue = UniteEnseignement.objects.select_related('module').get(id=uid)
    print(f"   {ue.module.code} unité {uid} : {total} h / {attendu} h")

# 5. Règles de passage
passages = {p.unite_id: p for p in Passage.objects.filter(actif=True)}
groupes_unites = defaultdict(list)
for ug in UniteGroupe.objects.filter(unite__annee_scolaire=annee).select_related(
    'unite__module'
):
    groupes_unites[ug.groupe_id].append(ug.unite)

sur_gen, sur_loc = [], []
for gid, unites in groupes_unites.items():
    for numero in range(1, 46):
        gen = loc = 0
        for u in unites:
            p = passages.get(u.id)
            if not p or not (p.semaine_debut <= numero <= p.semaine_fin):
                continue
            if u.module.type_module == 'general':
                gen += 1
            elif not u.module.regional:
                loc += 1
        if gen > 2:
            sur_gen.append((gid, numero, gen))
        if loc > 1:
            sur_loc.append((gid, numero, loc))
print(f"Passages : >2 généraux={len(sur_gen)}, >1 local={len(sur_loc)}")

# 6. Prérequis
prec_violations = []
for module in Module.objects.prefetch_related('prerequis'):
    for prec in module.prerequis.all():
        for gid, unites in groupes_unites.items():
            suite = [u for u in unites if u.module_id == module.id]
            avant = [u for u in unites if u.module_id == prec.id]
            for a in suite:
                for b in avant:
                    pa, pb = passages.get(a.id), passages.get(b.id)
                    if pa and pb and not pb.semaine_fin < pa.semaine_debut:
                        prec_violations.append((gid, module.code, prec.code))
print(f"Prérequis : {len(prec_violations)} violation(s)")

# 7. Régionaux terminés dans la semaine de l'EFM
bad_efm = []
for m in Module.objects.filter(regional=True, date_efm__isnull=False):
    semaine_efm = next(
        (
            s.numero for s in semaines
            if s.date_debut and s.date_fin and s.date_debut <= m.date_efm <= s.date_fin
        ),
        None,
    )
    if semaine_efm is None:
        continue
    for p in Passage.objects.filter(unite__module=m, actif=True):
        if p.semaine_fin != semaine_efm:
            bad_efm.append((m.code, p.semaine_fin, semaine_efm))
print(f"Régionaux hors semaine EFM : {len(bad_efm)}")

# 8. EFM marqués
efm_units = set(
    Seance.objects.filter(nature=Seance.NATURE_EXAMEN).values_list('unite_id', flat=True)
)
regionaux = set(
    UniteEnseignement.objects.filter(
        annee_scolaire=annee, module__regional=True
    ).values_list('id', flat=True)
)
print(
    f"EFM : {len(efm_units)} séance(s) d'examen ; "
    f"{len(regionaux - efm_units)} module(s) régional(aux) sans EFM"
)

# 9. Pic hebdomadaire par formateur vs plafond
pic = defaultdict(float)
for pid, semaine_id, duree in Seance.objects.values_list(
    'seance_professeurs__professeur_id',
    'seance_professeurs__semaine_id',
    'creneau__duree_h',
):
    if pid is not None:
        pic[(pid, semaine_id)] += float(duree or 2.5)
plafonds = {p.id: float(p.heures_max_semaine or 30.0) for p in Professeur.objects.all()}
depasses = [
    (pid, h, plafonds.get(pid, 30.0))
    for (pid, _semaine), h in pic.items()
    if h > plafonds.get(pid, 30.0) + 1e-6
]
print(
    f"Formateurs : {len(set(pid for pid, _ in pic))} chargés ; "
    f"{len(depasses)} dépassement(s) hebdomadaire(s)"
)
for pid, h, plafond in depasses[:8]:
    print(f"   {Professeur.objects.get(id=pid).nom_complet} : {h} h > {plafond} h")
