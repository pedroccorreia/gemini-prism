provider "google" {
  user_project_override = var.billing_project != null ? true : false
  billing_project       = var.billing_project
}

provider "google-beta" {
  user_project_override = var.billing_project != null ? true : false
  billing_project       = var.billing_project
}
