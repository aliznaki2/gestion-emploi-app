"""
Sérialiseurs Django REST Framework pour l'application OFPPT.
"""
from rest_framework import serializers
from core.models import (
    Utilisateur, Secteur, Filiere, Groupe, TypeSalle, Salle,
    Module, AnneeScolaire, Semestre, Semaine, Professeur,
    Creneau, Disponibilite, UniteEnseignement, VolumeHoraire,
    Passage, TacheGeneration, Journal, Seance, SeanceGroupe,
    SeanceProfesseur
)


# ─── Utilisateur ───────────────────────────────────────────────────────────────
class UtilisateurSerializer(serializers.ModelSerializer):
    professeur_id = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'telephone', 'professeur_id'
        ]
        read_only_fields = ['id', 'professeur_id']

    def get_professeur_id(self, obj):
        prof = getattr(obj, 'professeur', None)
        return prof.id if prof else None


# ─── Données de Base ──────────────────────────────────────────────────────────
class SecteurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Secteur
        fields = '__all__'


class FiliereSerializer(serializers.ModelSerializer):
    secteur_nom = serializers.ReadOnlyField(source='secteur.intitule')

    class Meta:
        model = Filiere
        fields = ['id', 'code', 'intitule', 'secteur', 'secteur_nom', 'niveau']


class GroupeSerializer(serializers.ModelSerializer):
    filiere_code = serializers.ReadOnlyField(source='filiere.code')
    filiere_nom = serializers.ReadOnlyField(source='filiere.intitule')

    class Meta:
        model = Groupe
        fields = [
            'id', 'code', 'filiere', 'filiere_code', 'filiere_nom',
            'annee_etude', 'effectif', 'mode_formation', 'actif'
        ]


class TypeSalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeSalle
        fields = '__all__'


class SalleSerializer(serializers.ModelSerializer):
    type_salle_code = serializers.ReadOnlyField(source='type_salle.code')
    type_salle_libelle = serializers.ReadOnlyField(source='type_salle.libelle')
    est_virtuelle = serializers.ReadOnlyField()

    class Meta:
        model = Salle
        fields = [
            'id', 'nom', 'type_salle', 'type_salle_code', 'type_salle_libelle',
            'capacite', 'actif', 'est_virtuelle'
        ]


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'code', 'intitule', 'type_module', 'regional', 'types_salles_compatibles']


class AnneeScolaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnneeScolaire
        fields = '__all__'


class SemestreSerializer(serializers.ModelSerializer):
    annee_libelle = serializers.ReadOnlyField(source='annee_scolaire.libelle')

    class Meta:
        model = Semestre
        fields = ['id', 'annee_scolaire', 'annee_libelle', 'numero', 'date_debut', 'date_fin']


class SemaineSerializer(serializers.ModelSerializer):
    annee_libelle = serializers.ReadOnlyField(source='annee_scolaire.libelle')
    semestre_numero = serializers.ReadOnlyField(source='semestre.numero')
    nb_seances = serializers.SerializerMethodField()

    class Meta:
        model = Semaine
        fields = [
            'id', 'annee_scolaire', 'annee_libelle', 'semestre', 'semestre_numero',
            'numero', 'date_debut', 'date_fin', 'active', 'nb_seances'
        ]

    def get_nb_seances(self, obj):
        return obj.seances.count()


class CreneauSerializer(serializers.ModelSerializer):
    periode = serializers.ReadOnlyField()
    jour_nom = serializers.CharField(source='get_jour_display', read_only=True)

    class Meta:
        model = Creneau
        fields = ['id', 'jour', 'jour_nom', 'numero_seance', 'heure_debut', 'heure_fin', 'duree_h', 'periode']


class ProfesseurSerializer(serializers.ModelSerializer):
    salle_preferee_nom = serializers.ReadOnlyField(source='salle_preferee.nom')

    class Meta:
        model = Professeur
        fields = [
            'id', 'matricule', 'nom_complet', 'utilisateur', 'statut',
            'heures_max_semaine', 'taux_presence', 'salle_preferee',
            'salle_preferee_nom', 'actif'
        ]


class DisponibiliteSerializer(serializers.ModelSerializer):
    creneau_details = CreneauSerializer(source='creneau', read_only=True)

    class Meta:
        model = Disponibilite
        fields = ['id', 'professeur', 'creneau', 'creneau_details', 'etat']


# ─── Unités Pédagogiques & Volumes ───────────────────────────────────────────
class VolumeHoraireSerializer(serializers.ModelSerializer):
    heures_restantes = serializers.ReadOnlyField()

    class Meta:
        model = VolumeHoraire
        fields = [
            'id', 'unite', 'h_total', 'h_presentiel', 'h_synchrone',
            'h_asynchrone', 'heures_effectuees', 'heures_restantes'
        ]


class PassageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Passage
        fields = '__all__'


class UniteEnseignementSerializer(serializers.ModelSerializer):
    module_details = ModuleSerializer(source='module', read_only=True)
    volume_horaire = VolumeHoraireSerializer(read_only=True)
    groupes = serializers.SerializerMethodField()
    professeurs = serializers.SerializerMethodField()

    class Meta:
        model = UniteEnseignement
        fields = [
            'id', 'module', 'module_details', 'annee_scolaire', 'semestre',
            'code_fusion', 'volume_horaire', 'groupes', 'professeurs'
        ]

    def get_groupes(self, obj):
        return [{'id': g.id, 'code': g.code} for g in Groupe.objects.filter(groupe_unites__unite=obj)]

    def get_professeurs(self, obj):
        return [
            {'id': p.id, 'nom_complet': p.nom_complet, 'matricule': p.matricule}
            for p in Professeur.objects.filter(professeur_unites__unite=obj)
        ]


# ─── Tâches de Génération & Logs ─────────────────────────────────────────────
class JournalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Journal
        fields = ['id', 'tache', 'niveau', 'message', 'horodatage']


class TacheGenerationSerializer(serializers.ModelSerializer):
    semaine_numero = serializers.ReadOnlyField(source='semaine.numero')
    journaux = JournalSerializer(many=True, read_only=True)
    cree_par_nom = serializers.ReadOnlyField(source='cree_par.username')

    class Meta:
        model = TacheGeneration
        fields = [
            'id', 'semaine', 'semaine_numero', 'semestre', 'statut',
            'message', 'temps_resolution_ms', 'score_penalite',
            'cree_par', 'cree_par_nom', 'date_debut', 'date_fin', 'journaux'
        ]


# ─── Séances & Emplois du Temps ───────────────────────────────────────────────
class SeanceGroupeSerializer(serializers.ModelSerializer):
    groupe_code = serializers.ReadOnlyField(source='groupe.code')

    class Meta:
        model = SeanceGroupe
        fields = ['id', 'seance', 'groupe', 'groupe_code', 'semaine', 'creneau']


class SeanceProfesseurSerializer(serializers.ModelSerializer):
    professeur_nom = serializers.ReadOnlyField(source='professeur.nom_complet')

    class Meta:
        model = SeanceProfesseur
        fields = ['id', 'seance', 'professeur', 'professeur_nom', 'semaine', 'creneau']


class SeanceSerializer(serializers.ModelSerializer):
    module_code = serializers.ReadOnlyField(source='unite.module.code')
    module_intitule = serializers.ReadOnlyField(source='unite.module.intitule')
    module_type = serializers.ReadOnlyField(source='unite.module.type_module')
    salle_nom = serializers.ReadOnlyField(source='salle.nom')
    professeur_nom = serializers.ReadOnlyField(source='professeur.nom_complet')
    creneau_details = CreneauSerializer(source='creneau', read_only=True)
    groupes = serializers.SerializerMethodField()
    professeurs = serializers.SerializerMethodField()

    class Meta:
        model = Seance
        fields = [
            'id', 'unite', 'module_code', 'module_intitule', 'module_type',
            'semaine', 'creneau', 'creneau_details', 'salle', 'salle_nom',
            'professeur', 'professeur_nom', 'mode', 'nature', 'bloc_no',
            'statut', 'verrouillee', 'tache', 'date_creation', 'date_modification',
            'groupes', 'professeurs'
        ]

    def get_groupes(self, obj):
        return [
            {'id': sg.groupe_id, 'code': sg.groupe.code}
            for sg in obj.seance_groupes.select_related('groupe').all()
        ]

    def get_professeurs(self, obj):
        return [
            {'id': sp.professeur_id, 'nom_complet': sp.professeur.nom_complet}
            for sp in obj.seance_professeurs.select_related('professeur').all()
        ]


# ─── Requêtes d'Actions Métier ────────────────────────────────────────────────
class LancerGenerationSerializer(serializers.Serializer):
    semaine_id = serializers.IntegerField(required=True)
    max_time_seconds = serializers.IntegerField(default=60, min_value=5, max_value=600)
    groupes_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )


class ValiderSemaineSerializer(serializers.Serializer):
    confirmer = serializers.BooleanField(default=True)


class ImportFichierSerializer(serializers.Serializer):
    fichier = serializers.FileField(required=True)
    annee_scolaire_id = serializers.IntegerField(required=False)

