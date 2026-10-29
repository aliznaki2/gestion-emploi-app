-- =====================================================================
--  GÉNÉRATEUR D'EMPLOIS DU TEMPS : 01_schema.sql
--  Création de la base, des tables, des contraintes, des données de
--  référence (types de salle, créneaux) et des vues.
--  Compatible MySQL 8 et MariaDB 10.4+ (XAMPP, phpMyAdmin).
--  ATTENTION : ce script supprime la base emplois_du_temps si elle existe.
-- =====================================================================

SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
SET FOREIGN_KEY_CHECKS = 0;

DROP DATABASE IF EXISTS emplois_du_temps;
CREATE DATABASE emplois_du_temps CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE emplois_du_temps;

-- ---------------------------------------------------------------------
-- 1. CALENDRIER
-- ---------------------------------------------------------------------
CREATE TABLE annee_scolaire (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  annee_debut SMALLINT UNSIGNED NOT NULL COMMENT 'Ex. 2026 pour 2026-2027',
  libelle     VARCHAR(20) NOT NULL,
  date_debut  DATE NULL,
  date_fin    DATE NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_annee_debut (annee_debut),
  UNIQUE KEY uq_annee_libelle (libelle),
  CONSTRAINT ck_annee_dates CHECK (date_debut IS NULL OR date_fin IS NULL OR date_fin > date_debut)
) ENGINE=InnoDB;

CREATE TABLE semestre (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  annee_scolaire_id INT UNSIGNED NOT NULL,
  numero            TINYINT UNSIGNED NOT NULL COMMENT '1 ou 2',
  date_debut        DATE NULL COMMENT 'À renseigner par l''administrateur',
  date_fin          DATE NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_semestre (annee_scolaire_id, numero),
  UNIQUE KEY uq_semestre_annee (id, annee_scolaire_id),
  CONSTRAINT fk_semestre_annee FOREIGN KEY (annee_scolaire_id) REFERENCES annee_scolaire (id),
  CONSTRAINT ck_semestre_numero CHECK (numero IN (1, 2)),
  CONSTRAINT ck_semestre_dates CHECK (date_debut IS NULL OR date_fin IS NULL OR date_fin > date_debut)
) ENGINE=InnoDB;

CREATE TABLE semaine (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  annee_scolaire_id INT UNSIGNED NOT NULL,
  semestre_id       INT UNSIGNED NULL COMMENT 'NULL pour une semaine hors semestre',
  numero            SMALLINT UNSIGNED NOT NULL COMMENT 'Numéro de la semaine dans l''année scolaire',
  date_debut        DATE NOT NULL COMMENT 'Lundi',
  date_fin          DATE NOT NULL COMMENT 'Samedi',
  nature            ENUM('cours','vacances','examens') NOT NULL DEFAULT 'cours',
  PRIMARY KEY (id),
  UNIQUE KEY uq_semaine_numero (annee_scolaire_id, numero),
  UNIQUE KEY uq_semaine_date (date_debut),
  UNIQUE KEY uq_semaine_annee (id, annee_scolaire_id),
  CONSTRAINT fk_semaine_annee FOREIGN KEY (annee_scolaire_id) REFERENCES annee_scolaire (id),
  CONSTRAINT fk_semaine_semestre FOREIGN KEY (semestre_id, annee_scolaire_id) REFERENCES semestre (id, annee_scolaire_id),
  CONSTRAINT ck_semaine_dates CHECK (date_fin >= date_debut)
) ENGINE=InnoDB;

