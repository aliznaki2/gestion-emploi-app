"""
Django Admin configuration for core OFPPT models.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Utilisateur, Secteur, Filiere, Groupe, TypeSalle, Salle,
    Module, AnneeScolaire, Semestre, Semaine, Professeur,
    Creneau, Disponibilite, UniteEnseignement, UniteGroupe,
    VolumeHoraire, UniteProfesseur, Passage, TacheGeneration,
    Journal, Seance, SeanceGroupe, SeanceProfesseur,
)


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Rôle Métier', {'fields': ('role', 'telephone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rôle Métier', {'fields': ('role', 'telephone')}),
    )


@admin.register(Secteur)
class SecteurAdmin(admin.ModelAdmin):
    list_display = ('code', 'intitule')
    search_fields = ('code', 'intitule')


@admin.register(Filiere)
class FiliereAdmin(admin.ModelAdmin):
    list_display = ('code', 'intitule', 'secteur', 'niveau')
    list_filter = ('secteur', 'niveau')
    search_fields = ('code', 'intitule')


@admin.register(Groupe)
class GroupeAdmin(admin.ModelAdmin):
    list_display = ('code', 'filiere', 'annee_etude', 'effectif', 'mode_formation', 'actif')
    list_filter = ('filiere', 'annee_etude', 'mode_formation', 'actif')
    search_fields = ('code',)


@admin.register(TypeSalle)
class TypeSalleAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle')


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):
    list_display = ('nom', 'type_salle', 'capacite', 'actif', 'est_virtuelle')
    list_filter = ('type_salle', 'actif')
    search_fields = ('nom',)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('code', 'intitule', 'type_module', 'regional')
    list_filter = ('type_module', 'regional')
    search_fields = ('code', 'intitule')
    filter_horizontal = ('types_salles_compatibles',)


@admin.register(AnneeScolaire)
class AnneeScolaireAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'date_debut', 'date_fin', 'active')
    list_filter = ('active',)


@admin.register(Semestre)
class SemestreAdmin(admin.ModelAdmin):
    list_display = ('numero', 'annee_scolaire', 'date_debut', 'date_fin')
    list_filter = ('annee_scolaire',)


@admin.register(Semaine)
class SemaineAdmin(admin.ModelAdmin):
    list_display = ('numero', 'annee_scolaire', 'semestre', 'date_debut', 'date_fin', 'active')
    list_filter = ('annee_scolaire', 'semestre', 'active')
    search_fields = ('numero',)


@admin.register(Professeur)
class ProfesseurAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'nom_complet', 'statut', 'heures_max_semaine', 'salle_preferee', 'actif')
    list_filter = ('statut', 'actif')
    search_fields = ('matricule', 'nom_complet')


@admin.register(Creneau)
class CreneauAdmin(admin.ModelAdmin):
    list_display = ('jour', 'numero_seance', 'heure_debut', 'heure_fin', 'duree_h', 'periode')
    list_filter = ('jour', 'numero_seance')


@admin.register(Disponibilite)
class DisponibiliteAdmin(admin.ModelAdmin):
    list_display = ('professeur', 'creneau', 'etat')
    list_filter = ('etat', 'creneau__jour', 'creneau__numero_seance')
    search_fields = ('professeur__nom_complet', 'professeur__matricule')


class UniteGroupeInline(admin.TabularInline):
    model = UniteGroupe
    extra = 1


class UniteProfesseurInline(admin.TabularInline):
    model = UniteProfesseur
    extra = 1


class VolumeHoraireInline(admin.StackedInline):
    model = VolumeHoraire
    extra = 0


@admin.register(UniteEnseignement)
class UniteEnseignementAdmin(admin.ModelAdmin):
    list_display = ('id', 'module', 'annee_scolaire', 'semestre', 'code_fusion')
    list_filter = ('annee_scolaire', 'semestre', 'module__type_module')
    search_fields = ('module__code', 'module__intitule', 'code_fusion')
    inlines = [UniteGroupeInline, UniteProfesseurInline, VolumeHoraireInline]


@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = ('unite', 'semaine_debut', 'semaine_fin', 'intensite_h', 'actif')
    list_filter = ('actif', 'intensite_h')


class JournalInline(admin.TabularInline):
    model = Journal
    extra = 0
    readonly_fields = ('niveau', 'message', 'horodatage')


@admin.register(TacheGeneration)
class TacheGenerationAdmin(admin.ModelAdmin):
    list_display = ('id', 'semaine', 'statut', 'score_penalite', 'temps_resolution_ms', 'date_debut', 'date_fin')
    list_filter = ('statut', 'semaine')
    inlines = [JournalInline]


class SeanceGroupeInline(admin.TabularInline):
    model = SeanceGroupe
    extra = 0


class SeanceProfesseurInline(admin.TabularInline):
    model = SeanceProfesseur
    extra = 0


@admin.register(Seance)
class SeanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'unite', 'semaine', 'creneau', 'salle', 'professeur', 'mode', 'nature', 'statut', 'verrouillee')
    list_filter = ('semaine', 'statut', 'mode', 'nature', 'verrouillee', 'creneau__jour')
    search_fields = ('unite__module__code', 'salle__nom', 'professeur__nom_complet')
    inlines = [SeanceGroupeInline, SeanceProfesseurInline]


@admin.register(SeanceGroupe)
class SeanceGroupeAdmin(admin.ModelAdmin):
    list_display = ('seance', 'groupe', 'semaine', 'creneau')
    list_filter = ('semaine', 'groupe')


@admin.register(SeanceProfesseur)
class SeanceProfesseurAdmin(admin.ModelAdmin):
    list_display = ('seance', 'professeur', 'semaine', 'creneau')
    list_filter = ('semaine', 'professeur')

