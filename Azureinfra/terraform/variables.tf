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

# DB
variable "pg_admin_user" {
  type = string
}

variable "pg_admin_password" {
  type      = string
  sensitive = true
}

variable "pg_database" {
  type    = string
  default = "appdb"
}

variable "pg_sku_name" {
  type    = string
  default = "B_Standard_B1ms"
}

# AKS
variable "aks_node_count" {
  type    = number
  default = 2
}

variable "aks_vm_size" {
  type    = string
  default = "Standard_DS2_v2"
}

# Images Docker
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

# Ports
variable "blur_container_port" {
  type    = number
  default = 8080
}

variable "analyse_container_port" {
  type    = number
  default = 8080
}
