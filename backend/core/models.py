"""
Modèles du Domaine Métier OFPPT (MCD / MLD).
Génération automatique d'emplois du temps sous contraintes.
"""
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


# ─── 1. Utilisateur & Rôles ────────────────────────────────────────────────────
class Utilisateur(AbstractUser):
    """
    Utilisateur du système avec contrôle des accès basé sur le rôle.
    Roles: 'admin', 'professeur', 'stagiaire'.
    """
    ROLE_ADMIN = 'admin'
    ROLE_PROFESSEUR = 'professeur'
    ROLE_STAGIAIRE = 'stagiaire'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrateur / Planificateur'),
        (ROLE_PROFESSEUR, 'Formateur / Professeur'),
        (ROLE_STAGIAIRE, 'Stagiaire / Délégué de Groupe'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_STAGIAIRE,
        verbose_name=_("Rôle"),
    )
    telephone = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Téléphone"))

    class Meta:
        verbose_name = _("Utilisateur")
        verbose_name_plural = _("Utilisateurs")
        ordering = ['last_name', 'first_name']

    def is_admin_role(self) -> bool:
        return self.role == self.ROLE_ADMIN or self.is_superuser

    def is_professeur_role(self) -> bool:
        return self.role == self.ROLE_PROFESSEUR

    def is_stagiaire_role(self) -> bool:
        return self.role == self.ROLE_STAGIAIRE


# ─── 2. Secteur, Filière & Groupe ──────────────────────────────────────────────
class Secteur(models.Model):
    """Secteur de formation (ex: NTIC, AGC, Génie Mécanique)."""
    code = models.CharField(max_length=20, unique=True, verbose_name=_("Code Secteur"))
    intitule = models.CharField(max_length=150, verbose_name=_("Intitulé"))

    class Meta:
        verbose_name = _("Secteur")
        verbose_name_plural = _("Secteurs")
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.intitule}"


class Filiere(models.Model):
    """Filière d'études appartenant à un secteur."""
    code = models.CharField(max_length=30, unique=True, verbose_name=_("Code Filière"))
    intitule = models.CharField(max_length=150, verbose_name=_("Intitulé"))
    secteur = models.ForeignKey(Secteur, on_delete=models.CASCADE, related_name='filieres', verbose_name=_("Secteur"))
    niveau = models.CharField(max_length=50, default='TS', verbose_name=_("Niveau de formation"))

    class Meta:
        verbose_name = _("Filière")
        verbose_name_plural = _("Filières")
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.intitule}"


class Groupe(models.Model):
    """Groupe de stagiaires (ex: DEV101, DEV201, ID102)."""
    MODE_PRESENTIEL = 'presentiel'
    MODE_ALTERNANCE = 'alternance'
    MODE_HYBRIDE = 'hybride'

    MODE_CHOICES = [
        (MODE_PRESENTIEL, 'Présentiel'),
        (MODE_ALTERNANCE, 'Alternance'),
        (MODE_HYBRIDE, 'Hybride'),
    ]

    code = models.CharField(max_length=30, unique=True, verbose_name=_("Code Groupe"))
    filiere = models.ForeignKey(Filiere, on_delete=models.CASCADE, related_name='groupes', verbose_name=_("Filière"))
    annee_etude = models.PositiveSmallIntegerField(default=1, verbose_name=_("Année d'étude (1 ou 2)"))
    effectif = models.PositiveIntegerField(default=25, verbose_name=_("Effectif"))
    mode_formation = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_PRESENTIEL, verbose_name=_("Mode de Formation"))
    actif = models.BooleanField(default=True, verbose_name=_("Actif"))

    class Meta:
        verbose_name = _("Groupe")
        verbose_name_plural = _("Groupes")
        ordering = ['code']

    def __str__(self):
        return f"{self.code} ({self.effectif} stagiaires)"


# ─── 3. Types de Salles & Salles ───────────────────────────────────────────────
class TypeSalle(models.Model):
    """Type de salle: Salle de Cours (SC), Salle Pratique (SP), Labo Réseau (LABO), Virtuelle (TEAM)."""
    code = models.CharField(max_length=20, unique=True, verbose_name=_("Code Type Salle"))
    libelle = models.CharField(max_length=100, verbose_name=_("Libellé"))

    class Meta:
        verbose_name = _("Type de Salle")
        verbose_name_plural = _("Types de Salle")
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.libelle}"


