"""
Vues de compatibilité directe avec le frontend React (Dashboard.jsx).

Ces vues exposent une API JSON simple (sans authentification) qui correspond
exactement aux chemins et aux formats utilisés par le frontend.  Elles gèrent
aussi le CRUD complet des données de base : groupes, formateurs, salles,
modules, filières et secteurs.
"""
import json

from django.db import IntegrityError, transaction
from django.db.models import Count, ProtectedError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from core.models import (
    Semaine, Groupe, Professeur, Salle, Creneau,
    UniteEnseignement, Filiere, Secteur, TypeSalle, Module, Seance,
    SeanceGroupe, SeanceProfesseur, AnneeScolaire, Semestre
)
from solver.services import GenerateurEmploiDuTemps


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _body(request):
    """Lit un corps JSON de façon tolérante."""
    try:
        raw = request.body.decode('utf-8') if request.body else '{}'
        data = json.loads(raw or '{}')
        return data if isinstance(data, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


def _error(message, status=400, details=None):
    payload = {'error': message, 'message': message}
    if details:
        payload['details'] = details
    return JsonResponse(payload, status=status)


def _value(data, *keys, default=None):
    """Retourne la première valeur non vide parmi plusieurs clés."""
    for key in keys:
        if key in data and data[key] not in (None, ''):
            return data[key]
    return default


def _int_or_none(value):
    try:
        return int(value) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def _bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'oui', 'yes', 'actif', 'active')


def _normalize_mode(value):
    raw = str(value or '').strip().lower()
    if 'alter' in raw:
        return Groupe.MODE_ALTERNANCE
    if 'hybride' in raw or 'hybrid' in raw:
        return Groupe.MODE_HYBRIDE
    return Groupe.MODE_PRESENTIEL


def _normalize_taux(value):
    """Le frontend envoie un pourcentage (0-100), le modèle attend 0-1."""
    try:
        taux = float(value)
    except (TypeError, ValueError):
        return 1.0
    if taux > 1:
        taux = taux / 100.0
    return max(0.0, min(1.0, taux))


def _get_or_none(model, pk):
    if pk in (None, ''):
        return None
    try:
        return model.objects.filter(pk=pk).first()
    except (TypeError, ValueError):
        return None


# ─── Sérialisation ────────────────────────────────────────────────────────────
def _groupe_data(g):
    return {
        'id': g.id,
        'code': g.code,
        'filiere_id': g.filiere_id,
        'filiere_code': g.filiere.code,
        'filiere_nom': g.filiere.intitule,
        'annee_etude': g.annee_etude,
        'effectif': g.effectif,
        'regime': g.regime,
        'mode_formation': g.mode_formation,
        'mode_formation_libelle': g.get_mode_formation_display(),
        'actif': g.actif,
    }


def _professeur_data(p):
    email = ''
    if getattr(p, 'utilisateur', None):
        email = p.utilisateur.email or ''
    return {
        'id': p.id,
        'matricule': p.matricule,
        'nom_complet': p.nom_complet,
        'email': email,
        'statut': p.statut,
        'taux_presence': round(float(p.taux_presence or 0) * 100, 1),
        'heures_max_semaine': float(p.heures_max_semaine) if p.heures_max_semaine is not None else None,
        'salle_preferee_id': p.salle_preferee_id,
        'salle_preferee_nom': p.salle_preferee.nom if p.salle_preferee else None,
        'salle_preferee_matin_id': p.salle_preferee_matin_id,
        'salle_preferee_matin_nom': p.salle_preferee_matin.nom if p.salle_preferee_matin else None,
        'salle_preferee_apm_id': p.salle_preferee_apm_id,
        'salle_preferee_apm_nom': p.salle_preferee_apm.nom if p.salle_preferee_apm else None,
        'actif': p.actif,
    }


def _salle_data(s):
    return {
        'id': s.id,
        'nom': s.nom,
        'capacite': s.capacite,
        'actif': s.actif,
        'type_salle_id': s.type_salle_id,
        'type_code': s.type_salle.code,
        'type_libelle': s.type_salle.libelle,
        'type_salle_libelle': s.type_salle.libelle,
        'est_virtuelle': s.type_salle.code == 'TEAM',
    }


