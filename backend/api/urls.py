"""
Configuration des routes d'API REST (DRF et routes de compatibilité Frontend).
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ConnexionTokenView, RafraichirTokenView, ProfilUtilisateurView,
    GenerationViewSet, SeanceViewSet, ValiderSemaineView,
    ImportAvancementView, SemaineViewSet, GroupeViewSet,
    ProfesseurViewSet, SalleViewSet, CreneauViewSet,
    ModuleViewSet, DisponibiliteViewSet
)
from .compat_views import (
    health_check, get_semaines_compat, init_semaines_compat,
    get_creneaux_compat, get_types_salles_compat, get_unites_compat,
    get_emploi_du_temps_compat, get_stats_compat,
    generer_semaine_compat, valider_semaine_compat, vider_semaine_compat,
    groupes_collection, groupe_detail,
    professeurs_collection, professeur_detail,
    salles_collection, salle_detail,
    modules_collection, module_detail,
    filieres_collection, filiere_detail,
    secteurs_collection, secteur_detail,
)

router = DefaultRouter()
router.register(r'seances', SeanceViewSet, basename='seance')
router.register(r'semaines', SemaineViewSet, basename='semaine')
router.register(r'groupes', GroupeViewSet, basename='groupe')
router.register(r'professeurs', ProfesseurViewSet, basename='professeur')
router.register(r'salles', SalleViewSet, basename='salle')
router.register(r'creneaux', CreneauViewSet, basename='creneau')
router.register(r'modules', ModuleViewSet, basename='module')
router.register(r'disponibilites', DisponibiliteViewSet, basename='disponibilite')

urlpatterns = [
    # ─── Routes Directes pour le Dashboard React (Compatibilité Port 3001) ───
    path('health', health_check, name='compat_health'),
    path('health/', health_check),
    path('semaines', get_semaines_compat, name='compat_semaines'),
    path('init-semaines', init_semaines_compat, name='compat_init_semaines'),
    path('creneaux', get_creneaux_compat, name='compat_creneaux'),
    path('types-salles', get_types_salles_compat, name='compat_types_salles'),
    path('unites', get_unites_compat, name='compat_unites'),

    # ─── CRUD Séances (routes sans slash final utilisées par React) ──────────
    path('seances', SeanceViewSet.as_view({'get': 'list', 'post': 'create'}), name='compat_seances'),
    path('seances/<int:pk>', SeanceViewSet.as_view({
        'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
    }), name='compat_seance_detail'),

    # ─── CRUD Données de Base (sans slash final, format attendu par React) ───
    path('groupes', groupes_collection, name='compat_groupes'),
    path('groupes/<int:pk>', groupe_detail, name='compat_groupe_detail'),
    path('professeurs', professeurs_collection, name='compat_professeurs'),
    path('professeurs/<int:pk>', professeur_detail, name='compat_professeur_detail'),
    path('salles', salles_collection, name='compat_salles'),
    path('salles/<int:pk>', salle_detail, name='compat_salle_detail'),
    path('modules', modules_collection, name='compat_modules'),
    path('modules/<int:pk>', module_detail, name='compat_module_detail'),
    path('filieres', filieres_collection, name='compat_filieres'),
    path('filieres/<int:pk>', filiere_detail, name='compat_filiere_detail'),
    path('secteurs', secteurs_collection, name='compat_secteurs'),
    path('secteurs/<int:pk>', secteur_detail, name='compat_secteur_detail'),

    # ─── Emploi du temps, statistiques & actions ─────────────────────────────
    path('emploi-du-temps/<int:semaine_id>', get_emploi_du_temps_compat, name='compat_emploi_du_temps'),
    path('emploi-du-temps/<int:semaine_id>/', get_emploi_du_temps_compat),
    path('stats/<int:semaine_id>', get_stats_compat, name='compat_stats'),
    path('stats/<int:semaine_id>/', get_stats_compat),
    path('generer/<int:semaine_id>', generer_semaine_compat, name='compat_generer'),
    path('generer/<int:semaine_id>/', generer_semaine_compat),
    path('semaines/<int:semaine_id>/valider', valider_semaine_compat, name='compat_valider'),
    path('vider-semaine/<int:semaine_id>', vider_semaine_compat, name='compat_vider'),
    path('vider-semaine/<int:semaine_id>/', vider_semaine_compat),

    # ─── Authentification JWT & Profil ───────────────────────────────────────
    path('auth/connexion/', ConnexionTokenView.as_view(), name='token_obtain_pair'),
    path('auth/rafraichir/', RafraichirTokenView.as_view(), name='token_refresh'),
    path('auth/profil/', ProfilUtilisateurView.as_view(), name='profil_utilisateur'),

    # ─── Génération Automatique DRF ──────────────────────────────────────────
    path('generation/', GenerationViewSet.as_view({'get': 'list', 'post': 'create'}), name='generation_list_create'),
    path('generation/<int:pk>/', GenerationViewSet.as_view({'get': 'retrieve'}), name='generation_detail'),

    # ─── Validation Semaine DRF ──────────────────────────────────────────────
    path('semaines/<int:semaine_id>/valider/', ValiderSemaineView.as_view(), name='valider_semaine'),

    # ─── Import & Normalisation Excel / CSV ──────────────────────────────────
    path('import/', ImportAvancementView.as_view(), name='import_avancement'),

    # ─── DRF ViewSets Router ─────────────────────────────────────────────────
    path('', include(router.urls)),
]
