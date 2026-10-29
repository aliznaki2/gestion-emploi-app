-- =====================================================================
--  GÉNÉRATEUR D'EMPLOIS DU TEMPS : 04_jeu_essai.sql
--  Jeu d'essai : un calendrier d'exemple et quelques séances pour tester les requêtes.
--  À exécuter APRÈS 01_schema.sql et 02_import_donnees.sql.
--  Les dates sont des EXEMPLES : l'administrateur renseignera les vraies dates.
-- =====================================================================
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
USE emplois_du_temps;

-- 1. Dates d'exemple pour S1 (16 semaines à partir du lundi 14/09/2026)
UPDATE annee_scolaire SET date_debut = '2026-09-14', date_fin = '2027-06-26' WHERE annee_debut = 2026;
UPDATE semestre SET date_debut = '2026-09-14', date_fin = '2027-01-02'
WHERE numero = 1 AND annee_scolaire_id = (SELECT id FROM annee_scolaire WHERE annee_debut = 2026);

-- 2. Les 16 semaines de S1 (lundi au samedi)
INSERT INTO semaine (annee_scolaire_id, semestre_id, numero, date_debut, date_fin, nature)
WITH RECURSIVE n (num) AS (SELECT 1 UNION ALL SELECT num + 1 FROM n WHERE num < 16)
SELECT a.id, sm.id, n.num, DATE_ADD(sm.date_debut, INTERVAL (n.num - 1) * 7 DAY),
       DATE_ADD(sm.date_debut, INTERVAL (n.num - 1) * 7 + 5 DAY), 'cours'
FROM n
JOIN annee_scolaire a ON a.annee_debut = 2026
JOIN semestre sm ON sm.annee_scolaire_id = a.id AND sm.numero = 1;

-- 3. Séances de la semaine 1 (brouillon)
SET @sem := (SELECT s.id FROM semaine s JOIN annee_scolaire a ON a.id = s.annee_scolaire_id WHERE a.annee_debut = 2026 AND s.numero = 1);

-- 3.a Bloc de 5 h (créneaux 1 et 2 du lundi) : module M104 du groupe DEV105 (unité fusionnée DEV105 + DEV106), salle SP1
SET @u1 := (SELECT ug.unite_id FROM unite_groupe ug
            JOIN groupe g ON g.id = ug.groupe_id JOIN module m ON m.id = ug.module_id
            WHERE g.code = 'DEV105' AND m.code = 'M104');
INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature, bloc_no)
SELECT @u1, @sem, c.id, (SELECT id FROM salle WHERE nom = 'SP1'), 'presentiel', 'bloc', 1
FROM creneau c WHERE c.jour = 1 AND c.numero_seance IN (1, 2);

-- 3.b Unité fusionnée avec DEUX formateurs (GE106 + GE107, module M105) : bloc du mardi matin en SP2
SET @u2 := (SELECT id FROM unite_enseignement WHERE code_fusion = '714710');
INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature, bloc_no)
SELECT @u2, @sem, c.id, (SELECT id FROM salle WHERE nom = 'SP2'), 'presentiel', 'bloc', 2
FROM creneau c WHERE c.jour = 2 AND c.numero_seance IN (1, 2);

-- 3.c Séance à distance (sans salle) : deux unités différentes au même créneau, c'est autorisé
SET @u3 := (SELECT ug.unite_id FROM unite_groupe ug
            JOIN groupe g ON g.id = ug.groupe_id JOIN module m ON m.id = ug.module_id
            WHERE g.code = 'DEV101' AND m.code = 'M104');
SET @u4 := (SELECT ug.unite_id FROM unite_groupe ug
            JOIN groupe g ON g.id = ug.groupe_id JOIN module m ON m.id = ug.module_id
            WHERE g.code = 'DEV103' AND m.code = 'M104');
INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature, bloc_no)
SELECT u.id, @sem, c.id, NULL, 'distance', 'simple', NULL
FROM (SELECT @u3 AS id UNION ALL SELECT @u4) u
JOIN creneau c ON c.jour = 3 AND c.numero_seance = 3;

-- 3.d Rattacher à chaque séance ses groupes et ses professeurs (tirés de l'unité d'enseignement)
INSERT INTO seance_groupe (seance_id, semaine_id, creneau_id, groupe_id)
SELECT s.id, s.semaine_id, s.creneau_id, ug.groupe_id
FROM seance s JOIN unite_groupe ug ON ug.unite_id = s.unite_id
WHERE s.semaine_id = @sem;

INSERT INTO seance_professeur (seance_id, semaine_id, creneau_id, professeur_id)
SELECT DISTINCT s.id, s.semaine_id, s.creneau_id, up.professeur_id
FROM seance s JOIN unite_professeur up ON up.unite_id = s.unite_id
WHERE s.semaine_id = @sem AND up.mode = IF(s.mode = 'distance', 'synchrone', 'presentiel');

SELECT COUNT(*) AS seances, (SELECT COUNT(*) FROM seance_groupe) AS liens_groupes, (SELECT COUNT(*) FROM seance_professeur) AS liens_professeurs FROM seance;