def _module_data(m):
    types = list(m.types_salles_compatibles.all())
    return {
        'id': m.id,
        'code': m.code,
        'intitule': m.intitule,
        'type_module': m.type_module,
        'type_module_libelle': m.get_type_module_display(),
        'regional': m.regional,
        'types_salles_compatibles': [t.id for t in types],
        'types_salles_ids': [t.id for t in types],
        'types_salles_codes': [t.code for t in types],
        'types_salles_libelles': [t.libelle for t in types],
    }


def _filiere_data(f):
    return {
        'id': f.id,
        'code': f.code,
        'intitule': f.intitule,
        'secteur_id': f.secteur_id,
        'secteur_code': f.secteur.code,
        'secteur_nom': f.secteur.intitule,
        'niveau': f.niveau,
    }


def _secteur_data(s):
    return {'id': s.id, 'code': s.code, 'intitule': s.intitule}


# ─── Santé / Référentiels ─────────────────────────────────────────────────────
def health_check(request):
    """GET /api/health"""
    return JsonResponse({'status': 'ok', 'backend': 'Django / OR-Tools CP-SAT'})


def get_semaines_compat(request):
    """GET /api/semaines"""
    semaines = Semaine.objects.select_related('annee_scolaire', 'semestre').annotate(
        nb_seances=Count('seances')
    ).order_by('numero')

    data = [
        {
            'id': sw.id,
            'numero': sw.numero,
            'annee_scolaire_id': sw.annee_scolaire_id,
            'annee_libelle': sw.annee_scolaire.libelle,
            'semestre_id': sw.semestre_id,
            'semestre_numero': sw.semestre.numero if sw.semestre else 1,
            'date_debut': sw.date_debut.isoformat() if sw.date_debut else None,
            'date_fin': sw.date_fin.isoformat() if sw.date_fin else None,
            'active': sw.active,
            'nb_seances': sw.nb_seances,
        }
        for sw in semaines
    ]
    return JsonResponse(data, safe=False)


@csrf_exempt
def init_semaines_compat(request):
    """POST /api/init-semaines"""
    annee = AnneeScolaire.objects.filter(active=True).first() or AnneeScolaire.objects.first()
    s1 = Semestre.objects.filter(annee_scolaire=annee, numero=1).first() if annee else None

    for num in range(1, 17):
        Semaine.objects.get_or_create(
            annee_scolaire=annee,
            numero=num,
            defaults={'semestre': s1, 'active': True}
        )
    return JsonResponse({'message': '16 semaines initialisées avec succès'})


def get_creneaux_compat(request):
    """GET /api/creneaux"""
    creneaux = Creneau.objects.all().order_by('jour', 'numero_seance')
    data = [
        {
            'id': c.id,
            'jour': c.jour,
            'jour_nom': c.get_jour_display(),
            'numero_seance': c.numero_seance,
            'heure_debut': c.heure_debut.strftime('%H:%M:%S'),
            'heure_fin': c.heure_fin.strftime('%H:%M:%S'),
            'duree_h': float(c.duree_h),
            'periode': c.periode,
        }
        for c in creneaux
    ]
    return JsonResponse(data, safe=False)


def get_types_salles_compat(request):
    """GET /api/types-salles"""
    types = TypeSalle.objects.all().order_by('code')
    data = [{'id': t.id, 'code': t.code, 'libelle': t.libelle} for t in types]
    return JsonResponse(data, safe=False)


