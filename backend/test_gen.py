import pymysql
from pymysql.cursors import DictCursor


def test():
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='emplois_du_temps',
        cursorclass=DictCursor,
    )

    with conn.cursor() as cur:
        cur.execute('SELECT * FROM semaine WHERE numero=1 LIMIT 1')
        semaine = cur.fetchone()
        print('Semaine:', semaine)

        cur.execute('''
            SELECT ue.id AS unite_id, ue.code_fusion,
                   m.id AS module_id, m.code AS module_code, m.intitule AS module_intitule, m.type_module,
                   v.h_presentiel, v.h_synchrone,
                   GROUP_CONCAT(DISTINCT g.id ORDER BY g.id) AS groupe_ids,
                   GROUP_CONCAT(DISTINCT g.code ORDER BY g.code) AS groupe_codes,
                   GROUP_CONCAT(DISTINCT p.id ORDER BY p.id) AS prof_ids,
                   GROUP_CONCAT(DISTINCT p.nom_complet ORDER BY p.nom_complet) AS prof_noms
            FROM volume_horaire v
            JOIN unite_enseignement ue ON ue.id = v.unite_id
            JOIN module m ON m.id = ue.module_id
            JOIN unite_groupe ug ON ug.unite_id = ue.id
            JOIN groupe g ON g.id = ug.groupe_id
            LEFT JOIN unite_professeur up ON up.unite_id = ue.id AND up.mode = 'presentiel'
            LEFT JOIN professeur p ON p.id = up.professeur_id
            WHERE v.semestre_id = %s AND g.actif = 1
            GROUP BY ue.id, ue.code_fusion, m.id, m.code, m.intitule, m.type_module, v.h_presentiel, v.h_synchrone
            ORDER BY g.code, m.code
        ''', (semaine['semestre_id'],))
        unites = cur.fetchall()

        print('Total units for semester 1:', len(unites))

        cur.execute('SELECT * FROM creneau ORDER BY jour, numero_seance')
        creneaux = cur.fetchall()

        cur.execute('SELECT s.*, ts.code as type_code FROM salle s JOIN type_salle ts ON ts.id=s.type_salle_id WHERE s.actif=1')
        salles = cur.fetchall()

    # Group unites by groupe_id
    groupe_units = {}
    for u in unites:
        gids = [g for g in (u['groupe_ids'] or '').split(',') if g]
        for gid in gids:
            if gid not in groupe_units:
                groupe_units[gid] = []
            groupe_units[gid].append(u)

    # Let's test generating blocks
    seances_to_insert = []
    groupe_occupe = {}   # gid -> set of cr_id
    prof_occupe = {}     # pid -> set of cr_id
    salle_occupe = {}    # sid -> set of cr_id

    for s in salles:
        salle_occupe[s['id']] = set()

    # Available blocks in a week: 6 days * 2 blocks (Matin: S1+S2, Apm: S3+S4) = 12 blocks
    # Day 5 (Vendredi) only has Matin (S1+S2) and APM S4 (or S3+S4 depending on config)
    blocks = []
    for jour in range(1, 7):
        s1 = next((c for c in creneaux if c['jour'] == jour and c['numero_seance'] == 1), None)
        s2 = next((c for c in creneaux if c['jour'] == jour and c['numero_seance'] == 2), None)
        s3 = next((c for c in creneaux if c['jour'] == jour and c['numero_seance'] == 3), None)
        s4 = next((c for c in creneaux if c['jour'] == jour and c['numero_seance'] == 4), None)

        if s1 and s2:
            blocks.append({'jour': jour, 'periode': 'matin', 'creneaux': [s1, s2]})
        if s3 and s4:
            blocks.append({'jour': jour, 'periode': 'apm', 'creneaux': [s3, s4]})

    print('Total blocks per week:', len(blocks))

    # For each group, target ~5-6 blocks (25-30h)
    gids = list(groupe_units.keys())
    total_sessions_placed = 0

    for gid in gids:
        if gid not in groupe_occupe:
            groupe_occupe[gid] = set()
        units = list(groupe_units[gid])
        # Sort or rotate based on semaine.numero
        offset = (semaine['numero'] or 1) % len(units)
        rotated_units = units[offset:] + units[:offset]

        blocks_assigned = 0
        target_blocks = 5  # 25 hours per week

        for u in rotated_units:
            if blocks_assigned >= target_blocks:
                break
            pids = [int(p) for p in (u['prof_ids'] or '').split(',') if p]
            for p in pids:
                if p not in prof_occupe:
                    prof_occupe[p] = set()

            # Find an available block for this group and prof
            for b in blocks:
                if blocks_assigned >= target_blocks:
                    break
                cr1 = b['creneaux'][0]
                cr2 = b['creneaux'][1]

                # Check group collision
                if cr1['id'] in groupe_occupe[gid] or cr2['id'] in groupe_occupe[gid]:
                    continue

                # Check prof collision
                p_conf = any(
                    cr1['id'] in prof_occupe[p] or cr2['id'] in prof_occupe[p]
                    for p in pids
                )
                if p_conf:
                    continue

                # Find available room
                # Prefer room type: if general module -> SC, if tech -> SP, if info/lab -> LABO
                type_map = {'general': 'SC', 'pratique': 'LABO'}
                preferred_type = type_map.get(u['type_module'], 'SP')
                chosen_salle = next(
                    (s for s in salles
                     if s['type_code'] == preferred_type
                     and cr1['id'] not in salle_occupe[s['id']]
                     and cr2['id'] not in salle_occupe[s['id']]),
                    None
                )
                if not chosen_salle:
                    chosen_salle = next(
                        (s for s in salles
                         if cr1['id'] not in salle_occupe[s['id']]
                         and cr2['id'] not in salle_occupe[s['id']]),
                        None
                    )

                if not chosen_salle:
                    continue

                # Book it!
                groupe_occupe[gid].add(cr1['id'])
                groupe_occupe[gid].add(cr2['id'])
                for p in pids:
                    prof_occupe[p].add(cr1['id'])
                    prof_occupe[p].add(cr2['id'])
                salle_occupe[chosen_salle['id']].add(cr1['id'])
                salle_occupe[chosen_salle['id']].add(cr2['id'])

                seances_to_insert.append({'unite': u, 'creneau': cr1, 'salle': chosen_salle, 'gid': gid, 'pids': pids})
                seances_to_insert.append({'unite': u, 'creneau': cr2, 'salle': chosen_salle, 'gid': gid, 'pids': pids})
                blocks_assigned += 1
                total_sessions_placed += 2
                break

    print(f'Placed {total_sessions_placed} sessions across {len(gids)} groups!')
    conn.close()


if __name__ == '__main__':
    test()
