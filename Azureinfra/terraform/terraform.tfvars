subscription_id = "c43ec34b-a7d8-48f3-8707-f22296559a82"
project_name    = "turbodex"
environment     = "staging"
location        = "francecentral"

appservice_sku     = "B1"
backend_image_name = "backend"
backend_image_tag  = "latest"
backend_port       = 8000

pg_admin_user     = "pgadmin"
pg_admin_password = "REPLACE_ME_STRONG_PASSWORD"
pg_database       = "turbodex"
pg_sku_name       = "B_Standard_B1ms"


resource_group_name = "turbodex-rg"
app_service_plan    = "turbodex-plan"
app_service_name    = "turbodex-api"
storage_account     = "turbodexstorage"
postgres_server     = "turbodex-db"
postgres_user       = "turbodexadmin"
postgres_password   = "YourSecurePassword123!"

acr_admin_password  = "AnotherSecretPassword456!"
