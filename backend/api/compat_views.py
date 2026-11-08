"""
Vues de compatibilité directe avec le frontend React (Dashboard.jsx).

Ces vues exposent une API JSON simple (sans authentification) qui correspond
exactement aux chemins et aux formats utilisés par le frontend.  Elles gèrent
aussi le CRUD complet des données de base : groupes, formateurs, salles,
modules, filières et secteurs.
"""
import json
import re
import unicodedata
from datetime import date as _date_cls

from django.db import IntegrityError, transaction
from django.db.models import Count, F, ProtectedError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email

from core.models import (
    Semaine, Groupe, Professeur, Salle, Creneau,
    UniteEnseignement, Filiere, Secteur, TypeSalle, Module, Seance,
    SeanceGroupe, SeanceProfesseur, AnneeScolaire, Semestre, Indisponibilite,
    AffectationEnseignement, Disponibilite, DemandeModificationProfil,
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


def _float_or_default(value, default=0.0):
    try:
        if value in (None, ''):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value):
    """Convertit une date ISO (YYYY-MM-DD) en objet date, sinon None."""
    if value in (None, ''):
        return None
    if isinstance(value, _date_cls):
        return value
    try:
        return _date_cls.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


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


def _module_ids_from(data):
    """Extrait une liste d'identifiants de modules depuis le corps JSON.

    Accepte ``module_ids`` (liste d'ids) ou ``modules`` (liste d'ids ou
    d'objets ``{id, code, intitule}`` renvoyés par l'API.
    """
    raw = data.get('module_ids')
    if raw is None:
        raw = data.get('modules')
    if not isinstance(raw, list):
        return []
    ids = []
    for item in raw:
        if isinstance(item, dict):
            item = item.get('id')
        module_id = _int_or_none(item)
        if module_id is not None:
            ids.append(module_id)
    return ids


def _code_depuis_intitule(intitule, max_len=20):
    """Génère un code lisible à partir d'un intitulé (sans accents)."""
    normalized = unicodedata.normalize('NFKD', intitule or '')
    ascii_label = normalized.encode('ascii', 'ignore').decode('ascii')
    code = re.sub(r'[^A-Za-z0-9]+', '', ascii_label).upper()[:max_len]
    return code or 'SEC'


def _secteur_depuis_intitule(intitule):
    """Retourne le secteur correspondant à l'intitulé, ou le crée."""
    intitule = str(intitule or '').strip()
    if not intitule:
        return None
    existant = Secteur.objects.filter(intitule__iexact=intitule).first()
    if existant:
        return existant

    base = _code_depuis_intitule(intitule)
    code = base
    suffixe = 2
    while Secteur.objects.filter(code=code).exists():
        suffixe_str = str(suffixe)
        code = f"{base[:max(1, 20 - len(suffixe_str))]}{suffixe_str}"
        suffixe += 1
    return Secteur.objects.create(code=code, intitule=intitule)


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


def _affectations_from(data):
    """Extrait les couples (module, groupe) depuis le corps JSON.

    Accepte une liste ``affectations`` d'objets ``{module_id, groupe_id}``.
    """
    raw = data.get('affectations')
    if not isinstance(raw, list):
        return []
    couples = []
    for item in raw:
        if isinstance(item, dict):
            module_id = _int_or_none(_value(item, 'module_id', 'module'))
            groupe_id = _int_or_none(_value(item, 'groupe_id', 'groupe'))
            if module_id is not None and groupe_id is not None:
                couples.append((module_id, groupe_id))
    return couples


def _sync_affectations(prof, data):
    """Remplace les affectations module/groupe d'un formateur."""
    couples = _affectations_from(data)
    valid_modules = set(
        Module.objects.filter(id__in={m for m, _ in couples}).values_list('id', flat=True)
    )
    valid_groupes = set(
        Groupe.objects.filter(id__in={g for _, g in couples}).values_list('id', flat=True)
    )
    prof.affectations_enseignement.all().delete()
    AffectationEnseignement.objects.bulk_create([
        AffectationEnseignement(
            professeur=prof,
            module_id=module_id,
            groupe_id=groupe_id,
            statut=AffectationEnseignement.STATUT_AFFECTE,
        )
        for module_id, groupe_id in sorted(set(couples))
        if module_id in valid_modules and groupe_id in valid_groupes
    ], ignore_conflicts=True)


def _recompute_prof_modules(prof):
    """Synchronise les modules d'un formateur avec ses affectations.

    Les modules enseignés ne sont plus saisis dans la fiche formateur : ils
    découlent des couples (module, groupe) définis dans l'onglet Affectations.
    """
    if prof is None:
        return
    module_ids = prof.affectations_enseignement.filter(
        professeur__isnull=False
    ).values_list('module_id', flat=True)
    prof.modules.set(Module.objects.filter(id__in=module_ids))


