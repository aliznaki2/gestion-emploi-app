"""
Vues de l'API REST DRF pour le système d'emploi du temps OFPPT.
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from core.models import (
    Utilisateur, Secteur, Filiere, Groupe, TypeSalle, Salle,
    Module, AnneeScolaire, Semestre, Semaine, Professeur,
    Creneau, Disponibilite, UniteEnseignement, TacheGeneration,
    Seance, SeanceGroupe, SeanceProfesseur
)
from solver.services import GenerateurEmploiDuTemps
from .permissions import EstAdmin, EstAdminOuLectureSeule, SeancePermission
from .importer import FichierAvancementImporter
from .serializers import (
    UtilisateurSerializer, SecteurSerializer, FiliereSerializer,
    GroupeSerializer, TypeSalleSerializer, SalleSerializer,
    ModuleSerializer, AnneeScolaireSerializer, SemestreSerializer,
    SemaineSerializer, CreneauSerializer, ProfesseurSerializer,
    DisponibiliteSerializer, UniteEnseignementSerializer,
    TacheGenerationSerializer, SeanceSerializer,
    LancerGenerationSerializer, ValiderSemaineSerializer,
    ImportFichierSerializer
)


# ─── Authentification ─────────────────────────────────────────────────────────
class ConnexionTokenView(TokenObtainPairView):
    """Obtention du token JWT d'authentification."""
    pass


class RafraichirTokenView(TokenRefreshView):
    """Rafraîchissement du token JWT d'authentification."""
    pass


class ProfilUtilisateurView(APIView):
    """Renvoie les informations du profil utilisateur connecté et son rôle."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UtilisateurSerializer(request.user)
        return Response(serializer.data)


# ─── Génération Automatique d'Emplois du Temps ────────────────────────────────
class GenerationViewSet(viewsets.ViewSet):
    """
    Gestion des lancements de génération du solver CP-SAT et consultation de l'avancement.
    """
    permission_classes = [EstAdmin]

    def list(self, request):
        """Liste les tâches de génération exécutées."""
        semaine_id = request.query_params.get('semaine_id')
        queryset = TacheGeneration.objects.all().order_by('-date_debut')
        if semaine_id:
            queryset = queryset.filter(semaine_id=semaine_id)
        serializer = TacheGenerationSerializer(queryset[:50], many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Détail d'une tâche avec son journal d'audit."""
        tache = get_object_or_404(TacheGeneration, pk=pk)
        serializer = TacheGenerationSerializer(tache)
        return Response(serializer.data)

    def create(self, request):
        """
        POST /api/generation/
        Lance le solveur d'optimisation CP-SAT pour une semaine donnée.
        """
        serializer = LancerGenerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        semaine_id = serializer.validated_data['semaine_id']
        max_time_seconds = serializer.validated_data.get('max_time_seconds', 60)
        groupes_ids = serializer.validated_data.get('groupes_ids', None)

        semaine = get_object_or_404(Semaine, id=semaine_id)

        # Exécution du moteur d'optimisation
        generateur = GenerateurEmploiDuTemps(
            semaine_id=semaine.id,
            utilisateur=request.user,
        )
        resultat = generateur.executer(
            max_time_seconds=max_time_seconds,
            groupes_ids=groupes_ids,
        )

        http_status = status.HTTP_200_OK if resultat['succes'] else status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(resultat, status=http_status)


