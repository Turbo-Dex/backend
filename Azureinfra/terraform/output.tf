output "acr_login_server" {
  value = azurerm_container_registry.acr.login_server
}

output "storage_account_name" {
  value = azurerm_storage_account.sa.name
}

output "db_host" {
  value = azurerm_postgresql_flexible_server.pg.fqdn
}

output "aks_name" {
  value = azurerm_kubernetes_cluster.aks.name
}

output "blur_lb_ip" {
  value = kubernetes_service.blur_lb.status[0].load_balancer[0].ingress[0].ip
}

output "analyse_lb_ip" {
  value = kubernetes_service.analyse_lb.status[0].load_balancer[0].ingress[0].ip
}