def _statut_besoin(value, prof):
    """Statut cohérent avec la présence ou l'absence d'un formateur."""
    if prof is not None:
        return AffectationEnseignement.STATUT_AFFECTE
    if value in (
        AffectationEnseignement.STATUT_A_POURVOIR,
        AffectationEnseignement.STATUT_VACATAIRE,
    ):
        return value
    return AffectationEnseignement.STATUT_A_POURVOIR


def _affectation_data(a):
    prof = a.professeur
    return {
        'id': a.id,
        'professeur_id': a.professeur_id,
        'professeur_nom': prof.nom_complet if prof else None,
        'matricule': prof.matricule if prof else None,
        'statut': a.statut,
        'statut_label': a.get_statut_display(),
        'est_pourvu': bool(prof),
        'notes': a.notes or '',
        'module_id': a.module_id,
        'module_code': a.module.code,
        'module_intitule': a.module.intitule,
        'module_heures': float(a.module.heures_hebdomadaires or 0),
        'groupe_id': a.groupe_id,
        'groupe_code': a.groupe.code,
        'filiere_id': a.groupe.filiere_id,
        'filiere_code': a.groupe.filiere.code if a.groupe.filiere_id else None,
    }


def _professeur_data(p):
    email = p.email or ''
    telephone = p.telephone or ''
    if getattr(p, 'utilisateur', None):
        email = email or (p.utilisateur.email or '')
        telephone = telephone or (p.utilisateur.telephone or '')
    modules = list(p.modules.all())
    affectations = [
        {'module_id': a.module_id, 'groupe_id': a.groupe_id}
        for a in p.affectations_enseignement.all()
    ]
    return {
        'id': p.id,
        'matricule': p.matricule,
        'nom_complet': p.nom_complet,
        'email': email,
        'telephone': telephone,
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
        'module_ids': [m.id for m in modules],
        'modules': [
            {'id': m.id, 'code': m.code, 'intitule': m.intitule}
            for m in modules
        ],
        'affectations': affectations,
    }


PROFIL_CHAMPS_SALLES = (
    ('salle_preferee_id', 'salle_preferee'),
    ('salle_preferee_matin_id', 'salle_preferee_matin'),
    ('salle_preferee_apm_id', 'salle_preferee_apm'),
)


def _valeurs_profil(prof):
    """Valeurs actuelles de la fiche formateur (pour l'affichage et les diffs)."""
    email = prof.email or ''
    telephone = prof.telephone or ''
    if prof.utilisateur_id:
        utilisateur = prof.utilisateur
        email = email or (utilisateur.email or '')
        telephone = telephone or (utilisateur.telephone or '')
    return {
        'email': email,
        'telephone': telephone,
        'statut': prof.statut,
        'heures_max_semaine': float(prof.heures_max_semaine) if prof.heures_max_semaine is not None else None,
        'salle_preferee_id': prof.salle_preferee_id,
        'salle_preferee_nom': prof.salle_preferee.nom if prof.salle_preferee else None,
        'salle_preferee_matin_id': prof.salle_preferee_matin_id,
        'salle_preferee_matin_nom': prof.salle_preferee_matin.nom if prof.salle_preferee_matin else None,
        'salle_preferee_apm_id': prof.salle_preferee_apm_id,
        'salle_preferee_apm_nom': prof.salle_preferee_apm.nom if prof.salle_preferee_apm else None,
    }


def _normaliser_donnees_profil(data):
    """Valide les champs modifiables d'une demande de profil.

    Retourne ``(donnees, message_erreur)``.  Seuls les champs présents dans le
    corps de la requête sont conservés, afin de ne pas écraser les autres.
    """
    donnees = {}

    if 'email' in data:
        email = str(data.get('email') or '').strip()
        if email:
            try:
                validate_email(email)
            except DjangoValidationError:
                return None, "L'adresse email n'est pas valide."
        donnees['email'] = email

    if 'telephone' in data:
        telephone = str(data.get('telephone') or '').strip()
        if len(telephone) > 20:
            return None, 'Le numéro de téléphone ne doit pas dépasser 20 caractères.'
        donnees['telephone'] = telephone

    if 'statut' in data:
        statut = str(data.get('statut') or '').strip().lower()
        if statut not in (Professeur.STATUT_PERMANENT, Professeur.STATUT_VACATAIRE):
            return None, 'Le statut doit être « permanent » ou « vacataire ».'
        donnees['statut'] = statut

    if 'heures_max_semaine' in data:
        try:
            heures = float(data.get('heures_max_semaine') or 0)
        except (TypeError, ValueError):
            return None, 'Le nombre d’heures maximales est invalide.'
        if heures < 0 or heures > 60:
            return None, 'Le nombre d’heures maximales doit être compris entre 0 et 60.'
        donnees['heures_max_semaine'] = heures

    for cle, libelle in PROFIL_CHAMPS_SALLES:
        if cle not in data:
            continue
        valeur = data.get(cle)
        if valeur in (None, '', 0, '0'):
            donnees[cle] = None
            continue
        salle_id = _int_or_none(valeur)
        salle = _get_or_none(Salle, salle_id) if salle_id else None
        if not salle:
            return None, 'La salle sélectionnée est introuvable.'
        donnees[cle] = salle.id

    return donnees, None


