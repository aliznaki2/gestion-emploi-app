-- =====================================================================
--  GÉNÉRATEUR D'EMPLOIS DU TEMPS : 03_requetes.sql
--  Requêtes de contrôle, de consultation et d'indicateurs.
--  Dans phpMyAdmin : copiez le bloc « Paramètres » ET la requête voulue dans l'onglet SQL, puis cliquez sur Exécuter
--  (les variables @ ne sont pas conservées d'une exécution à l'autre, il faut donc les recopier à chaque fois).
--  En ligne de commande, le fichier entier peut être exécuté d'un coup.
--  Les requêtes des parties C et D utilisent des séances : lancez d'abord 04_jeu_essai.sql.
-- =====================================================================
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
USE emplois_du_temps;

-- Paramètres (à adapter) ------------------------------------------------
SET @semaine := (SELECT s.id FROM semaine s JOIN annee_scolaire a ON a.id = s.annee_scolaire_id
                 WHERE a.annee_debut = 2026 AND s.numero = 1);
SET @groupe_code := 'DEV105';
SET @nb_semaines := 16;      -- semaines de cours d'un semestre (hypothèse)

-- =====================================================================
-- A. CONTRÔLES DES DONNÉES IMPORTÉES
-- =====================================================================

-- A1. Nombre de lignes par table
SELECT 'groupe' AS table_nom, COUNT(*) AS lignes FROM groupe
UNION ALL SELECT 'module', COUNT(*) FROM module
UNION ALL SELECT 'professeur', COUNT(*) FROM professeur
UNION ALL SELECT 'unite_enseignement', COUNT(*) FROM unite_enseignement
UNION ALL SELECT 'unite_groupe', COUNT(*) FROM unite_groupe;

-- A2. Unités d'enseignement sans professeur en présentiel (à traiter avant la génération)
SELECT f.code AS filiere, COUNT(*) AS unites_sans_professeur
FROM unite_enseignement u
JOIN module m ON m.id = u.module_id
JOIN filiere f ON f.id = m.filiere_id
WHERE NOT EXISTS (SELECT 1 FROM unite_professeur up WHERE up.unite_id = u.id AND up.mode = 'presentiel')
GROUP BY f.code
ORDER BY unites_sans_professeur DESC;

-- A3. Unités avec plusieurs professeurs en présentiel (deux formateurs dans la même salle)
SELECT u.id AS unite_id, u.code_fusion, m.code AS module, m.intitule,
       GROUP_CONCAT(DISTINCT p.nom_complet ORDER BY p.nom_complet SEPARATOR ' + ') AS professeurs,
       (SELECT GROUP_CONCAT(g.code ORDER BY g.code SEPARATOR ' + ') FROM unite_groupe ug JOIN groupe g ON g.id = ug.groupe_id WHERE ug.unite_id = u.id) AS groupes
FROM unite_enseignement u
JOIN module m ON m.id = u.module_id
JOIN unite_professeur up ON up.unite_id = u.id AND up.mode = 'presentiel'
JOIN professeur p ON p.id = up.professeur_id
GROUP BY u.id, u.code_fusion, m.code, m.intitule
HAVING COUNT(DISTINCT p.id) > 1;

-- A4. Volumes horaires qui ne sont pas un multiple de 2,5 h (à corriger ou arrondir), regroupés par module
SELECT m.code AS module, m.intitule, sm.numero AS semestre, v.h_presentiel, v.h_synchrone, COUNT(*) AS nb_unites
FROM volume_horaire v
JOIN unite_enseignement u ON u.id = v.unite_id
JOIN module m ON m.id = u.module_id
JOIN semestre sm ON sm.id = v.semestre_id
WHERE MOD((v.h_presentiel + v.h_synchrone) * 10, 25) <> 0
GROUP BY m.code, m.intitule, sm.numero, v.h_presentiel, v.h_synchrone
ORDER BY nb_unites DESC;

-- A5. Heures à planifier par groupe et par semestre (présentiel + synchrone), avec les semaines nécessaires à 32,5 h
SELECT g.code AS groupe, sm.numero AS semestre,
       SUM(v.h_presentiel + v.h_synchrone) AS heures_a_planifier,
       ROUND(SUM(v.h_presentiel + v.h_synchrone) / 32.5, 1) AS semaines_a_32_5h
FROM unite_groupe ug
JOIN groupe g ON g.id = ug.groupe_id
JOIN volume_horaire v ON v.unite_id = ug.unite_id
JOIN semestre sm ON sm.id = v.semestre_id
GROUP BY g.code, sm.numero
ORDER BY semaines_a_32_5h DESC
LIMIT 10;

