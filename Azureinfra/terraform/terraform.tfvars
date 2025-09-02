subscription_id = "ea710538-3bbf-4569-9ac5-d08e62266a3c"
project_name    = "turbodex"
environment     = "staging"
location        = "francecentral"

backend_image_name = "backend"
backend_image_tag  = "latest"
backend_port       = 8000


resource_group_name = "turbodex-rg"
app_service_plan    = "turbodex-plan"
app_service_name    = "turbodex-api"
storage_account     = "turbodexstorage"

acr_admin_password  = "AnotherSecretPassword456!"


acr_login_server      = "turbodexacr.azurecr.io"
aks_name              = "turbodex-staging-aks"
storage_account_name  = "turbodexyt3t1r"

# IPs LoadBalancer optionnelles
blur_lb_ip            = null
analyse_lb_ip         = null

blur_image_name = "car-blur"
blur_image_tag  = "latest"
analyse_image_name = "car-api"
analyse_image_tag  = "latest"

