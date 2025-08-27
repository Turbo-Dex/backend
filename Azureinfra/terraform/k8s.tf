##########################################################
# Kubernetes Secret pour ACR + DB
##########################################################
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

##########################################################
# Deployment Blur IA
##########################################################
resource "kubernetes_deployment" "blur" {
  metadata {
    name = "blur-deployment"
    labels = { app = "blur" }
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
          image = "turbodexacr.azurecr.io/test-python:latest"
          image_pull_policy = "Always"
          port {
            container_port = 80
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
    name = "analyse-deployment"
    labels = { app = "analyse" }
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
          image = "turbodexacr.azurecr.io/test-python:latest"
          image_pull_policy = "Always"
          port {
            container_port = 80
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
# ClusterIP Services (internes)
##########################################################
resource "kubernetes_service" "blur" {
  metadata { name = "blur-service" }
  spec {
    selector = { app = "blur" }
    port {
      port        = 80
      target_port = 80
    }
    type = "ClusterIP"
  }
}

resource "kubernetes_service" "analyse" {
  metadata { name = "analyse-service" }
  spec {
    selector = { app = "analyse" }
    port {
      port        = 80
      target_port = 80
    }
    type = "ClusterIP"
  }
}

##########################################################
# LoadBalancer Service (externe pour les deux apps)
##########################################################
resource "kubernetes_service" "app_lb" {
  metadata { name = "app-lb" }
  spec {
    type = "LoadBalancer"
    selector = { app = "blur" } # Choisit un des pods pour le label "blur" (option: on peut faire un ingress plus tard)

    port {
      name        = "blur"
      port        = 80
      target_port = 80
    }

    port {
      name        = "analyse"
      port        = 81
      target_port = 80
    }
  }
}