def get_unites_compat(request):
    """GET /api/unites"""
    unites = UniteEnseignement.objects.select_related('module').prefetch_related(
        'unite_groupes__groupe__filiere', 'unite_professeurs__professeur'
    ).all()
    data = []
    for u in unites:
        first_ug = u.unite_groupes.first()
        filiere = first_ug.groupe.filiere if first_ug else None
        first_up = u.unite_professeurs.first()
        prof = first_up.professeur if first_up else None
        groupes = [
            {'id': ug.groupe.id, 'code': ug.groupe.code}
            for ug in u.unite_groupes.all()
        ]
        data.append({
            'id': u.id,
            'code_fusion': u.code_fusion,
            'module_id': u.module_id,
            'module_code': u.module.code,
            'module_intitule': u.module.intitule,
            'module_nom': u.module.intitule,
            'type_module': u.module.type_module,
            'filiere_code': filiere.code if filiere else '',
            'prof_nom': prof.nom_complet if prof else '',
            'groupes': groupes,
            'groupes_codes': ', '.join(g['code'] for g in groupes),
        })
    return JsonResponse(data, safe=False)


# ─── CRUD : Groupes ───────────────────────────────────────────────────────────
@csrf_exempt
def groupes_collection(request):
    if request.method == 'GET':
        groupes = Groupe.objects.select_related('filiere').all().order_by('code')
        return JsonResponse([_groupe_data(g) for g in groupes], safe=False)

    if request.method != 'POST':
        return _error('Méthode non autorisée.', 405)

    data = _body(request)
    code = str(_value(data, 'code', default='')).strip().upper()
    filiere = _get_or_none(Filiere, _value(data, 'filiere_id', 'filiere'))
    if not code:
        return _error('Le code du groupe est obligatoire.')
    if not filiere:
        return _error('La filière est obligatoire.')
    if Groupe.objects.filter(code=code).exists():
        return _error(f'Le groupe {code} existe déjà.')

    try:
        groupe = Groupe.objects.create(
            code=code,
            filiere=filiere,
            annee_etude=_int_or_none(data.get('annee_etude')) or 1,
            effectif=_int_or_none(data.get('effectif')) or 25,
            regime=str(data.get('regime') or 'CDJ').strip().upper(),
            mode_formation=_normalize_mode(data.get('mode_formation')),
            actif=_bool(data.get('actif'), True),
        )
    except IntegrityError as exc:
        return _error(f'Impossible de créer le groupe : {exc}')
    return JsonResponse(_groupe_data(groupe), status=201)


@csrf_exempt
def groupe_detail(request, pk):
    groupe = _get_or_none(Groupe, pk)
    if not groupe:
        return _error('Groupe introuvable.', 404)

    if request.method == 'GET':
        return JsonResponse(_groupe_data(groupe))

    if request.method in ('PUT', 'PATCH'):
        data = _body(request)
        if 'code' in data and data['code']:
            code = str(data['code']).strip().upper()
            if Groupe.objects.filter(code=code).exclude(pk=groupe.pk).exists():
                return _error(f'Le groupe {code} existe déjà.')
            groupe.code = code
        filiere_id = _value(data, 'filiere_id', 'filiere')
        if filiere_id not in (None, ''):
            filiere = _get_or_none(Filiere, filiere_id)
            if not filiere:
                return _error('Filière introuvable.')
            groupe.filiere = filiere
        if 'annee_etude' in data:
            groupe.annee_etude = _int_or_none(data.get('annee_etude')) or 1
        if 'effectif' in data:
            groupe.effectif = _int_or_none(data.get('effectif')) or 25
        if 'regime' in data:
            groupe.regime = str(data.get('regime') or 'CDJ').strip().upper()
        if 'mode_formation' in data:
            groupe.mode_formation = _normalize_mode(data.get('mode_formation'))
        if 'actif' in data:
            groupe.actif = _bool(data.get('actif'), True)
        groupe.save()
        return JsonResponse(_groupe_data(groupe))

    if request.method == 'DELETE':
        # Archivage de sécurité si le groupe possède des séances.
        if groupe.groupe_seances.exists() or groupe.groupe_unites.exists():
            groupe.actif = False
            groupe.save(update_fields=['actif'])
            return JsonResponse({
                'success': True,
                'message': f'Le groupe {groupe.code} est utilisé : il a été archivé (désactivé).',
            })
        groupe.delete()
        return JsonResponse({'success': True, 'message': f'Groupe {groupe.code} supprimé.'})

    return _error('Méthode non autorisée.', 405)


