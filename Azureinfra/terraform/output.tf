output "webapp_fqdn" {
  value = "https://${azurerm_linux_web_app.api.default_hostname}"
}
output "postgres_host" {
  value = azurerm_postgresql_flexible_server.pg.fqdn
}
output "storage_account" {
  value = azurerm_storage_account.sa.name
}
