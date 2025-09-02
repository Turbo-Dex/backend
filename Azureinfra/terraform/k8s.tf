##########################################################
# Kubernetes Secret pour ACR + DB
##########################################################
resource "kubernetes_secret" "app_secrets" {
  metadata {
    name      = "app-secrets"
    namespace = "default"
  }
  data = {
    DOCKER_REGISTRY_SERVER_URL      = var.acr_login_server
    DOCKER_REGISTRY_SERVER_USERNAME = azurerm_container_registry.acr.admin_username
    DOCKER_REGISTRY_SERVER_PASSWORD = azurerm_container_registry.acr.admin_password

    STORAGE_ACCOUNT        = var.storage_account_name
    BLOB_CONNECTION_STRING = azurerm_storage_account.sa.primary_connection_string

    COSMOS_ENDPOINT  = azurerm_cosmosdb_account.cosmos.endpoint
    COSMOS_KEY       = azurerm_cosmosdb_account.cosmos.primary_key
    COSMOS_DB        = azurerm_cosmosdb_sql_database.db.name
    COSMOS_CONTAINER = azurerm_cosmosdb_sql_container.container.name
  }
}

##########################################################
# Deployment Blur IA
##########################################################
resource "kubernetes_deployment" "blur" {
  metadata {
    name      = "blur-deployment"
    namespace = "default"
    labels    = { app = "blur" }
  }

  spec {
    replicas = 2
    selector {
      match_labels = { app = "blur" }
    }
    template {
      metadata {
        labels = { app = "blur" }
      }
      spec {
        container {
          name  = "blur"
          image = "${var.acr_login_server}/${var.blur_image_name}:${var.blur_image_tag}"
          image_pull_policy = "Always"
          port {
            container_port = var.blur_container_port
          }
          env_from {
            secret_ref {
              name = kubernetes_secret.app_secrets.metadata[0].name
            }
          }
        }
      }
    }
  }
}

##########################################################
# Deployment Analyse IA
##########################################################
resource "kubernetes_deployment" "analyse" {
  metadata {
    name      = "analyse-deployment"
    namespace = "default"
    labels    = { app = "analyse" }
  }

  spec {
    replicas = 2
    selector {
      match_labels = { app = "analyse" }
    }
    template {
      metadata {
        labels = { app = "analyse" }
      }
      spec {
        container {
          name  = "analyse"
          image = "${var.acr_login_server}/${var.analyse_image_name}:${var.analyse_image_tag}"
          image_pull_policy = "Always"
          port {
            container_port = var.analyse_container_port
          }
          env_from {
            secret_ref {
              name = kubernetes_secret.app_secrets.metadata[0].name
            }
          }
        }
      }
    }
  }
}

##########################################################
# Services internes (ClusterIP)
##########################################################
resource "kubernetes_service" "blur_service" {
  metadata {
    name      = "blur-service"
    namespace = "default"
  }
  spec {
    selector = { app = "blur" }
    port {
      port        = 80
      target_port = var.blur_container_port
    }
    type = "ClusterIP"
  }
}

resource "kubernetes_service" "analyse_service" {
  metadata {
    name      = "analyse-service"
    namespace = "default"
  }
  spec {
    selector = { app = "analyse" }
    port {
      port        = 5000
      target_port = var.analyse_container_port
    }
    type = "ClusterIP"
  }
}

##########################################################
# LoadBalancer Blur
##########################################################
resource "kubernetes_service" "blur_lb" {
  metadata {
    name      = "blur-lb"
    namespace = "default"
  }
  spec {
    type     = "LoadBalancer"
    selector = { app = "blur" }

    port {
      name        = "http"
      port        = 80
      target_port = var.blur_container_port
    }

    # IP fixe optionnelle
    load_balancer_ip = var.blur_lb_ip
  }
}

##########################################################
# LoadBalancer Analyse
##########################################################
resource "kubernetes_service" "analyse_lb" {
  metadata {
    name      = "analyse-lb"
    namespace = "default"
  }
  spec {
    type     = "LoadBalancer"
    selector = { app = "analyse" }

    port {
      name        = "http"
      port        = 80
      target_port = var.analyse_container_port
    }

    # IP fixe optionnelle
    load_balancer_ip = var.analyse_lb_ip
  }
}