def _demande_profil_data(demande):
    return {
        'id': demande.id,
        'professeur_id': demande.professeur_id,
        'professeur_nom': demande.professeur.nom_complet,
        'matricule': demande.professeur.matricule,
        'donnees': demande.donnees or {},
        'actuel': demande.donnees_avant or _valeurs_profil(demande.professeur),
        'statut': demande.statut,
        'commentaire_formateur': demande.commentaire_formateur,
        'commentaire_admin': demande.commentaire_admin,
        'date_demande': demande.date_demande.isoformat() if demande.date_demande else None,
        'date_traitement': demande.date_traitement.isoformat() if demande.date_traitement else None,
    }


def _appliquer_donnees_profil(prof, donnees):
    """Applique une demande approuvée à la fiche formateur et au compte lié."""
    if 'email' in donnees:
        prof.email = donnees['email']
    if 'telephone' in donnees:
        prof.telephone = donnees['telephone']
    if 'statut' in donnees:
        prof.statut = donnees['statut']
    if 'heures_max_semaine' in donnees:
        prof.heures_max_semaine = donnees['heures_max_semaine']
    for cle, champ in PROFIL_CHAMPS_SALLES:
        if cle in donnees:
            salle_id = donnees[cle]
            setattr(prof, champ, _get_or_none(Salle, salle_id) if salle_id else None)
    prof.save()

    if prof.utilisateur_id:
        utilisateur = prof.utilisateur
        champs = []
        if 'email' in donnees:
            utilisateur.email = donnees['email']
            champs.append('email')
        if 'telephone' in donnees:
            utilisateur.telephone = donnees['telephone']
            champs.append('telephone')
        if champs:
            utilisateur.save(update_fields=champs)


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
        'efm_fin_module': m.efm_fin_module,
        'date_efm': m.date_efm.isoformat() if m.date_efm else None,
        'seances_2_5_autorisees': m.seances_2_5_autorisees,
        'peut_avoir_seance_2_5': m.peut_avoir_seance_2_5,
        'heures_hebdomadaires': float(m.heures_hebdomadaires or 0),
        'est_technique_m10': m.est_technique_m10,
        'types_salles_compatibles': [t.id for t in types],
        'types_salles_ids': [t.id for t in types],
        'types_salles_codes': [t.code for t in types],
        'types_salles_libelles': [t.libelle for t in types],
    }


def _filiere_data(f):
    modules = list(f.modules.all())
    return {
        'id': f.id,
        'code': f.code,
        'intitule': f.intitule,
        'secteur_id': f.secteur_id,
        'secteur_code': f.secteur.code,
        'secteur_nom': f.secteur.intitule,
        'niveau': f.niveau,
        'module_ids': [m.id for m in modules],
        'modules': [
            {'id': m.id, 'code': m.code, 'intitule': m.intitule}
            for m in modules
        ],
    }


def _secteur_data(s):
    return {'id': s.id, 'code': s.code, 'intitule': s.intitule}


