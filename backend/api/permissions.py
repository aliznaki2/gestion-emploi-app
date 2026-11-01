"""
Permissions d'accès basées sur les rôles OFPPT :
Admin (Planificateur), Formateur (Professeur), Stagiaire.
"""
from rest_framework import permissions


class EstAdmin(permissions.BasePermission):
    """Accès réservé aux administrateurs et superutilisateurs."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_admin_role()
        )


class EstProfesseur(permissions.BasePermission):
    """Accès réservé aux formateurs."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_professeur_role()
        )


class EstStagiaire(permissions.BasePermission):
    """Accès réservé aux stagiaires."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_stagiaire_role()
        )


class EstAdminOuLectureSeule(permissions.BasePermission):
    """Lecture autorisée pour tous les utilisateurs authentifiés, écriture réservée aux admins."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_admin_role()


class SeancePermission(permissions.BasePermission):
    """
    Règle métier sur les séances :
    - Admin : Consultation et modification de tous les brouillons et séances validées.
    - Professeur : Consultation uniquement de ses propres séances VALIDÉES.
    - Stagiaire : Consultation uniquement des séances VALIDÉES de son groupe.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Seul l'administrateur peut créer, modifier ou supprimer des séances
        if request.method not in permissions.SAFE_METHODS:
            return request.user.is_admin_role()

        return True

    def has_object_permission(self, request, view, obj):
        # Modifications réservées aux admins
        if request.method not in permissions.SAFE_METHODS:
            return request.user.is_admin_role()

        # Lecture
        user = request.user
        if user.is_admin_role():
            return True

        # Les professeurs et stagiaires ne peuvent voir QUE les séances validées
        if obj.statut != 'valide':
            return False

        if user.is_professeur_role():
            prof = getattr(user, 'professeur', None)
            if not prof:
                return False
            return obj.professeur_id == prof.id or obj.seance_professeurs.filter(professeur=prof).exists()

        # Pour les stagiaires : visibilité des séances validées
        return True