class Salle(models.Model):
    """Salle physique ou virtuelle de l'établissement."""
    nom = models.CharField(max_length=50, unique=True, verbose_name=_("Nom / Numéro Salle"))
    type_salle = models.ForeignKey(TypeSalle, on_delete=models.PROTECT, related_name='salles', verbose_name=_("Type de Salle"))
    capacite = models.PositiveIntegerField(default=30, verbose_name=_("Capacité"))
    actif = models.BooleanField(default=True, verbose_name=_("Actif"))

    class Meta:
        verbose_name = _("Salle")
        verbose_name_plural = _("Salles")
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.type_salle.code}, cap. {self.capacite})"

    @property
    def est_virtuelle(self) -> bool:
        return self.type_salle.code == 'TEAM'


# ─── 4. Modules ────────────────────────────────────────────────────────────────
class Module(models.Model):
    """Module de formation (M101, EGTS101, etc.)."""
    TYPE_TECHNIQUE = 'technique'
    TYPE_GENERAL = 'general'

    TYPE_CHOICES = [
        (TYPE_TECHNIQUE, 'Technique (Métier)'),
        (TYPE_GENERAL, 'Général (Soft Skills / Langues)'),
    ]

    code = models.CharField(max_length=30, unique=True, verbose_name=_("Code Module"))
    intitule = models.CharField(max_length=150, verbose_name=_("Intitulé"))
    type_module = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_TECHNIQUE, verbose_name=_("Type de Module"))
    regional = models.BooleanField(default=False, verbose_name=_("Épreuve régionale (EFM)"))
    types_salles_compatibles = models.ManyToManyField(
        TypeSalle,
        blank=True,
        related_name='modules_compatibles',
        verbose_name=_("Types de salles compatibles"),
    )

    class Meta:
        verbose_name = _("Module")
        verbose_name_plural = _("Modules")
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.intitule} ({self.get_type_module_display()})"


# ─── 5. Année Scolaire, Semestre & Semaine ─────────────────────────────────────
class AnneeScolaire(models.Model):
    libelle = models.CharField(max_length=20, unique=True, verbose_name=_("Libellé (ex: 2025/2026)"))
    date_debut = models.DateField(verbose_name=_("Date de début"))
    date_fin = models.DateField(verbose_name=_("Date de fin"))
    active = models.BooleanField(default=True, verbose_name=_("Année en cours"))

    class Meta:
        verbose_name = _("Année Scolaire")
        verbose_name_plural = _("Années Scolaires")
        ordering = ['-date_debut']

    def __str__(self):
        return self.libelle


class Semestre(models.Model):
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='semestres')
    numero = models.PositiveSmallIntegerField(default=1, verbose_name=_("Semestre (1 ou 2)"))
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = _("Semestre")
        verbose_name_plural = _("Semestres")
        constraints = [
            models.UniqueConstraint(fields=['annee_scolaire', 'numero'], name='unique_semestre_par_annee')
        ]
        ordering = ['annee_scolaire', 'numero']

    def __str__(self):
        return f"S{self.numero} ({self.annee_scolaire.libelle})"


class Semaine(models.Model):
    """Semaine du calendrier pédagogique (S1 à S36)."""
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='semaines')
    semestre = models.ForeignKey(Semestre, on_delete=models.SET_NULL, null=True, blank=True, related_name='semaines')
    numero = models.PositiveIntegerField(verbose_name=_("Numéro Semaine"))
    date_debut = models.DateField(null=True, blank=True, verbose_name=_("Date début"))
    date_fin = models.DateField(null=True, blank=True, verbose_name=_("Date fin"))
    active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Semaine Pédagogique")
        verbose_name_plural = _("Semaines Pédagogiques")
        constraints = [
            models.UniqueConstraint(fields=['annee_scolaire', 'numero'], name='unique_semaine_par_annee')
        ]
        ordering = ['numero']

    def __str__(self):
        return f"Semaine {self.numero} ({self.annee_scolaire.libelle})"