def _indisponibilite_data(i):
    return {
        'id': i.id,
        'type_cible': i.type_cible,
        'type_cible_libelle': i.get_type_cible_display(),
        'groupe_id': i.groupe_id,
        'groupe_code': i.groupe.code if i.groupe else None,
        'professeur_id': i.professeur_id,
        'professeur_nom': i.professeur.nom_complet if i.professeur else None,
        'type_periode': i.type_periode,
        'type_periode_libelle': i.get_type_periode_display(),
        'semaine_id': i.semaine_id,
        'semaine_numero': i.semaine.numero if i.semaine else None,
        'jour': i.jour,
        'date_debut': i.date_debut.isoformat() if i.date_debut else None,
        'date_fin': i.date_fin.isoformat() if i.date_fin else None,
        'motif': i.motif,
        'actif': i.actif,
        'date_creation': i.date_creation.isoformat() if i.date_creation else None,
    }


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
        ).prefetch_related('modules', 'affectations_enseignement').all().order_by('nom_complet')
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
            email=str(data.get('email') or '').strip(),
            telephone=str(data.get('telephone') or '').strip(),
            statut=str(data.get('statut') or 'permanent').strip().lower(),
            heures_max_semaine=float(data.get('heures_max_semaine') or 30.0),
            taux_presence=_normalize_taux(data.get('taux_presence')),
            salle_preferee=_get_or_none(Salle, _value(data, 'salle_preferee', 'salle_preferee_id')),
            salle_preferee_matin=_get_or_none(Salle, _value(data, 'salle_preferee_matin', 'salle_preferee_matin_id')),
            salle_preferee_apm=_get_or_none(Salle, _value(data, 'salle_preferee_apm', 'salle_preferee_apm_id')),
            actif=_bool(data.get('actif'), True),
        )
        prof.modules.set(Module.objects.filter(
            id__in=set(_module_ids_from(data)) | {m for m, _ in _affectations_from(data)}
        ))
        _sync_affectations(prof, data)
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
        if 'email' in data:
            prof.email = str(data.get('email') or '').strip()
        if 'telephone' in data:
            prof.telephone = str(data.get('telephone') or '').strip()
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
        if 'module_ids' in data or 'modules' in data or 'affectations' in data:
            prof.modules.set(Module.objects.filter(
                id__in=set(_module_ids_from(data)) | {m for m, _ in _affectations_from(data)}
            ))
        if 'affectations' in data:
            _sync_affectations(prof, data)
        return JsonResponse(_professeur_data(prof))

    if request.method == 'DELETE':
        if prof.professeur_seances.exists() or prof.seances_directes.exists() or prof.professeur_unites.exists():
            prof.actif = False
            prof.save(update_fields=['actif'])
            return JsonResponse({
                'success': True,
                'message': f'Le formateur {prof.nom_complet} est utilisé : il a été archivé (désactivé).',
            })
        # Ses besoins redeviennent des postes à pourvoir plutôt que d'être perdus.
        for affectation in AffectationEnseignement.objects.filter(professeur=prof):
            doublon = AffectationEnseignement.objects.filter(
                module_id=affectation.module_id,
                groupe_id=affectation.groupe_id,
                professeur__isnull=True,
            ).exclude(pk=affectation.pk).exists()
            if doublon:
                affectation.delete()
            else:
                affectation.professeur = None
                affectation.statut = AffectationEnseignement.STATUT_A_POURVOIR
                affectation.save()
        prof.delete()
        return JsonResponse({'success': True, 'message': f'Formateur {prof.nom_complet} supprimé.'})

    return _error('Méthode non autorisée.', 405)


# ─── Demandes de modification de profil formateur ─────────────────────────────
@csrf_exempt
def demandes_profil_collection(request):
    """GET/POST /api/demandes-profil"""
    if request.method == 'GET':
        demandes = DemandeModificationProfil.objects.select_related(
            'professeur',
            'professeur__utilisateur',
            'professeur__salle_preferee',
            'professeur__salle_preferee_matin',
            'professeur__salle_preferee_apm',
        ).all()
        professeur_id = _int_or_none(request.GET.get('professeur_id'))
        if professeur_id:
            demandes = demandes.filter(professeur_id=professeur_id)
        statut = (request.GET.get('statut') or '').strip()
        if statut:
            demandes = demandes.filter(statut=statut)
        return JsonResponse([_demande_profil_data(d) for d in demandes], safe=False)

    if request.method != 'POST':
        return _error('Méthode non autorisée.', 405)

    data = _body(request)
    prof = _get_or_none(Professeur, _value(data, 'professeur_id', 'professeur'))
    if not prof:
        return _error('Formateur introuvable.', 404)

    donnees, erreur = _normaliser_donnees_profil(data)
    if erreur:
        return _error(erreur)
    if not donnees:
        return _error('Aucune modification à envoyer.')

    commentaire = str(data.get('commentaire_formateur') or '').strip()[:1000]

    demande = DemandeModificationProfil.objects.filter(
        professeur=prof,
        statut=DemandeModificationProfil.STATUT_EN_ATTENTE,
    ).first()
    creee = demande is None
    if creee:
        demande = DemandeModificationProfil(professeur=prof)
    demande.donnees = donnees
    demande.donnees_avant = _valeurs_profil(prof)
    demande.commentaire_formateur = commentaire
    demande.save()

    return JsonResponse(_demande_profil_data(demande), status=201 if creee else 200)


@csrf_exempt
def demande_profil_detail(request, pk):
    """GET/DELETE /api/demandes-profil/<id>"""
    demande = _get_or_none(DemandeModificationProfil, pk)
    if not demande:
        return _error('Demande introuvable.', 404)

    if request.method == 'GET':
        return JsonResponse(_demande_profil_data(demande))

    if request.method == 'DELETE':
        if demande.statut != DemandeModificationProfil.STATUT_EN_ATTENTE:
            return _error('Seule une demande en attente peut être annulée.')
        demande.delete()
        return JsonResponse({'success': True, 'message': 'Demande annulée.'})

    return _error('Méthode non autorisée.', 405)


def _traiter_demande_profil(request, pk, statut):
    if request.method != 'POST':
        return _error('Méthode non autorisée.', 405)

    demande = _get_or_none(DemandeModificationProfil, pk)
    if not demande:
        return _error('Demande introuvable.', 404)
    if demande.statut != DemandeModificationProfil.STATUT_EN_ATTENTE:
        return _error('Cette demande a déjà été traitée.')

    data = _body(request)
    commentaire = str(data.get('commentaire_admin') or '').strip()[:1000]

    with transaction.atomic():
        if statut == DemandeModificationProfil.STATUT_APPROUVEE:
            _appliquer_donnees_profil(demande.professeur, demande.donnees or {})
        demande.statut = statut
        demande.commentaire_admin = commentaire
        demande.date_traitement = timezone.now()
        demande.save(update_fields=['statut', 'commentaire_admin', 'date_traitement'])

    return JsonResponse({
        'demande': _demande_profil_data(demande),
        'professeur': _professeur_data(demande.professeur),
    })


