# GestEmploi SaaS — Plateforme Multi-Tenant de Gestion & Génération d'Emplois du Temps

> **Plateforme SaaS intelligente** de génération automatique et gestion centralisée des emplois du temps pour établissements scolaires, centres de formation professionnelle et instituts spécialisés (OFPPT / Privé).

---

## Sommaire
- [Points Clés & Fonctionnalités](#-points-clés--fonctionnalités)
- [Architecture Multi-Tenant & Rôles](#-architecture-multi-tenant--rôles)
- [Stack Technologique](#-stack-technologique)
- [Structure du Projet](#-structure-du-projet)
- [Installation & Démarrage](#-installation--démarrage-rapide)
- [Comptes de Démonstration](#-comptes-de-démonstration)
- [Catalogue des APIs REST](#-catalogue-des-apis-rest-principales)
- [Licence & Auteur](#-licence)

---

## 🌟 Points Clés & Fonctionnalités

### 1. Portail Super Administrateur (Supervision SaaS)
- **Gestion des Établissements (Tenants) :** Création, modification, activation, désactivation, suspension et suppression d'établissements avec suivi des quotas (formateurs, groupes).
- **Gouvernance des Administrateurs :** Création de directeurs/administrateurs locaux, modification des identifiants et emails, réinitialisation sécurisée des mots de passe.
- **Workflow des Demandes d'Adhésion :** Traitement des demandes d'abonnement soumises via la page d'accueil avec **approbation automatique** (création en un clic de l'établissement + compte admin) ou refus motivé.
- **Statistiques Globales du Réseau :** Suivi consolidé des centres, formateurs, groupes, salles et demandes.

### 2. Gestion Opérationnelle par Établissement (Tenant)
- **Formateurs :** Statuts (permanents, vacataires), masse horaire maximale hebdomadaire, affectations préférentielles, indisponibilités.
- **Groupes & Filières :** Années d'études (1ère, 2ème, 3ème année), effectifs, créneaux libres réservés aux modules généraux (TEAM/Distanciel).
- **Salles & Espaces :** Capacités, types (cours, TP info, ateliers), salles dédiées ou partagées.
- **Contraintes & Indisponibilités :** Gestion des demi-journées libres, contraintes de blocs pédagogiques de 2.5h / 5h consécutives.

### 3. Moteur d'Optimisation Algorithmique (Google OR-Tools CP-SAT)
- Solveur de programmation par contraintes (Constraint Programming).
- Respect strict des **contraintes dures** (zéro chevauchement de formateur, groupe ou salle).
- Optimisation des **contraintes souples** (minimisation des trous d'emploi du temps, équilibrage de charge, respect des préférences de salle).

### 4. Consultation & Exports Avancés
- Emploi du temps interactif par **Groupe**, **Formateur** ou **Salle**.
- Exports haute définition en **PDF imprimable** et classeurs **Excel (XLSX)**.

---

## 🏛 Architecture Multi-Tenant & Rôles

Le système applique une séparation stricte des données entre les établissements :

```
                  ┌────────────────────────────────────────┐
                  │          SUPER ADMINISTRATEUR          │
                  │   Console centrale & Gestion Réseau    │
                  └───────────────────┬────────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            ▼                         ▼                         ▼
  ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
  │  Établissement A  │     │  Établissement B  │     │  Établissement C  │
  │  (Tenant Dédié)   │     │  (Tenant Dédié)   │     │  (Tenant Dédié)   │
  ├───────────────────┤     ├───────────────────┤     ├───────────────────┤
  │ • Admin Local     │     │ • Admin Local     │     │ • Admin Local     │
  │ • Formateurs      │     │ • Formateurs      │     │ • Formateurs      │
  │ • Groupes/Salles  │     │ • Groupes/Salles  │     │ • Groupes/Salles  │
  │ • Emplois du temps│     │ • Emplois du temps│     │ • Emplois du temps│
  └───────────────────┘     └───────────────────┘     └───────────────────┘
```

| Rôle | Périmètre d'Accès |
|---|---|
| **Super Admin** (`super_admin`) | Supervision globale, gestion des établissements, validation des souscriptions, gestion des administrateurs. |
| **Admin Établissement** (`admin`) | Gestion intégrale des ressources de son propre institut, génération et validation des emplois du temps. |
| **Formateur** (`professeur`) | Consultation de son emploi du temps personnel, saisie de ses préférences et indisponibilités. |
| **Stagiaire** (`stagiaire`) | Consultation en direct du planning hebdomadaire de son groupe. |

---

## 🛠 Stack Technologique

- **Frontend :** React 19, Vite 8, JavaScript (ESNext), CSS3 modulaire (interfaçage pur sans emoji avec icônes vectorielles SVG).
- **Backend :** Python 3.11+, Django 5.1.3, Django REST Framework (DRF).
- **Solveur IA & Optimisation :** Google OR-Tools (solveur CP-SAT).
- **Base de Données :** SQLite (développement) / PostgreSQL ou MySQL (production).
- **Exports & Utilitaires :** OpenPyXL (Excel), ReportLab / Canvas (PDF).

---

## 📁 Structure du Projet

```text
gestion-emploi-app/
├── backend/
│   ├── api/                     # Vues REST & URLs
│   │   ├── superadmin_views.py  # APIs dédiées au Super Administrateur
│   │   ├── superadmin_urls.py   # Routes /api/superadmin/
│   │   ├── views.py             # APIs métier (emplois, ressources)
│   │   └── urls.py
│   ├── config/                  # Configuration Django (settings, wsgi, urls)
│   ├── core/                    # Modèles de données ORM & Migrations
│   │   ├── models.py            # Etablissement, Utilisateur, DemandeAbonnement...
│   │   └── migrations/
│   ├── solver/                  # Solveur CP-SAT d'optimisation
│   ├── app.py                   # Lanceur du backend (Port 3001)
│   └── requirements.txt         # Dépendances Python
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SuperAdminDashboard/ # Console Super Admin (Tenants, Demandes, Stats)
│   │   │   ├── Dashboard/           # Dashboard administrateur local
│   │   │   ├── Login/               # Authentification multi-rôles
│   │   │   ├── SubscriptionModal/   # Formulaire public d'adhésion
│   │   │   └── Timetable/           # Grille et visualiseur d'emplois du temps
│   │   ├── config/                  # Configuration de marque & branding
│   │   ├── App.jsx                  # Routeur principal
│   │   └── main.jsx
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── .gitignore                   # Exclusion node_modules, pycache, db locale
├── rapport_developpement_superadmin.html # Rapport complet imprimable en PDF
└── README.md
```

---

## 🚀 Démarrage Rapide

### 1. Prérequis
- **Node.js** (v18+) & **npm**
- **Python** (v3.11+)

---

### 2. Configuration & Démarrage du Backend

```bash
# 1. Se positionner dans le dossier backend
cd backend

# 2. Installer les dépendances Python
pip install -r requirements.txt

# 3. Appliquer les migrations de base de données
python manage.py migrate

# 4. Lancer le serveur backend
python app.py
```
> Le serveur API écoute sur **`http://localhost:3001`** (Panel admin sur `/admin/`).

---

### 3. Configuration & Démarrage du Frontend

Dans un second terminal :

```bash
# 1. Se positionner dans le dossier frontend
cd frontend

# 2. Installer les packages npm
npm install

# 3. Lancer le serveur de développement Vite
npm run dev
```
> L'application est accessible sur **`http://localhost:5173`**.

---

## 🔑 Comptes de Démonstration

| Rôle | Identifiant (Login) | Mot de passe | Espace Accessible |
|---|---|---|---|
| **Super Administrateur** | `superadmin` | `superadmin123` | Console Super Admin (`#dashboard`) |
| **Admin Établissement** | `admin` | `admin123` | Dashboard de Gestion (`#dashboard`) |
| **Formateur** | `formateur` | `prof123` | Espace Enseignant (`#professeur`) |
| **Stagiaire** | `stagiaire` | `stagiaire123` | Planning Groupe (`#stagiaire`) |

---

## 📡 Catalogue des APIs REST Principales

### Super Administrateur (`/api/superadmin/`)
- `GET / POST /api/superadmin/etablissements` : Lister tous les établissements / En créer un nouveau.
- `GET / PUT / DELETE /api/superadmin/etablissements/<id>` : Détail, modification, suppression d'un tenant.
- `POST /api/superadmin/etablissements/<id>/(activer|desactiver|suspendre)` : Changement d'état opérationnel.
- `GET /api/superadmin/etablissements/<id>/stats` : Statistiques d'un établissement.
- `GET / POST /api/superadmin/etablissements/<id>/admins` : Gestion des administrateurs rattachés.
- `PUT / PATCH / DELETE /api/superadmin/etablissements/<id>/admins/<uid>` : Mise à jour identifiant/email, réinitialisation de mot de passe.
- `POST /api/superadmin/demandes/soumettre` : Endpoint public de demande d'adhésion.
- `GET /api/superadmin/demandes` : Consultation et filtrage des demandes d'abonnement.
- `POST /api/superadmin/demandes/<id>/approuver` : Approbation avec création automatique de l'établissement + compte admin.
- `POST /api/superadmin/demandes/<id>/refuser` : Rejet avec note explicative.
- `GET /api/superadmin/stats-globales` : Indicateurs clés consolidés de la plateforme.

---

## 📄 Licence
Ce projet est développé dans le cadre de la modernisation et de l'automatisation des emplois du temps. Tous droits réservés.