CREATE TABLE creneau (
  id            TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  jour          TINYINT UNSIGNED NOT NULL COMMENT '1 = lundi ... 6 = samedi',
  numero_seance TINYINT UNSIGNED NOT NULL COMMENT '1 à 4',
  heure_debut   TIME NOT NULL,
  heure_fin     TIME NOT NULL,
  duree_h       DECIMAL(3,1) NOT NULL DEFAULT 2.5,
  PRIMARY KEY (id),
  UNIQUE KEY uq_creneau (jour, numero_seance),
  CONSTRAINT ck_creneau_jour CHECK (jour BETWEEN 1 AND 6),
  CONSTRAINT ck_creneau_seance CHECK (numero_seance BETWEEN 1 AND 4),
  CONSTRAINT ck_creneau_duree CHECK (duree_h > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. STRUCTURE PÉDAGOGIQUE
-- ---------------------------------------------------------------------
CREATE TABLE secteur (
  id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  libelle VARCHAR(100) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_secteur_libelle (libelle)
) ENGINE=InnoDB;

CREATE TABLE filiere (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  code           VARCHAR(30) NOT NULL COMMENT 'Ex. DIA_DEV_TS',
  intitule       VARCHAR(120) NOT NULL,
  secteur_id     INT UNSIGNED NOT NULL,
  niveau         VARCHAR(10) NOT NULL DEFAULT 'TS',
  type_formation VARCHAR(40) NOT NULL DEFAULT 'Diplômante',
  PRIMARY KEY (id),
  UNIQUE KEY uq_filiere_code (code),
  CONSTRAINT fk_filiere_secteur FOREIGN KEY (secteur_id) REFERENCES secteur (id)
) ENGINE=InnoDB;

CREATE TABLE groupe (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  annee_scolaire_id INT UNSIGNED NOT NULL,
  code              VARCHAR(20) NOT NULL COMMENT 'Ex. DEV105',
  filiere_id        INT UNSIGNED NOT NULL,
  annee_etude       TINYINT UNSIGNED NOT NULL COMMENT '1, 2 ou 3 (Année de formation)',
  effectif          SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  regime            VARCHAR(10) NOT NULL DEFAULT 'CDJ' COMMENT 'CDJ = cours de jour',
  mode_formation    VARCHAR(30) NOT NULL DEFAULT 'Résidentiel',
  actif             TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uq_groupe_code (annee_scolaire_id, code),
  UNIQUE KEY uq_groupe_cle (id, annee_scolaire_id, filiere_id),
  CONSTRAINT fk_groupe_annee FOREIGN KEY (annee_scolaire_id) REFERENCES annee_scolaire (id),
  CONSTRAINT fk_groupe_filiere FOREIGN KEY (filiere_id) REFERENCES filiere (id),
  CONSTRAINT ck_groupe_annee_etude CHECK (annee_etude BETWEEN 1 AND 3)
) ENGINE=InnoDB;

CREATE TABLE module (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  filiere_id  INT UNSIGNED NOT NULL,
  code        VARCHAR(20) NOT NULL COMMENT 'Ex. M104, EGTS102. Un même code peut exister dans plusieurs filières',
  intitule    VARCHAR(200) NOT NULL,
  type_module ENUM('technique','general') NOT NULL COMMENT 'general = code EGTS ou EGTSA',
  regional    TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Examen régional (Régional = O)',
  PRIMARY KEY (id),
  UNIQUE KEY uq_module_code (filiere_id, code),
  UNIQUE KEY uq_module_cle (id, filiere_id),
  CONSTRAINT fk_module_filiere FOREIGN KEY (filiere_id) REFERENCES filiere (id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. SALLES
-- ---------------------------------------------------------------------
CREATE TABLE type_salle (
  id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  code    VARCHAR(10) NOT NULL,
  libelle VARCHAR(60) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_type_salle_code (code)
) ENGINE=InnoDB;

CREATE TABLE salle (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nom           VARCHAR(30) NOT NULL COMMENT 'Ex. SP1, SC3, LABO1',
  type_salle_id INT UNSIGNED NOT NULL,
  capacite      SMALLINT UNSIGNED NULL COMMENT 'À renseigner : absente des fichiers sources',
  actif         TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uq_salle_nom (nom),
  CONSTRAINT fk_salle_type FOREIGN KEY (type_salle_id) REFERENCES type_salle (id)
) ENGINE=InnoDB;

CREATE TABLE module_type_salle (
  module_id     INT UNSIGNED NOT NULL,
  type_salle_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (module_id, type_salle_id),
  CONSTRAINT fk_mts_module FOREIGN KEY (module_id) REFERENCES module (id) ON DELETE CASCADE,
  CONSTRAINT fk_mts_type FOREIGN KEY (type_salle_id) REFERENCES type_salle (id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. UTILISATEURS ET PROFESSEURS
-- ---------------------------------------------------------------------
CREATE TABLE utilisateur (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  identifiant   VARCHAR(50) NOT NULL,
  email         VARCHAR(120) NULL,
  mot_de_passe  VARCHAR(255) NOT NULL COMMENT 'Mot de passe haché, jamais en clair',
  nom           VARCHAR(80) NOT NULL,
  prenom        VARCHAR(80) NOT NULL,
  role          ENUM('admin','professeur','stagiaire') NOT NULL,
  groupe_id     INT UNSIGNED NULL COMMENT 'Groupe du stagiaire (rôle stagiaire uniquement)',
  actif         TINYINT(1) NOT NULL DEFAULT 1,
  date_creation DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_utilisateur_identifiant (identifiant),
  UNIQUE KEY uq_utilisateur_email (email),
  CONSTRAINT fk_utilisateur_groupe FOREIGN KEY (groupe_id) REFERENCES groupe (id),
  CONSTRAINT ck_utilisateur_groupe CHECK (groupe_id IS NULL OR role = 'stagiaire')
) ENGINE=InnoDB;

CREATE TABLE professeur (
  id                 INT UNSIGNED NOT NULL AUTO_INCREMENT,
  matricule          VARCHAR(20) NOT NULL COMMENT 'Mle du fichier source',
  nom_complet        VARCHAR(120) NOT NULL,
  utilisateur_id     INT UNSIGNED NULL COMMENT 'Compte de connexion (peut être créé plus tard)',
  statut             ENUM('permanent','vacataire') NULL COMMENT 'Absent des fichiers sources',
  heures_max_semaine DECIMAL(4,1) NULL COMMENT 'À confirmer',
  taux_presence      DECIMAL(5,2) NOT NULL DEFAULT 100.00 COMMENT 'En pourcentage',
  actif              TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uq_professeur_matricule (matricule),
  UNIQUE KEY uq_professeur_utilisateur (utilisateur_id),
  CONSTRAINT fk_professeur_utilisateur FOREIGN KEY (utilisateur_id) REFERENCES utilisateur (id),
  CONSTRAINT ck_professeur_presence CHECK (taux_presence BETWEEN 0 AND 100),
  CONSTRAINT ck_professeur_heures CHECK (heures_max_semaine IS NULL OR heures_max_semaine > 0)
) ENGINE=InnoDB;

CREATE TABLE professeur_module (
  professeur_id INT UNSIGNED NOT NULL,
  module_id     INT UNSIGNED NOT NULL,
  PRIMARY KEY (professeur_id, module_id),
  CONSTRAINT fk_pm_professeur FOREIGN KEY (professeur_id) REFERENCES professeur (id) ON DELETE CASCADE,
  CONSTRAINT fk_pm_module FOREIGN KEY (module_id) REFERENCES module (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE disponibilite (
  professeur_id INT UNSIGNED NOT NULL,
  creneau_id    TINYINT UNSIGNED NOT NULL,
  etat          ENUM('disponible','bloque','prefere') NOT NULL DEFAULT 'disponible' COMMENT 'Sans ligne = disponible',
  PRIMARY KEY (professeur_id, creneau_id),
  CONSTRAINT fk_dispo_professeur FOREIGN KEY (professeur_id) REFERENCES professeur (id) ON DELETE CASCADE,
  CONSTRAINT fk_dispo_creneau FOREIGN KEY (creneau_id) REFERENCES creneau (id)
) ENGINE=InnoDB;

CREATE TABLE absence_professeur (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  professeur_id     INT UNSIGNED NOT NULL,
  semaine_debut_id  INT UNSIGNED NOT NULL,
  semaine_fin_id    INT UNSIGNED NOT NULL,
  motif             VARCHAR(200) NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_abs_professeur FOREIGN KEY (professeur_id) REFERENCES professeur (id) ON DELETE CASCADE,
  CONSTRAINT fk_abs_debut FOREIGN KEY (semaine_debut_id) REFERENCES semaine (id),
  CONSTRAINT fk_abs_fin FOREIGN KEY (semaine_fin_id) REFERENCES semaine (id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. UNITÉS D'ENSEIGNEMENT (un module enseigné à un groupe, ou à deux groupes fusionnés)
-- ---------------------------------------------------------------------
CREATE TABLE unite_enseignement (
  id                     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  annee_scolaire_id      INT UNSIGNED NOT NULL,
  module_id              INT UNSIGNED NOT NULL,
  filiere_id             INT UNSIGNED NOT NULL COMMENT 'Redondant avec module : sert aux clés composites',
  code_fusion            VARCHAR(20) NULL COMMENT 'Code Fusion du fichier source ; NULL si pas de fusion (code 0)',
  cle_source             VARCHAR(120) NOT NULL COMMENT 'Clé de rapprochement avec le fichier source',
  nb_cc                  TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Nombre de contrôles continus',
  efm_planifie           TINYINT(1) NOT NULL DEFAULT 0,
  efm_valide             TINYINT(1) NOT NULL DEFAULT 0,
  h_realisees_presentiel DECIMAL(6,1) NOT NULL DEFAULT 0,
  h_realisees_synchrone  DECIMAL(6,1) NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_unite_source (annee_scolaire_id, cle_source),
  UNIQUE KEY uq_unite_annee (id, annee_scolaire_id),
  UNIQUE KEY uq_unite_cle (id, annee_scolaire_id, module_id, filiere_id),
  CONSTRAINT fk_unite_annee FOREIGN KEY (annee_scolaire_id) REFERENCES annee_scolaire (id),
  CONSTRAINT fk_unite_module FOREIGN KEY (module_id, filiere_id) REFERENCES module (id, filiere_id),
  CONSTRAINT ck_unite_realisees CHECK (h_realisees_presentiel >= 0 AND h_realisees_synchrone >= 0)
) ENGINE=InnoDB;

CREATE TABLE unite_groupe (
  unite_id          INT UNSIGNED NOT NULL,
  groupe_id         INT UNSIGNED NOT NULL,
  annee_scolaire_id INT UNSIGNED NOT NULL,
  module_id         INT UNSIGNED NOT NULL,
  filiere_id        INT UNSIGNED NOT NULL,
  moyenne_absence   DECIMAL(4,1) NULL,
  PRIMARY KEY (unite_id, groupe_id),
  -- un groupe suit un module au plus une fois par année scolaire
  UNIQUE KEY uq_unite_groupe_module (groupe_id, annee_scolaire_id, module_id),
  CONSTRAINT fk_ug_unite FOREIGN KEY (unite_id, annee_scolaire_id, module_id, filiere_id)
    REFERENCES unite_enseignement (id, annee_scolaire_id, module_id, filiere_id) ON DELETE CASCADE,
  -- le groupe doit être de la même année et de la même filière que le module
  CONSTRAINT fk_ug_groupe FOREIGN KEY (groupe_id, annee_scolaire_id, filiere_id)
    REFERENCES groupe (id, annee_scolaire_id, filiere_id)
) ENGINE=InnoDB;

CREATE TABLE volume_horaire (
  unite_id          INT UNSIGNED NOT NULL,
  semestre_id       INT UNSIGNED NOT NULL,
  annee_scolaire_id INT UNSIGNED NOT NULL,
  h_presentiel      DECIMAL(6,1) NOT NULL DEFAULT 0,
  h_synchrone       DECIMAL(6,1) NOT NULL DEFAULT 0,
  h_asynchrone      DECIMAL(6,1) NOT NULL DEFAULT 0 COMMENT 'Hors emploi du temps, compte pour le taux de réalisation',
  PRIMARY KEY (unite_id, semestre_id),
  CONSTRAINT fk_vh_unite FOREIGN KEY (unite_id, annee_scolaire_id)
    REFERENCES unite_enseignement (id, annee_scolaire_id) ON DELETE CASCADE,
  CONSTRAINT fk_vh_semestre FOREIGN KEY (semestre_id, annee_scolaire_id)
    REFERENCES semestre (id, annee_scolaire_id),
  CONSTRAINT ck_vh_positif CHECK (h_presentiel >= 0 AND h_synchrone >= 0 AND h_asynchrone >= 0)
) ENGINE=InnoDB;

CREATE TABLE unite_professeur (
  unite_id      INT UNSIGNED NOT NULL,
  professeur_id INT UNSIGNED NOT NULL,
  mode          ENUM('presentiel','synchrone') NOT NULL,
  PRIMARY KEY (unite_id, professeur_id, mode),
  CONSTRAINT fk_up_unite FOREIGN KEY (unite_id) REFERENCES unite_enseignement (id) ON DELETE CASCADE,
  CONSTRAINT fk_up_professeur FOREIGN KEY (professeur_id) REFERENCES professeur (id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. PLANIFICATION
-- ---------------------------------------------------------------------
CREATE TABLE passage (
  id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  unite_id         INT UNSIGNED NOT NULL,
  semestre_id      INT UNSIGNED NOT NULL,
  semaine_debut_id INT UNSIGNED NOT NULL,
  semaine_fin_id   INT UNSIGNED NOT NULL,
  intensite_h      DECIMAL(3,1) NOT NULL DEFAULT 5.0 COMMENT 'Heures par semaine',
  statut           ENUM('prevu','en_cours','termine') NOT NULL DEFAULT 'prevu',
  PRIMARY KEY (id),
  UNIQUE KEY uq_passage (unite_id, semestre_id),
  CONSTRAINT fk_passage_unite FOREIGN KEY (unite_id) REFERENCES unite_enseignement (id) ON DELETE CASCADE,
  CONSTRAINT fk_passage_semestre FOREIGN KEY (semestre_id) REFERENCES semestre (id),
  CONSTRAINT fk_passage_debut FOREIGN KEY (semaine_debut_id) REFERENCES semaine (id),
  CONSTRAINT fk_passage_fin FOREIGN KEY (semaine_fin_id) REFERENCES semaine (id),
  CONSTRAINT ck_passage_intensite CHECK (intensite_h > 0)
) ENGINE=InnoDB;

CREATE TABLE tache_generation (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  semaine_id   INT UNSIGNED NOT NULL,
  type         ENUM('passages','semaine') NOT NULL DEFAULT 'semaine',
  statut       ENUM('en_attente','en_cours','terminee','echec') NOT NULL DEFAULT 'en_attente',
  lance_par    INT UNSIGNED NULL,
  debut        DATETIME NULL,
  fin          DATETIME NULL,
  duree_s      INT UNSIGNED NULL,
  resume       TEXT NULL COMMENT 'Résumé du résultat (JSON) : heures par groupe, heures creuses, conflits',
  date_creation DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_tache_semaine FOREIGN KEY (semaine_id) REFERENCES semaine (id),
  CONSTRAINT fk_tache_utilisateur FOREIGN KEY (lance_par) REFERENCES utilisateur (id)
) ENGINE=InnoDB;

-- Une ligne = une séance de 2,5 h. Un bloc de 5 h = deux lignes qui partagent le même bloc_no.
CREATE TABLE seance (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  unite_id          INT UNSIGNED NOT NULL,
  semaine_id        INT UNSIGNED NOT NULL,
  creneau_id        TINYINT UNSIGNED NOT NULL,
  salle_id          INT UNSIGNED NULL COMMENT 'NULL pour une séance à distance',
  mode              ENUM('presentiel','distance') NOT NULL DEFAULT 'presentiel',
  nature            ENUM('bloc','simple','examen') NOT NULL,
  bloc_no           INT UNSIGNED NULL COMMENT 'Même numéro pour les deux séances d''un bloc de 5 h',
  statut            ENUM('brouillon','valide') NOT NULL DEFAULT 'brouillon',
  verrouillee       TINYINT(1) NOT NULL DEFAULT 0,
  tache_id          INT UNSIGNED NULL,
  date_creation     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  date_modification DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  -- cibles des clés composites de seance_groupe et seance_professeur
  UNIQUE KEY uq_seance_cle (id, semaine_id, creneau_id),
  -- une unité d'enseignement n'a qu'une séance par créneau
  UNIQUE KEY uq_seance_unite (unite_id, semaine_id, creneau_id),
  -- une salle ne reçoit qu'une séance par créneau (plusieurs NULL autorisés : séances à distance)
  UNIQUE KEY uq_seance_salle (salle_id, semaine_id, creneau_id),
  CONSTRAINT fk_seance_unite FOREIGN KEY (unite_id) REFERENCES unite_enseignement (id),
  CONSTRAINT fk_seance_semaine FOREIGN KEY (semaine_id) REFERENCES semaine (id),
  CONSTRAINT fk_seance_creneau FOREIGN KEY (creneau_id) REFERENCES creneau (id),
  CONSTRAINT fk_seance_salle FOREIGN KEY (salle_id) REFERENCES salle (id),
  CONSTRAINT fk_seance_tache FOREIGN KEY (tache_id) REFERENCES tache_generation (id) ON DELETE SET NULL,
  CONSTRAINT ck_seance_salle_mode CHECK ((mode = 'presentiel' AND salle_id IS NOT NULL) OR (mode = 'distance' AND salle_id IS NULL)),
  CONSTRAINT ck_seance_bloc CHECK ((nature = 'bloc' AND bloc_no IS NOT NULL) OR (nature <> 'bloc' AND bloc_no IS NULL))
) ENGINE=InnoDB;

-- Les groupes d'une séance (1 ou 2 si fusion). Semaine et créneau sont recopiés pour que
-- la base interdise à un groupe d'avoir deux séances en même temps.
CREATE TABLE seance_groupe (
  seance_id  BIGINT UNSIGNED NOT NULL,
  semaine_id INT UNSIGNED NOT NULL,
  creneau_id TINYINT UNSIGNED NOT NULL,
  groupe_id  INT UNSIGNED NOT NULL,
  PRIMARY KEY (seance_id, groupe_id),
  UNIQUE KEY uq_sg_groupe_creneau (groupe_id, semaine_id, creneau_id),
  CONSTRAINT fk_sg_seance FOREIGN KEY (seance_id, semaine_id, creneau_id)
    REFERENCES seance (id, semaine_id, creneau_id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_sg_groupe FOREIGN KEY (groupe_id) REFERENCES groupe (id)
) ENGINE=InnoDB;

-- Les professeurs d'une séance (1 ou plusieurs : cas des deux formateurs dans la même salle).
CREATE TABLE seance_professeur (
  seance_id     BIGINT UNSIGNED NOT NULL,
  semaine_id    INT UNSIGNED NOT NULL,
  creneau_id    TINYINT UNSIGNED NOT NULL,
  professeur_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (seance_id, professeur_id),
  UNIQUE KEY uq_sp_professeur_creneau (professeur_id, semaine_id, creneau_id),
  CONSTRAINT fk_sp_seance FOREIGN KEY (seance_id, semaine_id, creneau_id)
    REFERENCES seance (id, semaine_id, creneau_id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_sp_professeur FOREIGN KEY (professeur_id) REFERENCES professeur (id)
) ENGINE=InnoDB;

CREATE TABLE journal (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  utilisateur_id INT UNSIGNED NULL,
  action         VARCHAR(40) NOT NULL COMMENT 'creation, modification, suppression, validation, generation, import',
  objet_type     VARCHAR(40) NOT NULL,
  objet_id       BIGINT UNSIGNED NULL,
  detail         TEXT NULL,
  date_action    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_journal_date (date_action),
  CONSTRAINT fk_journal_utilisateur FOREIGN KEY (utilisateur_id) REFERENCES utilisateur (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 7. INDEX DE CONSULTATION
-- ---------------------------------------------------------------------
CREATE INDEX ix_seance_semaine ON seance (semaine_id, statut);
CREATE INDEX ix_unite_module ON unite_enseignement (module_id);
CREATE INDEX ix_groupe_filiere ON groupe (filiere_id);

-- ---------------------------------------------------------------------
-- 8. DONNÉES DE RÉFÉRENCE
-- ---------------------------------------------------------------------
INSERT INTO type_salle (code, libelle) VALUES
  ('SC',    'Salle de cours'),
  ('SP',    'Salle spécialisée'),
  ('LABO',  'Laboratoire'),
  ('SEM',   'Salle de séminaire'),
  ('AUTRE', 'Autre salle');

-- 6 jours x 4 séances de 2,5 h. Horaires repris du fichier d'exemple (à confirmer).
INSERT INTO creneau (jour, numero_seance, heure_debut, heure_fin, duree_h)
SELECT j.n, s.n, s.debut, s.fin, 2.5
FROM (SELECT 1 AS n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6) j
CROSS JOIN (
  SELECT 1 AS n, TIME('08:30:00') AS debut, TIME('10:30:00') AS fin
  UNION ALL SELECT 2, TIME('10:30:00'), TIME('13:00:00')
  UNION ALL SELECT 3, TIME('13:30:00'), TIME('16:00:00')
  UNION ALL SELECT 4, TIME('16:00:00'), TIME('18:30:00')
) s;

-- Salles du fichier d'exemple (capacité à renseigner)
INSERT INTO salle (nom, type_salle_id)
SELECT n.nom, t.id FROM (
  SELECT 'SP1' AS nom, 'SP' AS code UNION ALL SELECT 'SP2','SP' UNION ALL SELECT 'SP3','SP' UNION ALL SELECT 'SP4','SP'
  UNION ALL SELECT 'SP5','SP' UNION ALL SELECT 'SP6','SP' UNION ALL SELECT 'SP7','SP' UNION ALL SELECT 'SP8','SP' UNION ALL SELECT 'SP9','SP'
  UNION ALL SELECT 'SC1','SC' UNION ALL SELECT 'SC2','SC' UNION ALL SELECT 'SC3','SC' UNION ALL SELECT 'SC4','SC' UNION ALL SELECT 'SC5','SC'
  UNION ALL SELECT 'SC6','SC' UNION ALL SELECT 'SC7','SC' UNION ALL SELECT 'SC8','SC' UNION ALL SELECT 'SC9','SC' UNION ALL SELECT 'SC10','SC'
  UNION ALL SELECT 'LABO1','LABO' UNION ALL SELECT 'LABO2','LABO' UNION ALL SELECT 'SEM1','SEM'
) n JOIN type_salle t ON t.code = n.code;

-- ---------------------------------------------------------------------
-- 9. VUES
-- ---------------------------------------------------------------------
-- Heures de séances par groupe et par semaine
CREATE VIEW v_heures_groupe_semaine AS
SELECT sg.groupe_id, g.code AS groupe, s.semaine_id, SUM(c.duree_h) AS heures
FROM seance_groupe sg
JOIN seance s ON s.id = sg.seance_id
JOIN creneau c ON c.id = s.creneau_id
JOIN groupe g ON g.id = sg.groupe_id
GROUP BY sg.groupe_id, g.code, s.semaine_id;

-- Taux d'occupation des salles par semaine (capacité = somme des durées de tous les créneaux = 60 h)
CREATE VIEW v_occupation_salle_semaine AS
SELECT s.semaine_id, sa.id AS salle_id, sa.nom AS salle, SUM(c.duree_h) AS heures_utilisees,
       ROUND(100 * SUM(c.duree_h) / (SELECT SUM(duree_h) FROM creneau), 1) AS taux_occupation_pct
FROM seance s
JOIN salle sa ON sa.id = s.salle_id
JOIN creneau c ON c.id = s.creneau_id
GROUP BY s.semaine_id, sa.id, sa.nom;

-- Taux de réalisation de chaque unité d'enseignement (heures réalisées / heures prévues en présentiel et synchrone)
CREATE VIEW v_taux_realisation_unite AS
SELECT u.id AS unite_id, m.code AS code_module, m.intitule AS module,
       SUM(v.h_presentiel + v.h_synchrone) AS heures_prevues,
       u.h_realisees_presentiel + u.h_realisees_synchrone AS heures_realisees,
       ROUND(100 * (u.h_realisees_presentiel + u.h_realisees_synchrone) / NULLIF(SUM(v.h_presentiel + v.h_synchrone), 0), 1) AS taux_realisation_pct
FROM unite_enseignement u
JOIN module m ON m.id = u.module_id
JOIN volume_horaire v ON v.unite_id = u.id
GROUP BY u.id, m.code, m.intitule, u.h_realisees_presentiel, u.h_realisees_synchrone;

SET FOREIGN_KEY_CHECKS = 1;