@csrf_exempt
def approuver_demande_profil(request, pk):
    """POST /api/demandes-profil/<id>/approuver"""
    return _traiter_demande_profil(request, pk, DemandeModificationProfil.STATUT_APPROUVEE)


@csrf_exempt
def refuser_demande_profil(request, pk):
    """POST /api/demandes-profil/<id>/refuser"""
    return _traiter_demande_profil(request, pk, DemandeModificationProfil.STATUT_REFUSEE)


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
                efm_fin_module=_bool(data.get('efm_fin_module'), True),
                date_efm=_parse_date(data.get('date_efm')),
                seances_2_5_autorisees=_bool(data.get('seances_2_5_autorisees'), True),
                heures_hebdomadaires=_float_or_default(data.get('heures_hebdomadaires'), 5.0),
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
        if 'efm_fin_module' in data:
            module.efm_fin_module = _bool(data.get('efm_fin_module'), True)
        if 'date_efm' in data:
            module.date_efm = _parse_date(data.get('date_efm'))
        if 'seances_2_5_autorisees' in data:
            module.seances_2_5_autorisees = _bool(data.get('seances_2_5_autorisees'), True)
        if 'heures_hebdomadaires' in data:
            module.heures_hebdomadaires = _float_or_default(
                data.get('heures_hebdomadaires'), 5.0
            )
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
        filieres = (
            Filiere.objects.select_related('secteur')
            .prefetch_related('modules')
            .all()
            .order_by('code')
        )
        return JsonResponse([_filiere_data(f) for f in filieres], safe=False)

    if request.method != 'POST':
        return _error('Méthode non autorisée.', 405)

    data = _body(request)
    code = str(_value(data, 'code', default='')).strip().upper()
    intitule = str(_value(data, 'intitule', default='')).strip()
    if not code:
        return _error('Le code de la filière est obligatoire.')
    if not intitule:
        return _error("L'intitulé de la filière est obligatoire.")
    if Filiere.objects.filter(code=code).exists():
        return _error(f'La filière {code} existe déjà.')

    # Secteur : sélection d'un secteur existant, ou création à la volée
    # depuis le champ texte « nouveau secteur ».
    secteur = _get_or_none(Secteur, _value(data, 'secteur_id', 'secteur'))
    if not secteur:
        secteur = _secteur_depuis_intitule(
            _value(data, 'secteur_intitule', 'nouveau_secteur', default='')
        )
    if not secteur:
        return _error('Le secteur est obligatoire.')

    try:
        with transaction.atomic():
            filiere = Filiere.objects.create(
                code=code,
                intitule=intitule,
                secteur=secteur,
                niveau=str(data.get('niveau') or 'TS').strip(),
            )
            module_ids = _module_ids_from(data)
            if module_ids:
                filiere.modules.set(Module.objects.filter(id__in=module_ids))
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
        else:
            nouveau_secteur = _value(
                data, 'secteur_intitule', 'nouveau_secteur', default=''
            )
            if nouveau_secteur:
                filiere.secteur = _secteur_depuis_intitule(nouveau_secteur)
        if 'niveau' in data:
            filiere.niveau = str(data.get('niveau') or 'TS').strip()
        filiere.save()
        if 'module_ids' in data or 'modules' in data:
            filiere.modules.set(
                Module.objects.filter(id__in=_module_ids_from(data))
            )
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