# ─── 6. Professeur (Formateur) ────────────────────────────────────────────────
class Professeur(models.Model):
    """Formateur de l'établissement."""
    STATUT_PERMANENT = 'permanent'
    STATUT_VACATAIRE = 'vacataire'

    STATUT_CHOICES = [
        (STATUT_PERMANENT, 'Permanent'),
        (STATUT_VACATAIRE, 'Vacataire'),
    ]

    matricule = models.CharField(max_length=30, unique=True, verbose_name=_("Matricule"))
    nom_complet = models.CharField(max_length=120, verbose_name=_("Nom Complet"))
    utilisateur = models.OneToOneField(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='professeur',
        verbose_name=_("Compte Utilisateur lié"),
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=STATUT_PERMANENT, verbose_name=_("Statut"))
    heures_max_semaine = models.DecimalField(max_digits=4, decimal_places=1, default=30.0, verbose_name=_("Heures Max / Semaine"))
    taux_presence = models.FloatField(default=1.0, verbose_name=_("Taux de présence (0 à 1)"))
    salle_preferee = models.ForeignKey(
        Salle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='professeurs_preferes',
        verbose_name=_("Salle préférée"),
    )
    actif = models.BooleanField(default=True, verbose_name=_("Actif"))

    class Meta:
        verbose_name = _("Professeur / Formateur")
        verbose_name_plural = _("Professeurs / Formateurs")
        ordering = ['nom_complet']

    def __str__(self):
        return f"{self.nom_complet} ({self.matricule} - {self.get_statut_display()})"


# ─── 7. Créneaux Horaires ─────────────────────────────────────────────────────
class Creneau(models.Model):
    """
    Créneau horaire type d'une journée OFPPT:
    - Jour: 1=Lundi, 2=Mardi, 3=Mercredi, 4=Jeudi, 5=Vendredi, 6=Samedi
    - Séance: 1 (08h30-11h00), 2 (11h00-13h30), 3 (13h30-16h00), 4 (16h00-18h30)
    - Durée: 2.5h
    """
    JOUR_LUNDI = 1
    JOUR_MARDI = 2
    JOUR_MERCREDI = 3
    JOUR_JEUDI = 4
    JOUR_VENDREDI = 5
    JOUR_SAMEDI = 6

    JOUR_CHOICES = [
        (JOUR_LUNDI, 'Lundi'),
        (JOUR_MARDI, 'Mardi'),
        (JOUR_MERCREDI, 'Mercredi'),
        (JOUR_JEUDI, 'Jeudi'),
        (JOUR_VENDREDI, 'Vendredi'),
        (JOUR_SAMEDI, 'Samedi'),
    ]

    jour = models.PositiveSmallIntegerField(choices=JOUR_CHOICES, verbose_name=_("Jour de la semaine (1 à 6)"))
    numero_seance = models.PositiveSmallIntegerField(verbose_name=_("Numéro de séance (1 à 4)"))
    heure_debut = models.TimeField(verbose_name=_("Heure de début"))
    heure_fin = models.TimeField(verbose_name=_("Heure de fin"))
    duree_h = models.DecimalField(max_digits=3, decimal_places=1, default=2.5, verbose_name=_("Durée en heures"))

    class Meta:
        verbose_name = _("Créneau Horaire")
        verbose_name_plural = _("Créneaux Horaires")
        constraints = [
            models.UniqueConstraint(fields=['jour', 'numero_seance'], name='unique_jour_numero_seance')
        ]
        ordering = ['jour', 'numero_seance']

    def __str__(self):
        return f"{self.get_jour_display()} S{self.numero_seance} ({self.heure_debut.strftime('%H:%M')}-{self.heure_fin.strftime('%H:%M')})"

    @property
    def periode(self) -> str:
        """'matin' (S1, S2) ou 'apm' (S3, S4)."""
        return 'matin' if self.numero_seance in (1, 2) else 'apm'


