"""
API views pour le Super Administrateur — gestion des établissements (tenants),
des comptes administrateurs, des demandes d'adhésion et des statistiques globales.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count, Q
from django.utils import timezone

from core.models import (
    Etablissement, Utilisateur, Professeur, Groupe, Salle, Module,
    Secteur, Seance, AnneeScolaire, DemandeAbonnement,
)


# ─── Permission ───────────────────────────────────────────────────────────────
class EstSuperAdmin(IsAuthenticated):
    """Accès réservé aux super administrateurs."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.is_super_admin()

# En mode dev / compatibilité sans JWT obligatoire côté frontend
SUPERADMIN_PERM = [AllowAny]


# ─── Serialization helpers ────────────────────────────────────────────────────
def _serialize_etablissement(e):
    return {
        'id': e.id,
        'code': e.code,
        'nom': e.nom,
        'nom_court': e.nom_court,
        'ville': e.ville,
        'quartier': e.quartier,
        'adresse': e.adresse,
        'email': e.email,
        'telephone': e.telephone,
        'site_web': e.site_web,
        'couleur_accent': e.couleur_accent,
        'actif': e.actif,
        'suspendu': e.suspendu,
        'max_formateurs': e.max_formateurs,
        'max_groupes': e.max_groupes,
        'date_creation': e.date_creation.isoformat() if e.date_creation else None,
        'date_modification': e.date_modification.isoformat() if e.date_modification else None,
        'est_accessible': e.est_accessible,
    }


def _serialize_admin(u):
    return {
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'first_name': u.first_name,
        'last_name': u.last_name,
        'nom_complet': f"{u.first_name} {u.last_name}".strip() or u.username,
        'is_active': u.is_active,
        'role': u.role,
        'date_joined': u.date_joined.isoformat() if u.date_joined else None,
    }


def _serialize_demande(d):
    return {
        'id': d.id,
        'nom_etablissement': d.nom_etablissement,
        'ville': d.ville,
        'nom_contact': d.nom_contact,
        'role_contact': d.role_contact,
        'email': d.email,
        'telephone': d.telephone,
        'message': d.message,
        'statut': d.statut,
        'date_demande': d.date_demande.isoformat() if d.date_demande else None,
        'date_traitement': d.date_traitement.isoformat() if d.date_traitement else None,
        'notes_admin': d.notes_admin,
        'etablissement_cree_id': d.etablissement_cree_id,
        'etablissement_cree_nom': d.etablissement_cree.nom if d.etablissement_cree else None,
    }