# ─── CRUD : Formateurs ────────────────────────────────────────────────────────
@csrf_exempt
def professeurs_collection(request):
    if request.method == 'GET':
        profs = Professeur.objects.select_related(
            'salle_preferee', 'salle_preferee_matin', 'salle_preferee_apm', 'utilisateur'
        ).all().order_by('nom_complet')
        return JsonResponse([_professeur_data(p) for p in profs], safe=False)

    if request.method != 'POST':
        return _error('Méthode non autorisée.', 405)

    data = _body(request)
    nom_complet = str(_value(data, 'nom_complet', default='')).strip()
    if not nom_complet:
        return _error('Le nom complet du formateur est obligatoire.')

    matricule = str(data.get('matricule') or '').strip()
    if not matricule:
        base = 'P'
        index = Professeur.objects.count() + 1
        matricule = f'{base}{index:04d}'
        while Professeur.objects.filter(matricule=matricule).exists():
            index += 1
            matricule = f'{base}{index:04d}'
    elif Professeur.objects.filter(matricule=matricule).exists():
        return _error(f'Le matricule {matricule} existe déjà.')

    try:
        prof = Professeur.objects.create(
            matricule=matricule,
            nom_complet=nom_complet.upper(),
            statut=str(data.get('statut') or 'permanent').strip().lower(),
            heures_max_semaine=float(data.get('heures_max_semaine') or 30.0),
            taux_presence=_normalize_taux(data.get('taux_presence')),
            salle_preferee=_get_or_none(Salle, _value(data, 'salle_preferee', 'salle_preferee_id')),
            salle_preferee_matin=_get_or_none(Salle, _value(data, 'salle_preferee_matin', 'salle_preferee_matin_id')),
            salle_preferee_apm=_get_or_none(Salle, _value(data, 'salle_preferee_apm', 'salle_preferee_apm_id')),
            actif=_bool(data.get('actif'), True),
        )
    except (IntegrityError, ValueError) as exc:
        return _error(f'Impossible de créer le formateur : {exc}')
    return JsonResponse(_professeur_data(prof), status=201)


@csrf_exempt
def professeur_detail(request, pk):
    prof = _get_or_none(Professeur, pk)
    if not prof:
        return _error('Formateur introuvable.', 404)

    if request.method == 'GET':
        return JsonResponse(_professeur_data(prof))

    if request.method in ('PUT', 'PATCH'):
        data = _body(request)
        if 'nom_complet' in data and data['nom_complet']:
            prof.nom_complet = str(data['nom_complet']).strip().upper()
        if 'matricule' in data and data['matricule']:
            matricule = str(data['matricule']).strip()
            if Professeur.objects.filter(matricule=matricule).exclude(pk=prof.pk).exists():
                return _error(f'Le matricule {matricule} existe déjà.')
            prof.matricule = matricule
        if 'statut' in data:
            prof.statut = str(data.get('statut') or 'permanent').strip().lower()
        if 'heures_max_semaine' in data:
            try:
                prof.heures_max_semaine = float(data.get('heures_max_semaine') or 30.0)
            except (TypeError, ValueError):
                prof.heures_max_semaine = 30.0
        if 'taux_presence' in data:
            prof.taux_presence = _normalize_taux(data.get('taux_presence'))
        for field, keys in (
            ('salle_preferee', ('salle_preferee', 'salle_preferee_id')),
            ('salle_preferee_matin', ('salle_preferee_matin', 'salle_preferee_matin_id')),
            ('salle_preferee_apm', ('salle_preferee_apm', 'salle_preferee_apm_id')),
        ):
            if any(k in data for k in keys):
                setattr(prof, field, _get_or_none(Salle, _value(data, *keys)))
        if 'actif' in data:
            prof.actif = _bool(data.get('actif'), True)
        prof.save()
        return JsonResponse(_professeur_data(prof))

    if request.method == 'DELETE':
        if prof.professeur_seances.exists() or prof.seances_directes.exists() or prof.professeur_unites.exists():
            prof.actif = False
            prof.save(update_fields=['actif'])
            return JsonResponse({
                'success': True,
                'message': f'Le formateur {prof.nom_complet} est utilisé : il a été archivé (désactivé).',
            })
        prof.delete()
        return JsonResponse({'success': True, 'message': f'Formateur {prof.nom_complet} supprimé.'})

    return _error('Méthode non autorisée.', 405)