# ─── 8. Disponibilités des Formateurs ─────────────────────────────────────────
class Disponibilite(models.Model):
    """Disponibilité d'un professeur sur un créneau donné."""
    ETAT_DISPONIBLE = 'disponible'
    ETAT_BLOQUE = 'bloque'
    ETAT_PREFERE = 'prefere'

    ETAT_CHOICES = [
        (ETAT_DISPONIBLE, 'Disponible'),
        (ETAT_BLOQUE, 'Bloqué / Indisponible'),
        (ETAT_PREFERE, 'Préféré / Souhaité'),
    ]

    professeur = models.ForeignKey(Professeur, on_delete=models.CASCADE, related_name='disponibilites')
    creneau = models.ForeignKey(Creneau, on_delete=models.CASCADE, related_name='disponibilites')
    etat = models.CharField(max_length=20, choices=ETAT_CHOICES, default=ETAT_DISPONIBLE)

    class Meta:
        verbose_name = _("Disponibilité Formateur")
        verbose_name_plural = _("Disponibilités Formateurs")
        constraints = [
            models.UniqueConstraint(fields=['professeur', 'creneau'], name='unique_professeur_creneau')
        ]

    def __str__(self):
        return f"{self.professeur.nom_complet} @ {self.creneau} : {self.get_etat_display()}"


# ─── 9. Unités d'Enseignement & Volumes Horaires ──────────────────────────────
class UniteEnseignement(models.Model):
    """
    Unité d'enseignement liant un Module, une Année Scolaire, des Groupes et Formateurs.
    Peut comporter un code_fusion (ex: 2 groupes fusionnés pour 1 séance commune).
    """
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='unites')
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='unites')
    semestre = models.ForeignKey(Semestre, on_delete=models.SET_NULL, null=True, blank=True, related_name='unites')
    code_fusion = models.CharField(max_length=60, null=True, blank=True, db_index=True, verbose_name=_("Code Fusion (Groupes)"))

    class Meta:
        verbose_name = _("Unité d'Enseignement")
        verbose_name_plural = _("Unités d'Enseignement")

    def __str__(self):
        fusion_tag = f" [Fusion: {self.code_fusion}]" if self.code_fusion else ""
        return f"UE: {self.module.code} - {self.annee_scolaire.libelle}{fusion_tag}"


class UniteGroupe(models.Model):
    """Liaison entre une Unité d'Enseignement et un Groupe."""
    unite = models.ForeignKey(UniteEnseignement, on_delete=models.CASCADE, related_name='unite_groupes')
    groupe = models.ForeignKey(Groupe, on_delete=models.CASCADE, related_name='groupe_unites')

    class Meta:
        verbose_name = _("Liaison Unité-Groupe")
        verbose_name_plural = _("Liaisons Unité-Groupe")
        constraints = [
            models.UniqueConstraint(fields=['unite', 'groupe'], name='unique_unite_groupe')
        ]

    def __str__(self):
        return f"{self.unite} <-> {self.groupe.code}"


class VolumeHoraire(models.Model):
    """Volume horaire prescrit et réalisé pour une unité d'enseignement."""
    unite = models.OneToOneField(UniteEnseignement, on_delete=models.CASCADE, related_name='volume_horaire')
    h_total = models.FloatField(default=0.0, verbose_name=_("Total heures prescrites"))
    h_presentiel = models.FloatField(default=0.0, verbose_name=_("Heures en présentiel"))
    h_synchrone = models.FloatField(default=0.0, verbose_name=_("Heures synchrones à distance (TEAM)"))
    h_asynchrone = models.FloatField(default=0.0, verbose_name=_("Heures asynchrones"))
    heures_effectuees = models.FloatField(default=0.0, verbose_name=_("Heures déjà effectuées"))

    class Meta:
        verbose_name = _("Volume Horaire")
        verbose_name_plural = _("Volumes Horaires")

    def __str__(self):
        return f"{self.unite}: {self.heures_effectuees}/{self.h_presentiel}h présentiel"

    @property
    def heures_restantes(self) -> float:
        return max(0.0, float(self.h_presentiel) - float(self.heures_effectuees))