# ─── Indisponibilités / Congés ────────────────────────────────────────────────
@csrf_exempt
def indisponibilites_collection(request):
    if request.method == 'GET':
        qs = Indisponibilite.objects.select_related('groupe', 'professeur', 'semaine').all().order_by('-date_creation')
        type_cible = request.GET.get('type_cible')
        if type_cible:
            qs = qs.filter(type_cible=type_cible)
        return JsonResponse([_indisponibilite_data(i) for i in qs], safe=False)

    if request.method != 'POST':
        return _error('Méthode non autorisée.', 405)

    data = _body(request)
    type_cible = str(_value(data, 'type_cible', default='groupe')).strip()
    type_periode = str(_value(data, 'type_periode', default='jour')).strip()
    motif = str(_value(data, 'motif', default='')).strip()
    actif = _bool(data.get('actif'), True)

    groupe = None
    professeur = None
    if type_cible == 'groupe':
        gid = _value(data, 'groupe', 'groupe_id')
        if gid:
            groupe = _get_or_none(Groupe, gid)
            if not groupe:
                return _error('Groupe introuvable.', 404)
    elif type_cible == 'professeur':
        pid = _value(data, 'professeur', 'professeur_id')
        if pid:
            professeur = _get_or_none(Professeur, pid)
            if not professeur:
                return _error('Formateur introuvable.', 404)

    semaine = None
    jour = None
    date_debut = None
    date_fin = None

    sid = _value(data, 'semaine', 'semaine_id')
    if sid:
        semaine = _get_or_none(Semaine, sid)
        if not semaine:
            return _error('Semaine introuvable.', 404)

    if 'jour' in data and data['jour'] not in (None, ''):
        try:
            jour = int(data['jour'])
        except (ValueError, TypeError):
            return _error('Jour invalide.')

    if data.get('date_debut'):
        try:
            date_debut = _date_cls.fromisoformat(data['date_debut'])
        except ValueError:
            return _error('Date de début invalide.')
    if data.get('date_fin'):
        try:
            date_fin = _date_cls.fromisoformat(data['date_fin'])
        except ValueError:
            return _error('Date de fin invalide.')

    if type_periode == 'jour':
        if not semaine or not jour:
            return _error('Semaine et jour requis pour un jour libre.')
    elif type_periode == 'semaine':
        if not semaine:
            return _error('Semaine requise pour une semaine libre.')
    elif type_periode == 'periode':
        if not date_debut or not date_fin:
            return _error('Dates de début et de fin requises pour une période.')
        if date_fin < date_debut:
            return _error('La date de fin doit être après la date de début.')

    if type_cible == 'tous':
        groupe = None
        professeur = None

    ind = Indisponibilite.objects.create(
        type_cible=type_cible,
        groupe=groupe,
        professeur=professeur,
        type_periode=type_periode,
        semaine=semaine,
        jour=jour,
        date_debut=date_debut,
        date_fin=date_fin,
        motif=motif,
        actif=actif,
    )
    return JsonResponse(_indisponibilite_data(ind), status=201)


@csrf_exempt
def indisponibilite_detail(request, pk):
    ind = _get_or_none(Indisponibilite, pk)
    if not ind:
        return _error('Indisponibilité introuvable.', 404)

    if request.method == 'GET':
        return JsonResponse(_indisponibilite_data(ind))

    if request.method in ('PUT', 'PATCH'):
        data = _body(request)
        if 'type_cible' in data and data['type_cible']:
            ind.type_cible = str(data['type_cible']).strip()
        if 'type_periode' in data and data['type_periode']:
            ind.type_periode = str(data['type_periode']).strip()
        if 'motif' in data:
            ind.motif = str(data['motif'] or '').strip()
        if 'actif' in data:
            ind.actif = _bool(data.get('actif'), ind.actif)

        # cible
        if 'groupe_id' in data or 'groupe' in data:
            gid = _value(data, 'groupe', 'groupe_id')
            ind.groupe = _get_or_none(Groupe, gid) if gid else None
        if 'professeur_id' in data or 'professeur' in data:
            pid = _value(data, 'professeur', 'professeur_id')
            ind.professeur = _get_or_none(Professeur, pid) if pid else None

        if 'semaine_id' in data or 'semaine' in data:
            sid = _value(data, 'semaine', 'semaine_id')
            ind.semaine = _get_or_none(Semaine, sid) if sid else None
        if 'jour' in data:
            val = data['jour']
            ind.jour = int(val) if val not in (None, '') else None
        if 'date_debut' in data:
            val = data['date_debut']
            ind.date_debut = _date_cls.fromisoformat(val) if val else None
        if 'date_fin' in data:
            val = data['date_fin']
            ind.date_fin = _date_cls.fromisoformat(val) if val else None

        if ind.type_cible == 'tous':
            ind.groupe = None
            ind.professeur = None
        elif ind.type_cible == 'groupe':
            ind.professeur = None
        elif ind.type_cible == 'professeur':
            ind.groupe = None

        ind.save()
        return JsonResponse(_indisponibilite_data(ind))

    if request.method == 'DELETE':
        ind.delete()
        return JsonResponse({'success': True, 'message': 'Indisponibilité supprimée.'})

    return _error('Méthode non autorisée.', 405)


# ─── Disponibilités des formateurs ───────────────────────────────────────────
ETATS_DISPONIBILITE = {Disponibilite.ETAT_DISPONIBLE, Disponibilite.ETAT_BLOQUE,
                       Disponibilite.ETAT_PREFERE}


def _disponibilite_data(d):
    return {
        'id': d.id,
        'professeur_id': d.professeur_id,
        'creneau_id': d.creneau_id,
        'etat': d.etat,
        'jour': d.creneau.jour,
        'numero_seance': d.creneau.numero_seance,
        'heure_debut': d.creneau.heure_debut.strftime('%H:%M'),
        'heure_fin': d.creneau.heure_fin.strftime('%H:%M'),
    }


def _disponibilites_prof(prof_id):
    qs = Disponibilite.objects.filter(professeur_id=prof_id).select_related('creneau')
    return JsonResponse([_disponibilite_data(d) for d in qs], safe=False)