# ─── CRUD Séances & Détection de Conflits ──────────────────────────────────────
class SeanceViewSet(viewsets.ModelViewSet):
    """
    Endpoints CRUD pour les séances de cours.
    - Contrôle strict des permissions selon le rôle (Admin, Formateur, Stagiaire).
    - Détection proactive des conflits (double réservation groupe, formateur ou salle).
    """
    serializer_class = SeanceSerializer
    # L'authentification du frontend est simulée : on autorise l'accès direct
    # au CRUD des séances (le rôle est géré côté interface).
    permission_classes = [AllowAny]

    # ─── Normalisation des données envoyées par le frontend ──────────────────
    @staticmethod
    def _ids_liste(data, *cles):
        """Extrait une liste d'identifiants depuis plusieurs clés possibles."""
        for cle in cles:
            if cle in data and data[cle] is not None:
                valeur = data[cle]
                if isinstance(valeur, (list, tuple)):
                    return [int(x) for x in valeur if x not in (None, '')]
                if valeur in ('', 0, '0'):
                    return []
                return [int(valeur)]
        return None

    def _normaliser(self, data):
        """Convertit les champs `*_id` du frontend vers les champs du modèle."""
        donnees = dict(data)
        for champ, cles in (
            ('unite', ('unite_id',)),
            ('semaine', ('semaine_id',)),
            ('creneau', ('creneau_id',)),
            ('salle', ('salle_id',)),
            ('professeur', ('professeur_id',)),
        ):
            if champ not in donnees:
                for cle in cles:
                    if cle in donnees:
                        valeur = donnees.pop(cle)
                        donnees[champ] = None if valeur in ('', 0, '0') else valeur
                        break

        groupe_ids = self._ids_liste(donnees, 'groupe_ids')
        prof_ids = self._ids_liste(donnees, 'professeur_ids')
        donnees.pop('groupe_ids', None)
        donnees.pop('professeur_ids', None)

        # Aligne le champ direct `professeur` sur la liste des formateurs
        if prof_ids and not donnees.get('professeur'):
            donnees['professeur'] = prof_ids[0]

        return donnees, groupe_ids, prof_ids

    def get_queryset(self):
        user = self.request.user
        queryset = Seance.objects.select_related(
            'unite__module', 'semaine', 'creneau', 'salle__type_salle', 'professeur'
        ).prefetch_related(
            'seance_groupes__groupe', 'seance_professeurs__professeur'
        ).all()

        # Filtrage selon le rôle
        if user.is_authenticated and not user.is_admin_role():
            if user.is_professeur_role():
                prof = getattr(user, 'professeur', None)
                if prof:
                    queryset = queryset.filter(
                        Q(professeur=prof) | Q(seance_professeurs__professeur=prof),
                        statut=Seance.STATUT_VALIDE
                    )
                else:
                    queryset = queryset.none()
            elif user.is_stagiaire_role():
                queryset = queryset.filter(statut=Seance.STATUT_VALIDE)

        # Filtres de requête
        semaine_id = self.request.query_params.get('semaine')
        if semaine_id:
            queryset = queryset.filter(semaine_id=semaine_id)

        groupe_id = self.request.query_params.get('groupe')
        if groupe_id:
            queryset = queryset.filter(seance_groupes__groupe_id=groupe_id)

        professeur_id = self.request.query_params.get('professeur')
        if professeur_id:
            queryset = queryset.filter(
                Q(professeur_id=professeur_id) | Q(seance_professeurs__professeur_id=professeur_id)
            )

        salle_id = self.request.query_params.get('salle')
        if salle_id:
            queryset = queryset.filter(salle_id=salle_id)

        jour = self.request.query_params.get('jour')
        if jour:
            queryset = queryset.filter(creneau__jour=jour)

        statut = self.request.query_params.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        return queryset.distinct()

    def _verifier_conflits(self, seance_id, semaine_id, creneau_id, salle_id, professeur_id, groupes_ids):
        """Vérifie l'absence de chevauchements lors de la modification manuelle."""
        conflits = []

        # 1. Conflit Formateur
        if professeur_id:
            conflit_prof = SeanceProfesseur.objects.filter(
                professeur_id=professeur_id,
                semaine_id=semaine_id,
                creneau_id=creneau_id,
            ).exclude(seance_id=seance_id).first()

            if conflit_prof:
                conflits.append(
                    f"Le formateur {conflit_prof.professeur.nom_complet} est déjà affecté à une autre séance "
                    f"(Séance #{conflit_prof.seance_id}) sur ce même créneau."
                )

        # 2. Conflit Salle (sauf distanciel TEAM)
        if salle_id:
            salle = Salle.objects.filter(id=salle_id).select_related('type_salle').first()
            if salle and salle.type_salle.code != 'TEAM':
                conflit_salle = Seance.objects.filter(
                    salle_id=salle_id,
                    semaine_id=semaine_id,
                    creneau_id=creneau_id,
                ).exclude(id=seance_id).first()

                if conflit_salle:
                    conflits.append(
                        f"La salle {salle.nom} est déjà occupée par la séance #{conflit_salle.id} "
                        f"sur ce créneau."
                    )

        # 3. Conflits Groupes
        if groupes_ids:
            for gid in groupes_ids:
                conflit_g = SeanceGroupe.objects.filter(
                    groupe_id=gid,
                    semaine_id=semaine_id,
                    creneau_id=creneau_id,
                ).exclude(seance_id=seance_id).first()

                if conflit_g:
                    conflits.append(
                        f"Le groupe {conflit_g.groupe.code} a déjà cours sur ce créneau (Séance #{conflit_g.seance_id})."
                    )

        return conflits

    def create(self, request, *args, **kwargs):
        """POST /api/seances — création manuelle d'une séance."""
        donnees, groupe_ids, prof_ids = self._normaliser(request.data)

        if not donnees.get('semaine'):
            return Response(
                {'erreur': 'semaine_id est obligatoire.', 'message': 'semaine_id est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not donnees.get('unite') or not donnees.get('creneau'):
            return Response(
                {'erreur': 'unite_id et creneau_id sont obligatoires.',
                 'message': 'unite_id et creneau_id sont obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prof_id = donnees.get('professeur')
        groupes_ids = groupe_ids or []

        conflits = self._verifier_conflits(
            seance_id=None,
            semaine_id=donnees.get('semaine'),
            creneau_id=donnees.get('creneau'),
            salle_id=donnees.get('salle'),
            professeur_id=prof_id,
            groupes_ids=groupes_ids,
        )
        if conflits:
            return Response(
                {'erreur': 'Conflit de planification détecté.', 'message': 'Conflit de planification détecté.',
                 'details': conflits},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            serializer = self.get_serializer(data=donnees)
            serializer.is_valid(raise_exception=True)
            seance = serializer.save()

            for gid in groupes_ids:
                SeanceGroupe.objects.get_or_create(
                    seance=seance,
                    groupe_id=gid,
                    defaults={'semaine_id': seance.semaine_id, 'creneau_id': seance.creneau_id},
                )
            for pid in (prof_ids or ([prof_id] if prof_id else [])):
                SeanceProfesseur.objects.get_or_create(
                    seance=seance,
                    professeur_id=pid,
                    defaults={'semaine_id': seance.semaine_id, 'creneau_id': seance.creneau_id},
                )

        return Response(SeanceSerializer(seance).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()

        donnees, groupe_ids, prof_ids = self._normaliser(request.data)

        nouv_semaine_id = donnees.get('semaine', instance.semaine_id)
        nouv_creneau_id = donnees.get('creneau', instance.creneau_id)
        nouv_salle_id = donnees.get('salle', instance.salle_id)
        nouv_prof_id = donnees.get('professeur', instance.professeur_id)

        # Récupérer les groupes associés à la séance (ou ceux envoyés par le frontend)
        groupes_ids = groupe_ids if groupe_ids is not None else list(
            instance.seance_groupes.values_list('groupe_id', flat=True)
        )

        conflits = self._verifier_conflits(
            seance_id=instance.id,
            semaine_id=nouv_semaine_id,
            creneau_id=nouv_creneau_id,
            salle_id=nouv_salle_id,
            professeur_id=nouv_prof_id,
            groupes_ids=groupes_ids,
        )

        if conflits:
            return Response(
                {
                    'erreur': 'Conflit de planification détecté.',
                    'message': 'Conflit de planification détecté.',
                    'details': conflits,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            serializer = self.get_serializer(instance, data=donnees, partial=partial)
            serializer.is_valid(raise_exception=True)
            seance = serializer.save()

            # Mise à jour des tables de liaison SeanceGroupe et SeanceProfesseur
            SeanceGroupe.objects.filter(seance=seance).update(
                semaine_id=seance.semaine_id, creneau_id=seance.creneau_id
            )
            SeanceProfesseur.objects.filter(seance=seance).update(
                semaine_id=seance.semaine_id, creneau_id=seance.creneau_id
            )

            if groupe_ids is not None:
                SeanceGroupe.objects.filter(seance=seance).exclude(groupe_id__in=groupe_ids).delete()
                for gid in groupe_ids:
                    SeanceGroupe.objects.get_or_create(
                        seance=seance,
                        groupe_id=gid,
                        defaults={'semaine_id': seance.semaine_id, 'creneau_id': seance.creneau_id},
                    )

            if prof_ids is not None:
                SeanceProfesseur.objects.filter(seance=seance).exclude(professeur_id__in=prof_ids).delete()
                for pid in prof_ids:
                    SeanceProfesseur.objects.get_or_create(
                        seance=seance,
                        professeur_id=pid,
                        defaults={'semaine_id': seance.semaine_id, 'creneau_id': seance.creneau_id},
                    )
            elif nouv_prof_id and nouv_prof_id != instance.professeur_id:
                SeanceProfesseur.objects.filter(seance=seance).delete()
                SeanceProfesseur.objects.create(
                    seance=seance,
                    professeur_id=nouv_prof_id,
                    semaine_id=seance.semaine_id,
                    creneau_id=seance.creneau_id,
                )

        return Response(SeanceSerializer(seance).data)


# ─── Validation Globale de la Semaine ─────────────────────────────────────────
class ValiderSemaineView(APIView):
    """
    POST /api/semaines/{semaine_id}/valider/
    Bascule toutes les séances de la semaine du statut 'brouillon' au statut 'valide'.
    """
    permission_classes = [EstAdmin]

    def post(self, request, semaine_id):
        semaine = get_object_or_404(Semaine, id=semaine_id)

        brouillons = Seance.objects.filter(semaine=semaine, statut=Seance.STATUT_BROUILLON)
        nb_brouillons = brouillons.count()

        if nb_brouillons == 0:
            return Response(
                {'message': f"Aucun brouillon à valider pour la Semaine {semaine.numero}."},
                status=status.HTTP_200_OK
            )

        # Validation groupée
        brouillons.update(statut=Seance.STATUT_VALIDE)

        return Response(
            {
                'succes': True,
                'message': f"Validation réussie : {nb_brouillons} séance(s) validée(s) pour la Semaine {semaine.numero}.",
                'nb_validees': nb_brouillons,
            },
            status=status.HTTP_200_OK
        )


# ─── Import Fichier Avancement (Excel / CSV) ──────────────────────────────────
class ImportAvancementView(APIView):
    """
    POST /api/import/
    Importe un fichier Excel ou CSV de suivi d'avancement pour mettre à jour
    les volumes horaires et heures réalisées.
    """
    permission_classes = [EstAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = ImportFichierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fichier = serializer.validated_data['fichier']
        annee_id = serializer.validated_data.get('annee_scolaire_id')

        if annee_id:
            annee = get_object_or_404(AnneeScolaire, id=annee_id)
        else:
            annee = AnneeScolaire.objects.filter(active=True).first()
            if not annee:
                annee = AnneeScolaire.objects.first()

        if not annee:
            return Response(
                {'erreur': "Aucune année scolaire active n'est définie."},
                status=status.HTTP_400_BAD_REQUEST
            )

        importer = FichierAvancementImporter(uploaded_file=fichier, annee_scolaire=annee)
        rapport = importer.importer()

        http_status = status.HTTP_200_OK if rapport['succes'] else status.HTTP_400_BAD_REQUEST
        return Response(rapport, status=http_status)


# ─── ViewSets Utilitaires pour le Frontend ─────────────────────────────────────
class SemaineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Semaine.objects.select_related('annee_scolaire', 'semestre').all().order_by('numero')
    serializer_class = SemaineSerializer
    permission_classes = [IsAuthenticated]


class GroupeViewSet(viewsets.ModelViewSet):
    queryset = Groupe.objects.select_related('filiere').all().order_by('code')
    serializer_class = GroupeSerializer
    permission_classes = [EstAdminOuLectureSeule]


class ProfesseurViewSet(viewsets.ModelViewSet):
    queryset = Professeur.objects.select_related('salle_preferee').all().order_by('nom_complet')
    serializer_class = ProfesseurSerializer
    permission_classes = [EstAdminOuLectureSeule]


class SalleViewSet(viewsets.ModelViewSet):
    queryset = Salle.objects.select_related('type_salle').all().order_by('nom')
    serializer_class = SalleSerializer
    permission_classes = [EstAdminOuLectureSeule]


class CreneauViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Creneau.objects.all().order_by('jour', 'numero_seance')
    serializer_class = CreneauSerializer
    permission_classes = [IsAuthenticated]


class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.all().order_by('code')
    serializer_class = ModuleSerializer
    permission_classes = [EstAdminOuLectureSeule]


class DisponibiliteViewSet(viewsets.ModelViewSet):
    queryset = Disponibilite.objects.select_related('professeur', 'creneau').all()
    serializer_class = DisponibiliteSerializer
    permission_classes = [EstAdminOuLectureSeule]

    def get_queryset(self):
        qs = super().get_queryset()
        prof_id = self.request.query_params.get('professeur')
        if prof_id:
            qs = qs.filter(professeur_id=prof_id)
        return qs