class UniteProfesseur(models.Model):
    """Affectation des formateurs à l'unité d'enseignement."""
    MODE_CHOICES = [
        ('presentiel', 'Présentiel'),
        ('distance', 'À distance'),
    ]

    unite = models.ForeignKey(UniteEnseignement, on_delete=models.CASCADE, related_name='unite_professeurs')
    professeur = models.ForeignKey(Professeur, on_delete=models.CASCADE, related_name='professeur_unites')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='presentiel')

    class Meta:
        verbose_name = _("Affectation Formateur UE")
        verbose_name_plural = _("Affectations Formateur UE")
        constraints = [
            models.UniqueConstraint(fields=['unite', 'professeur', 'mode'], name='unique_unite_professeur_mode')
        ]

    def __str__(self):
        return f"{self.professeur.nom_complet} -> {self.unite} ({self.mode})"


# ─── 10. Passages (Modules Généraux Intensifs) ─────────────────────────────────
class Passage(models.Model):
    """
    Suivi des modules généraux en passage continu (ex: cours intensif de 5h/semaine
    de la semaine X à la semaine Y).
    """
    unite = models.ForeignKey(UniteEnseignement, on_delete=models.CASCADE, related_name='passages')
    semaine_debut = models.PositiveIntegerField(verbose_name=_("Semaine Début"))
    semaine_fin = models.PositiveIntegerField(verbose_name=_("Semaine Fin"))
    intensite_h = models.FloatField(default=5.0, verbose_name=_("Intensité horaire par semaine (h)"))
    actif = models.BooleanField(default=True, verbose_name=_("Passage Actif"))

    class Meta:
        verbose_name = _("Passage Module Général")
        verbose_name_plural = _("Passages Modules Généraux")
        ordering = ['semaine_debut', 'semaine_fin']

    def __str__(self):
        return f"Passage {self.unite}: S{self.semaine_debut}->S{self.semaine_fin} ({self.intensite_h}h/sem)"


# ─── 11. Tâche de Génération & Journal ─────────────────────────────────────────
class TacheGeneration(models.Model):
    """Enregistre le statut et le diagnostic de l'exécution du solver CP-SAT."""
    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_EN_COURS = 'en_cours'
    STATUT_TERMINEE = 'terminee'
    STATUT_ECHEC = 'echec'

    STATUT_CHOICES = [
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_EN_COURS, 'En cours d\'optimisation'),
        (STATUT_TERMINEE, 'Génération Terminée avec Succès'),
        (STATUT_ECHEC, 'Échec / Infaisable'),
    ]

    semaine = models.ForeignKey(Semaine, on_delete=models.CASCADE, related_name='taches_generation')
    semestre = models.ForeignKey(Semestre, on_delete=models.SET_NULL, null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=STATUT_EN_ATTENTE)
    message = models.TextField(blank=True, verbose_name=_("Message / Diagnostic"))
    temps_resolution_ms = models.IntegerField(default=0, verbose_name=_("Temps de résolution (ms)"))
    score_penalite = models.IntegerField(default=0, verbose_name=_("Pénalité Objectif"))
    cree_par = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Tâche de Génération")
        verbose_name_plural = _("Tâches de Génération")
        ordering = ['-date_debut']

    def __str__(self):
        return f"Tâche #{self.id} - Semaine {self.semaine.numero} [{self.get_statut_display()}]"


class Journal(models.Model):
    """Logs détaillés pour l'audit et le débogage de la génération."""
    NIVEAU_INFO = 'INFO'
    NIVEAU_WARNING = 'WARNING'
    NIVEAU_ERROR = 'ERROR'

    NIVEAU_CHOICES = [
        (NIVEAU_INFO, 'Information'),
        (NIVEAU_WARNING, 'Avertissement'),
        (NIVEAU_ERROR, 'Erreur'),
    ]

    tache = models.ForeignKey(TacheGeneration, on_delete=models.CASCADE, null=True, blank=True, related_name='journaux')
    niveau = models.CharField(max_length=10, choices=NIVEAU_CHOICES, default=NIVEAU_INFO)
    message = models.TextField()
    horodatage = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Journal de Génération")
        verbose_name_plural = _("Journaux de Génération")
        ordering = ['horodatage']

    def __str__(self):
        return f"[{self.niveau}] {self.horodatage.strftime('%H:%M:%S')} - {self.message[:60]}"


