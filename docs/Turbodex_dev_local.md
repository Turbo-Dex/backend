#  Turbodex — Guide Dev Local

## 1. Pré-requis

- **Python 3.11+**
- **Azure Functions Core Tools v4**
- **Azure CLI** (optionnel pour debug)

Vérifier :

```bash
python3 --version
func --version
```

## 2. Préparer la config

- Copiez les fichiers fournis :
  - `backend/.env` → pour l’API
  - `backend/functions/local.settings.json` → pour la Function

⚠️ Ces fichiers contiennent les secrets → **ne pas commit sur Git, respecter le .gitignore**

## 3. Installer les dépendances API

```bash
cd backend
python3 -m venv .venv_api
source .venv_api/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Lancer l’API FastAPI

Toujours dans `backend/` :

```bash
source .venv_api/bin/activate
export PYTHONPATH=$(pwd)   # nécessaire pour "app.*"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

+ L’API est dispo sur http://localhost:8000

+ Documentation interactive : http://localhost:8000/docs

## 5. Lancer la Function

Dans un autre terminal :

```bash
cd backend/functions
func start
```

 La Function consomme automatiquement les messages envoyés dans la queue `process-image`.

**Rappel du pipeline : **

```sql
[Client / Front] --(POST multipart)--> [FastAPI /v1/images/upload]
       |                                        |
       |                              1) Upload blob RAW
       |                              2) Enqueue message (Base64)
       v                                        |
                                   [Azure Queue: process-image]
                                                |
                                                | (trigger)
                                                v
                                      [Azure Function process_image]
                                    3) download RAW
                                    4) blur (IA_BLUR_URL) 
                                    5) predict (IA_PREDICT_URL) 
                                    6) upload PROCESSED
                                    7) update Mongo 
                                                |
                                                v
                         [Azure Blob: processed/<YYYYMMDD>/<uuid>.png|jpg]

                   (Contrôle) --> GET /v1/images/status?blob_name=YYYYMMDD/xxx.jpg
```

## 6. Tester l’upload

Envoyer une image de test :

```bash
curl -F "file=@test.jpg" -F "post_id=000000000000000000000000" \
  http://localhost:8000/v1/images/upload
```

Réponse attendue :

```bash
{
  "ok": true,
  "blob_name": "20250903/xxxx.jpg",
  "raw_url": "https://.../raw/20250903/xxxx.jpg",
  "processed_url_hint": "https://.../processed/20250903/xxxx.jpg",
  "queue": "process-image",
  "message_id": "...",
  "message_payload": {...},
  "storage_account": "turbodexeyne07"
}
```

## 7. Vérifier le statut

```bash
BLOB="20250903/xxxx.jpg"
curl "http://localhost:8000/v1/images/status?blob_name=$BLOB"
```

Si tout va bien :

```json
{
  "blob_name": "...jpg",
  "processed_exists": true,
  "processed_url": "https://.../processed/20250903/xxxx.jpg"
}
```

## 8. Debug rapide

- **Si `processed_exists: false`**
   → Vérifier les logs de la Function (`func start`).
- **Si `message_id` = null**
   → Vérifier que `.env` contient bien `AZURE_STORAGE_CONN`.
- **Si Mongo ne répond pas**
   → Vérifier `MONGO_URI` et le firewall de Cosmos DB.