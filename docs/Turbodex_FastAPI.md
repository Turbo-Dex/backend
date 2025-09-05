# Turbodex API

## Intégration FastAPI / Azure Functions / IA

### 1) Vue d'ensemble du pipeline

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

#### Remarques

+ Le message dans la queue doit être encodé en Base64.
+ L'API force l'encodage en Base64 pour éviter les erreur d'encodage lors du traîtement
+ La Function est tolérantes, si `BLUR` `PREDICT` `Mongo` échouent, on loggue et passe au reste. 

### 2) Arborescence minimale du repo

```lua
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── deps.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── auth.py
│   │   ├── uploads.py
│   │   └── images.py     <-- (route image)
│   ├── services/...
│   └── utils/...
├── requirements.txt       <-- (requirements API)
├── functions/             <-- (Azure Functions)
│   ├── host.json
│   ├── local.settings.json (local uniquement, non commit)
│   ├── requirements.txt    (requirements Function)
│   └── process_image/
│       ├── function.json
│       └── __init__.py     <-- (code de la Function)
└── README.md (ce document)

```

### 3) Pré-requis

+ Azure CLI (az) et Azure Functions Core Tools (func) installés.

+ Python 3.11+ (3.11 recommandé côté API; Functions local supporte 3.11/3.10, vérifier Core Tools install).

+ Accès à un Storage Account Azure (blobs + queues) avec :

  + Conteneurs raw et processed

  + Queues process-image et process-image-poison (créée automatiquement si poison)

  + (Optionnel) Accès à MongoDB (Atlas/Cosmos) si vous voulez le “update” en fin de traitement.

+ Endpoints IA accessibles : IA_BLUR_URL et IA_PREDICT_URL (sinon laissez vide).

### 4) variables d'environnement

`app/config.py` charge ces valeurs :

| Variable                         | Exemple                                                      | Obligatoire                              | Rôle                                         |
| -------------------------------- | ------------------------------------------------------------ | ---------------------------------------- | -------------------------------------------- |
| `APP_ENV`                        | `dev`                                                        | non                                      | Environnement d’exécution                    |
| `API_TITLE` / `API_VERSION`      | `Turbodex API` / `0.1.0`                                     | non                                      | Métadonnées API                              |
| `AZURE_STORAGE_CONN`             | `DefaultEndpointsProtocol=...;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net` | **oui** (ou variantes ci-dessous)        | Chaîne de connexion Storage                  |
| `AzureWebJobsStorage`            | idem                                                         | **oui** (si `AZURE_STORAGE_CONN` absent) | Fallback pour Storage                        |
| `StorageConn`                    | idem                                                         | non                                      | Fallback bis                                 |
| `AZURE_BLOB_CONTAINER_RAW`       | `raw`                                                        | non                                      | Conteneur source                             |
| `AZURE_BLOB_CONTAINER_PROCESSED` | `processed`                                                  | non                                      | Conteneur cible                              |
| `AZURE_QUEUE_NAME`               | `process-image`                                              | non                                      | Nom de la queue                              |
| `AZURE_STORAGE_ACCOUNT`          | `turbodexstorage`                                            | non                                      | Pour composer des URLs publiques (optionnel) |
| `MONGO_URI`                      | `mongodb+srv://user:pass@host/...`                           | non                                      | Si absent, l’API fonctionne quand même       |
| `DB_NAME`                        | `turbodex`                                                   | non                                      | DB name                                      |

> **Note Mongo** : si votre mot de passe contient des caractères spéciaux, encodez-le RFC 3986 (ex: via `urllib.parse.quote_plus`). Une URI non encodée provoque des erreurs `InvalidURI`.

Function `process_image` (fichier `functions/local.settings.json` en local ; en prod dans  variables d’App Service)

| Variable                         | Exemple                  | Obligatoire | Rôle                         |
| -------------------------------- | ------------------------ | ----------: | ---------------------------- |
| `AzureWebJobsStorage`            | Connexion Storage        |     **oui** | Blobs + Queues               |
| `AZURE_BLOB_CONTAINER_RAW`       | `raw`                    |         non | Conteneur input              |
| `AZURE_BLOB_CONTAINER_PROCESSED` | `processed`              |         non | Conteneur output             |
| `IA_BLUR_URL`                    | `http://<host>/blur/`    |         non | Endpoint blur (POST file)    |
| `IA_PREDICT_URL`                 | `http://<host>/predict/` |         non | Endpoint predict (POST file) |
| `HTTP_TIMEOUT_SECONDS`           | `20`                     |         non | Timeout HTTP IA              |
| `MONGO_URI`                      | `mongodb+srv://...`      |         non | Optionnel                    |
| `DB_NAME`                        | `turbodex`               |         non | Optionnel                    |