# ─── 12. Séances & Tables de Liaison ──────────────────────────────────────────
class Seance(models.Model):
    """
    Séance d'enseignement placée sur un créneau et une salle dans la semaine.
    Peut appartenir à un bloc de 5h (2 créneaux consécutifs).
    """
    MODE_PRESENTIEL = 'presentiel'
    MODE_DISTANCE = 'distance'

    MODE_CHOICES = [
        (MODE_PRESENTIEL, 'Présentiel'),
        (MODE_DISTANCE, 'À distance (TEAM)'),
    ]

    NATURE_BLOC = 'bloc'
    NATURE_SIMPLE = 'simple'
    NATURE_EXAMEN = 'examen'

    NATURE_CHOICES = [
        (NATURE_BLOC, 'Bloc de 5h'),
        (NATURE_SIMPLE, 'Séance Simple de 2.5h'),
        (NATURE_EXAMEN, 'Examen / EFM'),
    ]

    STATUT_BROUILLON = 'brouillon'
    STATUT_VALIDE = 'valide'

    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_VALIDE, 'Validé'),
    ]

    unite = models.ForeignKey(UniteEnseignement, on_delete=models.CASCADE, related_name='seances')
    semaine = models.ForeignKey(Semaine, on_delete=models.CASCADE, related_name='seances')
    creneau = models.ForeignKey(Creneau, on_delete=models.PROTECT, related_name='seances')
    salle = models.ForeignKey(Salle, on_delete=models.SET_NULL, null=True, blank=True, related_name='seances')
    professeur = models.ForeignKey(Professeur, on_delete=models.SET_NULL, null=True, blank=True, related_name='seances_directes')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_PRESENTIEL)
    nature = models.CharField(max_length=20, choices=NATURE_CHOICES, default=NATURE_BLOC)
    bloc_no = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Identifiant du Bloc"))
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=STATUT_BROUILLON)
    verrouillee = models.BooleanField(default=False, verbose_name=_("Verrouillée (non écrasable par régénération)"))
    tache = models.ForeignKey(TacheGeneration, on_delete=models.SET_NULL, null=True, blank=True, related_name='seances')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Séance")
        verbose_name_plural = _("Séances")
        ordering = ['semaine', 'creneau__jour', 'creneau__numero_seance']

    def __str__(self):
        salle_str = self.salle.nom if self.salle else "Distanciel"
        return f"Séance #{self.id}: {self.unite.module.code} - {self.creneau} ({salle_str}) [{self.get_statut_display()}]"


class SeanceGroupe(models.Model):
    """
    Table de liaison Séance <-> Groupe recopiant semaine_id et creneau_id
    avec contrainte d'unicité stricte au niveau base de données.
    """
    seance = models.ForeignKey(Seance, on_delete=models.CASCADE, related_name='seance_groupes')
    groupe = models.ForeignKey(Groupe, on_delete=models.CASCADE, related_name='groupe_seances')
    semaine = models.ForeignKey(Semaine, on_delete=models.CASCADE)
    creneau = models.ForeignKey(Creneau, on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Liaison Séance-Groupe")
        verbose_name_plural = _("Liaisons Séance-Groupe")
        constraints = [
            models.UniqueConstraint(
                fields=['groupe', 'semaine', 'creneau'],
                name='unique_groupe_semaine_creneau',
            )
        ]

    def __str__(self):
        return f"G:{self.groupe.code} - S{self.semaine.numero} - {self.creneau}"


class SeanceProfesseur(models.Model):
    """
    Table de liaison Séance <-> Professeur recopiant semaine_id et creneau_id
    avec contrainte d'unicité stricte au niveau base de données.
    """
    seance = models.ForeignKey(Seance, on_delete=models.CASCADE, related_name='seance_professeurs')
    professeur = models.ForeignKey(Professeur, on_delete=models.CASCADE, related_name='professeur_seances')
    semaine = models.ForeignKey(Semaine, on_delete=models.CASCADE)
    creneau = models.ForeignKey(Creneau, on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Liaison Séance-Formateur")
        verbose_name_plural = _("Liaisons Séance-Formateur")
        constraints = [
            models.UniqueConstraint(
                fields=['professeur', 'semaine', 'creneau'],
                name='unique_professeur_semaine_creneau',
            )
        ]

    def __str__(self):
        return f"P:{self.professeur.nom_complet} - S{self.semaine.numero} - {self.creneau}"

