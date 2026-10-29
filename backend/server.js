import express from 'express';
import mysql from 'mysql2/promise';
import cors from 'cors';

const app = express();
app.use(cors());
app.use(express.json());

// ─── MySQL Connection Pool ────────────────────────────────────────────────────
const pool = mysql.createPool({
  host: 'localhost',
  port: 3306,
  user: 'root',
  password: '',
  database: 'emplois_du_temps',
  waitForConnections: true,
  connectionLimit: 10,
  charset: 'utf8mb4',
});

// ─── Health Check ─────────────────────────────────────────────────────────────
app.get('/api/health', async (req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ok', db: 'emplois_du_temps' });
  } catch (err) {
    res.status(500).json({ status: 'error', message: err.message });
  }
});

// ─── Semaines ─────────────────────────────────────────────────────────────────
app.get('/api/semaines', async (req, res) => {
  try {
    const [rows] = await pool.query(`
      SELECT sw.*, a.libelle AS annee_libelle, sm.numero AS semestre_numero,
             (SELECT COUNT(*) FROM seance s WHERE s.semaine_id = sw.id) AS nb_seances
      FROM semaine sw
      JOIN annee_scolaire a ON a.id = sw.annee_scolaire_id
      LEFT JOIN semestre sm ON sm.id = sw.semestre_id
      ORDER BY sw.numero ASC
    `);
    res.json(rows);
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── Initialiser les semaines (si la table est vide) ─────────────────────────
app.post('/api/init-semaines', async (req, res) => {
  const conn = await pool.getConnection();
  try {
    await conn.beginTransaction();
    // Check if weeks already exist
    const [[{ cnt }]] = await conn.query('SELECT COUNT(*) AS cnt FROM semaine');
    if (cnt > 0) {
      await conn.rollback();
      return res.json({ message: `${cnt} semaines déjà présentes`, created: 0 });
    }
    // Get annee scolaire 2026
    const [[annee]] = await conn.query("SELECT * FROM annee_scolaire WHERE annee_debut = 2026");
    if (!annee) { await conn.rollback(); return res.status(404).json({ error: 'Année scolaire 2026 non trouvée' }); }

    // Update dates for annee and semestres
    await conn.query("UPDATE annee_scolaire SET date_debut='2026-09-14', date_fin='2027-06-26' WHERE annee_debut=2026");
    await conn.query("UPDATE semestre SET date_debut='2026-09-14', date_fin='2027-01-02' WHERE numero=1 AND annee_scolaire_id=?", [annee.id]);
    await conn.query("UPDATE semestre SET date_debut='2027-01-12', date_fin='2027-06-26' WHERE numero=2 AND annee_scolaire_id=?", [annee.id]);

    const [[s1]] = await conn.query("SELECT * FROM semestre WHERE numero=1 AND annee_scolaire_id=?", [annee.id]);
    const [[s2]] = await conn.query("SELECT * FROM semestre WHERE numero=2 AND annee_scolaire_id=?", [annee.id]);

    let created = 0;
    // S1: 16 weeks from 2026-09-14
    for (let i = 0; i < 16; i++) {
      const debut = new Date('2026-09-14'); debut.setDate(debut.getDate() + i*7);
      const fin = new Date(debut); fin.setDate(fin.getDate() + 5);
      await conn.query(
        'INSERT INTO semaine (annee_scolaire_id, semestre_id, numero, date_debut, date_fin, nature) VALUES (?,?,?,?,?,?)',
        [annee.id, s1.id, i+1, debut.toISOString().slice(0,10), fin.toISOString().slice(0,10), 'cours']
      );
      created++;
    }
    // S2: 16 weeks from 2027-01-12
    for (let i = 0; i < 16; i++) {
      const debut = new Date('2027-01-12'); debut.setDate(debut.getDate() + i*7);
      const fin = new Date(debut); fin.setDate(fin.getDate() + 5);
      await conn.query(
        'INSERT INTO semaine (annee_scolaire_id, semestre_id, numero, date_debut, date_fin, nature) VALUES (?,?,?,?,?,?)',
        [annee.id, s2.id, i+17, debut.toISOString().slice(0,10), fin.toISOString().slice(0,10), 'cours']
      );
      created++;
    }
    await conn.commit();
    res.json({ message: `${created} semaines créées (S1+S2 2026-2027)`, created });
  } catch (err) {
    await conn.rollback();
    res.status(500).json({ error: err.message });
  } finally { conn.release(); }
});

// ─── Créneaux ─────────────────────────────────────────────────────────────────
app.get('/api/creneaux', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT * FROM creneau ORDER BY jour, numero_seance');
    res.json(rows);
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── Groupes ──────────────────────────────────────────────────────────────────
app.get('/api/groupes', async (req, res) => {
  try {
    const [rows] = await pool.query(`
      SELECT g.*, f.intitule AS filiere_nom, f.code AS filiere_code
      FROM groupe g
      JOIN filiere f ON f.id = g.filiere_id
      JOIN annee_scolaire a ON a.id = g.annee_scolaire_id
      WHERE g.actif = 1
      ORDER BY f.code, g.annee_etude, g.code
    `);
    res.json(rows);
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── Professeurs ──────────────────────────────────────────────────────────────
app.get('/api/professeurs', async (req, res) => {
  try {
    const [rows] = await pool.query(`
      SELECT p.*, u.email
      FROM professeur p
      LEFT JOIN utilisateur u ON u.id = p.utilisateur_id
      WHERE p.actif = 1
      ORDER BY p.nom_complet
    `);
    res.json(rows);
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── Salles ───────────────────────────────────────────────────────────────────
app.get('/api/salles', async (req, res) => {
  try {
    const [rows] = await pool.query(`
      SELECT s.*, t.libelle AS type_libelle, t.code AS type_code
      FROM salle s JOIN type_salle t ON t.id = s.type_salle_id
      WHERE s.actif = 1
      ORDER BY t.code, s.nom
    `);
    res.json(rows);
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── Filières ─────────────────────────────────────────────────────────────────
app.get('/api/filieres', async (req, res) => {
  try {
    const [rows] = await pool.query(`
      SELECT f.*, s.libelle AS secteur_nom
      FROM filiere f JOIN secteur s ON s.id = f.secteur_id
      ORDER BY f.code
    `);
    res.json(rows);
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── Emploi du temps d'une semaine ────────────────────────────────────────────
app.get('/api/emploi-du-temps/:semaine_id', async (req, res) => {
  const { semaine_id } = req.params;
  try {
    const [seances] = await pool.query(`
      SELECT
        s.id, s.unite_id, s.semaine_id, s.creneau_id, s.salle_id,
        s.mode, s.nature, s.bloc_no, s.statut, s.verrouillee,
        c.jour, c.numero_seance, c.heure_debut, c.heure_fin, c.duree_h,
        sa.nom AS salle_nom, ts.code AS type_salle_code,
        m.code AS module_code, m.intitule AS module_intitule, m.type_module,
        f.code AS filiere_code, f.intitule AS filiere_nom
      FROM seance s
      JOIN creneau c ON c.id = s.creneau_id
      LEFT JOIN salle sa ON sa.id = s.salle_id
      LEFT JOIN type_salle ts ON ts.id = sa.type_salle_id
      JOIN unite_enseignement ue ON ue.id = s.unite_id
      JOIN module m ON m.id = ue.module_id
      JOIN filiere f ON f.id = ue.filiere_id
      WHERE s.semaine_id = ?
      ORDER BY c.jour, c.numero_seance
    `, [semaine_id]);

    const seanceIds = seances.map(s => s.id);
    let groupes = [], profs = [];

    if (seanceIds.length > 0) {
      const ph = seanceIds.map(() => '?').join(',');
      [groupes] = await pool.query(`
        SELECT sg.seance_id, g.id AS groupe_id, g.code AS groupe_code, g.annee_etude
        FROM seance_groupe sg JOIN groupe g ON g.id = sg.groupe_id
        WHERE sg.seance_id IN (${ph})
      `, seanceIds);

      [profs] = await pool.query(`
        SELECT sp.seance_id, p.id AS prof_id, p.nom_complet AS prof_nom, p.matricule
        FROM seance_professeur sp JOIN professeur p ON p.id = sp.professeur_id
        WHERE sp.seance_id IN (${ph})
      `, seanceIds);
    }

    const result = seances.map(s => ({
      ...s,
      groupes: groupes.filter(g => g.seance_id === s.id),
      professeurs: profs.filter(p => p.seance_id === s.id),
    }));

    res.json(result);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// ─── Créer une séance ─────────────────────────────────────────────────────────
app.post('/api/seances', async (req, res) => {
  const { unite_id, semaine_id, creneau_id, salle_id, mode, nature, groupe_ids, professeur_ids } = req.body;
  const conn = await pool.getConnection();
  try {
    await conn.beginTransaction();

    if (salle_id) {
      const [c] = await conn.query('SELECT id FROM seance WHERE salle_id=? AND semaine_id=? AND creneau_id=?', [salle_id, semaine_id, creneau_id]);
      if (c.length) { await conn.rollback(); return res.status(409).json({ error: 'Conflit de salle' }); }
    }
    for (const gid of (groupe_ids || [])) {
      const [c] = await conn.query('SELECT seance_id FROM seance_groupe WHERE groupe_id=? AND semaine_id=? AND creneau_id=?', [gid, semaine_id, creneau_id]);
      if (c.length) { await conn.rollback(); return res.status(409).json({ error: 'Conflit de groupe' }); }
    }
    for (const pid of (professeur_ids || [])) {
      const [c] = await conn.query('SELECT seance_id FROM seance_professeur WHERE professeur_id=? AND semaine_id=? AND creneau_id=?', [pid, semaine_id, creneau_id]);
      if (c.length) { await conn.rollback(); return res.status(409).json({ error: 'Conflit de formateur' }); }
    }

    const [result] = await conn.query(
      "INSERT INTO seance (unite_id,semaine_id,creneau_id,salle_id,mode,nature,statut) VALUES (?,?,?,?,?,?,'brouillon')",
      [unite_id, semaine_id, creneau_id, salle_id || null, mode || 'presentiel', nature || 'simple']
    );
    const sid = result.insertId;
    for (const gid of (groupe_ids || [])) await conn.query('INSERT INTO seance_groupe(seance_id,semaine_id,creneau_id,groupe_id) VALUES(?,?,?,?)', [sid, semaine_id, creneau_id, gid]);
    for (const pid of (professeur_ids || [])) await conn.query('INSERT INTO seance_professeur(seance_id,semaine_id,creneau_id,professeur_id) VALUES(?,?,?,?)', [sid, semaine_id, creneau_id, pid]);

    await conn.commit();
    res.status(201).json({ id: sid, message: 'Séance créée' });
  } catch (err) {
    await conn.rollback();
    res.status(500).json({ error: err.message });
  } finally { conn.release(); }
});

// ─── Modifier une séance ──────────────────────────────────────────────────────
app.put('/api/seances/:id', async (req, res) => {
  const { id } = req.params;
  const { creneau_id, salle_id, statut, verrouillee, unite_id, mode, professeur_id } = req.body;
  const conn = await pool.getConnection();
  try {
    await conn.beginTransaction();
    const [[s]] = await conn.query('SELECT * FROM seance WHERE id=?', [id]);
    if (!s) { await conn.rollback(); return res.status(404).json({ error: 'Séance introuvable' }); }
    if (s.verrouillee && verrouillee === undefined) { await conn.rollback(); return res.status(403).json({ error: 'Séance verrouillée' }); }

    const nc = creneau_id || s.creneau_id;
    const ns = salle_id !== undefined ? salle_id : s.salle_id;
    const nu = unite_id || s.unite_id;
    const nm = mode || s.mode;

    if (ns && ns !== s.salle_id) {
      const [c] = await conn.query('SELECT id FROM seance WHERE salle_id=? AND semaine_id=? AND creneau_id=? AND id!=?', [ns, s.semaine_id, nc, id]);
      if (c.length) { await conn.rollback(); return res.status(409).json({ error: 'Conflit de salle : salle déjà occupée' }); }
    }
    if (nc !== s.creneau_id) {
      await conn.query('UPDATE seance_groupe SET creneau_id=? WHERE seance_id=?', [nc, id]);
      await conn.query('UPDATE seance_professeur SET creneau_id=? WHERE seance_id=?', [nc, id]);
    }
    if (professeur_id !== undefined) {
      await conn.query('DELETE FROM seance_professeur WHERE seance_id=?', [id]);
      if (professeur_id) {
        await conn.query('INSERT INTO seance_professeur (seance_id, semaine_id, creneau_id, professeur_id) VALUES (?,?,?,?)', [id, s.semaine_id, nc, professeur_id]);
      }
    }
    await conn.query('UPDATE seance SET unite_id=?, creneau_id=?, salle_id=?, mode=?, statut=?, verrouillee=? WHERE id=?',
      [nu, nc, ns, nm, statut || s.statut, verrouillee !== undefined ? verrouillee : s.verrouillee, id]);

    await conn.commit();
    res.json({ message: 'Séance mise à jour' });
  } catch (err) {
    await conn.rollback();
    res.status(500).json({ error: err.message });
  } finally { conn.release(); }
});

// ─── Supprimer une séance ─────────────────────────────────────────────────────
app.delete('/api/seances/:id', async (req, res) => {
  try {
    await pool.query('DELETE FROM seance WHERE id=? AND verrouillee=0', [req.params.id]);
    res.json({ message: 'Séance supprimée' });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── Valider les séances d'une semaine ───────────────────────────────────────
app.post('/api/semaines/:semaine_id/valider', async (req, res) => {
  try {
    await pool.query("UPDATE seance SET statut='valide' WHERE semaine_id=? AND statut='brouillon'", [req.params.semaine_id]);
    res.json({ message: 'Emploi du temps validé' });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── Générer automatiquement une semaine spécifique ───────────────────────────
app.post('/api/generer/:semaine_id', async (req, res) => {
  const { semaine_id } = req.params;
  const conn = await pool.getConnection();
  try {
    await conn.beginTransaction();

    // Récupérer les détails de la semaine
    const [[semaine]] = await conn.query('SELECT * FROM semaine WHERE id = ?', [semaine_id]);
    if (!semaine) {
      await conn.rollback();
      return res.status(404).json({ error: 'Semaine non trouvée' });
    }

    // Supprimer les séances brouillon non verrouillées de cette semaine
    await conn.query("DELETE FROM seance WHERE semaine_id=? AND statut='brouillon' AND verrouillee=0", [semaine_id]);

    // Récupérer les unités d'enseignement pour ce semestre
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

    const [creneaux] = await conn.query('SELECT * FROM creneau ORDER BY jour, numero_seance');
    const [salles] = await conn.query('SELECT s.*, ts.code AS type_code FROM salle s JOIN type_salle ts ON ts.id=s.type_salle_id WHERE s.actif=1');

    // Regrouper par groupe
    const groupeUnits = {};
    for (const u of unites) {
      const gids = (u.groupe_ids || '').split(',').filter(Boolean);
      for (const gid of gids) {
        if (!groupeUnits[gid]) groupeUnits[gid] = [];
        groupeUnits[gid].push(u);
      }
    }

    // Blocs de 2 séances (matin : S1+S2, après-midi : S3+S4)
    const blocks = [];
    for (let jour = 1; jour <= 6; jour++) {
      const s1 = creneaux.find(c => c.jour === jour && c.numero_seance === 1);
      const s2 = creneaux.find(c => c.jour === jour && c.numero_seance === 2);
      const s3 = creneaux.find(c => c.jour === jour && c.numero_seance === 3);
      const s4 = creneaux.find(c => c.jour === jour && c.numero_seance === 4);

      if (s1 && s2) blocks.push({ jour, periode: 'matin', creneaux: [s1, s2] });
      if (s3 && s4) blocks.push({ jour, periode: 'apm', creneaux: [s3, s4] });
    }

    // Suivi des occupations
    const groupeOccupe = {};
    const profOccupe = {};
    const salleOccupe = {};
    salles.forEach(s => { salleOccupe[s.id] = new Set(); });

    // Charger les séances déjà existantes et verrouillées
    const [existing] = await conn.query('SELECT s.id, s.creneau_id, s.salle_id, sg.groupe_id, sp.professeur_id FROM seance s LEFT JOIN seance_groupe sg ON sg.seance_id=s.id LEFT JOIN seance_professeur sp ON sp.seance_id=s.id WHERE s.semaine_id=?', [semaine_id]);
    for (const ex of existing) {
      if (ex.salle_id) salleOccupe[ex.salle_id]?.add(ex.creneau_id);
      if (ex.groupe_id) {
        if (!groupeOccupe[ex.groupe_id]) groupeOccupe[ex.groupe_id] = new Set();
        groupeOccupe[ex.groupe_id].add(ex.creneau_id);
      }
      if (ex.professeur_id) {
        if (!profOccupe[ex.professeur_id]) profOccupe[ex.professeur_id] = new Set();
        profOccupe[ex.professeur_id].add(ex.creneau_id);
      }
    }

    let created = 0;
    const gids = Object.keys(groupeUnits);

    for (const gid of gids) {
      if (!groupeOccupe[gid]) groupeOccupe[gid] = new Set();
      const units = [...groupeUnits[gid]];
      // Rotation selon le numéro de semaine pour que chaque semaine change !
      const rot = (semaine.numero || 1) % units.length;
      const rotated = [...units.slice(rot), ...units.slice(0, rot)];

      let blocksAssigned = 0;
      const targetBlocks = 5; // 25h par groupe et par semaine

      for (const u of rotated) {
        if (blocksAssigned >= targetBlocks) break;
        const pids = (u.prof_ids || '').split(',').map(Number).filter(Boolean);
        for (const p of pids) if (!profOccupe[p]) profOccupe[p] = new Set();

        for (const b of blocks) {
          if (blocksAssigned >= targetBlocks) break;
          const cr1 = b.creneaux[0];
          const cr2 = b.creneaux[1];

          if (groupeOccupe[gid].has(cr1.id) || groupeOccupe[gid].has(cr2.id)) continue;
          const pConf = pids.some(p => profOccupe[p].has(cr1.id) || profOccupe[p].has(cr2.id));
          if (pConf) continue;

          // Choix de salle selon type
          const pref = u.type_module === 'general' ? 'SC' : (u.type_module === 'pratique' ? 'LABO' : 'SP');
          let salle = salles.find(s => s.type_code === pref && !salleOccupe[s.id].has(cr1.id) && !salleOccupe[s.id].has(cr2.id));
          if (!salle) {
            salle = salles.find(s => !salleOccupe[s.id].has(cr1.id) && !salleOccupe[s.id].has(cr2.id));
          }
          if (!salle) continue;

          // Réserver
          groupeOccupe[gid].add(cr1.id);
          groupeOccupe[gid].add(cr2.id);
          pids.forEach(p => { profOccupe[p].add(cr1.id); profOccupe[p].add(cr2.id); });
          salleOccupe[salle.id].add(cr1.id);
          salleOccupe[salle.id].add(cr2.id);

          const blocNo = Math.floor(created / 2) + 1;

          // Insérer créneau 1
          const [ins1] = await conn.query(
            "INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature, bloc_no, statut) VALUES (?,?,?,?,'presentiel','bloc',?,'brouillon')",
            [u.unite_id, semaine_id, cr1.id, salle.id, blocNo]
          );
          await conn.query('INSERT INTO seance_groupe (seance_id, semaine_id, creneau_id, groupe_id) VALUES (?,?,?,?)', [ins1.insertId, semaine_id, cr1.id, gid]);
          for (const p of pids) await conn.query('INSERT INTO seance_professeur (seance_id, semaine_id, creneau_id, professeur_id) VALUES (?,?,?,?)', [ins1.insertId, semaine_id, cr1.id, p]);

          // Insérer créneau 2
          const [ins2] = await conn.query(
            "INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature, bloc_no, statut) VALUES (?,?,?,?,'presentiel','bloc',?,'brouillon')",
            [u.unite_id, semaine_id, cr2.id, salle.id, blocNo]
          );
          await conn.query('INSERT INTO seance_groupe (seance_id, semaine_id, creneau_id, groupe_id) VALUES (?,?,?,?)', [ins2.insertId, semaine_id, cr2.id, gid]);
          for (const p of pids) await conn.query('INSERT INTO seance_professeur (seance_id, semaine_id, creneau_id, professeur_id) VALUES (?,?,?,?)', [ins2.insertId, semaine_id, cr2.id, p]);

          blocksAssigned++;
          created += 2;
          break;
        }
      }
    }

    await conn.commit();
    res.json({ message: `Génération réussie : ${created} séances créées pour la semaine ${semaine.numero}`, seances_creees: created });
  } catch (err) {
    await conn.rollback();
    console.error(err);
    res.status(500).json({ error: err.message });
  } finally { conn.release(); }
});

// ─── Copier l'emploi d'une semaine vers une autre ──────────────────────────────
app.post('/api/copier-semaine', async (req, res) => {
  const { source_id, target_id } = req.body;
  if (!source_id || !target_id) return res.status(400).json({ error: 'source_id et target_id requis' });
  const conn = await pool.getConnection();
  try {
    await conn.beginTransaction();
    // Supprimer les séances non verrouillées de la cible
    await conn.query("DELETE FROM seance WHERE semaine_id=? AND verrouillee=0", [target_id]);

    const [sourceSeances] = await conn.query('SELECT * FROM seance WHERE semaine_id=?', [source_id]);
    let copied = 0;

    for (const s of sourceSeances) {
      const [ins] = await conn.query(
        "INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature, statut) VALUES (?,?,?,?,?,?,'brouillon')",
        [s.unite_id, target_id, s.creneau_id, s.salle_id, s.mode, s.nature]
      );
      const newId = ins.insertId;

      const [groupes] = await conn.query('SELECT groupe_id FROM seance_groupe WHERE seance_id=?', [s.id]);
      for (const g of groupes) {
        await conn.query('INSERT INTO seance_groupe (seance_id, semaine_id, creneau_id, groupe_id) VALUES (?,?,?,?)', [newId, target_id, s.creneau_id, g.groupe_id]);
      }

      const [profs] = await conn.query('SELECT professeur_id FROM seance_professeur WHERE seance_id=?', [s.id]);
      for (const p of profs) {
        await conn.query('INSERT INTO seance_professeur (seance_id, semaine_id, creneau_id, professeur_id) VALUES (?,?,?,?)', [newId, target_id, s.creneau_id, p.professeur_id]);
      }
      copied++;
    }

    await conn.commit();
    res.json({ message: `${copied} séances copiées avec succès`, count: copied });
  } catch (err) {
    await conn.rollback();
    res.status(500).json({ error: err.message });
  } finally { conn.release(); }
});

// ─── Vider les séances d'une semaine ──────────────────────────────────────────
app.post('/api/vider-semaine/:semaine_id', async (req, res) => {
  try {
    const [resDel] = await pool.query('DELETE FROM seance WHERE semaine_id=? AND verrouillee=0', [req.params.semaine_id]);
    res.json({ message: 'Séances de la semaine effacées', count: resDel.affectedRows });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── Stats ────────────────────────────────────────────────────────────────────
app.get('/api/stats/:semaine_id', async (req, res) => {
  const { semaine_id } = req.params;
  try {
    const [[{ total }]] = await pool.query('SELECT COUNT(*) AS total FROM seance WHERE semaine_id=?', [semaine_id]);
    const [[{ brouillon }]] = await pool.query("SELECT COUNT(*) AS brouillon FROM seance WHERE semaine_id=? AND statut='brouillon'", [semaine_id]);
    const [[{ valide }]] = await pool.query("SELECT COUNT(*) AS valide FROM seance WHERE semaine_id=? AND statut='valide'", [semaine_id]);
    const [[{ nb }]] = await pool.query('SELECT COUNT(DISTINCT sg.groupe_id) AS nb FROM seance_groupe sg JOIN seance s ON s.id=sg.seance_id WHERE s.semaine_id=?', [semaine_id]);
    res.json({ total, brouillon, valide, groupes_actifs: nb });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── Unités d'enseignement ────────────────────────────────────────────────────
app.get('/api/unites', async (req, res) => {
  try {
    const [rows] = await pool.query(`
      SELECT ue.id, ue.code_fusion, m.code AS module_code, m.intitule AS module_nom,
             f.code AS filiere_code,
             GROUP_CONCAT(DISTINCT g.code ORDER BY g.code SEPARATOR ', ') AS groupes,
             GROUP_CONCAT(DISTINCT p.nom_complet ORDER BY p.nom_complet SEPARATOR ', ') AS formateurs
      FROM unite_enseignement ue
      JOIN module m ON m.id = ue.module_id
      JOIN filiere f ON f.id = ue.filiere_id
      LEFT JOIN unite_groupe ug ON ug.unite_id = ue.id
      LEFT JOIN groupe g ON g.id = ug.groupe_id
      LEFT JOIN unite_professeur up ON up.unite_id = ue.id AND up.mode = 'presentiel'
      LEFT JOIN professeur p ON p.id = up.professeur_id
      GROUP BY ue.id, ue.code_fusion, m.code, m.intitule, f.code
      ORDER BY f.code, m.code
    `);
    res.json(rows);
  } catch (err) { res.status(500).json({ error: err.message }); }
});

const PORT = 3001;
app.listen(PORT, () => {
  console.log(`✅ API GestEmploi → http://localhost:${PORT}`);
});
