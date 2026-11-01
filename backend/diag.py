#!/usr/bin/env python3
"""Dry-run the generation algorithm and print the schedule."""
import pymysql, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
conn = pymysql.connect(host='localhost', user='root', password='', database='emplois_du_temps',
                       charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

semaine_id = 1
cur.execute('SELECT * FROM semaine WHERE id=%s', (semaine_id,))
semaine = cur.fetchone()
semestre_id = semaine['semestre_id']
semaine_numero = semaine['numero'] or 1

# Load units (fixed query: no v.id)
cur.execute("""
    SELECT ue.id AS unite_id, ue.code_fusion,
           m.code AS module_code, m.type_module,
           v.h_presentiel, v.semestre_id,
           GROUP_CONCAT(DISTINCT g.id ORDER BY g.id) AS groupe_ids,
           GROUP_CONCAT(DISTINCT p.id ORDER BY p.id) AS prof_ids
    FROM volume_horaire v
    JOIN unite_enseignement ue ON ue.id = v.unite_id
    JOIN module m ON m.id = ue.module_id
    JOIN filiere f ON f.id = ue.filiere_id
    JOIN unite_groupe ug ON ug.unite_id = ue.id
    JOIN groupe g ON g.id = ug.groupe_id AND g.actif = 1
    LEFT JOIN unite_professeur up ON up.unite_id = ue.id AND up.mode = 'presentiel'
    LEFT JOIN professeur p ON p.id = up.professeur_id AND p.actif = 1
    WHERE v.semestre_id = %s
    GROUP BY ue.id, ue.code_fusion, m.id, m.code, m.intitule,
             m.type_module, f.id, v.h_presentiel, v.h_synchrone, v.semestre_id
    ORDER BY m.code
""", (semestre_id,))
unites_raw = cur.fetchall()
print(f"Units loaded: {len(unites_raw)}")

# Creneaux
cur.execute('SELECT * FROM creneau ORDER BY jour, numero_seance')
creneaux = cur.fetchall()
DUREE_CRENEAU = float(creneaux[0].get('duree_h', 2.5))
BLOC_H = DUREE_CRENEAU * 2

# Build blocks
blocks = []
for jour in range(1, 7):
    for debut in [1, 3]:
        c1 = next((c for c in creneaux if c['jour'] == jour and c['numero_seance'] == debut), None)
        c2 = next((c for c in creneaux if c['jour'] == jour and c['numero_seance'] == debut + 1), None)
        if c1 and c2:
            blocks.append({'jour': jour, 'periode': 'matin' if debut == 1 else 'apm', 'creneaux': [c1, c2]})

# Simulate scheduling (no DB writes)
semaines_total = 16
semaines_restantes = 16
semaines_passees = 0

tasks = []
for u in unites_raw:
    gids_str = [g for g in (u['groupe_ids'] or '').split(',') if g]
    if not gids_str: continue
    h_total = float(u['h_presentiel'] or 0)
    if h_total <= 0: continue
    h_restant = h_total
    retard = 0.0
    h_cible = h_restant / semaines_restantes
    nb_blocs = min(2, max(1, round(h_cible / BLOC_H)))
    pids = [int(p) for p in (u['prof_ids'] or '').split(',') if p]
    type_mod = (u['type_module'] or 'general').lower()
    tasks.append({
        'unite_id': u['unite_id'], 'module_code': u['module_code'], 'type_module': type_mod,
        'groupe_ids': [int(g) for g in gids_str], 'prof_ids': pids,
        'h_restant': h_restant, 'nb_blocs': nb_blocs, 'retard': retard,
        'is_general': type_mod == 'general',
    })

tasks.sort(key=lambda t: (-t['retard'], t['module_code']))

groupe_occupe = {}
prof_occupe = {}
groupe_jour_count = {}

def score(jour, gids):
    return sum(groupe_jour_count.get(g, {}).get(jour, 0) for g in gids)

placed_log = []  # (module, groupe, jour, periode, nb_blocs)
by_groupe_jour = {}

for task in tasks:
    gids = task['groupe_ids']
    pids = task['prof_ids']
    nb_target = 1 if task['is_general'] else task['nb_blocs']
    blocs_placed = 0
    for gid in gids: groupe_occupe.setdefault(gid, set()); groupe_jour_count.setdefault(gid, {})
    for p in pids: prof_occupe.setdefault(p, set())

    while blocs_placed < nb_target:
        sorted_blocks = sorted(blocks, key=lambda b: (score(b['jour'], gids), b['jour'], 0 if b['periode']=='matin' else 1))
        placed = False
        for block in sorted_blocks:
            cr1, cr2 = block['creneaux']
            if any(cr1['id'] in groupe_occupe.get(g, set()) or cr2['id'] in groupe_occupe.get(g, set()) for g in gids): continue
            if any(cr1['id'] in prof_occupe.get(p, set()) or cr2['id'] in prof_occupe.get(p, set()) for p in pids): continue
            # Reserve
            for g in gids:
                groupe_occupe[g].add(cr1['id']); groupe_occupe[g].add(cr2['id'])
                groupe_jour_count[g][block['jour']] = groupe_jour_count[g].get(block['jour'], 0) + 1
                key = (g, block['jour'])
                by_groupe_jour[key] = by_groupe_jour.get(key, 0) + 1
            for p in pids:
                prof_occupe[p].add(cr1['id']); prof_occupe[p].add(cr2['id'])
            placed_log.append((task['module_code'], gids, block['jour'], block['periode']))
            blocs_placed += 1; placed = True; break
        if not placed: break

print(f"\nTotal blocs placed: {len(placed_log)}")

# Analyse distribution per group
print("\n=== Distribution par groupe (blocs par jour) ===")
all_gids = set()
for gid, d in groupe_jour_count.items(): all_gids.add(gid)
for gid in sorted(list(all_gids))[:10]:
    dist = groupe_jour_count.get(gid, {})
    total = sum(dist.values())
    spread = len(dist)
    print(f"  Groupe {gid}: {total} blocs sur {spread} jours -> {dict(sorted(dist.items()))}")

# Check if any group has >2 blocs on same day (condensed problem)
print("\n=== Jours surcharges (>1 bloc same day same groupe) ===")
condensed = {k: v for k, v in by_groupe_jour.items() if v > 1}
if condensed:
    for k, v in sorted(condensed.items()):
        print(f"  Groupe {k[0]}, Jour {k[1]}: {v} blocs")
else:
    print("  Aucun! Distribution parfaite.")

conn.close()
