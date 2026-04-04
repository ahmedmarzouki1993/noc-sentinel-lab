variable "location" {
  description = "Azure region"
  type        = string
  default     = "UAE North"
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
  default     = "noc-lab-rg"
}

variable "vm_size" {
  description = "VM size"
  type        = string
  default     = "Standard_D2_v4"
}

variable "admin_username" {
  description = "VM admin username"
  type        = string
  default     = "azureuser"
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}