-- A6. Charge annuelle de chaque professeur en présentiel et en synchrone
SELECT p.matricule, p.nom_complet, COUNT(DISTINCT up.unite_id) AS unites,
       ROUND(SUM(v.h_presentiel + v.h_synchrone), 1) AS heures_annee
FROM professeur p
JOIN unite_professeur up ON up.professeur_id = p.id AND up.mode = 'presentiel'
JOIN volume_horaire v ON v.unite_id = up.unite_id
GROUP BY p.id, p.matricule, p.nom_complet
ORDER BY heures_annee DESC
LIMIT 10;

-- =====================================================================
-- B. CONSULTATION DES EMPLOIS DU TEMPS D'UNE SEMAINE
-- =====================================================================

-- B1. Emploi du temps d'un groupe
SELECT c.jour, c.numero_seance, c.heure_debut, c.heure_fin, m.code AS module, m.intitule,
       IFNULL(sa.nom, 'À distance') AS salle,
       (SELECT GROUP_CONCAT(p.nom_complet SEPARATOR ' + ') FROM seance_professeur sp JOIN professeur p ON p.id = sp.professeur_id WHERE sp.seance_id = s.id) AS professeurs,
       s.statut
FROM seance_groupe sg
JOIN groupe g ON g.id = sg.groupe_id
JOIN seance s ON s.id = sg.seance_id
JOIN creneau c ON c.id = s.creneau_id
JOIN unite_enseignement u ON u.id = s.unite_id
JOIN module m ON m.id = u.module_id
LEFT JOIN salle sa ON sa.id = s.salle_id
WHERE g.code = @groupe_code AND s.semaine_id = @semaine
ORDER BY c.jour, c.numero_seance;

-- B2. Emploi du temps d'un professeur (les professeurs ne voient que les séances validées)
SELECT c.jour, c.numero_seance, c.heure_debut, c.heure_fin, m.code AS module,
       (SELECT GROUP_CONCAT(g.code SEPARATOR ' + ') FROM seance_groupe sg JOIN groupe g ON g.id = sg.groupe_id WHERE sg.seance_id = s.id) AS groupes,
       IFNULL(sa.nom, 'À distance') AS salle
FROM seance_professeur sp
JOIN professeur p ON p.id = sp.professeur_id
JOIN seance s ON s.id = sp.seance_id
JOIN creneau c ON c.id = s.creneau_id
JOIN unite_enseignement u ON u.id = s.unite_id
JOIN module m ON m.id = u.module_id
LEFT JOIN salle sa ON sa.id = s.salle_id
WHERE p.matricule = '20573' AND s.semaine_id = @semaine      -- remplacer par le matricule voulu
  -- AND s.statut = 'valide'                                  -- à activer pour l'espace professeur
ORDER BY c.jour, c.numero_seance;

-- =====================================================================
-- C. INDICATEURS
-- =====================================================================

-- C1. Taux d'occupation de chaque salle pour la semaine (24 séances = 60 h par salle)
SELECT sa.nom AS salle, ts.code AS type_salle, IFNULL(SUM(c.duree_h), 0) AS heures_utilisees,
       ROUND(100 * IFNULL(SUM(c.duree_h), 0) / (SELECT SUM(duree_h) FROM creneau), 1) AS taux_occupation_pct
FROM salle sa
JOIN type_salle ts ON ts.id = sa.type_salle_id
LEFT JOIN seance s ON s.salle_id = sa.id AND s.semaine_id = @semaine
LEFT JOIN creneau c ON c.id = s.creneau_id
GROUP BY sa.id, sa.nom, ts.code
ORDER BY taux_occupation_pct DESC, sa.nom;

-- C2. Taux d'occupation global des salles pour la semaine
SELECT ROUND(100 * IFNULL(SUM(c.duree_h), 0) / ((SELECT COUNT(*) FROM salle WHERE actif = 1) * (SELECT SUM(duree_h) FROM creneau)), 1) AS taux_occupation_global_pct
FROM seance s JOIN creneau c ON c.id = s.creneau_id
WHERE s.semaine_id = @semaine AND s.salle_id IS NOT NULL;

-- C3. Heures de chaque groupe pour la semaine, avec l'écart à la plage de 30 à 35 h
SELECT g.code AS groupe, IFNULL(h.heures, 0) AS heures,
       CASE WHEN IFNULL(h.heures, 0) < 30 THEN 'sous 30 h' WHEN h.heures > 35 THEN 'au-dessus de 35 h' ELSE 'conforme' END AS controle
FROM groupe g
LEFT JOIN v_heures_groupe_semaine h ON h.groupe_id = g.id AND h.semaine_id = @semaine
WHERE g.actif = 1
ORDER BY heures DESC, g.code
LIMIT 10;