@csrf_exempt
def disponibilites_collection(request):
    """GET/POST/PUT /api/disponibilites

    GET  ?professeur=<id>  — disponibilités d'un formateur.
    POST {professeur_id, creneau_id, etat} — met à jour un créneau.
    PUT  {professeur_id, disponibilites: [{creneau_id, etat}, ...]}
         — remplace l'ensemble des disponibilités du formateur.
    """
    if request.method == 'GET':
        prof_id = _int_or_none(request.GET.get('professeur')
                               or request.GET.get('professeur_id'))
        if prof_id:
            return _disponibilites_prof(prof_id)
        qs = Disponibilite.objects.select_related('professeur', 'creneau').all()
        return JsonResponse([_disponibilite_data(d) for d in qs], safe=False)

    if request.method not in ('POST', 'PUT'):
        return _error('Méthode non autorisée.', 405)

    data = _body(request)
    prof = _get_or_none(Professeur, _value(data, 'professeur_id', 'professeur'))
    if not prof:
        return _error('Formateur introuvable.')

    # Remplacement global de la grille (bouton « Enregistrer »).
    raw = data.get('disponibilites')
    if isinstance(raw, list):
        creneaux_valides = set(Creneau.objects.values_list('id', flat=True))
        entrees = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            creneau_id = _int_or_none(_value(item, 'creneau_id', 'creneau'))
            etat = str(item.get('etat') or Disponibilite.ETAT_DISPONIBLE).strip().lower()
            if etat not in ETATS_DISPONIBILITE:
                etat = Disponibilite.ETAT_DISPONIBLE
            if creneau_id in creneaux_valides and etat != Disponibilite.ETAT_DISPONIBLE:
                entrees.append(Disponibilite(professeur=prof, creneau_id=creneau_id, etat=etat))

        with transaction.atomic():
            Disponibilite.objects.filter(professeur=prof).delete()
            if entrees:
                Disponibilite.objects.bulk_create(entrees)
        return _disponibilites_prof(prof.id)

    # Mise à jour d'un seul créneau.
    creneau = _get_or_none(Creneau, _value(data, 'creneau_id', 'creneau'))
    if not creneau:
        return _error('Créneau introuvable.')
    etat = str(data.get('etat') or Disponibilite.ETAT_DISPONIBLE).strip().lower()
    if etat not in ETATS_DISPONIBILITE:
        return _error('État de disponibilité invalide.')

    if etat == Disponibilite.ETAT_DISPONIBLE:
        Disponibilite.objects.filter(professeur=prof, creneau=creneau).delete()
        return JsonResponse({
            'professeur_id': prof.id,
            'creneau_id': creneau.id,
            'etat': Disponibilite.ETAT_DISPONIBLE,
        })

    dispo, created = Disponibilite.objects.update_or_create(
        professeur=prof, creneau=creneau, defaults={'etat': etat}
    )
    return JsonResponse(_disponibilite_data(dispo), status=201 if created else 200)


@csrf_exempt
def disponibilite_detail(request, pk):
    dispo = Disponibilite.objects.select_related('creneau', 'professeur').filter(pk=pk).first()
    if not dispo:
        return _error('Disponibilité introuvable.', 404)

    if request.method == 'GET':
        return JsonResponse(_disponibilite_data(dispo))

    if request.method in ('PUT', 'PATCH'):
        data = _body(request)
        etat = str(data.get('etat') or dispo.etat).strip().lower()
        if etat not in ETATS_DISPONIBILITE:
            return _error('État de disponibilité invalide.')
        dispo.etat = etat
        dispo.save(update_fields=['etat'])
        return JsonResponse(_disponibilite_data(dispo))

    if request.method == 'DELETE':
        dispo.delete()
        return JsonResponse({'success': True, 'message': 'Disponibilité supprimée.'})

    return _error('Méthode non autorisée.', 405)


