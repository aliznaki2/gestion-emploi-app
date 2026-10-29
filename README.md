# Gestion Emploi du Temps

Projet structuré en **Frontend** et **Backend**.

---

## 📁 Structure du Projet

```text
gestion-emploi-app/
├── backend/
│   ├── data/             # Scripts SQL et données
│   ├── server.js         # Serveur Express & API REST (Port 3001)
│   ├── test_gen.mjs      # Scripts de test
│   └── package.json
│
├── frontend/
│   ├── public/           # Assets statiques
│   ├── src/              # Composants React
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
└── package.json          # Scripts d'orchestration globaux
```

---

## 🚀 Démarrage Rapide

### 1. Démarrer le Backend
```bash
# Depuis la racine gestion-emploi-app :
npm run dev:backend

# OU directement dans le dossier backend :
cd backend
npm run dev
```
> Le serveur API écoute sur **http://localhost:3001**

### 2. Démarrer le Frontend
```bash
# Depuis la racine gestion-emploi-app :
npm run dev:frontend

# OU directement dans le dossier frontend :
cd frontend
npm run dev
```
> L'application s'ouvrira sur **http://localhost:5173**

---

## 📦 Installation des dépendances

Pour réinstaller toutes les dépendances d'un coup :
```bash
npm run install:all
```
