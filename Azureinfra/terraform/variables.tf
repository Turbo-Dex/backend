variable "subscription_id" {
  type = string
}

variable "project_name" {
  type    = string
  default = "turbodex"
}

variable "environment" {
  type    = string
  default = "staging"
}

variable "location" {
  type    = string
  default = "westeurope"
}

variable "tags" {
  type    = map(string)
  default = {}
}

# App Service
variable "appservice_sku" {
  type    = string
  default = "B1"
}

variable "backend_image_name" {
  type    = string
  default = "backend"
}

variable "backend_image_tag" {
  type    = string
  default = "latest"
}

variable "backend_port" {
  type    = number
  default = 8000
}

# PostgreSQL
variable "pg_admin_user" {
  type    = string
  default = "pgadmin"
}

variable "pg_admin_password" {
  type      = string
  sensitive = true
}

variable "pg_database" {
  type    = string
  default = "turbodex"
}

variable "pg_sku_name" {
  type    = string
  default = "B_Standard_B1ms" 
}

variable "storage_account" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "app_service_name" {
  type = string
}

variable "postgres_server" {
  type = string
}

variable "acr_admin_password" {
  type      = string
  sensitive = true
}
