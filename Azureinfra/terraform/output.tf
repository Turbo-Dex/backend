output "acr_login_server" {
  value = azurerm_container_registry.acr.login_server
}

output "storage_account_name" {
  value = azurerm_storage_account.sa.name
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

output "cosmos_endpoint" {
  value = azurerm_cosmosdb_account.cosmos.endpoint
}

output "function_app_name" {
  value = azurerm_linux_function_app.func.name
}

output "function_default_hostname" {
  value = azurerm_linux_function_app.func.default_hostname
}

output "blob_connection_string" {
  value     = azurerm_storage_account.sa.primary_connection_string
  sensitive = true
}