**Important : **`host.json` contient :

```json
{
  "version": "2.0",
  "queues": {
    "messageEncoding": "Base64",
    "maxDequeueCount": 5,
    "visibilityTimeout": "00:00:15",
    "batchSize": 16,
    "newBatchThreshold": 64
  }
}
```

> message dans la queue en Base64

### 5) Installation et lancement (local)

#### API (FastAPI)

```bash
cd backend
python -m venv .venv_api
source .venv_api/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Exporte la racine pour les imports "app.*"
export PYTHONPATH=$(pwd)

# Démarre l’API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`app/routers/images.py` – points critiques :

- **Encodage Base64 vers la queue (obligatoire) :**

```python
from azure.storage.queue import QueueClient, TextBase64EncodePolicy

q = QueueClient.from_connection_string(
    conn,
    queue_name=QUEUE_NAME,
    message_encode_policy=TextBase64EncodePolicy(),  # ← force Base64
)
q_msg = q.send_message(json.dumps(payload))

```

+ **Upload du blob RAW avec  `Content-Type` :**

```python
raw_client.upload_blob(
    data,
    overwrite=True,
    content_settings=ContentSettings(content_type=file.content_type),
)
```

+ **Endpoints exposés :**

  + POST /v1/images/upload (multipart form)

  + GET /v1/images/status?blob_name=YYYYMMDD/<name>.jpg|png|webp

#### Azure Functions (local)

```bash
cd backend/functions
python -m venv .venv_func
source .venv_func/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Vérifier que local.settings.json contient bien toutes les variables 
func start --verbose
```

**Bindings :** functions/process_image/function.json (queue trigger) :

```json
{
  "scriptFile": "__init__.py",
  "entryPoint": "main",
  "bindings": [
    {
      "name": "msg",
      "type": "queueTrigger",
      "direction": "in",
      "queueName": "process-image",
      "connection": "AzureWebJobsStorage"
    }
  ]
}
```

**Code Function :** ` functions/process_image/init.py`
Points à vérifier :

```

