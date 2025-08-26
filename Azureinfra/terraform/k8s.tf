# Kubernetes Secret pour les credentials ACR + DB
resource "kubernetes_secret" "app_secrets" {
  metadata {
    name = "app-secrets"
  }

  data = {
    DOCKER_REGISTRY_SERVER_URL      = azurerm_container_registry.acr.login_server
    DOCKER_REGISTRY_SERVER_USERNAME = azurerm_container_registry.acr.admin_username
    DOCKER_REGISTRY_SERVER_PASSWORD = azurerm_container_registry.acr.admin_password
    DB_HOST                         = azurerm_postgresql_flexible_server.pg.fqdn
    DB_NAME                         = azurerm_postgresql_flexible_server_database.db.name
    DB_USER                         = "${var.pg_admin_user}@${azurerm_postgresql_flexible_server.pg.name}"
    DB_PASSWORD                     = var.pg_admin_password
    STORAGE_ACCOUNT                 = azurerm_storage_account.sa.name
  }
}

# Deployment Blur IA
resource "kubernetes_deployment" "blur" {
  metadata {
    name = "blur-deployment"
    labels = {
      app = "blur"
    }
  }

  spec {
    replicas = 2
    selector {
      match_labels = {
        app = "blur"
      }
    }
    template {
      metadata {
        labels = {
          app = "blur"
        }
      }
      spec {
        container {
          name  = "blur"
          image = "turbodexacr.azurecr.io/test-python:latest"
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

resource "kubernetes_service" "blur" {
  metadata {
    name = "blur-service"
  }
  spec {
    selector = {
      app = "blur"
    }
    port {
      port        = 80
      target_port = var.blur_container_port
    }
    type = "ClusterIP"
  }
}

# Deployment Analyse IA
resource "kubernetes_deployment" "analyse" {
  metadata {
    name = "analyse-deployment"
    labels = {
      app = "analyse"
    }
  }

  spec {
    replicas = 2
    selector {
      match_labels = {
        app = "analyse"
      }
    }
    template {
      metadata {
        labels = {
          app = "analyse"
        }
      }
      spec {
        container {
          name  = "analyse"
          image = "turbodexacr.azurecr.io/test-python:latest"
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

resource "kubernetes_service" "analyse" {
  metadata {
    name = "analyse-service"
  }
  spec {
    selector = {
      app = "analyse"
    }
    port {
      port        = 80
      target_port = var.analyse_container_port
    }
    type = "ClusterIP"
  }
}

# LoadBalancer exposant les 2 apps
resource "kubernetes_service" "loadbalancer" {
  metadata {
    name = "app-lb"
  }
  spec {
    type = "LoadBalancer"

    port {
    name        = "blur"
    port        = 80
    target_port = var.blur_container_port
    }
    port {
    name        = "analyse"
    port        = 81
    target_port = var.analyse_container_port
    }

    selector = {
      app = "blur"
    }
  }
}
