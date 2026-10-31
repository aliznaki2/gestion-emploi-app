# Gestion Emploi du Temps

Projet structuré en **Frontend** (React/Vite) et **Backend** (Python/Flask).

---

## 📁 Structure du Projet

```text
gestion-emploi-app/
├── backend/
│   ├── data/             # Scripts SQL et données
│   ├── app.py            # Serveur Flask & API REST (Port 3001)
│   ├── test_gen.py       # Script de test de génération
│   ├── requirements.txt  # Dépendances Python
│   └── .gitignore
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

### 1. Installer les dépendances

```bash
# Frontend
npm install --prefix frontend

# Backend
pip install -r backend/requirements.txt
```

### 2. Démarrer le Backend (Python/Flask)
```bash
# Depuis la racine :
npm run dev:backend

# OU directement :
cd backend
python app.py
```
> Le serveur API écoute sur **http://localhost:3001**

### 3. Démarrer le Frontend (React/Vite)
```bash
# Depuis la racine :
npm run dev:frontend

# OU directement :
cd frontend
npm run dev
```
> L'application s'ouvrira sur **http://localhost:5173**

---

## 🛠 Technologies

| Couche   | Stack                    |
|----------|--------------------------|
| Frontend | React 19, Vite 8         |
| Backend  | Python 3.13, Flask 3     |
| Database | MySQL (emplois_du_temps) |