```



+ Lit le message JSON (le runtime le décodera de Base64 → string) ;

+ Télécharge le RAW (Blob) ;

+ POST vers IA_BLUR_URL (si set) → attend une image (ex. image/png) en réponse ;

+ POST vers IA_PREDICT_URL (si set) → attend un JSON ;

+ Upload dans processed (Content-Type cohérent : image/png si blur renvoie PNG) ;

+ (Optionnel) Mise à jour Mongo.

### 6) Tests de bout en bout

#### Nettoyage des queues (conseillé avant un test)

```bash
ACC="turbodexstorage"; KEY="<votre_account_key>"
az storage message clear --account-name "$ACC" --account-key "$KEY" --queue-name process-image
az storage message clear --account-name "$ACC" --account-key "$KEY" --queue-name process-image-poison
```

#### Upload via l'API 

```bash
RESP=$(curl -s -F "file=@test.jpg" -F "post_id=000000000000000000000000" \
       http://localhost:8000/v1/images/upload)
echo "$RESP" | jq
BLOB=$(echo "$RESP" | jq -r .blob_name)
```

**Attendu dans les logs Functions (fenêtre func start):**

+ got queue message ...

+ downloaded raw bytes=...

+ blur ok ... (si BLUR actif)

+ predict ok ... (si PREDICT actif)

+ uploaded processed processed/<BLOB>

#### Vérifier le résultat

```bash
# par l’API
curl -s "http://localhost:8000/v1/images/status?blob_name=$BLOB" | jq
# doit renvoyer "processed_exists": true

# côté Azure CLI (accès direct)
az storage blob show \
  --account-name "$ACC" --account-key "$KEY" \
  --container-name processed --name "$BLOB" \
  --query "{name:name, size:properties.contentLength, ct:properties.contentType}"
```

### 7) Déploiement en prod

#### 7.1 API (FastAPI)

- Déployer votre service (VM, App Service, container, etc.).
- Exporter les mêmes variables d’env (section 4.1) sur l’hôte cible.
- Assurez-vous que l’API a accès au Storage Account (via connection string ou RBAC/AAD si vous utilisez `--auth-mode login` côté CLI ; pour l’API on recommande la connection string simple).
- Ouvrir le port du serveur (ex. 8000 derrière un reverse proxy).

#### 7.2 Azure Function

- Publier la Function (via Azure DevOps, VS Code, `func azure functionapp publish`, etc.).
- Dans Configuration de la Function App, définir toutes les variables d’env (section 4.2).
- Vérifier que l’App Service a accès au Storage Account référencé par `AzureWebJobsStorage`.
- Vérifier les logs Application Insights (si activé) ou “Log stream”.

### 8) FAQ & Dépannage

#### “Message decoding has failed! Check MessageEncoding settings.”

- **Cause** : la queue est configurée en Base64 (`host.json`) mais l’émetteur envoie du texte brut.

- **Solution** : dans l’API, créer le `QueueClient` avec :

  ```
  QueueClient(..., message_encode_policy=TextBase64EncodePolicy())
  ```

  (ou, en dernier recours, mettre `messageEncoding: "None"` dans `host.json` — déconseillé).

#### “BlobNotFound” dans `processed`

- La Function n’a pas traité le message (poison ou erreur amont).

- Check :

  ```
  az storage message peek --account-name "$ACC" --account-key "$KEY" --queue-name process-image-poison --num-messages 5
  ```

- Si poison,  corriger la cause (le plus souvent encodage Base64).

#### Mongo : `InvalidURI` ou `Connection refused`

- `MONGO_URI` mal encodée (caractères spéciaux) → URL-encoder user/pass.
- Mongo down / firewall / DNS.  l’app loggue “Mongo unreachable” mais continue quand même.

#### “ModuleNotFoundError: No module named '...'”

- Installer les deps dans le bon venv (`.venv_api` pour API, `.venv_func` pour Functions).
- Vérifier `requirements.txt` (API) et `functions/requirements.txt` (Function).

#### “ImportError: attempted relative import with no known parent package”

- Toujours lancer l’API depuis la racine en exportant `PYTHONPATH` :

  ```
  export PYTHONPATH=$(pwd)
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```

#### URLs publiques `raw_url` / `processed_url_hint` nulles

- `AZURE_STORAGE_ACCOUNT` non défini ou conteneur non public, ce sont des liens indicatifs.
   Pour du privé, utilisez des SAS si vous voulez du partage temporaire.

### 9) Endpoints & Contrats
`POST /v1/images/upload`

+ **Form-data :**

  + file: l’image (jpeg/png/webp)

  + post_id: (optionnel) _id Mongo en hex 24 chars

+ **200/201 JSON :**

```json
{
  "ok": true,
  "blob_name": "YYYYMMDD/<uuid>.jpg",
  "raw_url": "https://<account>.blob.core.windows.net/raw/...",
  "processed_url_hint": "https://<account>.blob.core.windows.net/processed/...",
  "queue": "process-image",
  "message_id": "<id>",
  "message_payload": {"post_id":"...","blob_name":"..."},
  "storage_account": "<account>"
}
```

`GET /v1/images/status?blob_name=YYYYMMDD/<name>`

- **200 JSON :** 

```json
{
  "blob_name": "YYYYMMDD/<name>",
  "processed_exists": true,
  "processed_url": "https://<account>.blob.core.windows.net/processed/..."
}
```

### 10) Annexes

#### Exemple de functions/local.settings.json (local uniquement)

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "DefaultEndpointsProtocol=...;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net",

    "AZURE_BLOB_CONTAINER_RAW": "raw",
    "AZURE_BLOB_CONTAINER_PROCESSED": "processed",

    "IA_BLUR_URL": "http://<IP-ou-host>/blur/",
    "IA_PREDICT_URL": "http://<IP-ou-host>/predict/",
    "HTTP_TIMEOUT_SECONDS": "20",

    "MONGO_URI": "mongodb+srv://user:PASS_ENCODED@host/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000",
    "DB_NAME": "turbodex"
  }
}
```

#### Rejouer un message **manuellement** (Base64)

```bash
BLOB="20250903/xyz.jpg"
MSG='{"post_id":"000000000000000000000000","blob_name":"'"$BLOB"'"}'
BASE64=$(printf '%s' "$MSG" | base64 -w0)

az storage message put \
  --account-name "$ACC" --account-key "$KEY" \
  --queue-name process-image \
  --content "$BASE64"
```