# ─── CRUD : Salles ────────────────────────────────────────────────────────────
@csrf_exempt
def salles_collection(request):
    if request.method == 'GET':
        salles = Salle.objects.select_related('type_salle').all().order_by('nom')
        return JsonResponse([_salle_data(s) for s in salles], safe=False)

    if request.method != 'POST':
        return _error('Méthode non autorisée.', 405)

    data = _body(request)
    nom = str(_value(data, 'nom', default='')).strip().upper()
    type_salle = _get_or_none(TypeSalle, _value(data, 'type_salle_id', 'type_salle'))
    if not nom:
        return _error('Le nom de la salle est obligatoire.')
    if not type_salle:
        return _error('Le type de salle est obligatoire.')
    if Salle.objects.filter(nom=nom).exists():
        return _error(f'La salle {nom} existe déjà.')

    try:
        salle = Salle.objects.create(
            nom=nom,
            type_salle=type_salle,
            capacite=_int_or_none(data.get('capacite')) or 30,
            actif=_bool(data.get('actif'), True),
        )
    except IntegrityError as exc:
        return _error(f'Impossible de créer la salle : {exc}')
    return JsonResponse(_salle_data(salle), status=201)


@csrf_exempt
def salle_detail(request, pk):
    salle = _get_or_none(Salle, pk)
    if not salle:
        return _error('Salle introuvable.', 404)

    if request.method == 'GET':
        return JsonResponse(_salle_data(salle))

    if request.method in ('PUT', 'PATCH'):
        data = _body(request)
        if 'nom' in data and data['nom']:
            nom = str(data['nom']).strip().upper()
            if Salle.objects.filter(nom=nom).exclude(pk=salle.pk).exists():
                return _error(f'La salle {nom} existe déjà.')
            salle.nom = nom
        type_salle_id = _value(data, 'type_salle_id', 'type_salle')
        if type_salle_id not in (None, ''):
            type_salle = _get_or_none(TypeSalle, type_salle_id)
            if not type_salle:
                return _error('Type de salle introuvable.')
            salle.type_salle = type_salle
        if 'capacite' in data:
            salle.capacite = _int_or_none(data.get('capacite')) or 30
        if 'actif' in data:
            salle.actif = _bool(data.get('actif'), True)
        salle.save()
        return JsonResponse(_salle_data(salle))

    if request.method == 'DELETE':
        if salle.seances.exists():
            salle.actif = False
            salle.save(update_fields=['actif'])
            return JsonResponse({
                'success': True,
                'message': f'La salle {salle.nom} est utilisée : elle a été archivée (désactivée).',
            })
        salle.delete()
        return JsonResponse({'success': True, 'message': f'Salle {salle.nom} supprimée.'})

    return _error('Méthode non autorisée.', 405)


