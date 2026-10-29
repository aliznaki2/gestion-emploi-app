import mysql from 'mysql2/promise';

async function test() {
  const conn = await mysql.createConnection({
    host: 'localhost',
    user: 'root',
    password: '',
    database: 'emplois_du_temps'
  });

  const [[semaine]] = await conn.query('SELECT * FROM semaine WHERE numero=1 LIMIT 1');
  console.log('Semaine:', semaine);

  const [unites] = await conn.query(`
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
    WHERE v.semestre_id = ? AND g.actif = 1
    GROUP BY ue.id, ue.code_fusion, m.id, m.code, m.intitule, m.type_module, v.h_presentiel, v.h_synchrone
    ORDER BY g.code, m.code
  `, [semaine.semestre_id]);

  console.log('Total units for semester 1:', unites.length);

  const [creneaux] = await conn.query('SELECT * FROM creneau ORDER BY jour, numero_seance');
  const [salles] = await conn.query('SELECT s.*, ts.code as type_code FROM salle s JOIN type_salle ts ON ts.id=s.type_salle_id WHERE s.actif=1');

  // Group unites by groupe_id
  const groupeUnits = {};
  for (const u of unites) {
    const gids = (u.groupe_ids || '').split(',').filter(Boolean);
    for (const gid of gids) {
      if (!groupeUnits[gid]) groupeUnits[gid] = [];
      groupeUnits[gid].push(u);
    }
  }

  // Let's test generating blocks
  const seancesToInsert = [];
  const groupeOccupe = {}; // gid -> Set of cr_id
  const profOccupe = {};   // pid -> Set of cr_id
  const salleOccupe = {};  // sid -> Set of cr_id

  salles.forEach(s => { salleOccupe[s.id] = new Set(); });

  // Available blocks in a week: 6 days * 2 blocks (Matin: S1+S2, Apm: S3+S4) = 12 blocks
  // Day 5 (Vendredi) only has Matin (S1+S2) and APM S4 (or S3+S4 depending on config)
  const blocks = [];
  for (let jour = 1; jour <= 6; jour++) {
    const s1 = creneaux.find(c => c.jour === jour && c.numero_seance === 1);
    const s2 = creneaux.find(c => c.jour === jour && c.numero_seance === 2);
    const s3 = creneaux.find(c => c.jour === jour && c.numero_seance === 3);
    const s4 = creneaux.find(c => c.jour === jour && c.numero_seance === 4);

    if (s1 && s2) blocks.push({ jour, periode: 'matin', creneaux: [s1, s2] });
    if (s3 && s4) blocks.push({ jour, periode: 'apm', creneaux: [s3, s4] });
  }

  console.log('Total blocks per week:', blocks.length);

  // For each group, target ~5-6 blocks (25-30h)
  const gids = Object.keys(groupeUnits);
  let totalSessionsPlaced = 0;

  for (const gid of gids) {
    if (!groupeOccupe[gid]) groupeOccupe[gid] = new Set();
    const units = [...groupeUnits[gid]];
    // Sort or rotate based on semaine.numero
    const offset = (semaine.numero || 1) % units.length;
    const rotatedUnits = [...units.slice(offset), ...units.slice(0, offset)];

    let blocksAssigned = 0;
    const targetBlocks = 5; // 25 hours per week

    for (const u of rotatedUnits) {
      if (blocksAssigned >= targetBlocks) break;
      const pids = (u.prof_ids || '').split(',').map(Number).filter(Boolean);
      for (const p of pids) if (!profOccupe[p]) profOccupe[p] = new Set();

      // Find an available block for this group and prof
      for (const b of blocks) {
        if (blocksAssigned >= targetBlocks) break;
        const cr1 = b.creneaux[0];
        const cr2 = b.creneaux[1];

        // Check group collision
        if (groupeOccupe[gid].has(cr1.id) || groupeOccupe[gid].has(cr2.id)) continue;

        // Check prof collision
        const pConf = pids.some(p => profOccupe[p].has(cr1.id) || profOccupe[p].has(cr2.id));
        if (pConf) continue;

        // Find available room
        // Prefer room type: if general module -> SC, if tech -> SP, if info/lab -> LABO
        const preferredType = u.type_module === 'general' ? 'SC' : (u.type_module === 'pratique' ? 'LABO' : 'SP');
        let chosenSalle = salles.find(s => s.type_code === preferredType && !salleOccupe[s.id].has(cr1.id) && !salleOccupe[s.id].has(cr2.id));
        if (!chosenSalle) {
          chosenSalle = salles.find(s => !salleOccupe[s.id].has(cr1.id) && !salleOccupe[s.id].has(cr2.id));
        }

        if (!chosenSalle) continue;

        // Book it!
        groupeOccupe[gid].add(cr1.id);
        groupeOccupe[gid].add(cr2.id);
        pids.forEach(p => {
          profOccupe[p].add(cr1.id);
          profOccupe[p].add(cr2.id);
        });
        salleOccupe[chosenSalle.id].add(cr1.id);
        salleOccupe[chosenSalle.id].add(cr2.id);

        seancesToInsert.push({ unite: u, creneau: cr1, salle: chosenSalle, gid, pids });
        seancesToInsert.push({ unite: u, creneau: cr2, salle: chosenSalle, gid, pids });
        blocksAssigned++;
        totalSessionsPlaced += 2;
        break;
      }
    }
  }

  console.log(`Placed ${totalSessionsPlaced} sessions across ${gids.length} groups!`);
  await conn.end();
}

test();
