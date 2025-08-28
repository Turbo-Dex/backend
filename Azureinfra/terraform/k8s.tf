##########################################################
# Kubernetes Secret pour ACR + DB
##########################################################
resource "kubernetes_secret" "app_secrets" {
  metadata {
    name = "app-secrets"
  }
  data = {
    DOCKER_REGISTRY_SERVER_URL      = var.acr_login_server
    DOCKER_REGISTRY_SERVER_USERNAME = azurerm_container_registry.acr.admin_username
    DOCKER_REGISTRY_SERVER_PASSWORD = azurerm_container_registry.acr.admin_password
    DB_HOST                         = var.db_host
    DB_NAME                         = var.pg_database
    DB_USER                         = var.pg_admin_user
    DB_PASSWORD                     = var.pg_admin_password
    STORAGE_ACCOUNT                 = var.storage_account_name
  }
}

##########################################################
# Deployment Blur IA
##########################################################
resource "kubernetes_deployment" "blur" {
  metadata {
    name   = "blur-deployment"
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
    name   = "analyse-deployment"
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
  metadata { name = "blur-service" }
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
  metadata { name = "analyse-service" }
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
  metadata { name = "blur-lb" }
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
  metadata { name = "analyse-lb" }
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