# ─── CRUD : Modules ───────────────────────────────────────────────────────────
@csrf_exempt
def modules_collection(request):
    if request.method == 'GET':
        modules = Module.objects.prefetch_related('types_salles_compatibles').all().order_by('code')
        return JsonResponse([_module_data(m) for m in modules], safe=False)

    if request.method != 'POST':
        return _error('Méthode non autorisée.', 405)

    data = _body(request)
    code = str(_value(data, 'code', default='')).strip().upper()
    intitule = str(_value(data, 'intitule', default='')).strip()
    if not code:
        return _error('Le code du module est obligatoire.')
    if not intitule:
        return _error("L'intitulé du module est obligatoire.")
    if Module.objects.filter(code=code).exists():
        return _error(f'Le module {code} existe déjà.')

    try:
        with transaction.atomic():
            module = Module.objects.create(
                code=code,
                intitule=intitule,
                type_module=str(data.get('type_module') or 'technique').strip().lower(),
                regional=_bool(data.get('regional'), False),
            )
            types_ids = data.get('types_salles_compatibles') or data.get('types_salles_ids') or []
            if types_ids:
                module.types_salles_compatibles.set(
                    TypeSalle.objects.filter(id__in=[_int_or_none(x) for x in types_ids if _int_or_none(x)])
                )
    except IntegrityError as exc:
        return _error(f'Impossible de créer le module : {exc}')
    module.refresh_from_db()
    return JsonResponse(_module_data(module), status=201)


@csrf_exempt
def module_detail(request, pk):
    module = _get_or_none(Module, pk)
    if not module:
        return _error('Module introuvable.', 404)

    if request.method == 'GET':
        return JsonResponse(_module_data(module))

    if request.method in ('PUT', 'PATCH'):
        data = _body(request)
        if 'code' in data and data['code']:
            code = str(data['code']).strip().upper()
            if Module.objects.filter(code=code).exclude(pk=module.pk).exists():
                return _error(f'Le module {code} existe déjà.')
            module.code = code
        if 'intitule' in data and data['intitule']:
            module.intitule = str(data['intitule']).strip()
        if 'type_module' in data:
            module.type_module = str(data.get('type_module') or 'technique').strip().lower()
        if 'regional' in data:
            module.regional = _bool(data.get('regional'), False)
        module.save()
        if 'types_salles_compatibles' in data or 'types_salles_ids' in data:
            types_ids = data.get('types_salles_compatibles') or data.get('types_salles_ids') or []
            module.types_salles_compatibles.set(
                TypeSalle.objects.filter(id__in=[_int_or_none(x) for x in types_ids if _int_or_none(x)])
            )
        return JsonResponse(_module_data(module))

    if request.method == 'DELETE':
        if module.unites.exists():
            return _error(
                f'Le module {module.code} est utilisé par une ou plusieurs unités '
                'd\'enseignement : supprimez d\'abord ces unités.',
                409,
            )
        module.delete()
        return JsonResponse({'success': True, 'message': f'Module {module.code} supprimé.'})

    return _error('Méthode non autorisée.', 405)


# ─── CRUD : Filières ──────────────────────────────────────────────────────────
@csrf_exempt
def filieres_collection(request):
    if request.method == 'GET':
        filieres = Filiere.objects.select_related('secteur').all().order_by('code')
        return JsonResponse([_filiere_data(f) for f in filieres], safe=False)

    if request.method != 'POST':
        return _error('Méthode non autorisée.', 405)

    data = _body(request)
    code = str(_value(data, 'code', default='')).strip().upper()
    intitule = str(_value(data, 'intitule', default='')).strip()
    secteur = _get_or_none(Secteur, _value(data, 'secteur_id', 'secteur'))
    if not code:
        return _error('Le code de la filière est obligatoire.')
    if not intitule:
        return _error("L'intitulé de la filière est obligatoire.")
    if not secteur:
        return _error('Le secteur est obligatoire.')
    if Filiere.objects.filter(code=code).exists():
        return _error(f'La filière {code} existe déjà.')

    try:
        filiere = Filiere.objects.create(
            code=code,
            intitule=intitule,
            secteur=secteur,
            niveau=str(data.get('niveau') or 'TS').strip(),
        )
    except IntegrityError as exc:
        return _error(f'Impossible de créer la filière : {exc}')
    return JsonResponse(_filiere_data(filiere), status=201)