-- C4. Heures creuses des groupes : séances vides entre deux séances occupées le même jour
SELECT g.code AS groupe, c.jour, MIN(c.numero_seance) AS premiere_seance, MAX(c.numero_seance) AS derniere_seance,
       COUNT(*) AS seances_occupees,
       MAX(c.numero_seance) - MIN(c.numero_seance) + 1 - COUNT(*) AS heures_creuses_en_seances
FROM seance_groupe sg
JOIN seance s ON s.id = sg.seance_id
JOIN creneau c ON c.id = s.creneau_id
JOIN groupe g ON g.id = sg.groupe_id
WHERE s.semaine_id = @semaine
GROUP BY g.code, c.jour
HAVING MAX(c.numero_seance) - MIN(c.numero_seance) + 1 > COUNT(*);

-- C5. Heures creuses des professeurs (même principe)
SELECT p.nom_complet AS professeur, c.jour, COUNT(*) AS seances_occupees,
       MAX(c.numero_seance) - MIN(c.numero_seance) + 1 - COUNT(*) AS heures_creuses_en_seances
FROM seance_professeur sp
JOIN seance s ON s.id = sp.seance_id
JOIN creneau c ON c.id = s.creneau_id
JOIN professeur p ON p.id = sp.professeur_id
WHERE s.semaine_id = @semaine
GROUP BY p.id, p.nom_complet, c.jour
HAVING MAX(c.numero_seance) - MIN(c.numero_seance) + 1 > COUNT(*);

-- C6. Journées de 10 h (les 4 séances occupées) pour les groupes
SELECT g.code AS groupe, c.jour, COUNT(*) AS seances
FROM seance_groupe sg
JOIN seance s ON s.id = sg.seance_id
JOIN creneau c ON c.id = s.creneau_id
JOIN groupe g ON g.id = sg.groupe_id
WHERE s.semaine_id = @semaine
GROUP BY g.code, c.jour
HAVING COUNT(*) = 4;

-- C7. Charge de la semaine de chaque professeur, comparée à son maximum (si défini)
SELECT p.nom_complet AS professeur, SUM(c.duree_h) AS heures_semaine, p.heures_max_semaine,
       CASE WHEN p.heures_max_semaine IS NOT NULL AND SUM(c.duree_h) > p.heures_max_semaine THEN 'dépassement' ELSE 'ok' END AS controle
FROM seance_professeur sp
JOIN seance s ON s.id = sp.seance_id
JOIN creneau c ON c.id = s.creneau_id
JOIN professeur p ON p.id = sp.professeur_id
WHERE s.semaine_id = @semaine
GROUP BY p.id, p.nom_complet, p.heures_max_semaine
ORDER BY heures_semaine DESC;

-- C8. Taux de réalisation des modules (heures réalisées / heures prévues)
SELECT code_module, module, heures_prevues, heures_realisees, taux_realisation_pct
FROM v_taux_realisation_unite
WHERE heures_realisees > 0
ORDER BY taux_realisation_pct DESC
LIMIT 10;

-- C9. Taux de réalisation moyen par professeur (présentiel)
SELECT p.nom_complet AS professeur,
       ROUND(SUM(t.heures_realisees), 1) AS heures_realisees, ROUND(SUM(t.heures_prevues), 1) AS heures_prevues,
       ROUND(100 * SUM(t.heures_realisees) / NULLIF(SUM(t.heures_prevues), 0), 1) AS taux_pct
FROM v_taux_realisation_unite t
JOIN unite_professeur up ON up.unite_id = t.unite_id AND up.mode = 'presentiel'
JOIN professeur p ON p.id = up.professeur_id
GROUP BY p.id, p.nom_complet
HAVING SUM(t.heures_realisees) > 0
ORDER BY taux_pct DESC;

-- =====================================================================
-- D. CONTRÔLES DE VALIDITÉ DES SÉANCES (avant de valider une semaine)
-- =====================================================================

-- D1. Blocs invalides : un bloc doit avoir 2 séances, le même jour, aux séances 1+2 ou 3+4
SELECT s.bloc_no, COUNT(*) AS nb_seances, MIN(c.jour) AS jour_min, MAX(c.jour) AS jour_max,
       MIN(c.numero_seance) AS seance_min, MAX(c.numero_seance) AS seance_max
FROM seance s JOIN creneau c ON c.id = s.creneau_id
WHERE s.nature = 'bloc' AND s.semaine_id = @semaine
GROUP BY s.bloc_no
HAVING COUNT(*) <> 2 OR MIN(c.jour) <> MAX(c.jour)
    OR MAX(c.numero_seance) - MIN(c.numero_seance) <> 1 OR MIN(c.numero_seance) NOT IN (1, 3);

