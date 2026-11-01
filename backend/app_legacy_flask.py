from flask import Flask, request, jsonify
from flask_cors import CORS
import pymysql
from pymysql.cursors import DictCursor
from datetime import date, timedelta, datetime
import traceback

app = Flask(__name__)
CORS(app)

# ─── MySQL Connection Pool ────────────────────────────────────────────────────
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '',
    'database': 'emplois_du_temps',
    'charset': 'utf8mb4',
    'cursorclass': DictCursor,
}


def get_db():
    """Crée une connexion MySQL."""
    return pymysql.connect(**DB_CONFIG)


def json_serial(obj):
    """Sérialise les types date/datetime pour JSON."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return str(obj)
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Type {type(obj)} non sérialisable")


def row_to_json(row):
    if not row:
        return None
    clean = {}
    for k, v in row.items():
        if isinstance(v, (date, datetime)):
            clean[k] = v.isoformat()
        elif isinstance(v, timedelta):
            total_seconds = int(v.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            clean[k] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            clean[k] = v
    return clean


def rows_to_json(rows):
    """Convertit les lignes MySQL (avec dates/timedelta) en objets JSON-safe."""
    if isinstance(rows, dict):
        return row_to_json(rows)
    if rows is None:
        return []
    return [row_to_json(r) for r in rows if r]


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
        conn.close()
        return jsonify({'status': 'ok', 'db': 'emplois_du_temps'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── Semaines ─────────────────────────────────────────────────────────────────
@app.route('/api/semaines', methods=['GET'])
def get_semaines():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('''
                SELECT sw.*, a.libelle AS annee_libelle, sm.numero AS semestre_numero,
                       (SELECT COUNT(*) FROM seance s WHERE s.semaine_id = sw.id) AS nb_seances
                FROM semaine sw
                JOIN annee_scolaire a ON a.id = sw.annee_scolaire_id
                LEFT JOIN semestre sm ON sm.id = sw.semestre_id
                ORDER BY sw.numero ASC
            ''')
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows_to_json(rows))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Initialiser les semaines (si la table est vide) ─────────────────────────
@app.route('/api/init-semaines', methods=['POST'])
def init_semaines():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS cnt FROM semaine')
            cnt = cur.fetchone()['cnt']
            if cnt > 0:
                return jsonify({'message': f'{cnt} semaines déjà présentes', 'created': 0})

            cur.execute("SELECT * FROM annee_scolaire WHERE annee_debut = 2026")
            annee = cur.fetchone()
            if not annee:
                return jsonify({'error': 'Année scolaire 2026 non trouvée'}), 404

            # Update dates for annee and semestres
            cur.execute("UPDATE annee_scolaire SET date_debut='2026-09-14', date_fin='2027-06-26' WHERE annee_debut=2026")
            cur.execute("UPDATE semestre SET date_debut='2026-09-14', date_fin='2027-01-02' WHERE numero=1 AND annee_scolaire_id=%s", (annee['id'],))
            cur.execute("UPDATE semestre SET date_debut='2027-01-12', date_fin='2027-06-26' WHERE numero=2 AND annee_scolaire_id=%s", (annee['id'],))

            cur.execute("SELECT * FROM semestre WHERE numero=1 AND annee_scolaire_id=%s", (annee['id'],))
            s1 = cur.fetchone()
            cur.execute("SELECT * FROM semestre WHERE numero=2 AND annee_scolaire_id=%s", (annee['id'],))
            s2 = cur.fetchone()

            created = 0
            # S1: 16 weeks from 2026-09-14
            for i in range(16):
                debut = date(2026, 9, 14) + timedelta(days=i * 7)
                fin = debut + timedelta(days=5)
                cur.execute(
                    'INSERT INTO semaine (annee_scolaire_id, semestre_id, numero, date_debut, date_fin, nature) VALUES (%s,%s,%s,%s,%s,%s)',
                    (annee['id'], s1['id'], i + 1, debut.isoformat(), fin.isoformat(), 'cours')
                )
                created += 1

            # S2: 16 weeks from 2027-01-12
            for i in range(16):
                debut = date(2027, 1, 12) + timedelta(days=i * 7)
                fin = debut + timedelta(days=5)
                cur.execute(
                    'INSERT INTO semaine (annee_scolaire_id, semestre_id, numero, date_debut, date_fin, nature) VALUES (%s,%s,%s,%s,%s,%s)',
                    (annee['id'], s2['id'], i + 17, debut.isoformat(), fin.isoformat(), 'cours')
                )
                created += 1

        conn.commit()
        return jsonify({'message': f'{created} semaines créées (S1+S2 2026-2027)', 'created': created})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ─── Créneaux ─────────────────────────────────────────────────────────────────
@app.route('/api/creneaux', methods=['GET'])
def get_creneaux():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM creneau ORDER BY jour, numero_seance')
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows_to_json(rows))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Groupes ──────────────────────────────────────────────────────────────────
@app.route('/api/groupes', methods=['GET'])
def get_groupes():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('''
                SELECT g.*, f.intitule AS filiere_nom, f.code AS filiere_code
                FROM groupe g
                JOIN filiere f ON f.id = g.filiere_id
                JOIN annee_scolaire a ON a.id = g.annee_scolaire_id
                WHERE g.actif = 1
                ORDER BY f.code, g.annee_etude, g.code
            ''')
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows_to_json(rows))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/groupes', methods=['POST'])
def add_groupe():
    data = request.json or {}
    code = (data.get('code') or '').strip().upper()
    filiere_id = data.get('filiere_id')
    try:
        annee_etude = int(data.get('annee_etude') or 1)
    except (ValueError, TypeError):
        annee_etude = 1
    try:
        effectif = int(data.get('effectif') or 25)
    except (ValueError, TypeError):
        effectif = 25
    regime = (data.get('regime') or 'CDJ').strip()
    mode_formation = (data.get('mode_formation') or 'Résidentiel').strip()

    if not code:
        return jsonify({'error': 'Le code du groupe est obligatoire (ex: DEV105)'}), 400
    if not filiere_id:
        return jsonify({'error': 'La filière est obligatoire'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM annee_scolaire ORDER BY annee_debut DESC LIMIT 1')
            annee = cur.fetchone()
            annee_id = annee['id'] if annee else 2

            cur.execute('SELECT id, actif FROM groupe WHERE annee_scolaire_id = %s AND code = %s', (annee_id, code))
            existing = cur.fetchone()
            if existing:
                if existing['actif'] == 0:
                    cur.execute('''
                        UPDATE groupe 
                        SET filiere_id=%s, annee_etude=%s, effectif=%s, regime=%s, mode_formation=%s, actif=1
                        WHERE id=%s
                    ''', (filiere_id, annee_etude, effectif, regime, mode_formation, existing['id']))
                    groupe_id = existing['id']
                else:
                    return jsonify({'error': f'Un groupe avec le code "{code}" existe déjà'}), 409
            else:
                cur.execute('''
                    INSERT INTO groupe (annee_scolaire_id, code, filiere_id, annee_etude, effectif, regime, mode_formation, actif)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                ''', (annee_id, code, filiere_id, annee_etude, effectif, regime, mode_formation))
                groupe_id = cur.lastrowid

            cur.execute('''
                SELECT g.*, f.intitule AS filiere_nom, f.code AS filiere_code
                FROM groupe g
                JOIN filiere f ON f.id = g.filiere_id
                WHERE g.id = %s
            ''', (groupe_id,))
            created_group = cur.fetchone()

        conn.commit()
        return jsonify(rows_to_json(created_group)), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/groupes/<int:groupe_id>', methods=['PUT'])
def update_groupe(groupe_id):
    data = request.json or {}
    code = (data.get('code') or '').strip().upper()
    filiere_id = data.get('filiere_id')
    try:
        annee_etude = int(data.get('annee_etude') or 1)
    except (ValueError, TypeError):
        annee_etude = 1
    try:
        effectif = int(data.get('effectif') or 25)
    except (ValueError, TypeError):
        effectif = 25
    regime = (data.get('regime') or 'CDJ').strip()
    mode_formation = (data.get('mode_formation') or 'Résidentiel').strip()

    if not code:
        return jsonify({'error': 'Le code du groupe est obligatoire'}), 400
    if not filiere_id:
        return jsonify({'error': 'La filière est obligatoire'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM groupe WHERE id = %s', (groupe_id,))
            grp = cur.fetchone()
            if not grp:
                return jsonify({'error': 'Groupe introuvable'}), 404

            cur.execute('SELECT id FROM groupe WHERE annee_scolaire_id = %s AND code = %s AND id != %s', (grp['annee_scolaire_id'], code, groupe_id))
            if cur.fetchone():
                return jsonify({'error': f'Un autre groupe avec le code "{code}" existe déjà'}), 409

            cur.execute('''
                UPDATE groupe
                SET code=%s, filiere_id=%s, annee_etude=%s, effectif=%s, regime=%s, mode_formation=%s
                WHERE id=%s
            ''', (code, filiere_id, annee_etude, effectif, regime, mode_formation, groupe_id))

            cur.execute('''
                SELECT g.*, f.intitule AS filiere_nom, f.code AS filiere_code
                FROM groupe g
                JOIN filiere f ON f.id = g.filiere_id
                WHERE g.id = %s
            ''', (groupe_id,))
            updated_group = cur.fetchone()

        conn.commit()
        return jsonify(rows_to_json(updated_group))
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/groupes/<int:groupe_id>', methods=['DELETE'])
def delete_groupe(groupe_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM groupe WHERE id = %s', (groupe_id,))
            grp = cur.fetchone()
            if not grp:
                return jsonify({'error': 'Groupe introuvable'}), 404

            cur.execute('SELECT COUNT(*) AS cnt FROM seance_groupe WHERE groupe_id = %s', (groupe_id,))
            seances_cnt = cur.fetchone()['cnt']

            if seances_cnt > 0:
                cur.execute('UPDATE groupe SET actif = 0 WHERE id = %s', (groupe_id,))
                conn.commit()
                return jsonify({
                    'message': f'Groupe désactivé avec succès ({seances_cnt} séance(s) liée(s) archivée(s)).',
                    'soft_deleted': True
                })
            else:
                try:
                    cur.execute('DELETE FROM unite_groupe WHERE groupe_id = %s', (groupe_id,))
                    cur.execute('DELETE FROM groupe WHERE id = %s', (groupe_id,))
                    conn.commit()
                    return jsonify({'message': 'Groupe supprimé avec succès.', 'soft_deleted': False})
                except Exception:
                    conn.rollback()
                    cur.execute('UPDATE groupe SET actif = 0 WHERE id = %s', (groupe_id,))
                    conn.commit()
                    return jsonify({'message': 'Groupe désactivé avec succès.', 'soft_deleted': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/professeurs', methods=['GET'])
def get_professeurs():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('''
                SELECT p.*, u.email
                FROM professeur p
                LEFT JOIN utilisateur u ON u.id = p.utilisateur_id
                WHERE p.actif = 1
                ORDER BY p.nom_complet
            ''')
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows_to_json(rows))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/professeurs', methods=['POST'])
def add_professeur():
    data = request.json or {}
    nom_complet = (data.get('nom_complet') or '').strip()
    matricule = (data.get('matricule') or '').strip()
    email = (data.get('email') or '').strip()
    statut = (data.get('statut') or 'permanent').strip()
    try:
        taux_presence = float(data.get('taux_presence') if data.get('taux_presence') is not None else 100.0)
    except (ValueError, TypeError):
        taux_presence = 100.0
    try:
        heures_max = float(data.get('heures_max_semaine')) if data.get('heures_max_semaine') else None
    except (ValueError, TypeError):
        heures_max = None

    if not nom_complet:
        return jsonify({'error': 'Le nom complet du formateur est obligatoire'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            if not matricule:
                cur.execute('SELECT MAX(CAST(matricule AS UNSIGNED)) AS max_mle FROM professeur WHERE matricule REGEXP "^[0-9]+$"')
                row = cur.fetchone()
                max_mle = (row['max_mle'] or 20000) + 1
                matricule = str(max_mle)

            cur.execute('SELECT id, actif FROM professeur WHERE matricule = %s', (matricule,))
            existing = cur.fetchone()
            if existing:
                if existing['actif'] == 0:
                    cur.execute('''
                        UPDATE professeur
                        SET nom_complet=%s, statut=%s, taux_presence=%s, heures_max_semaine=%s, actif=1
                        WHERE id=%s
                    ''', (nom_complet, statut, taux_presence, heures_max, existing['id']))
                    prof_id = existing['id']
                else:
                    return jsonify({'error': f'Un formateur avec le matricule "{matricule}" existe déjà'}), 409
            else:
                cur.execute('''
                    INSERT INTO professeur (matricule, nom_complet, statut, taux_presence, heures_max_semaine, actif)
                    VALUES (%s, %s, %s, %s, %s, 1)
                ''', (matricule, nom_complet, statut, taux_presence, heures_max))
                prof_id = cur.lastrowid

            if email:
                cur.execute('SELECT utilisateur_id FROM professeur WHERE id = %s', (prof_id,))
                curr_user = cur.fetchone()
                if curr_user and curr_user['utilisateur_id']:
                    cur.execute('UPDATE utilisateur SET email=%s WHERE id=%s', (email, curr_user['utilisateur_id']))
                else:
                    identifiant = f"prof_{matricule}"
                    cur.execute('''
                        INSERT INTO utilisateur (identifiant, email, mot_de_passe, nom, prenom, role, actif)
                        VALUES (%s, %s, %s, %s, %s, 'professeur', 1)
                        ON DUPLICATE KEY UPDATE email=VALUES(email)
                    ''', (identifiant, email, 'temp_hash', nom_complet, ''))
                    user_id = cur.lastrowid
                    cur.execute('UPDATE professeur SET utilisateur_id=%s WHERE id=%s', (user_id, prof_id))

            cur.execute('''
                SELECT p.*, u.email
                FROM professeur p
                LEFT JOIN utilisateur u ON u.id = p.utilisateur_id
                WHERE p.id = %s
            ''', (prof_id,))
            created_prof = cur.fetchone()

        conn.commit()
        return jsonify(rows_to_json(created_prof)), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/professeurs/<int:prof_id>', methods=['PUT'])
def update_professeur(prof_id):
    data = request.json or {}
    nom_complet = (data.get('nom_complet') or '').strip()
    matricule = (data.get('matricule') or '').strip()
    email = (data.get('email') or '').strip()
    statut = (data.get('statut') or 'permanent').strip()
    try:
        taux_presence = float(data.get('taux_presence') if data.get('taux_presence') is not None else 100.0)
    except (ValueError, TypeError):
        taux_presence = 100.0
    try:
        heures_max = float(data.get('heures_max_semaine')) if data.get('heures_max_semaine') else None
    except (ValueError, TypeError):
        heures_max = None

    if not nom_complet:
        return jsonify({'error': 'Le nom complet du formateur est obligatoire'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM professeur WHERE id = %s', (prof_id,))
            prof = cur.fetchone()
            if not prof:
                return jsonify({'error': 'Formateur introuvable'}), 404

            if matricule and matricule != prof['matricule']:
                cur.execute('SELECT id FROM professeur WHERE matricule = %s AND id != %s', (matricule, prof_id))
                if cur.fetchone():
                    return jsonify({'error': f'Le matricule "{matricule}" est déjà utilisé'}), 409
            else:
                matricule = prof['matricule']

            cur.execute('''
                UPDATE professeur
                SET nom_complet=%s, matricule=%s, statut=%s, taux_presence=%s, heures_max_semaine=%s
                WHERE id=%s
            ''', (nom_complet, matricule, statut, taux_presence, heures_max, prof_id))

            if email:
                if prof['utilisateur_id']:
                    cur.execute('UPDATE utilisateur SET email=%s WHERE id=%s', (email, prof['utilisateur_id']))
                else:
                    identifiant = f"prof_{matricule}"
                    cur.execute('''
                        INSERT INTO utilisateur (identifiant, email, mot_de_passe, nom, prenom, role, actif)
                        VALUES (%s, %s, %s, %s, %s, 'professeur', 1)
                        ON DUPLICATE KEY UPDATE email=VALUES(email)
                    ''', (identifiant, email, 'temp_hash', nom_complet, ''))
                    user_id = cur.lastrowid
                    cur.execute('UPDATE professeur SET utilisateur_id=%s WHERE id=%s', (user_id, prof_id))

            cur.execute('''
                SELECT p.*, u.email
                FROM professeur p
                LEFT JOIN utilisateur u ON u.id = p.utilisateur_id
                WHERE p.id = %s
            ''', (prof_id,))
            updated_prof = cur.fetchone()

        conn.commit()
        return jsonify(rows_to_json(updated_prof))
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/professeurs/<int:prof_id>', methods=['DELETE'])
def delete_professeur(prof_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM professeur WHERE id = %s', (prof_id,))
            prof = cur.fetchone()
            if not prof:
                return jsonify({'error': 'Formateur introuvable'}), 404

            cur.execute('SELECT COUNT(*) AS cnt FROM seance_professeur WHERE professeur_id = %s', (prof_id,))
            seances_cnt = cur.fetchone()['cnt']

            if seances_cnt > 0:
                cur.execute('UPDATE professeur SET actif = 0 WHERE id = %s', (prof_id,))
                conn.commit()
                return jsonify({
                    'message': f'Formateur désactivé avec succès ({seances_cnt} séance(s) liée(s) archivée(s)).',
                    'soft_deleted': True
                })
            else:
                try:
                    cur.execute('DELETE FROM unite_professeur WHERE professeur_id = %s', (prof_id,))
                    cur.execute('DELETE FROM professeur WHERE id = %s', (prof_id,))
                    conn.commit()
                    return jsonify({'message': 'Formateur supprimé avec succès.', 'soft_deleted': False})
                except Exception:
                    conn.rollback()
                    cur.execute('UPDATE professeur SET actif = 0 WHERE id = %s', (prof_id,))
                    conn.commit()
                    return jsonify({'message': 'Formateur désactivé avec succès.', 'soft_deleted': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ─── Types de Salles ──────────────────────────────────────────────────────────
@app.route('/api/types-salles', methods=['GET'])
def get_types_salles():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM type_salle ORDER BY id')
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows_to_json(rows))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Salles ───────────────────────────────────────────────────────────────────
@app.route('/api/salles', methods=['GET'])
def get_salles():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('''
                SELECT s.*, t.libelle AS type_libelle, t.code AS type_code
                FROM salle s JOIN type_salle t ON t.id = s.type_salle_id
                WHERE s.actif = 1
                ORDER BY t.code, s.nom
            ''')
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows_to_json(rows))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/salles', methods=['POST'])
def add_salle():
    data = request.json or {}
    nom = (data.get('nom') or '').strip().upper()
    type_salle_id = data.get('type_salle_id')
    try:
        capacite = int(data.get('capacite') or 30)
    except (ValueError, TypeError):
        capacite = 30

    if not nom:
        return jsonify({'error': 'Le nom de la salle est obligatoire (ex: SC1, SP2)'}), 400
    if not type_salle_id:
        return jsonify({'error': 'Le type de salle est obligatoire'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, actif FROM salle WHERE nom = %s', (nom,))
            existing = cur.fetchone()
            if existing:
                if existing['actif'] == 0:
                    cur.execute('UPDATE salle SET type_salle_id=%s, capacite=%s, actif=1 WHERE id=%s', (type_salle_id, capacite, existing['id']))
                    salle_id = existing['id']
                else:
                    return jsonify({'error': f'Une salle avec le nom "{nom}" existe déjà'}), 409
            else:
                cur.execute('INSERT INTO salle (nom, type_salle_id, capacite, actif) VALUES (%s, %s, %s, 1)', (nom, type_salle_id, capacite))
                salle_id = cur.lastrowid

            cur.execute('''
                SELECT s.*, t.libelle AS type_libelle, t.code AS type_code
                FROM salle s JOIN type_salle t ON t.id = s.type_salle_id
                WHERE s.id = %s
            ''', (salle_id,))
            created_salle = cur.fetchone()

        conn.commit()
        return jsonify(rows_to_json(created_salle)), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/salles/<int:salle_id>', methods=['PUT'])
def update_salle(salle_id):
    data = request.json or {}
    nom = (data.get('nom') or '').strip().upper()
    type_salle_id = data.get('type_salle_id')
    try:
        capacite = int(data.get('capacite') or 30)
    except (ValueError, TypeError):
        capacite = 30

    if not nom:
        return jsonify({'error': 'Le nom de la salle est obligatoire'}), 400
    if not type_salle_id:
        return jsonify({'error': 'Le type de salle est obligatoire'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM salle WHERE id = %s', (salle_id,))
            sl = cur.fetchone()
            if not sl:
                return jsonify({'error': 'Salle introuvable'}), 404

            cur.execute('SELECT id FROM salle WHERE nom = %s AND id != %s', (nom, salle_id))
            if cur.fetchone():
                return jsonify({'error': f'Une autre salle nommée "{nom}" existe déjà'}), 409

            cur.execute('UPDATE salle SET nom=%s, type_salle_id=%s, capacite=%s WHERE id=%s', (nom, type_salle_id, capacite, salle_id))

            cur.execute('''
                SELECT s.*, t.libelle AS type_libelle, t.code AS type_code
                FROM salle s JOIN type_salle t ON t.id = s.type_salle_id
                WHERE s.id = %s
            ''', (salle_id,))
            updated_salle = cur.fetchone()

        conn.commit()
        return jsonify(rows_to_json(updated_salle))
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/salles/<int:salle_id>', methods=['DELETE'])
def delete_salle(salle_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM salle WHERE id = %s', (salle_id,))
            sl = cur.fetchone()
            if not sl:
                return jsonify({'error': 'Salle introuvable'}), 404

            cur.execute('SELECT COUNT(*) AS cnt FROM seance WHERE salle_id = %s', (salle_id,))
            seances_cnt = cur.fetchone()['cnt']

            if seances_cnt > 0:
                cur.execute('UPDATE salle SET actif = 0 WHERE id = %s', (salle_id,))
                conn.commit()
                return jsonify({
                    'message': f'Salle désactivée avec succès ({seances_cnt} séance(s) liée(s) archivée(s)).',
                    'soft_deleted': True
                })
            else:
                try:
                    cur.execute('DELETE FROM salle WHERE id = %s', (salle_id,))
                    conn.commit()
                    return jsonify({'message': 'Salle supprimée avec succès.', 'soft_deleted': False})
                except Exception:
                    conn.rollback()
                    cur.execute('UPDATE salle SET actif = 0 WHERE id = %s', (salle_id,))
                    conn.commit()
                    return jsonify({'message': 'Salle désactivée avec succès.', 'soft_deleted': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ─── Filières ─────────────────────────────────────────────────────────────────
@app.route('/api/filieres', methods=['GET'])
def get_filieres():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('''
                SELECT f.*, s.libelle AS secteur_nom
                FROM filiere f JOIN secteur s ON s.id = f.secteur_id
                ORDER BY f.code
            ''')
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows_to_json(rows))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Emploi du temps d'une semaine ────────────────────────────────────────────
@app.route('/api/emploi-du-temps/<int:semaine_id>', methods=['GET'])
def get_emploi_du_temps(semaine_id):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('''
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
                WHERE s.semaine_id = %s
                ORDER BY c.jour, c.numero_seance
            ''', (semaine_id,))
            seances = cur.fetchall()

            seance_ids = [s['id'] for s in seances]
            groupes = []
            profs = []

            if seance_ids:
                placeholders = ','.join(['%s'] * len(seance_ids))
                cur.execute(f'''
                    SELECT sg.seance_id, g.id AS groupe_id, g.code AS groupe_code, g.annee_etude
                    FROM seance_groupe sg JOIN groupe g ON g.id = sg.groupe_id
                    WHERE sg.seance_id IN ({placeholders})
                ''', seance_ids)
                groupes = cur.fetchall()

                cur.execute(f'''
                    SELECT sp.seance_id, p.id AS prof_id, p.nom_complet AS prof_nom, p.matricule
                    FROM seance_professeur sp JOIN professeur p ON p.id = sp.professeur_id
                    WHERE sp.seance_id IN ({placeholders})
                ''', seance_ids)
                profs = cur.fetchall()

        conn.close()

        result = []
        for s in rows_to_json(seances):
            s['groupes'] = [g for g in groupes if g['seance_id'] == s['id']]
            s['professeurs'] = [p for p in profs if p['seance_id'] == s['id']]
            result.append(s)

        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ─── Créer une séance ─────────────────────────────────────────────────────────
@app.route('/api/seances', methods=['POST'])
def creer_seance():
    data = request.get_json()
    unite_id = data.get('unite_id')
    semaine_id = data.get('semaine_id')
    creneau_id = data.get('creneau_id')
    salle_id = data.get('salle_id')
    mode = data.get('mode', 'presentiel')
    nature = data.get('nature', 'simple')
    groupe_ids = data.get('groupe_ids', [])
    professeur_ids = data.get('professeur_ids', [])

    conn = get_db()
    try:
        with conn.cursor() as cur:
            # Vérifier conflit de salle
            if salle_id:
                cur.execute('SELECT id FROM seance WHERE salle_id=%s AND semaine_id=%s AND creneau_id=%s',
                            (salle_id, semaine_id, creneau_id))
                if cur.fetchone():
                    return jsonify({'error': 'Conflit de salle'}), 409

            # Vérifier conflit de groupe
            for gid in groupe_ids:
                cur.execute('SELECT seance_id FROM seance_groupe WHERE groupe_id=%s AND semaine_id=%s AND creneau_id=%s',
                            (gid, semaine_id, creneau_id))
                if cur.fetchone():
                    return jsonify({'error': 'Conflit de groupe'}), 409

            # Vérifier conflit de formateur
            for pid in professeur_ids:
                cur.execute('SELECT seance_id FROM seance_professeur WHERE professeur_id=%s AND semaine_id=%s AND creneau_id=%s',
                            (pid, semaine_id, creneau_id))
                if cur.fetchone():
                    return jsonify({'error': 'Conflit de formateur'}), 409

            # Insérer la séance
            cur.execute(
                "INSERT INTO seance (unite_id,semaine_id,creneau_id,salle_id,mode,nature,statut) VALUES (%s,%s,%s,%s,%s,%s,'brouillon')",
                (unite_id, semaine_id, creneau_id, salle_id, mode, nature)
            )
            sid = cur.lastrowid

            for gid in groupe_ids:
                cur.execute('INSERT INTO seance_groupe(seance_id,semaine_id,creneau_id,groupe_id) VALUES(%s,%s,%s,%s)',
                            (sid, semaine_id, creneau_id, gid))
            for pid in professeur_ids:
                cur.execute('INSERT INTO seance_professeur(seance_id,semaine_id,creneau_id,professeur_id) VALUES(%s,%s,%s,%s)',
                            (sid, semaine_id, creneau_id, pid))

        conn.commit()
        return jsonify({'id': sid, 'message': 'Séance créée'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ─── Modifier une séance ──────────────────────────────────────────────────────
@app.route('/api/seances/<int:id>', methods=['PUT'])
def modifier_seance(id):
    data = request.get_json()
    creneau_id = data.get('creneau_id')
    salle_id = data.get('salle_id')
    statut = data.get('statut')
    verrouillee = data.get('verrouillee')
    unite_id = data.get('unite_id')
    mode = data.get('mode')
    professeur_id = data.get('professeur_id')

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM seance WHERE id=%s', (id,))
            s = cur.fetchone()
            if not s:
                return jsonify({'error': 'Séance introuvable'}), 404
            if s['verrouillee'] and verrouillee is None:
                return jsonify({'error': 'Séance verrouillée'}), 403

            nc = creneau_id or s['creneau_id']
            ns = salle_id if salle_id is not None else s['salle_id']
            nu = unite_id or s['unite_id']
            nm = mode or s['mode']

            # Vérifier conflit de salle
            if ns and ns != s['salle_id']:
                cur.execute('SELECT id FROM seance WHERE salle_id=%s AND semaine_id=%s AND creneau_id=%s AND id!=%s',
                            (ns, s['semaine_id'], nc, id))
                if cur.fetchone():
                    return jsonify({'error': 'Conflit de salle : salle déjà occupée'}), 409

            # MAJ créneaux dans les tables liées
            if nc != s['creneau_id']:
                cur.execute('UPDATE seance_groupe SET creneau_id=%s WHERE seance_id=%s', (nc, id))
                cur.execute('UPDATE seance_professeur SET creneau_id=%s WHERE seance_id=%s', (nc, id))

            # MAJ professeur
            if professeur_id is not None:
                cur.execute('DELETE FROM seance_professeur WHERE seance_id=%s', (id,))
                if professeur_id:
                    cur.execute(
                        'INSERT INTO seance_professeur (seance_id, semaine_id, creneau_id, professeur_id) VALUES (%s,%s,%s,%s)',
                        (id, s['semaine_id'], nc, professeur_id)
                    )

            cur.execute(
                'UPDATE seance SET unite_id=%s, creneau_id=%s, salle_id=%s, mode=%s, statut=%s, verrouillee=%s WHERE id=%s',
                (nu, nc, ns, nm, statut or s['statut'],
                 verrouillee if verrouillee is not None else s['verrouillee'], id)
            )

        conn.commit()
        return jsonify({'message': 'Séance mise à jour'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ─── Supprimer une séance ─────────────────────────────────────────────────────
@app.route('/api/seances/<int:id>', methods=['DELETE'])
def supprimer_seance(id):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('DELETE FROM seance WHERE id=%s AND verrouillee=0', (id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Séance supprimée'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Valider les séances d'une semaine ───────────────────────────────────────
@app.route('/api/semaines/<int:semaine_id>/valider', methods=['POST'])
def valider_semaine(semaine_id):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("UPDATE seance SET statut='valide' WHERE semaine_id=%s AND statut='brouillon'", (semaine_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Emploi du temps validé'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Générer automatiquement une semaine spécifique ───────────────────────────────────
@app.route('/api/generer/<int:semaine_id>', methods=['POST'])
def generer_semaine(semaine_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM semaine WHERE id = %s', (semaine_id,))
            semaine = cur.fetchone()
            if not semaine:
                return jsonify({'error': 'Semaine non trouvee'}), 404

            # Supprimer les seances brouillon non verrouillee
            cur.execute("DELETE FROM seance WHERE semaine_id=%s AND statut='brouillon' AND verrouillee=0", (semaine_id,))

            semestre_id = semaine['semestre_id']
            semaine_numero = semaine['numero'] or 1

            # ── 1. Unites du semestre avec volumes horaires ──
            # NOTE: volume_horaire PK is (unite_id, semestre_id) — no 'id' column
            cur.execute('''
                SELECT ue.id AS unite_id, ue.code_fusion,
                       m.id AS module_id, m.code AS module_code,
                       m.intitule AS module_intitule, m.type_module,
                       f.id AS filiere_id,
                       v.h_presentiel, v.h_synchrone,
                       v.semestre_id,
                       GROUP_CONCAT(DISTINCT g.id ORDER BY g.id) AS groupe_ids,
                       GROUP_CONCAT(DISTINCT g.code ORDER BY g.code) AS groupe_codes,
                       GROUP_CONCAT(DISTINCT p.id ORDER BY p.id) AS prof_ids,
                       GROUP_CONCAT(DISTINCT p.nom_complet ORDER BY p.nom_complet) AS prof_noms
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
            ''', (semestre_id,))
            unites_raw = cur.fetchall()

            # ── 2. Heures deja realisees par unite (hors semaine courante) ──
            cur.execute('''
                SELECT s.unite_id, SUM(c.duree_h) AS h_fait
                FROM seance s
                JOIN creneau c ON c.id = s.creneau_id
                JOIN semaine sw ON sw.id = s.semaine_id
                WHERE sw.semestre_id = %s
                  AND s.semaine_id != %s
                  AND (s.statut = 'valide' OR s.verrouillee = 1)
                GROUP BY s.unite_id
            ''', (semestre_id, semaine_id))
            heures_faites = {r['unite_id']: float(r['h_fait'] or 0) for r in cur.fetchall()}

            # ── 3. Nombre de semaines dans le semestre ──
            cur.execute('''
                SELECT COUNT(*) AS total_sem,
                       SUM(CASE WHEN numero >= %s THEN 1 ELSE 0 END) AS restantes
                FROM semaine WHERE semestre_id = %s
            ''', (semaine_numero, semestre_id))
            row_sem = cur.fetchone()
            semaines_total = max(1, int(row_sem['total_sem'] or 16))
            semaines_restantes = max(1, int(row_sem['restantes'] or 1))
            semaines_passees = semaines_total - semaines_restantes

            # ── 4. Creneaux et salles ──
            cur.execute('SELECT * FROM creneau ORDER BY jour, numero_seance')
            creneaux = cur.fetchall()

            cur.execute('''
                SELECT s.*, ts.code AS type_code
                FROM salle s JOIN type_salle ts ON ts.id = s.type_salle_id
                WHERE s.actif = 1 ORDER BY ts.code, s.capacite DESC
            ''')
            salles = cur.fetchall()

            # ── 5. Disponibilites bloquees des professeurs ──
            blocked_prof_creneaux = {}
            try:
                cur.execute('''
                    SELECT professeur_id, creneau_id
                    FROM indisponibilite_professeur
                    WHERE semaine_id = %s AND type = 'bloque'
                ''', (semaine_id,))
                for row in cur.fetchall():
                    blocked_prof_creneaux.setdefault(row['professeur_id'], set()).add(row['creneau_id'])
            except Exception:
                pass

            # ── 6. Heures formateurs cette semaine (verrouillee) ──
            cur.execute('''
                SELECT sp.professeur_id, SUM(c.duree_h) AS h_semaine
                FROM seance s
                JOIN seance_professeur sp ON sp.seance_id = s.id
                JOIN creneau c ON c.id = s.creneau_id
                WHERE s.semaine_id = %s AND s.verrouillee = 1
                GROUP BY sp.professeur_id
            ''', (semaine_id,))
            prof_h_semaine = {r['professeur_id']: float(r['h_semaine'] or 0) for r in cur.fetchall()}

            cur.execute('SELECT id, heures_max_semaine, taux_presence FROM professeur WHERE actif = 1')
            prof_limits = {}
            for r in cur.fetchall():
                max_h = float(r['heures_max_semaine']) if r['heures_max_semaine'] else 40.0
                taux = float(r['taux_presence']) if r['taux_presence'] else 100.0
                prof_limits[r['id']] = max_h * taux / 100.0

            # ── 7. Blocs de 2 creneaux (matin: S1+S2, apm: S3+S4) ──
            blocks = []
            for jour in range(1, 7):
                for debut in [1, 3]:
                    c1 = next((c for c in creneaux if c['jour'] == jour and c['numero_seance'] == debut), None)
                    c2 = next((c for c in creneaux if c['jour'] == jour and c['numero_seance'] == debut + 1), None)
                    if c1 and c2:
                        blocks.append({
                            'jour': jour,
                            'periode': 'matin' if debut == 1 else 'apm',
                            'creneaux': [c1, c2]
                        })

            # ── 8. Suivi des occupations ──
            groupe_occupe = {}
            prof_occupe = {}
            salle_occupe = {s['id']: set() for s in salles}
            groupe_jour_count = {}

            cur.execute('''
                SELECT s.creneau_id, s.salle_id, sg.groupe_id, sp.professeur_id, c.jour
                FROM seance s
                JOIN creneau c ON c.id = s.creneau_id
                LEFT JOIN seance_groupe sg ON sg.seance_id = s.id
                LEFT JOIN seance_professeur sp ON sp.seance_id = s.id
                WHERE s.semaine_id = %s
            ''', (semaine_id,))
            for ex in cur.fetchall():
                if ex['salle_id'] and ex['salle_id'] in salle_occupe:
                    salle_occupe[ex['salle_id']].add(ex['creneau_id'])
                if ex['groupe_id']:
                    gid_i = int(ex['groupe_id'])
                    groupe_occupe.setdefault(gid_i, set()).add(ex['creneau_id'])
                    groupe_jour_count.setdefault(gid_i, {})
                    groupe_jour_count[gid_i][ex['jour']] = groupe_jour_count[gid_i].get(ex['jour'], 0) + 1
                if ex['professeur_id']:
                    prof_occupe.setdefault(int(ex['professeur_id']), set()).add(ex['creneau_id'])

            # ── 9. Taches a planifier avec priorite ──
            tasks = []
            for u in unites_raw:
                gids_str = [g for g in (u['groupe_ids'] or '').split(',') if g]
                if not gids_str:
                    continue
                h_total = float(u['h_presentiel'] or 0)
                if h_total <= 0:
                    continue
                unite_id = u['unite_id']
                h_fait = heures_faites.get(unite_id, 0.0)
                h_restant = max(0.0, h_total - h_fait)
                if h_restant <= 0:
                    continue

                h_attendues = h_total * (semaines_passees / semaines_total)
                retard = h_attendues - h_fait

                # h_cible = heures a placer cette semaine
                # duree d'un bloc = 2 creneaux x 2.5h = 5h
                # donc nb_blocs = round(h_cible / 5.0) avec min 1
                BLOC_H = 5.0  # 2 creneaux x 2.5h
                h_cible = h_restant / semaines_restantes
                if retard > 0:
                    # Rattrappage: augmenter la cible de cette semaine
                    h_cible = min(h_restant, h_cible + retard / semaines_restantes)

                # Ne pas placer plus que ce qui reste
                # Max 2 blocs par module par semaine pour forcer la distribution
                nb_blocs = min(2, max(1, round(h_cible / BLOC_H)))

                pids = [int(p) for p in (u['prof_ids'] or '').split(',') if p]
                type_mod = (u['type_module'] or 'general').lower()  # 'general' or 'technique'

                tasks.append({
                    'unite_id': unite_id,
                    'module_code': u['module_code'],
                    'type_module': type_mod,
                    'groupe_ids': [int(g) for g in gids_str],
                    'prof_ids': pids,
                    'h_restant': h_restant,
                    'h_cible': h_cible,
                    'nb_blocs': nb_blocs,
                    'retard': retard,
                    # Modules generaux: 1 seance par semaine max (passage continu)
                    'is_general': type_mod == 'general',
                })

            # Trier par retard decroissant puis code module
            tasks.sort(key=lambda t: (-t['retard'], t['module_code']))

            # ── 10. Fonctions utilitaires de placement ──
            created = 0
            bloc_counter = 1

            # Duree reelle d'un creneau (2.5h selon la DB)
            DUREE_CRENEAU = float(creneaux[0].get('duree_h', 2.5)) if creneaux else 2.5
            DUREE_BLOC = DUREE_CRENEAU * 2  # 5h par bloc de 2 creneaux

            def pick_salle_best(type_module, cr1_id, cr2_id):
                # module.type_module ENUM: 'general' -> SC, 'technique' -> SP
                type_map = {'general': 'SC', 'technique': 'SP'}
                pref = type_map.get(type_module, 'SP')
                for s in salles:
                    if s['type_code'] == pref and \
                       cr1_id not in salle_occupe[s['id']] and \
                       cr2_id not in salle_occupe[s['id']]:
                        return s
                # Fallback: any free room
                for s in salles:
                    if cr1_id not in salle_occupe[s['id']] and \
                       cr2_id not in salle_occupe[s['id']]:
                        return s
                return None

            def profs_disponibles(pids, cr1_id, cr2_id):
                for p in pids:
                    if cr1_id in prof_occupe.get(p, set()) or cr2_id in prof_occupe.get(p, set()):
                        return False
                    if p in blocked_prof_creneaux:
                        if cr1_id in blocked_prof_creneaux[p] or cr2_id in blocked_prof_creneaux[p]:
                            return False
                    cap = prof_limits.get(p, 40.0)
                    # Use actual bloc duration (5h), not hardcoded 2h
                    if prof_h_semaine.get(p, 0.0) + DUREE_BLOC > cap:
                        return False
                return True

            def score_distribution(jour, groupe_ids):
                """Score bas = jour peu charge = prefere pour distribution.
                Compte le nombre de BLOCS (pas de creneaux) par jour par groupe."""
                total = 0
                for gid in groupe_ids:
                    # groupe_jour_count tracks blocs per day (incremented once per bloc in place_bloc)
                    total += groupe_jour_count.get(gid, {}).get(jour, 0)
                return total

            def place_bloc(task, block):
                nonlocal created, bloc_counter
                cr1 = block['creneaux'][0]
                cr2 = block['creneaux'][1]
                jour = block['jour']
                unite_id = task['unite_id']
                pids = task['prof_ids']
                gids = task['groupe_ids']
                type_mod = task['type_module']

                salle = pick_salle_best(type_mod, cr1['id'], cr2['id'])
                if not salle:
                    return False

                for gid in gids:
                    groupe_occupe.setdefault(gid, set()).add(cr1['id'])
                    groupe_occupe[gid].add(cr2['id'])
                    groupe_jour_count.setdefault(gid, {})
                    # Increment by 1 per BLOC (not per creneau) for accurate day scoring
                    groupe_jour_count[gid][jour] = groupe_jour_count[gid].get(jour, 0) + 1

                for p in pids:
                    prof_occupe.setdefault(p, set()).add(cr1['id'])
                    prof_occupe[p].add(cr2['id'])
                    dur1 = float(cr1.get('duree_h') or DUREE_CRENEAU)
                    dur2 = float(cr2.get('duree_h') or DUREE_CRENEAU)
                    prof_h_semaine[p] = prof_h_semaine.get(p, 0.0) + dur1 + dur2

                salle_occupe[salle['id']].add(cr1['id'])
                salle_occupe[salle['id']].add(cr2['id'])

                for cr in [cr1, cr2]:
                    cur.execute(
                        "INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature, bloc_no, statut)"
                        " VALUES (%s,%s,%s,%s,'presentiel','bloc',%s,'brouillon')",
                        (unite_id, semaine_id, cr['id'], salle['id'], bloc_counter)
                    )
                    sid = cur.lastrowid
                    for gid in gids:
                        cur.execute(
                            'INSERT INTO seance_groupe (seance_id, semaine_id, creneau_id, groupe_id) VALUES (%s,%s,%s,%s)',
                            (sid, semaine_id, cr['id'], gid)
                        )
                    for p in pids:
                        cur.execute(
                            'INSERT INTO seance_professeur (seance_id, semaine_id, creneau_id, professeur_id) VALUES (%s,%s,%s,%s)',
                            (sid, semaine_id, cr['id'], p)
                        )
                    created += 1

                bloc_counter += 1
                return True

            # ── 11. Placement distribue ──
            # Suivi des jours deja utilises par unite (evite meme module 2x le meme jour)
            unite_jours_utilises = {}  # unite_id -> set of jours

            for task in tasks:
                gids = task['groupe_ids']
                pids = task['prof_ids']
                unite_id = task['unite_id']

                for gid in gids:
                    groupe_occupe.setdefault(gid, set())
                    groupe_jour_count.setdefault(gid, {})
                for p in pids:
                    prof_occupe.setdefault(p, set())
                unite_jours_utilises.setdefault(unite_id, set())

                # Modules generaux en passage continu: 1 bloc max par semaine
                nb_target = 1 if task['is_general'] else task['nb_blocs']
                blocs_placed = 0

                while blocs_placed < nb_target:
                    # Trier: preferir jours peu charges pour ce groupe
                    # et alterner matin/apm pour equilibrer la journee
                    matin_count = sum(
                        1 for b in blocks if b['periode'] == 'matin'
                        and any(b['creneaux'][0]['id'] in groupe_occupe.get(g, set()) for g in gids)
                    )
                    apm_count = sum(
                        1 for b in blocks if b['periode'] == 'apm'
                        and any(b['creneaux'][0]['id'] in groupe_occupe.get(g, set()) for g in gids)
                    )
                    # Favoriser la periode moins utilisee
                    prefer_matin = matin_count <= apm_count

                    sorted_blocks = sorted(
                        blocks,
                        key=lambda b: (
                            score_distribution(b['jour'], gids),   # 1. jour le moins charge
                            b['jour'],                              # 2. jour le plus tot
                            (0 if b['periode'] == 'matin' else 1) if prefer_matin
                            else (0 if b['periode'] == 'apm' else 1)  # 3. periode preferee
                        )
                    )
                    placed_this_iter = False
                    for block in sorted_blocks:
                        cr1 = block['creneaux'][0]
                        cr2 = block['creneaux'][1]
                        jour = block['jour']

                        # Contrainte: meme module ne peut pas etre place 2 fois le meme jour
                        if jour in unite_jours_utilises.get(unite_id, set()):
                            continue

                        groupes_libres = all(
                            cr1['id'] not in groupe_occupe.get(gid, set()) and
                            cr2['id'] not in groupe_occupe.get(gid, set())
                            for gid in gids
                        )
                        if not groupes_libres:
                            continue
                        if pids and not profs_disponibles(pids, cr1['id'], cr2['id']):
                            continue

                        if place_bloc(task, block):
                            unite_jours_utilises[unite_id].add(jour)
                            blocs_placed += 1
                            placed_this_iter = True
                            break

                    if not placed_this_iter:
                        break  # Plus de creneaux disponibles pour ce module

        conn.commit()
        return jsonify({
            'message': f"Generation reussie : {created} seances creees pour la semaine {semaine_numero}",
            'seances_creees': created
        })
    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()



# ─── Copier l'emploi d'une semaine vers une autre ──────────────────────────────
@app.route('/api/copier-semaine', methods=['POST'])
def copier_semaine():
    data = request.get_json()
    source_id = data.get('source_id')
    target_id = data.get('target_id')
    if not source_id or not target_id:
        return jsonify({'error': 'source_id et target_id requis'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            # Supprimer les séances non verrouillées de la cible
            cur.execute("DELETE FROM seance WHERE semaine_id=%s AND verrouillee=0", (target_id,))

            cur.execute('SELECT * FROM seance WHERE semaine_id=%s', (source_id,))
            source_seances = cur.fetchall()
            copied = 0

            for s in source_seances:
                cur.execute(
                    "INSERT INTO seance (unite_id, semaine_id, creneau_id, salle_id, mode, nature, statut) VALUES (%s,%s,%s,%s,%s,%s,'brouillon')",
                    (s['unite_id'], target_id, s['creneau_id'], s['salle_id'], s['mode'], s['nature'])
                )
                new_id = cur.lastrowid

                cur.execute('SELECT groupe_id FROM seance_groupe WHERE seance_id=%s', (s['id'],))
                groupes = cur.fetchall()
                for g in groupes:
                    cur.execute('INSERT INTO seance_groupe (seance_id, semaine_id, creneau_id, groupe_id) VALUES (%s,%s,%s,%s)',
                                (new_id, target_id, s['creneau_id'], g['groupe_id']))

                cur.execute('SELECT professeur_id FROM seance_professeur WHERE seance_id=%s', (s['id'],))
                profs = cur.fetchall()
                for p in profs:
                    cur.execute('INSERT INTO seance_professeur (seance_id, semaine_id, creneau_id, professeur_id) VALUES (%s,%s,%s,%s)',
                                (new_id, target_id, s['creneau_id'], p['professeur_id']))
                copied += 1

        conn.commit()
        return jsonify({'message': f'{copied} séances copiées avec succès', 'count': copied})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ─── Vider les séances d'une semaine ──────────────────────────────────────────
@app.route('/api/vider-semaine/<int:semaine_id>', methods=['POST'])
def vider_semaine(semaine_id):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('DELETE FROM seance WHERE semaine_id=%s AND verrouillee=0', (semaine_id,))
            count = cur.rowcount
        conn.commit()
        conn.close()
        return jsonify({'message': 'Séances de la semaine effacées', 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Stats ────────────────────────────────────────────────────────────────────
@app.route('/api/stats/<int:semaine_id>', methods=['GET'])
def get_stats(semaine_id):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS total FROM seance WHERE semaine_id=%s', (semaine_id,))
            total = cur.fetchone()['total']

            cur.execute("SELECT COUNT(*) AS brouillon FROM seance WHERE semaine_id=%s AND statut='brouillon'", (semaine_id,))
            brouillon = cur.fetchone()['brouillon']

            cur.execute("SELECT COUNT(*) AS valide FROM seance WHERE semaine_id=%s AND statut='valide'", (semaine_id,))
            valide = cur.fetchone()['valide']

            cur.execute('SELECT COUNT(DISTINCT sg.groupe_id) AS nb FROM seance_groupe sg JOIN seance s ON s.id=sg.seance_id WHERE s.semaine_id=%s', (semaine_id,))
            nb = cur.fetchone()['nb']

        conn.close()
        return jsonify({'total': total, 'brouillon': brouillon, 'valide': valide, 'groupes_actifs': nb})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Unités d'enseignement ────────────────────────────────────────────────────
@app.route('/api/unites', methods=['GET'])
def get_unites():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('''
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
            ''')
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows_to_json(rows))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Démarrage ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    PORT = 3001
    print(f'[OK] API GestEmploi (Python/Flask) -> http://localhost:{PORT}')
    app.run(host='0.0.0.0', port=PORT, debug=True)
