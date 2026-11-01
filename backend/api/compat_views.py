"""
Vues de compatibilité directe avec le frontend React (Dashboard.jsx).
Permet au frontend React existant d'interagir immédiatement avec le backend Django
sans modifier les chemins d'URL ni le format des données JSON attendues.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.db.models import Count

from core.models import (
    Semaine, Groupe, Professeur, Salle, Creneau,
    UniteEnseignement, Filiere, TypeSalle, Seance,
    SeanceGroupe, SeanceProfesseur, AnneeScolaire, Semestre
)
from solver.services import GenerateurEmploiDuTemps


def health_check(request):
    """GET /api/health"""
    return JsonResponse({'status': 'ok', 'backend': 'Django 5.x / OR-Tools CP-SAT'})


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
    annee = AnneeScolaire.objects.filter(active=True).first()
    if not annee:
        annee = AnneeScolaire.objects.first()
    s1 = Semestre.objects.filter(annee_scolaire=annee, numero=1).first() if annee else None

    for num in range(1, 17):
        Semaine.objects.get_or_create(
            annee_scolaire=annee,
            numero=num,
            defaults={'semestre': s1, 'active': True}
        )
    return JsonResponse({'message': '16 semaines initialisées avec succès'})


def get_groupes_compat(request):
    """GET /api/groupes"""
    groupes = Groupe.objects.select_related('filiere').all().order_by('code')
    data = [
        {
            'id': g.id,
            'code': g.code,
            'filiere_id': g.filiere_id,
            'filiere_code': g.filiere.code,
            'filiere_nom': g.filiere.intitule,
            'annee_etude': g.annee_etude,
            'effectif': g.effectif,
            'mode_formation': g.mode_formation,
            'actif': g.actif,
        }
        for g in groupes
    ]
    return JsonResponse(data, safe=False)


def get_professeurs_compat(request):
    """GET /api/professeurs"""
    profs = Professeur.objects.select_related('salle_preferee').all().order_by('nom_complet')
    data = [
        {
            'id': p.id,
            'matricule': p.matricule,
            'nom_complet': p.nom_complet,
            'statut': p.statut,
            'heures_max_semaine': float(p.heures_max_semaine),
            'salle_preferee_id': p.salle_preferee_id,
            'salle_preferee_nom': p.salle_preferee.nom if p.salle_preferee else None,
            'actif': p.actif,
        }
        for p in profs
    ]
    return JsonResponse(data, safe=False)


def get_salles_compat(request):
    """GET /api/salles"""
    salles = Salle.objects.select_related('type_salle').all().order_by('nom')
    data = [
        {
            'id': s.id,
            'nom': s.nom,
            'capacite': s.capacite,
            'actif': s.actif,
            'type_salle_id': s.type_salle_id,
            'type_code': s.type_salle.code,
            'type_salle_libelle': s.type_salle.libelle,
        }
        for s in salles
    ]
    return JsonResponse(data, safe=False)


def get_creneaux_compat(request):
    """GET /api/creneaux"""
    creneaux = Creneau.objects.all().order_by('jour', 'numero_seance')
    data = [
        {
            'id': c.id,
            'jour': c.jour,
            'numero_seance': c.numero_seance,
            'heure_debut': c.heure_debut.strftime('%H:%M:%S'),
            'heure_fin': c.heure_fin.strftime('%H:%M:%S'),
            'duree_h': float(c.duree_h),
            'periode': c.periode,
        }
        for c in creneaux
    ]
    return JsonResponse(data, safe=False)


def get_filieres_compat(request):
    """GET /api/filieres"""
    filieres = Filiere.objects.select_related('secteur').all().order_by('code')
    data = [
        {
            'id': f.id,
            'code': f.code,
            'intitule': f.intitule,
            'secteur_id': f.secteur_id,
            'secteur_nom': f.secteur.intitule,
            'niveau': f.niveau,
        }
        for f in filieres
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
        data.append({
            'id': u.id,
            'code_fusion': u.code_fusion,
            'module_code': u.module.code,
            'module_intitule': u.module.intitule,
            'type_module': u.module.type_module,
            'filiere_code': filiere.code if filiere else '',
            'prof_nom': prof.nom_complet if prof else '',
            'groupes': [{'id': ug.groupe.id, 'code': ug.groupe.code} for ug in u.unite_groupes.all()],
        })
    return JsonResponse(data, safe=False)


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
    generateur = GenerateurEmploiDuTemps(semaine_id=semaine_id)
    res = generateur.executer(max_time_seconds=60)
    return JsonResponse(res, status=200 if res['succes'] else 422)


@csrf_exempt
def valider_semaine_compat(request, semaine_id):
    """POST /api/semaines/<semaine_id>/valider"""
    nb = Seance.objects.filter(semaine_id=semaine_id, statut='brouillon').update(statut='valide')
    return JsonResponse({
        'succes': True,
        'message': f'{nb} séance(s) validée(s) avec succès.',
    })


@csrf_exempt
def vider_semaine_compat(request, semaine_id):
    """POST /api/vider-semaine/<semaine_id>"""
    nb, _ = Seance.objects.filter(semaine_id=semaine_id, verrouillee=False).delete()
    return JsonResponse({
        'succes': True,
        'message': f'{nb} séance(s) supprimée(s).',
    })