-- D2. Séances sans professeur (interdit à la validation)
SELECT s.id AS seance_id, m.code AS module, c.jour, c.numero_seance
FROM seance s
JOIN unite_enseignement u ON u.id = s.unite_id
JOIN module m ON m.id = u.module_id
JOIN creneau c ON c.id = s.creneau_id
WHERE s.semaine_id = @semaine
  AND NOT EXISTS (SELECT 1 FROM seance_professeur sp WHERE sp.seance_id = s.id);

-- D3. Salle d'un type non accepté par le module
SELECT s.id AS seance_id, m.code AS module, sa.nom AS salle, ts.code AS type_salle
FROM seance s
JOIN unite_enseignement u ON u.id = s.unite_id
JOIN module m ON m.id = u.module_id
JOIN salle sa ON sa.id = s.salle_id
JOIN type_salle ts ON ts.id = sa.type_salle_id
WHERE s.semaine_id = @semaine AND s.mode = 'presentiel'
  AND NOT EXISTS (SELECT 1 FROM module_type_salle mts WHERE mts.module_id = m.id AND mts.type_salle_id = sa.type_salle_id);

-- D4. Séances placées sur un créneau bloqué par le professeur
SELECT s.id AS seance_id, p.nom_complet AS professeur, c.jour, c.numero_seance
FROM seance_professeur sp
JOIN seance s ON s.id = sp.seance_id
JOIN creneau c ON c.id = s.creneau_id
JOIN professeur p ON p.id = sp.professeur_id
JOIN disponibilite d ON d.professeur_id = sp.professeur_id AND d.creneau_id = s.creneau_id AND d.etat = 'bloque'
WHERE s.semaine_id = @semaine;

-- D5. Séances placées dans une semaine de vacances ou d'examens
SELECT s.id AS seance_id, w.numero AS semaine, w.nature
FROM seance s JOIN semaine w ON w.id = s.semaine_id
WHERE w.nature <> 'cours';

-- =====================================================================
-- E. PHASE 0 : PASSAGE DES MODULES GÉNÉRAUX
-- =====================================================================

-- E1. Groupes dont les modules généraux demandent plus de semaines que le semestre, à 10 h par semaine (plafond du groupe)
SELECT g.code AS groupe, sm.numero AS semestre, SUM(v.h_presentiel + v.h_synchrone) AS heures_generales,
       ROUND(SUM(v.h_presentiel + v.h_synchrone) / 10, 1) AS semaines_necessaires
FROM unite_groupe ug
JOIN groupe g ON g.id = ug.groupe_id
JOIN module m ON m.id = ug.module_id AND m.type_module = 'general'
JOIN volume_horaire v ON v.unite_id = ug.unite_id
JOIN semestre sm ON sm.id = v.semestre_id
GROUP BY g.code, sm.numero
HAVING SUM(v.h_presentiel + v.h_synchrone) / 10 > @nb_semaines
ORDER BY semaines_necessaires DESC;

-- E2. Formateurs de modules généraux : nombre de groupes, heures et semaines de passage à 5 h par semaine
SELECT p.matricule, p.nom_complet,
       (SELECT COUNT(DISTINCT ug.groupe_id)
          FROM unite_professeur up2
          JOIN unite_groupe ug ON ug.unite_id = up2.unite_id
          JOIN module m2 ON m2.id = ug.module_id AND m2.type_module = 'general'
         WHERE up2.professeur_id = p.id) AS groupes,
       ROUND(SUM(h.heures), 1) AS heures_annee,
       ROUND(SUM(h.heures) / 5, 1) AS semaines_de_passage_a_5h
FROM professeur p
JOIN (SELECT DISTINCT up.professeur_id, u.id AS unite_id
        FROM unite_professeur up
        JOIN unite_enseignement u ON u.id = up.unite_id
        JOIN module m ON m.id = u.module_id AND m.type_module = 'general') pu ON pu.professeur_id = p.id
JOIN (SELECT unite_id, SUM(h_presentiel + h_synchrone) AS heures FROM volume_horaire GROUP BY unite_id) h ON h.unite_id = pu.unite_id
GROUP BY p.id, p.matricule, p.nom_complet
ORDER BY groupes DESC
LIMIT 10;

-- E3. Heures restantes d'une unité d'enseignement (prévues - réalisées)
SELECT u.id AS unite_id, m.code AS module,
       SUM(v.h_presentiel + v.h_synchrone) - (u.h_realisees_presentiel + u.h_realisees_synchrone) AS heures_restantes
FROM unite_enseignement u
JOIN module m ON m.id = u.module_id
JOIN volume_horaire v ON v.unite_id = u.id
GROUP BY u.id, m.code, u.h_realisees_presentiel, u.h_realisees_synchrone
ORDER BY heures_restantes DESC
LIMIT 10;
