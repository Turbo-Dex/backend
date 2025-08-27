Absolutely! Here’s a concise **Markdown cheat sheet** summarizing all the **essential commands and steps** from our discussion to manage your Docker images, ACR, AKS deployments, and Kubernetes services. I’ve organized it step by step so it’s easy to follow.

````markdown
# TurboDex AKS & Docker Cheat Sheet

## 1. Azure CLI: Login & Subscription

```bash
# Show current Azure subscription
az account show --output table

# Login to Azure (opens browser)
az login

# If no browser, use device code
az login --use-device-code
````

---

## 2. Azure Container Registry (ACR)

```bash
# Login to ACR
az acr login --name turbodexacr

# List repositories
az acr repository list --name turbodexacr --output table

# List tags for a repository
az acr repository show-tags --name turbodexacr --repository <repo-name>
```

---

## 3. Docker Image: Build & Push

```bash
# Build image locally
docker build -t car-api .

# Tag image for ACR
docker tag car-api turbodexacr.azurecr.io/car-api:latest

# Push image to ACR
docker push turbodexacr.azurecr.io/car-api:latest
```

> ⚠️ If image is huge (e.g., >7GB), use a **multi-stage build** and CPU-only PyTorch to slim it down:

```dockerfile
# Example: slim Python image + CPU-only Torch
FROM python:3.11-slim AS build

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt
COPY . .

FROM python:3.11-slim
WORKDIR /app
COPY --from=build /install /usr/local
COPY --from=build /app /app
EXPOSE 5000
CMD ["python", "app.py"]
```

---

## 4. AKS Cluster & Terraform

```bash
# Apply Terraform config
terraform init
terraform apply -auto-approve
```

> Terraform outputs for AKS & services:

```bash
terraform output acr_login_server
terraform output storage_account_name
terraform output db_host
terraform output aks_name
terraform output blur_lb_ip
terraform output analyse_lb_ip
```

---

## 5. Kubernetes Deployments

```hcl
# Example Deployment (Terraform)
resource "kubernetes_deployment" "analyse" {
  metadata { name = "analyse-deployment" }
  spec {
    replicas = 2
    selector { match_labels = { app = "analyse" } }
    template {
      metadata { labels = { app = "analyse" } }
      spec {
        container {
          name  = "analyse"
          image = "${var.acr_login_server}/analyse:latest"
          port { container_port = 5000 }
          env_from { secret_ref { name = kubernetes_secret.app_secrets.metadata[0].name } }
        }
      }
    }
  }
}

# Services
resource "kubernetes_service" "analyse_lb" {
  metadata { name = "analyse-lb" }
  spec {
    type     = "LoadBalancer"
    selector = { app = "analyse" }
    port { port = 81 target_port = 5000 }
  }
}
```

---

## 6. Kubernetes Commands

```bash
# List pods
kubectl get pods -A

# List services
kubectl get svc -A

# Describe a pod
kubectl describe pod <pod-name>

# Check pod logs
kubectl logs <pod-name>
```

---

## 7. Test Your API

```bash
# Using curl (POST with image upload)
curl -X POST "http://<loadbalancer-ip>:<port>/predict" -F "image=@voiture.jpg"

# Example for Analyse service
curl -X POST "http://4.251.17.134:81/predict" -F "image=@voiture.jpg"
```

> ⚠️ Browser cannot directly do multipart POST; use **Postman/Insomnia** or a small HTML form:

```html
<form action="http://<loadbalancer-ip>:81/predict" method="post" enctype="multipart/form-data">
  <input type="file" name="image" />
  <input type="submit" value="Envoyer" />
</form>
```

---

## 8. Common Issues

* `ImagePullBackOff`: Docker image not found or ACR authentication failed.

  ```bash
  az acr login --name turbodexacr
  ```
* Large image: use multi-stage builds and CPU-only libraries.
* LB access: Kubernetes `ClusterIP` is internal; use `LoadBalancer` to expose externally.

---

## Notes

* Use **2 separate LoadBalancers** for Blur (`80`) and Analyse (`81`).
* Keep sensitive values (DB passwords) in Kubernetes Secrets.
* Always reference images with full ACR URL: `turbodexacr.azurecr.io/<image>:<tag>`.

```
```