# ─── CRUD Établissements ──────────────────────────────────────────────────────
@api_view(['GET', 'POST'])
@permission_classes(SUPERADMIN_PERM)
def etablissements_list(request):
    """
    GET: Liste tous les établissements avec compteurs résumés.
    POST: Crée un nouvel établissement.
    """
    if request.method == 'GET':
        qs = Etablissement.objects.annotate(
            nb_formateurs=Count('professeurs', distinct=True),
            nb_groupes=Count('groupes', distinct=True),
            nb_salles=Count('salles', distinct=True),
        )
        data = []
        for e in qs:
            item = _serialize_etablissement(e)
            item['stats'] = {
                'nb_formateurs': getattr(e, 'nb_formateurs', 0),
                'nb_groupes': getattr(e, 'nb_groupes', 0),
                'nb_salles': getattr(e, 'nb_salles', 0),
                'nb_admins': Utilisateur.objects.filter(etablissement=e, role='admin').count(),
            }
            data.append(item)
        return Response(data)

    # POST
    data = request.data
    code = data.get('code', '').strip().upper()
    nom = data.get('nom', '').strip()
    if not code or not nom:
        return Response(
            {'error': 'Les champs "code" et "nom" sont obligatoires.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if Etablissement.objects.filter(code=code).exists():
        return Response(
            {'error': f'Un établissement avec le code "{code}" existe déjà.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    etab = Etablissement.objects.create(
        code=code,
        nom=nom,
        nom_court=data.get('nom_court', '').strip(),
        ville=data.get('ville', '').strip(),
        quartier=data.get('quartier', '').strip(),
        adresse=data.get('adresse', '').strip(),
        email=data.get('email', '').strip(),
        telephone=data.get('telephone', '').strip(),
        site_web=data.get('site_web', '').strip(),
        couleur_accent=data.get('couleur_accent', '#1a5fa8').strip(),
        max_formateurs=data.get('max_formateurs', 100),
        max_groupes=data.get('max_groupes', 50),
    )
    return Response(_serialize_etablissement(etab), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes(SUPERADMIN_PERM)
def etablissement_detail(request, pk):
    """Consulter, modifier ou supprimer un établissement."""
    try:
        etab = Etablissement.objects.get(pk=pk)
    except Etablissement.DoesNotExist:
        return Response({'error': 'Établissement introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(_serialize_etablissement(etab))

    if request.method in ('PUT', 'PATCH'):
        data = request.data
        for field in [
            'nom', 'nom_court', 'ville', 'quartier', 'adresse',
            'email', 'telephone', 'site_web', 'couleur_accent',
            'max_formateurs', 'max_groupes',
        ]:
            if field in data:
                setattr(etab, field, data[field])
        if 'code' in data and data['code'].strip().upper() != etab.code:
            new_code = data['code'].strip().upper()
            if Etablissement.objects.filter(code=new_code).exclude(pk=etab.pk).exists():
                return Response({'error': f'Le code "{new_code}" est déjà utilisé.'}, status=status.HTTP_400_BAD_REQUEST)
            etab.code = new_code
        etab.save()
        return Response(_serialize_etablissement(etab))

    # DELETE
    etab.delete()
    return Response({'ok': True, 'message': 'Établissement supprimé.'})


# ─── Actions État Établissement ───────────────────────────────────────────────
@api_view(['POST'])
@permission_classes(SUPERADMIN_PERM)
def etablissement_activer(request, pk):
    try:
        etab = Etablissement.objects.get(pk=pk)
    except Etablissement.DoesNotExist:
        return Response({'error': 'Établissement introuvable.'}, status=status.HTTP_404_NOT_FOUND)
    etab.actif = True
    etab.suspendu = False
    etab.save()
    return Response({'ok': True, 'actif': True, 'suspendu': False})


@api_view(['POST'])
@permission_classes(SUPERADMIN_PERM)
def etablissement_desactiver(request, pk):
    try:
        etab = Etablissement.objects.get(pk=pk)
    except Etablissement.DoesNotExist:
        return Response({'error': 'Établissement introuvable.'}, status=status.HTTP_404_NOT_FOUND)
    etab.actif = False
    etab.save()
    return Response({'ok': True, 'actif': False, 'suspendu': etab.suspendu})


@api_view(['POST'])
@permission_classes(SUPERADMIN_PERM)
def etablissement_suspendre(request, pk):
    try:
        etab = Etablissement.objects.get(pk=pk)
    except Etablissement.DoesNotExist:
        return Response({'error': 'Établissement introuvable.'}, status=status.HTTP_404_NOT_FOUND)
    etab.suspendu = True
    etab.save()
    return Response({'ok': True, 'suspendu': True})


# ─── Statistiques Établissement ───────────────────────────────────────────────
@api_view(['GET'])
@permission_classes(SUPERADMIN_PERM)
def etablissement_stats(request, pk):
    """Statistiques détaillées pour un établissement."""
    try:
        etab = Etablissement.objects.get(pk=pk)
    except Etablissement.DoesNotExist:
        return Response({'error': 'Établissement introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    stats = {
        'etablissement': _serialize_etablissement(etab),
        'nb_formateurs': Professeur.objects.filter(etablissement=etab).count(),
        'nb_formateurs_permanents': Professeur.objects.filter(etablissement=etab, statut='permanent').count(),
        'nb_formateurs_vacataires': Professeur.objects.filter(etablissement=etab, statut='vacataire').count(),
        'nb_groupes': Groupe.objects.filter(etablissement=etab).count(),
        'nb_salles': Salle.objects.filter(etablissement=etab).count(),
        'nb_salles_actives': Salle.objects.filter(etablissement=etab, actif=True).count(),
        'nb_modules': Module.objects.filter(etablissement=etab).count(),
        'nb_secteurs': Secteur.objects.filter(etablissement=etab).count(),
        'nb_admins': Utilisateur.objects.filter(etablissement=etab, role='admin').count(),
        'nb_utilisateurs': Utilisateur.objects.filter(etablissement=etab).count(),
    }
    return Response(stats)


# ─── Gestion des Admins par Établissement ─────────────────────────────────────
@api_view(['GET', 'POST'])
@permission_classes(SUPERADMIN_PERM)
def etablissement_admins(request, pk):
    """GET: liste des admins. POST: créer un nouvel admin."""
    try:
        etab = Etablissement.objects.get(pk=pk)
    except Etablissement.DoesNotExist:
        return Response({'error': 'Établissement introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        admins = Utilisateur.objects.filter(etablissement=etab, role='admin')
        return Response([_serialize_admin(a) for a in admins])

    # POST — créer un admin
    data = request.data
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return Response(
            {'error': 'Les champs "username" et "password" sont obligatoires.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if Utilisateur.objects.filter(username=username).exists():
        return Response(
            {'error': f'Le nom d\'utilisateur "{username}" est déjà pris.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user = Utilisateur.objects.create_user(
        username=username,
        password=password,
        email=data.get('email', ''),
        first_name=data.get('first_name', ''),
        last_name=data.get('last_name', ''),
        role='admin',
        etablissement=etab,
    )
    return Response(_serialize_admin(user), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes(SUPERADMIN_PERM)
def etablissement_admin_detail(request, pk, user_id):
    """Consulter, modifier (email, mot de passe, etc.) ou supprimer un admin d'un établissement."""
    try:
        etab = Etablissement.objects.get(pk=pk)
    except Etablissement.DoesNotExist:
        return Response({'error': 'Établissement introuvable.'}, status=status.HTTP_404_NOT_FOUND)
    try:
        user = Utilisateur.objects.get(pk=user_id, etablissement=etab, role='admin')
    except Utilisateur.DoesNotExist:
        return Response({'error': 'Admin introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(_serialize_admin(user))

    if request.method in ('PUT', 'PATCH'):
        data = request.data
        if 'email' in data:
            user.email = data['email'].strip()
        if 'first_name' in data:
            user.first_name = data['first_name'].strip()
        if 'last_name' in data:
            user.last_name = data['last_name'].strip()
        if 'username' in data and data['username'].strip():
            new_username = data['username'].strip()
            if new_username != user.username and Utilisateur.objects.filter(username=new_username).exists():
                return Response({'error': f'Le nom d\'utilisateur "{new_username}" est déjà pris.'}, status=status.HTTP_400_BAD_REQUEST)
            user.username = new_username
        if 'password' in data and data['password'].strip():
            user.set_password(data['password'].strip())
        if 'is_active' in data:
            user.is_active = bool(data['is_active'])

        user.save()
        return Response(_serialize_admin(user))

    # DELETE
    user.delete()
    return Response({'ok': True})


# ─── Demandes d'Abonnement / Inscription ──────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def soumettre_demande_abonnement(request):
    """Endpoint public pour soumettre une demande d'abonnement / adhésion."""
    data = request.data
    nom_etablissement = data.get('nom_etablissement', '').strip()
    ville = data.get('ville', '').strip()
    nom_contact = data.get('nom_contact', '').strip()
    email = data.get('email', '').strip()

    if not nom_etablissement or not ville or not nom_contact or not email:
        return Response(
            {'error': "Les champs nom de l'établissement, ville, nom du contact et email sont obligatoires."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    demande = DemandeAbonnement.objects.create(
        nom_etablissement=nom_etablissement,
        ville=ville,
        nom_contact=nom_contact,
        role_contact=data.get('role_contact', '').strip(),
        email=email,
        telephone=data.get('telephone', '').strip(),
        message=data.get('message', '').strip(),
    )
    return Response({
        'ok': True,
        'message': 'Votre demande a été envoyée avec succès. L\'équipe vous contactera très rapidement.',
        'demande': _serialize_demande(demande),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes(SUPERADMIN_PERM)
def demandes_abonnement_list(request):
    """Liste de toutes les demandes avec filtres et compteurs."""
    statut_filter = request.GET.get('statut')
    qs = DemandeAbonnement.objects.all().order_by('-date_demande')
    if statut_filter in ('en_attente', 'approuvee', 'refusee'):
        qs = qs.filter(statut=statut_filter)

    counts = {
        'total': DemandeAbonnement.objects.count(),
        'en_attente': DemandeAbonnement.objects.filter(statut='en_attente').count(),
        'approuvee': DemandeAbonnement.objects.filter(statut='approuvee').count(),
        'refusee': DemandeAbonnement.objects.filter(statut='refusee').count(),
    }
    return Response({
        'counts': counts,
        'demandes': [_serialize_demande(d) for d in qs],
    })


@api_view(['GET', 'DELETE'])
@permission_classes(SUPERADMIN_PERM)
def demande_abonnement_detail(request, pk):
    """Consulter ou supprimer une demande d'abonnement."""
    try:
        demande = DemandeAbonnement.objects.get(pk=pk)
    except DemandeAbonnement.DoesNotExist:
        return Response({'error': 'Demande introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(_serialize_demande(demande))

    demande.delete()
    return Response({'ok': True, 'message': 'Demande supprimée.'})


@api_view(['POST'])
@permission_classes(SUPERADMIN_PERM)
def demande_abonnement_approuver(request, pk):
    """
    Approuver une demande :
    - Marque la demande approuvée.
    - Crée optionnellement l'établissement et son compte administrateur local.
    """
    try:
        demande = DemandeAbonnement.objects.get(pk=pk)
    except DemandeAbonnement.DoesNotExist:
        return Response({'error': 'Demande introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    data = request.data
    creer_etab = data.get('creer_etablissement', True)
    code = data.get('code', '').strip().upper()
    admin_username = data.get('admin_username', '').strip()
    admin_password = data.get('admin_password', 'Admin2026*').strip()
    notes = data.get('notes_admin', '').strip()

    etab = None
    if creer_etab:
        if not code:
            base_code = ''.join(c for c in demande.nom_etablissement if c.isalnum()).upper()[:6] or 'ETAB'
            code = base_code
            suffix = 1
            while Etablissement.objects.filter(code=code).exists():
                code = f"{base_code[:4]}{suffix}"
                suffix += 1

        if not Etablissement.objects.filter(code=code).exists():
            etab = Etablissement.objects.create(
                code=code,
                nom=demande.nom_etablissement,
                nom_court=demande.nom_etablissement[:30],
                ville=demande.ville,
                email=demande.email,
                telephone=demande.telephone,
                actif=True,
            )
        else:
            etab = Etablissement.objects.get(code=code)

        if admin_username and not Utilisateur.objects.filter(username=admin_username).exists():
            Utilisateur.objects.create_user(
                username=admin_username,
                password=admin_password,
                email=demande.email,
                first_name=demande.nom_contact,
                role='admin',
                etablissement=etab,
            )

    demande.statut = 'approuvee'
    demande.date_traitement = timezone.now()
    if notes:
        demande.notes_admin = notes
    if etab:
        demande.etablissement_cree = etab
    demande.save()

    return Response({
        'ok': True,
        'message': f"Demande approuvée avec succès. Établissement {etab.nom if etab else ''} activé.",
        'demande': _serialize_demande(demande),
    })


@api_view(['POST'])
@permission_classes(SUPERADMIN_PERM)
def demande_abonnement_refuser(request, pk):
    """Refuser une demande d'abonnement avec motif."""
    try:
        demande = DemandeAbonnement.objects.get(pk=pk)
    except DemandeAbonnement.DoesNotExist:
        return Response({'error': 'Demande introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    notes = request.data.get('notes_admin', '').strip()
    demande.statut = 'refusee'
    demande.date_traitement = timezone.now()
    if notes:
        demande.notes_admin = notes
    demande.save()

    return Response({
        'ok': True,
        'message': 'Demande refusée.',
        'demande': _serialize_demande(demande),
    })


# ─── Stats Globales ───────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes(SUPERADMIN_PERM)
def stats_globales(request):
    """Statistiques globales de la plateforme."""
    return Response({
        'nb_etablissements': Etablissement.objects.count(),
        'nb_etablissements_actifs': Etablissement.objects.filter(actif=True, suspendu=False).count(),
        'nb_etablissements_suspendus': Etablissement.objects.filter(suspendu=True).count(),
        'nb_etablissements_inactifs': Etablissement.objects.filter(actif=False).count(),
        'nb_demandes_en_attente': DemandeAbonnement.objects.filter(statut='en_attente').count(),
        'nb_demandes_total': DemandeAbonnement.objects.count(),
        'nb_formateurs_total': Professeur.objects.count(),
        'nb_groupes_total': Groupe.objects.count(),
        'nb_salles_total': Salle.objects.count(),
        'nb_utilisateurs_total': Utilisateur.objects.count(),
    })