# ─── CRUD : Affectations Module / Groupe / Formateur ─────────────────────────
@csrf_exempt
def affectations_collection(request):
    """GET /api/affectations — besoins d'enseignement (module, groupe, formateur).

    POST /api/affectations — crée ou met à jour un besoin. Le formateur est
    facultatif : sans lui, le besoin est « à pourvoir » ou « vacataire à recruter ».
    """
    if request.method == 'GET':
        qs = AffectationEnseignement.objects.select_related(
            'professeur', 'module', 'groupe__filiere'
        ).order_by(
            'groupe__code', 'module__code',
            F('professeur__nom_complet').asc(nulls_last=True),
        )

        prof_id = _int_or_none(request.GET.get('professeur_id'))
        module_id = _int_or_none(request.GET.get('module_id'))
        groupe_id = _int_or_none(request.GET.get('groupe_id'))
        statut = request.GET.get('statut')
        if prof_id:
            qs = qs.filter(professeur_id=prof_id)
        if module_id:
            qs = qs.filter(module_id=module_id)
        if groupe_id:
            qs = qs.filter(groupe_id=groupe_id)
        if statut in (
            AffectationEnseignement.STATUT_AFFECTE,
            AffectationEnseignement.STATUT_A_POURVOIR,
            AffectationEnseignement.STATUT_VACATAIRE,
        ):
            qs = qs.filter(statut=statut)

        return JsonResponse([_affectation_data(a) for a in qs], safe=False)

    if request.method != 'POST':
        return _error('Méthode non autorisée.', 405)

    data = _body(request)
    module = _get_or_none(Module, _value(data, 'module_id', 'module'))
    groupe = _get_or_none(Groupe, _value(data, 'groupe_id', 'groupe'))
    if not module:
        return _error('Module introuvable.')
    if not groupe:
        return _error('Groupe introuvable.')

    raw_prof = _value(data, 'professeur_id', 'professeur')
    prof = _get_or_none(Professeur, raw_prof)
    if raw_prof not in (None, '') and not prof:
        return _error('Formateur introuvable.')

    statut = _statut_besoin(data.get('statut'), prof)
    notes = str(data.get('notes') or '').strip()[:255]

    if prof:
        if AffectationEnseignement.objects.filter(
            module=module, groupe=groupe, professeur=prof
        ).exists():
            return _error('Ce formateur est déjà affecté à ce module pour ce groupe.')

        # Un besoin ouvert existant est complété plutôt que dupliqué.
        affectation = AffectationEnseignement.objects.filter(
            module=module, groupe=groupe, professeur__isnull=True
        ).first()
        if affectation:
            affectation.professeur = prof
            affectation.statut = AffectationEnseignement.STATUT_AFFECTE
            if notes:
                affectation.notes = notes
            affectation.save()
            created = False
        else:
            affectation = AffectationEnseignement.objects.create(
                professeur=prof,
                module=module,
                groupe=groupe,
                statut=AffectationEnseignement.STATUT_AFFECTE,
                notes=notes,
            )
            created = True
    else:
        affectation = AffectationEnseignement.objects.filter(
            module=module, groupe=groupe, professeur__isnull=True
        ).first()
        if affectation:
            affectation.statut = statut
            if notes:
                affectation.notes = notes
            affectation.save()
            created = False
        else:
            affectation = AffectationEnseignement.objects.create(
                professeur=None,
                module=module,
                groupe=groupe,
                statut=statut,
                notes=notes,
            )
            created = True

    _recompute_prof_modules(prof)
    return JsonResponse(
        _affectation_data(affectation),
        status=201 if created else 200,
    )


@csrf_exempt
def affectation_detail(request, pk):
    affectation = AffectationEnseignement.objects.select_related(
        'professeur', 'module', 'groupe__filiere'
    ).filter(pk=pk).first()
    if not affectation:
        return _error('Affectation introuvable.', 404)

    if request.method == 'GET':
        return JsonResponse(_affectation_data(affectation))

    if request.method in ('PUT', 'PATCH'):
        data = _body(request)
        module = _get_or_none(Module, _value(data, 'module_id', 'module')) \
            or affectation.module
        groupe = _get_or_none(Groupe, _value(data, 'groupe_id', 'groupe')) \
            or affectation.groupe

        # La présence de la clé professeur_id est significative : une valeur
        # nulle demande explicitement de retirer le formateur du besoin.
        prof_cle_presente = ('professeur_id' in data) or ('professeur' in data)
        if prof_cle_presente:
            raw_prof = data.get('professeur_id', data.get('professeur'))
            if raw_prof in (None, ''):
                prof = None
            else:
                prof = _get_or_none(Professeur, raw_prof)
                if not prof:
                    return _error('Formateur introuvable.')
        else:
            prof = affectation.professeur

        statut = _statut_besoin(
            data.get('statut', affectation.statut),
            prof,
        )
        notes = str(data.get('notes', affectation.notes) or '').strip()[:255]

        autres = AffectationEnseignement.objects.exclude(pk=affectation.pk).filter(
            module=module, groupe=groupe
        )
        if prof and autres.filter(professeur=prof).exists():
            return _error('Ce formateur est déjà affecté à ce module pour ce groupe.')
        if not prof and autres.filter(professeur__isnull=True).exists():
            return _error('Un besoin à pourvoir existe déjà pour ce couple module / groupe.')

        ancien_prof = affectation.professeur
        affectation.professeur = prof
        affectation.module = module
        affectation.groupe = groupe
        affectation.statut = statut
        affectation.notes = notes
        affectation.save()

        _recompute_prof_modules(prof)
        if ancien_prof and (not prof or ancien_prof.pk != prof.pk):
            _recompute_prof_modules(ancien_prof)
        affectation.refresh_from_db()
        return JsonResponse(_affectation_data(affectation))

    if request.method == 'DELETE':
        prof = affectation.professeur
        affectation.delete()
        _recompute_prof_modules(prof)
        return JsonResponse({'success': True, 'message': 'Affectation supprimée.'})

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
