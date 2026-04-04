output "public_ip" {
  description = "Public IP address of the NOC Sentinel VM"
  value       = azurerm_public_ip.noc_sentinel_pip.ip_address
}

output "ssh_command" {
  description = "SSH command to connect to the VM"
  value       = "ssh ${var.admin_username}@${azurerm_public_ip.noc_sentinel_pip.ip_address}"
}

output "dns_fqdn" {
  description = "Fully qualified domain name"
  value       = azurerm_public_ip.noc_sentinel_pip.fqdn
}
