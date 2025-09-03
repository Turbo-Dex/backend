terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.29"
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

# Création du RG
resource "azurerm_resource_group" "rg" {
  name     = "${var.project_name}-${var.environment}-rg"
  location = var.location
  tags     = var.tags
}

# Storage Account
resource "random_string" "suffix" {
  length  = 6
  upper   = false
  lower   = true
  special = false
}

resource "azurerm_storage_account" "sa" {
  name                     = "${replace(var.project_name, "-", "")}${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags                     = var.tags
}

resource "azurerm_storage_container" "images" {
  name                  = "images"
  storage_account_name  = azurerm_storage_account.sa.name
  container_access_type = "private"
}

# ACR
resource "azurerm_container_registry" "acr" {
  name                = "${replace(var.project_name, "-", "")}acr"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = true
  tags                = var.tags
}

# AKS Cluster
resource "azurerm_kubernetes_cluster" "aks" {
  name                = "${var.project_name}-${var.environment}-aks"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  dns_prefix          = "${var.project_name}-${var.environment}"

  default_node_pool {
    name       = "system"
    node_count = var.aks_node_count
    vm_size    = var.aks_vm_size
  }

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

provider "kubernetes" {
  host                   = azurerm_kubernetes_cluster.aks.kube_config[0].host
  client_certificate     = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_certificate)
  client_key             = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_key)
  cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].cluster_ca_certificate)
}


# Nom dérivé si non fourni
locals {
  cosmos_account_name  = coalesce(var.cosmos_account_name, "${replace(var.project_name, "-", "")}${var.environment}cosmos")
  function_app_name    = coalesce(var.function_app_name, "${var.project_name}-${var.environment}-func")
}

# Cosmos DB MongoDB (vCore)
resource "azurerm_cosmosdb_account" "cosmos" {
  name                = local.cosmos_account_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "MongoDB"          # SQL -> MongoDB
  offer_type          = "Standard"         # vCore nécessite Standard
  enable_multiple_write_locations = false

  capabilities {
    name = "EnableMongo"                   # MongoDB API
  }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.rg.location
    failover_priority = 0
  }

  is_virtual_network_filter_enabled = false

  tags = var.tags
}

# Base MongoDB
resource "azurerm_cosmosdb_mongo_database" "db" {
  name                = var.cosmos_db_name
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.cosmos.name
}

# Collection MongoDB
resource "azurerm_cosmosdb_mongo_collection" "collection" {
  name                = var.cosmos_container_name
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.cosmos.name
  database_name       = azurerm_cosmosdb_mongo_database.db.name
  throughput          = 400
  shard_key           = "_id"

  index {
    keys = ["_id"]
  }
}





# Observabilité
resource "azurerm_log_analytics_workspace" "law" {
  name                = "${var.project_name}-${var.environment}-law"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "appi" {
  name                = "${var.project_name}-${var.environment}-appi"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.law.id
  tags                = var.tags
}

# Function App Linux (Consumption)
resource "azurerm_linux_function_app" "func" {
  name                = local.function_app_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  # Plan "consumption" implicite via sku_name = "Y1"
  service_plan_id = azurerm_service_plan.func_plan.id

  storage_account_name       = azurerm_storage_account.sa.name
  storage_account_access_key = azurerm_storage_account.sa.primary_access_key
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version  = var.function_runtime == "python" ? "3.11" : null
      node_version    = var.function_runtime == "node"   ? "~18"  : null
      dotnet_version  = var.function_runtime == "dotnet" ? "v8.0" : null
      # adapte ci-dessus selon ton runtime
    }
    cors {
      allowed_origins = ["*"] # à restreindre en prod
    }
  }

app_settings = {
  APPINSIGHTS_INSTRUMENTATIONKEY        = azurerm_application_insights.appi.instrumentation_key
  APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.appi.connection_string
  FUNCTIONS_WORKER_RUNTIME              = var.function_runtime
  WEBSITE_RUN_FROM_PACKAGE              = "1"

  # Cosmos MongoDB vCore
  COSMOS_CONNECTION_STRING = azurerm_cosmosdb_account.cosmos.connection_strings[0]
  COSMOS_DB                = azurerm_cosmosdb_mongo_database.db.name
  COSMOS_COLLECTION        = azurerm_cosmosdb_mongo_collection.collection.name

  # Blob
  BLOB_CONNECTION_STRING = azurerm_storage_account.sa.primary_connection_string
  BLOB_CONTAINER_IMAGES  = azurerm_storage_container.images.name
}


  tags = var.tags
}

# Plan Functions (Y1 = Consumption)
resource "azurerm_service_plan" "func_plan" {
  name                = "${var.project_name}-${var.environment}-funcplan"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "Y1"   # Consumption
  tags                = var.tags
}