@csrf_exempt
def filiere_detail(request, pk):
    filiere = _get_or_none(Filiere, pk)
    if not filiere:
        return _error('Filière introuvable.', 404)

    if request.method == 'GET':
        return JsonResponse(_filiere_data(filiere))

    if request.method in ('PUT', 'PATCH'):
        data = _body(request)
        if 'code' in data and data['code']:
            code = str(data['code']).strip().upper()
            if Filiere.objects.filter(code=code).exclude(pk=filiere.pk).exists():
                return _error(f'La filière {code} existe déjà.')
            filiere.code = code
        if 'intitule' in data and data['intitule']:
            filiere.intitule = str(data['intitule']).strip()
        secteur_id = _value(data, 'secteur_id', 'secteur')
        if secteur_id not in (None, ''):
            secteur = _get_or_none(Secteur, secteur_id)
            if not secteur:
                return _error('Secteur introuvable.')
            filiere.secteur = secteur
        if 'niveau' in data:
            filiere.niveau = str(data.get('niveau') or 'TS').strip()
        filiere.save()
        return JsonResponse(_filiere_data(filiere))

    if request.method == 'DELETE':
        if filiere.groupes.exists():
            return _error(
                f'La filière {filiere.code} possède des groupes : supprimez d\'abord ces groupes.',
                409,
            )
        filiere.delete()
        return JsonResponse({'success': True, 'message': f'Filière {filiere.code} supprimée.'})

    return _error('Méthode non autorisée.', 405)


# ─── CRUD : Secteurs ──────────────────────────────────────────────────────────
@csrf_exempt
def secteurs_collection(request):
    if request.method == 'GET':
        secteurs = Secteur.objects.all().order_by('code')
        return JsonResponse([_secteur_data(s) for s in secteurs], safe=False)

    if request.method != 'POST':
        return _error('Méthode non autorisée.', 405)

    data = _body(request)
    code = str(_value(data, 'code', default='')).strip().upper()
    intitule = str(_value(data, 'intitule', default='')).strip()
    if not code or not intitule:
        return _error('Le code et l\'intitulé du secteur sont obligatoires.')
    if Secteur.objects.filter(code=code).exists():
        return _error(f'Le secteur {code} existe déjà.')
    secteur = Secteur.objects.create(code=code, intitule=intitule)
    return JsonResponse(_secteur_data(secteur), status=201)


@csrf_exempt
def secteur_detail(request, pk):
    secteur = _get_or_none(Secteur, pk)
    if not secteur:
        return _error('Secteur introuvable.', 404)

    if request.method == 'GET':
        return JsonResponse(_secteur_data(secteur))

    if request.method in ('PUT', 'PATCH'):
        data = _body(request)
        if 'code' in data and data['code']:
            code = str(data['code']).strip().upper()
            if Secteur.objects.filter(code=code).exclude(pk=secteur.pk).exists():
                return _error(f'Le secteur {code} existe déjà.')
            secteur.code = code
        if 'intitule' in data and data['intitule']:
            secteur.intitule = str(data['intitule']).strip()
        secteur.save()
        return JsonResponse(_secteur_data(secteur))

    if request.method == 'DELETE':
        if secteur.filieres.exists():
            return _error(
                f'Le secteur {secteur.code} possède des filières : supprimez d\'abord ces filières.',
                409,
            )
        secteur.delete()
        return JsonResponse({'success': True, 'message': f'Secteur {secteur.code} supprimé.'})

    return _error('Méthode non autorisée.', 405)


