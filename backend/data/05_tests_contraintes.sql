-- =====================================================================
--  GÉNÉRATEUR D'EMPLOIS DU TEMPS : 05_tests_contraintes.sql
--  Tests : chaque instruction ci-dessous doit ÉCHOUER, car la base interdit le conflit.
--  Exécutez-les UNE PAR UNE après 04_jeu_essai.sql. Le message attendu est indiqué en commentaire.
--  Dans phpMyAdmin, copiez à chaque fois les lignes SET @... du début (elles définissent les variables) ET le test voulu.
-- =====================================================================
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
USE emplois_du_temps;
SET @sem := (SELECT s.id FROM semaine s JOIN annee_scolaire a ON a.id = s.annee_scolaire_id WHERE a.annee_debut = 2026 AND s.numero = 1);
SET @ge106 := (SELECT id FROM groupe WHERE code = 'GE106');
SET @u2 := (SELECT id FROM unite_enseignement WHERE code_fusion = '714710');                    -- unité à deux formateurs
SET @prof2 := (SELECT professeur_id FROM unite_professeur WHERE unite_id = @u2 AND mode = 'presentiel' ORDER BY professeur_id LIMIT 1);

-- TEST 1 : une salle ne peut pas recevoir deux séances au même créneau (mardi, séance 1, salle SP2 déjà prise)
-- Erreur attendue : Duplicate entry ... for key 'uq_seance_salle'
INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature)
SELECT (SELECT id FROM unite_enseignement WHERE id <> @u2 ORDER BY id LIMIT 1), @sem, c.id,
       (SELECT id FROM salle WHERE nom = 'SP2'), 'presentiel', 'simple'
FROM creneau c WHERE c.jour = 2 AND c.numero_seance = 1;

-- TEST 2 : un professeur ne peut pas être dans deux séances au même créneau
-- (on crée une séance libre en SC2 le mardi séance 1, puis on lui rattache le professeur déjà occupé)
-- Erreur attendue sur le dernier INSERT : Duplicate entry ... for key 'uq_sp_professeur_creneau'
INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature)
SELECT (SELECT unite_id FROM unite_professeur WHERE professeur_id = @prof2 AND unite_id <> @u2 AND mode = 'presentiel' LIMIT 1),
       @sem, c.id, (SELECT id FROM salle WHERE nom = 'SC2'), 'presentiel', 'simple'
FROM creneau c WHERE c.jour = 2 AND c.numero_seance = 1;
SET @test2 := LAST_INSERT_ID();
INSERT INTO seance_professeur (seance_id, semaine_id, creneau_id, professeur_id)
SELECT s.id, s.semaine_id, s.creneau_id, @prof2 FROM seance s WHERE s.id = @test2;

-- TEST 3 : un groupe ne peut pas avoir deux séances au même créneau
-- Erreur attendue : Duplicate entry ... for key 'uq_sg_groupe_creneau'
INSERT INTO seance_groupe (seance_id, semaine_id, creneau_id, groupe_id)
SELECT s.id, s.semaine_id, s.creneau_id, @ge106 FROM seance s WHERE s.id = @test2;

-- TEST 4 : une séance à distance ne peut pas avoir de salle
-- Erreur attendue : CONSTRAINT `ck_seance_salle_mode` failed
INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature)
SELECT @u2, @sem, c.id, (SELECT id FROM salle WHERE nom = 'SC3'), 'distance', 'simple'
FROM creneau c WHERE c.jour = 5 AND c.numero_seance = 1;

-- TEST 5 : une séance de nature « bloc » doit avoir un numéro de bloc
-- Erreur attendue : CONSTRAINT `ck_seance_bloc` failed
INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature, bloc_no)
SELECT @u2, @sem, c.id, (SELECT id FROM salle WHERE nom = 'SC3'), 'presentiel', 'bloc', NULL
FROM creneau c WHERE c.jour = 5 AND c.numero_seance = 1;

-- TEST 6 : un groupe ne peut pas suivre deux fois le même module la même année
-- (on crée une deuxième unité pour le même module, puis on y rattache un groupe qui suit déjà ce module)
-- Erreur attendue sur le dernier INSERT : Duplicate entry ... for key 'uq_unite_groupe_module'
INSERT INTO unite_enseignement (annee_scolaire_id, module_id, filiere_id, cle_source)
SELECT annee_scolaire_id, module_id, filiere_id, 'TEST-DOUBLON' FROM unite_enseignement WHERE id = @u2;
SET @u_test := LAST_INSERT_ID();
INSERT INTO unite_groupe (unite_id, groupe_id, annee_scolaire_id, module_id, filiere_id)
SELECT @u_test, @ge106, annee_scolaire_id, module_id, filiere_id FROM unite_enseignement WHERE id = @u_test;
-- nettoyage du test
DELETE FROM unite_enseignement WHERE id = @u_test;

-- TEST 7 : un groupe d'une autre filière ne peut pas rejoindre l'unité d'un module
-- Erreur attendue : Cannot add or update a child row: a foreign key constraint fails (fk_ug_groupe)
INSERT INTO unite_groupe (unite_id, groupe_id, annee_scolaire_id, module_id, filiere_id)
SELECT u.id, (SELECT id FROM groupe WHERE code = 'DEV101'), u.annee_scolaire_id, u.module_id, u.filiere_id
FROM unite_enseignement u WHERE u.id = @u2;

-- TEST 8 (réussite) : déplacer une séance met à jour automatiquement ses groupes et ses professeurs
-- (ON UPDATE CASCADE). La séance du mardi (séance 1) passe au vendredi (séance 1) ; tout est annulé à la fin.
-- Résultat attendu : groupes_synchronises = 2 et professeurs_synchronises = 2 pour chaque séance de l'unité.
START TRANSACTION;
UPDATE seance SET creneau_id = (SELECT id FROM creneau WHERE jour = 5 AND numero_seance = 1)
WHERE unite_id = @u2 AND semaine_id = @sem
  AND creneau_id = (SELECT id FROM creneau WHERE jour = 2 AND numero_seance = 1);
SELECT s.id, s.creneau_id,
       (SELECT COUNT(*) FROM seance_groupe sg WHERE sg.seance_id = s.id AND sg.creneau_id = s.creneau_id) AS groupes_synchronises,
       (SELECT COUNT(*) FROM seance_professeur sp WHERE sp.seance_id = s.id AND sp.creneau_id = s.creneau_id) AS professeurs_synchronises
FROM seance s WHERE s.unite_id = @u2 AND s.semaine_id = @sem;
ROLLBACK;

-- Nettoyage : supprime la séance libre créée par le test 2
DELETE FROM seance WHERE id = @test2;
