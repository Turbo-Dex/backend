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
# PostgreSQL / Database
# =============================
variable "pg_admin_user" {
  type        = string
  description = "Utilisateur admin PostgreSQL"
}

variable "pg_admin_password" {
  type        = string
  description = "Mot de passe admin PostgreSQL"
  sensitive   = true
}

variable "pg_database" {
  type    = string
  default = "appdb"
}

variable "pg_sku_name" {
  type    = string
  default = "B_Standard_B1ms"
}

variable "db_host" {
  type        = string
  description = "Adresse du serveur PostgreSQL"
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
  default = 80
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

variable "postgres_user" {
  type = string
}