# ─── Emploi du temps / Statistiques ───────────────────────────────────────────
def get_emploi_du_temps_compat(request, semaine_id):
    """GET /api/emploi-du-temps/<semaine_id>"""
    seances = Seance.objects.filter(semaine_id=semaine_id).select_related(
        'creneau', 'salle__type_salle', 'unite__module', 'professeur'
    ).prefetch_related(
        'seance_groupes__groupe__filiere', 'seance_professeurs__professeur'
    ).order_by('creneau__jour', 'creneau__numero_seance')

    data = []
    for s in seances:
        first_sg = s.seance_groupes.first()
        filiere = first_sg.groupe.filiere if first_sg else None

        data.append({
            'id': s.id,
            'unite_id': s.unite_id,
            'semaine_id': s.semaine_id,
            'creneau_id': s.creneau_id,
            'salle_id': s.salle_id,
            'mode': s.mode,
            'nature': s.nature,
            'bloc_no': s.bloc_no,
            'statut': s.statut,
            'verrouillee': s.verrouillee,
            'jour': s.creneau.jour,
            'numero_seance': s.creneau.numero_seance,
            'periode': s.creneau.periode,
            'heure_debut': s.creneau.heure_debut.strftime('%H:%M:%S'),
            'heure_fin': s.creneau.heure_fin.strftime('%H:%M:%S'),
            'duree_h': float(s.creneau.duree_h),
            'salle_nom': s.salle.nom if s.salle else 'TEAM',
            'type_salle_code': s.salle.type_salle.code if s.salle else 'TEAM',
            'module_code': s.unite.module.code,
            'module_intitule': s.unite.module.intitule,
            'type_module': s.unite.module.type_module,
            'filiere_code': filiere.code if filiere else '',
            'filiere_nom': filiere.intitule if filiere else '',
            'groupes': [
                {
                    'seance_id': s.id,
                    'groupe_id': sg.groupe_id,
                    'groupe_code': sg.groupe.code,
                    'annee_etude': sg.groupe.annee_etude,
                }
                for sg in s.seance_groupes.all()
            ],
            'professeurs': [
                {
                    'seance_id': s.id,
                    'prof_id': sp.professeur_id,
                    'prof_nom': sp.professeur.nom_complet,
                    'matricule': sp.professeur.matricule,
                }
                for sp in s.seance_professeurs.all()
            ],
        })
    return JsonResponse(data, safe=False)


def get_stats_compat(request, semaine_id):
    """GET /api/stats/<semaine_id>"""
    total = Seance.objects.filter(semaine_id=semaine_id).count()
    brouillon = Seance.objects.filter(semaine_id=semaine_id, statut='brouillon').count()
    valide = Seance.objects.filter(semaine_id=semaine_id, statut='valide').count()
    groupes_actifs = SeanceGroupe.objects.filter(semaine_id=semaine_id).values('groupe_id').distinct().count()

    return JsonResponse({
        'total': total,
        'brouillon': brouillon,
        'valide': valide,
        'groupes_actifs': groupes_actifs,
    })


@csrf_exempt
def generer_semaine_compat(request, semaine_id):
    """POST /api/generer/<semaine_id> via solver Google OR-Tools CP-SAT"""
    data = _body(request)
    max_time = _int_or_none(data.get('max_time_seconds')) or 60
    groupes_ids = data.get('groupes_ids') or None
    generateur = GenerateurEmploiDuTemps(semaine_id=semaine_id)
    res = generateur.executer(max_time_seconds=max_time, groupes_ids=groupes_ids)
    return JsonResponse(res, status=200 if res.get('succes') else 422)


@csrf_exempt
def valider_semaine_compat(request, semaine_id):
    """POST /api/semaines/<semaine_id>/valider"""
    nb = Seance.objects.filter(semaine_id=semaine_id, statut='brouillon').update(statut='valide')
    return JsonResponse({
        'succes': True,
        'success': True,
        'message': f'{nb} séance(s) validée(s) avec succès.',
        'nb_validees': nb,
    })


@csrf_exempt
def vider_semaine_compat(request, semaine_id):
    """POST /api/vider-semaine/<semaine_id>"""
    nb, _ = Seance.objects.filter(semaine_id=semaine_id, verrouillee=False).delete()
    return JsonResponse({
        'succes': True,
        'success': True,
        'message': f'{nb} séance(s) supprimée(s).',
        'count': nb,
    })


# ─── Alias rétro-compatibles (anciens noms utilisés par le frontend) ──────────
def get_groupes_compat(request):
    return groupes_collection(request)


def get_professeurs_compat(request):
    return professeurs_collection(request)


def get_salles_compat(request):
    return salles_collection(request)


def get_filieres_compat(request):
    return filieres_collection(request)


def get_modules_compat(request):
    return modules_collection(request)


def get_secteurs_compat(request):
    return secteurs_collection(request)
