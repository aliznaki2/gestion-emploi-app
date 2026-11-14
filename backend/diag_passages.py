import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Semaine, AnneeScolaire
from solver.donnees import Donnees
from solver.passages import PlanificateurPassages

annee = AnneeScolaire.objects.get(libelle='2025/2026')
semaine = Semaine.objects.get(annee_scolaire=annee, numero=1)
d = Donnees.charger(semaine.id)
p = PlanificateurPassages(d)
unites = p._unites_a_planifier()
p._preparer_infos(unites)
print('horizon', p.horizon, 'unites', len(unites))

combos = [
    ('tout', {'groupe', 'general', 'local', 'prof', 'prerequis'}, 60, 40),
    ('sans prerequis', {'groupe', 'general', 'local', 'prof'}, 60, 40),
    ('sans prof', {'groupe', 'general', 'local', 'prerequis'}, 60, 100),
    ('sans groupe', {'general', 'local', 'prof', 'prerequis'}, 1000, 40),
    ('sans local', {'groupe', 'general', 'prof', 'prerequis'}, 60, 40),
    ('sans general', {'groupe', 'local', 'prof', 'prerequis'}, 60, 40),
    ('sans general ni local', {'groupe', 'prof', 'prerequis'}, 60, 40),
]
for nom, actives, cg, cp in combos:
    res = p._resoudre(unites, cg, cp, 8, actives=actives)
    print(f'{nom:28s} -> {"OK" if res else "INFEASIBLE"}')

# Structure : groupes avec le plus de modules par type et intensités.
from collections import defaultdict
stats = defaultdict(lambda: defaultdict(int))
for u in unites:
    info = p._infos[u.id]
    for gid in info.groupe_ids:
        stats[gid][info.type_module] += 1
        stats[gid]['h'] += int(info.intensite_h) * info.duree
worst = sorted(stats.items(), key=lambda kv: kv[1]['h'], reverse=True)[:8]
for gid, s in worst:
    from core.models import Groupe
    g = Groupe.objects.get(id=gid)
    print(g.code, dict(s))
