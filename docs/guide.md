


# TurboDex AKS & Docker Cheat Sheet

## 1. Azure CLI: Login & Subscription

```bash
# Show current Azure subscription
az account show --output table

# Login to Azure (opens browser)
az login

# If no browser, use device code
az login --use-device-code
```

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


### Car API
```bash
# Build image locally
docker build -t car-api .

# Tag image for ACR
docker tag car-api turbodexacr.azurecr.io/car-api:latest

# Push image to ACR
docker push turbodexacr.azurecr.io/car-api:latest
```

### Car API
```bash
# Build image locally
docker build -t car-blur .

# Tag image for ACR
docker tag car-blur turbodexacr.azurecr.io/car-blur:latest

# Push image to ACR
docker push turbodexacr.azurecr.io/car-blur:latest
```

---

## 4. AKS Cluster & Terraform

```bash
# Apply Terraform config
terraform init
terraform plan -out=tfplan  
terraform apply -auto-approve tfplan
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


## 5. Kubernetes Commands

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

## 6. Test Your API

```bash
# Car api
curl -X POST "http://<loadbalancer-ip>:<port>/predict" -F "image=@voiture.jpg"

# Car blur
curl -X POST "http://<loadbalancer-ip>/blur/" \
  -H "accept: image/png" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@car.jpg" \
  --output blurred_car.png
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

* We Use **2 separate LoadBalancers** for Blur and Analyse both on port 80 of their respective loadBalancer.
* Always reference images with full ACR URL: `turbodexacr.azurecr.io/<image>:<tag>`.

## Switch account
1. Logout from az
2. Delete temp tf files
3. Init then validate
4. Apply
5. Push docker images to ACR
6. Faire
```bash
az aks update -n turbodex-staging-aks -g turbodex-staging-rg --attach-acr turbodexacr
```
7. New terraform apply
   

