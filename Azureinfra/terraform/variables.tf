# =============================
# Azure / Project
# =============================
variable "subscription_id" {
  type = string
}

variable "project_name" {
  type = string
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "location" {
  type    = string
  default = "westeurope"
}

variable "tags" {
  type    = map(string)
  default = {}
}


# =============================
# AKS
# =============================
variable "aks_name" {
  type        = string
  description = "Nom du cluster AKS"
}

variable "aks_node_count" {
  type    = number
  default = 2
}

variable "aks_vm_size" {
  type    = string
  default = "Standard_DS2_v2"
}

# =============================
# Docker Images
# =============================
variable "blur_image_name" {
  type    = string
  default = "blur"
}

variable "blur_image_tag" {
  type    = string
  default = "latest"
}

variable "analyse_image_name" {
  type    = string
  default = "analyse"
}

variable "analyse_image_tag" {
  type    = string
  default = "latest"
}

variable "acr_login_server" {
  type        = string
  description = "Login server de l'Azure Container Registry"
}

# =============================
# Container Ports
# =============================
variable "blur_container_port" {
  type    = number
  default = 5000
}

variable "analyse_container_port" {
  type    = number
  default = 5000
}

# =============================
# Storage
# =============================
variable "storage_account_name" {
  type        = string
  description = "Nom du compte de stockage"
}

# =============================
# LoadBalancer IPs (optionnel)
# =============================
variable "blur_lb_ip" {
  type        = string
  description = "IP fixe pour le LoadBalancer Blur"
  default     = null
}

variable "analyse_lb_ip" {
  type        = string
  description = "IP fixe pour le LoadBalancer Analyse"
  default     = null
}


variable "app_service_plan" {
  type = string
}



variable "cosmos_account_name" {
  type        = string
  description = "Nom du compte Cosmos DB"
  default     = null
}

variable "cosmos_db_name" {
  type        = string
  default     = "turbodexdb"
}

variable "cosmos_container_name" {
  type        = string
  default     = "items"
}

variable "cosmos_container_pk" {
  type        = string
  default     = "/id"
}

variable "function_app_name" {
  type        = string
  default     = null
}

variable "function_runtime" {
  type        = string
  description = "Stack runtime Functions"
  default     = "python" # "node" / "dotnet" / "java" / "powershell"
}


variable "app_service_name" {
  description = "Nom de l'App Service (si utilisé)"
  type        = string
  default     = null
}

variable "backend_port" {
  description = "Port backend utilisé par l'application"
  type        = number
}

variable "acr_admin_password" {
  description = "Mot de passe admin ACR (si admin_enabled = true)"
  type        = string
  sensitive   = true
}
