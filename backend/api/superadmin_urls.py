"""
Routes Super Admin pour la gestion des établissements, demandes d'adhésion et statistiques globales.
"""
from django.urls import path
from .superadmin_views import (
    etablissements_list, etablissement_detail,
    etablissement_activer, etablissement_desactiver, etablissement_suspendre,
    etablissement_stats, etablissement_admins, etablissement_admin_detail,
    stats_globales,
    soumettre_demande_abonnement, demandes_abonnement_list,
    demande_abonnement_detail, demande_abonnement_approuver,
    demande_abonnement_refuser,
)

urlpatterns = [
    # ─── Établissements ───
    path('etablissements', etablissements_list, name='sa_etablissements'),
    path('etablissements/<int:pk>', etablissement_detail, name='sa_etablissement_detail'),
    path('etablissements/<int:pk>/activer', etablissement_activer, name='sa_etablissement_activer'),
    path('etablissements/<int:pk>/desactiver', etablissement_desactiver, name='sa_etablissement_desactiver'),
    path('etablissements/<int:pk>/suspendre', etablissement_suspendre, name='sa_etablissement_suspendre'),
    path('etablissements/<int:pk>/stats', etablissement_stats, name='sa_etablissement_stats'),
    path('etablissements/<int:pk>/admins', etablissement_admins, name='sa_etablissement_admins'),
    path('etablissements/<int:pk>/admins/<int:user_id>', etablissement_admin_detail, name='sa_etablissement_admin_detail'),
    path('stats-globales', stats_globales, name='sa_stats_globales'),

    # ─── Demandes d'Abonnement ───
    path('demandes/soumettre', soumettre_demande_abonnement, name='sa_demandes_soumettre'),
    path('demandes', demandes_abonnement_list, name='sa_demandes_list'),
    path('demandes/<int:pk>', demande_abonnement_detail, name='sa_demande_detail'),
    path('demandes/<int:pk>/approuver', demande_abonnement_approuver, name='sa_demande_approuver'),
    path('demandes/<int:pk>/refuser', demande_abonnement_refuser, name='sa_demande_refuser'),
]
