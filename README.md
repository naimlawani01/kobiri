# Kobiri - Backend de gestion de tontines

Plateforme backend FastAPI pour la digitalisation des tontines en Afrique de l'Ouest.

## Fonctionnalités

### Gestion des utilisateurs
- Inscription et authentification JWT
- Rôles: membre, président, trésorier, admin
- Profils utilisateurs avec vérification email/téléphone

### Gestion des tontines
- Création et paramétrage des tontines
- Types: rotative, cumulative, mixte
- Fréquences: quotidien, hebdomadaire, bimensuel, mensuel, trimestriel
- Gestion des membres et des règles
- Code unique pour rejoindre une tontine

### Sessions de cotisation
- Planification des sessions
- Suivi des cotisations attendues/reçues
- Statistiques détaillées

### Paiements
- **Manuel**: Enregistrement des paiements en espèces avec preuve
- **Automatisé**: Intégration mobile money
  - Orange Money
  - MTN Mobile Money
  - Wave
  - Free Money
  - Moov Money
- Validation par les gestionnaires
- Gestion des pénalités de retard

### Tours de passage
- Ordre de passage configurable
- Génération automatique (aléatoire, alphabétique, date d'adhésion)
- Suivi des versements
- Confirmation de réception

### Notifications
- SMS
- Email
- Push notifications
- In-app
- Rappels automatiques de cotisation

## Stack technique

- **Framework**: FastAPI 0.104.1
- **Base de données**: PostgreSQL avec SQLAlchemy 2.0
- **Authentification**: JWT (python-jose)
- **Validation**: Pydantic 2.5
- **Logging**: Loguru
- **Migrations**: Alembic
- **Tests**: pytest

## Installation

### Prérequis

- Python 3.10+
- PostgreSQL 14+
- pip ou poetry

### Configuration

1. Cloner le repository:
```bash
git clone <repository-url>
cd kobiri
```

2. Créer un environnement virtuel:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows
```

3. Installer les dépendances:
```bash
pip install -r requirements.txt
```

4. Configurer les variables d'environnement:
```bash
cp .env.example .env
# Éditer .env avec vos paramètres
```

Variables d'environnement requises:
```env
# Base de données
DATABASE_URL=postgresql://user:password@localhost:5432/kobiri_db

# JWT
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
APP_NAME=Kobiri
DEBUG=True
ENVIRONMENT=development

# Mobile Money (optionnel)
ORANGE_MONEY_API_KEY=
ORANGE_MONEY_API_SECRET=
MTN_MOMO_API_KEY=
MTN_MOMO_API_SECRET=
WAVE_API_KEY=
```

5. Créer la base de données:
```bash
# PostgreSQL
createdb kobiri_db
```

6. Appliquer les migrations:
```bash
alembic upgrade head
```

## Lancement

### Développement
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Avec Docker
```bash
docker-compose up -d
```

## Documentation API

Une fois l'application lancée:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Structure du projet

```
kobiri/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Point d'entrée FastAPI
│   ├── config.py               # Configuration
│   ├── database.py             # Configuration SQLAlchemy
│   ├── models/                 # Modèles SQLAlchemy
│   │   ├── user.py
│   │   ├── tontine.py
│   │   ├── session.py
│   │   ├── payment.py
│   │   ├── passage.py
│   │   └── notification.py
│   ├── schemas/                # Schémas Pydantic
│   │   ├── user.py
│   │   ├── tontine.py
│   │   ├── session.py
│   │   ├── payment.py
│   │   ├── passage.py
│   │   └── notification.py
│   ├── api/
│   │   ├── deps.py             # Dépendances (auth, permissions)
│   │   └── v1/
│   │       ├── router.py       # Routeur principal
│   │       └── endpoints/      # Routes API
│   ├── core/
│   │   ├── security.py         # JWT, hashing
│   │   └── logging.py          # Configuration logs
│   └── services/
│       ├── payment_service.py  # Intégration mobile money
│       └── notification_service.py
├── alembic/                    # Migrations
├── tests/                      # Tests
├── logs/                       # Fichiers de log
├── requirements.txt
├── alembic.ini
└── README.md
```

## API Endpoints

### Authentification
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/auth/register` | Inscription |
| POST | `/api/v1/auth/login` | Connexion |
| POST | `/api/v1/auth/refresh` | Rafraîchir token |
| GET | `/api/v1/auth/me` | Profil utilisateur |
| POST | `/api/v1/auth/change-password` | Changer mot de passe |
| POST | `/api/v1/auth/forgot-password` | Mot de passe oublié |

### Utilisateurs
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/users` | Liste utilisateurs (admin) |
| GET | `/api/v1/users/{id}` | Détails utilisateur |
| PUT | `/api/v1/users/{id}` | Modifier utilisateur |
| DELETE | `/api/v1/users/{id}` | Désactiver utilisateur |

### Tontines
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/tontines` | Créer tontine |
| GET | `/api/v1/tontines` | Liste tontines |
| GET | `/api/v1/tontines/{id}` | Détails tontine |
| PUT | `/api/v1/tontines/{id}` | Modifier tontine |
| DELETE | `/api/v1/tontines/{id}` | Désactiver tontine |
| POST | `/api/v1/tontines/join` | Rejoindre par code |
| POST | `/api/v1/tontines/{id}/members` | Ajouter membre |
| GET | `/api/v1/tontines/{id}/members` | Liste membres |
| POST | `/api/v1/tontines/{id}/leave` | Quitter tontine |

### Sessions
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/sessions` | Créer session |
| GET | `/api/v1/sessions/tontine/{id}` | Sessions d'une tontine |
| GET | `/api/v1/sessions/{id}` | Détails session |
| POST | `/api/v1/sessions/{id}/open` | Ouvrir session |
| POST | `/api/v1/sessions/{id}/close` | Fermer session |
| GET | `/api/v1/sessions/{id}/stats` | Statistiques |

### Paiements
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/payments` | Enregistrer paiement manuel |
| POST | `/api/v1/payments/initiate` | Initier paiement mobile |
| GET | `/api/v1/payments` | Liste paiements |
| GET | `/api/v1/payments/{id}` | Détails paiement |
| POST | `/api/v1/payments/{id}/validate` | Valider/rejeter |
| POST | `/api/v1/payments/callback/orange` | Callback Orange |
| POST | `/api/v1/payments/callback/mtn` | Callback MTN |
| POST | `/api/v1/payments/callback/wave` | Callback Wave |

### Passages
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/passages/generate/{tontine_id}` | Générer ordre |
| GET | `/api/v1/passages/tontine/{id}` | Liste passages |
| GET | `/api/v1/passages/tontine/{id}/schedule` | Planning |
| POST | `/api/v1/passages/{id}/start` | Démarrer passage |
| POST | `/api/v1/passages/{id}/payout` | Effectuer versement |
| POST | `/api/v1/passages/{id}/confirm` | Confirmer réception |

### Notifications
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/notifications` | Mes notifications |
| GET | `/api/v1/notifications/unread-count` | Nombre non lues |
| POST | `/api/v1/notifications/mark-read` | Marquer comme lues |
| POST | `/api/v1/notifications/send-reminder` | Envoyer rappel |

## Tests

```bash
# Tous les tests
pytest

# Avec couverture
pytest --cov=app --cov-report=html

# Tests spécifiques
pytest tests/test_auth.py -v
```

## Logging

Les logs sont enregistrés dans `logs/kobiri.log` avec rotation automatique.

Niveaux de log:
- **DEBUG**: Détails de développement
- **INFO**: Événements normaux
- **WARNING**: Alertes non critiques
- **ERROR**: Erreurs nécessitant attention

## Sécurité

- Mots de passe hashés avec bcrypt
- Tokens JWT avec expiration
- Validation des entrées avec Pydantic
- Protection CORS
- Rate limiting recommandé en production

## Contributions

1. Fork le projet
2. Créer une branche (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commit (`git commit -am 'Ajoute nouvelle fonctionnalité'`)
4. Push (`git push origin feature/nouvelle-fonctionnalite`)
5. Créer une Pull Request

## Licence

MIT License

## Contact

Pour toute question: contact@kobiri.com

