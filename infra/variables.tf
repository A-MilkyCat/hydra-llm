variable "db_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true
}

variable "jwt_secret" {
  description = "JWT signing secret"
  type        = string
  sensitive   = true
}