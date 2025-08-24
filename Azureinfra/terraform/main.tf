terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

locals {
  name_prefix = lower(replace(var.project_name, " ", "-"))
  tags = merge({
    project = var.project_name
    env     = var.environment
  }, var.tags)
}

# Resource Group
resource "azurerm_resource_group" "rg" {
  name     = "${local.name_prefix}-${var.environment}-rg"
  location = var.location
  tags     = local.tags
}

# Storage (Blob) - images & models
resource "random_string" "suffix" {
  length  = 6
  upper   = false
  lower   = true
  special = false
}

resource "azurerm_storage_account" "sa" {
  name                     = "${replace(local.name_prefix, "-", "")}${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags                     = local.tags
}

# Force containers to wait until storage account is ready
resource "azurerm_storage_container" "images" {
  name                  = "images"
  storage_account_name  = azurerm_storage_account.sa.name
  container_access_type = "private"

  depends_on = [azurerm_storage_account.sa]
}

resource "azurerm_storage_container" "models" {
  name                  = "models"
  storage_account_name  = azurerm_storage_account.sa.name
  container_access_type = "private"

  depends_on = [azurerm_storage_account.sa]
}


# Azure Container Registry (for backend/AI images)
resource "azurerm_container_registry" "acr" {
  name                = "${local.name_prefix}acr"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = true   # enable admin user
  tags                = local.tags
}

# App Service Plan (Linux)
resource "azurerm_service_plan" "asp" {
  name                = "${local.name_prefix}-${var.environment}-plan"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  os_type             = "Linux"
  sku_name            = var.appservice_sku
  tags                = local.tags
}

# Web App for Containers (FastAPI backend)
resource "azurerm_linux_web_app" "api" {
  name                = "${local.name_prefix}-${var.environment}-api"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  service_plan_id     = azurerm_service_plan.asp.id
  https_only          = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      docker_image     = "${azurerm_container_registry.acr.login_server}/${var.backend_image_name}"
      docker_image_tag = var.backend_image_tag
    }
    always_on = true
  }

app_settings = {
  WEBSITES_PORT              = tostring(var.backend_port)
  DOCKER_REGISTRY_SERVER_URL = "https://${azurerm_container_registry.acr.login_server}"
  DOCKER_REGISTRY_SERVER_USERNAME = azurerm_container_registry.acr.admin_username
  DOCKER_REGISTRY_SERVER_PASSWORD = azurerm_container_registry.acr.admin_password
  DOCKER_ENABLE_CI           = "true"

  # PostgreSQL connection settings
  DB_HOST     = azurerm_postgresql_flexible_server.pg.fqdn
  DB_NAME     = azurerm_postgresql_flexible_server_database.db.name
  DB_USER     = "${var.pg_admin_user}@${azurerm_postgresql_flexible_server.pg.name}"
  DB_PASSWORD = var.pg_admin_password

  # Storage settings
  AZURE_STORAGE_ACCOUNT_NAME     = azurerm_storage_account.sa.name
  AZURE_STORAGE_CONTAINER_IMAGES = azurerm_storage_container.images.name
  AZURE_STORAGE_CONTAINER_MODELS = azurerm_storage_container.models.name
}


  tags = local.tags

  depends_on = [
    azurerm_container_registry.acr,
    azurerm_service_plan.asp,
    azurerm_postgresql_flexible_server_database.db,
    azurerm_storage_account.sa
  ]
}

# Grant Web App identity pull access on ACR
data "azurerm_subscription" "current" {}

# PostgreSQL Flexible Server + DB
resource "azurerm_postgresql_flexible_server" "pg" {
  name                   = "${local.name_prefix}-${var.environment}-pg"
  resource_group_name    = azurerm_resource_group.rg.name
  location               = var.location
  administrator_login    = var.pg_admin_user
  administrator_password = var.pg_admin_password
  version                = "14"
  sku_name               = var.pg_sku_name
  storage_mb             = 32768
  backup_retention_days  = 7
  zone                   = "1"
  tags                   = local.tags
}

resource "azurerm_postgresql_flexible_server_database" "db" {
  name      = var.pg_database
  server_id = azurerm_postgresql_flexible_server.pg.id

  depends_on = [azurerm_postgresql_flexible_server.pg]
}

# Allow all Azure services to access DB
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  name             = "allow-azure"
  server_id        = azurerm_postgresql_flexible_server.pg.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"

  depends_on = [azurerm_postgresql_flexible_server.pg]
}

# Outputs
output "api_url" {
  value = azurerm_linux_web_app.api.default_hostname
}

output "acr_login_server" {
  value = azurerm_container_registry.acr.login_server
}

output "storage_account_name" {
  value = azurerm_storage_account.sa.name
}
