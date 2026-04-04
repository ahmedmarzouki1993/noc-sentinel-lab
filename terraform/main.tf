terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# Resource Group
resource "azurerm_resource_group" "noc_lab" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    project = "noc-sentinel-lab"
    env     = "lab"
    owner   = "ahmed-marzouki"
  }
}

# Public IP
resource "azurerm_public_ip" "noc_sentinel_pip" {
  name                = "noc-sentinel-pip"
  location            = azurerm_resource_group.noc_lab.location
  resource_group_name = azurerm_resource_group.noc_lab.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "noc-sentinel-lab"

  tags = {
    project = "noc-sentinel-lab"
    env     = "lab"
    owner   = "ahmed-marzouki"
  }
}

# Network Security Group
resource "azurerm_network_security_group" "noc_sentinel_nsg" {
  name                = "noc-sentinel-nsg"
  location            = azurerm_resource_group.noc_lab.location
  resource_group_name = azurerm_resource_group.noc_lab.name

  # SSH
  security_rule {
    name                       = "allow-ssh"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # Grafana
  security_rule {
    name                       = "allow-grafana"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "3000"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # Zabbix Web
  security_rule {
    name                       = "allow-zabbix-web"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "8080"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # Prometheus
  security_rule {
    name                       = "allow-prometheus"
    priority                   = 130
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "9090"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # AlertManager
  security_rule {
    name                       = "allow-alertmanager"
    priority                   = 140
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "9093"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # FastAPI app
  security_rule {
    name                       = "allow-fastapi"
    priority                   = 150
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "8000"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # HTTP (general)
  security_rule {
    name                       = "allow-http"
    priority                   = 160
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  tags = {
    project = "noc-sentinel-lab"
    env     = "lab"
    owner   = "ahmed-marzouki"
  }
}

# Virtual Network
resource "azurerm_virtual_network" "noc_sentinel_vnet" {
  name                = "noc-sentinel-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.noc_lab.location
  resource_group_name = azurerm_resource_group.noc_lab.name

  tags = {
    project = "noc-sentinel-lab"
    env     = "lab"
    owner   = "ahmed-marzouki"
  }
}

# Subnet
resource "azurerm_subnet" "noc_sentinel_subnet" {
  name                 = "noc-sentinel-subnet"
  resource_group_name  = azurerm_resource_group.noc_lab.name
  virtual_network_name = azurerm_virtual_network.noc_sentinel_vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}

# Associate NSG with subnet
resource "azurerm_subnet_network_security_group_association" "noc_sentinel_nsg_assoc" {
  subnet_id                 = azurerm_subnet.noc_sentinel_subnet.id
  network_security_group_id = azurerm_network_security_group.noc_sentinel_nsg.id
}

# Network Interface
resource "azurerm_network_interface" "noc_sentinel_nic" {
  name                = "noc-sentinel-nic"
  location            = azurerm_resource_group.noc_lab.location
  resource_group_name = azurerm_resource_group.noc_lab.name

  ip_configuration {
    name                          = "noc-sentinel-ipconfig"
    subnet_id                     = azurerm_subnet.noc_sentinel_subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.noc_sentinel_pip.id
  }

  tags = {
    project = "noc-sentinel-lab"
    env     = "lab"
    owner   = "ahmed-marzouki"
  }
}

# Linux Virtual Machine
resource "azurerm_linux_virtual_machine" "noc_sentinel_vm" {
  name                = "noc-sentinel-vm"
  resource_group_name = azurerm_resource_group.noc_lab.name
  location            = azurerm_resource_group.noc_lab.location
  size                = var.vm_size
  admin_username      = var.admin_username

  network_interface_ids = [
    azurerm_network_interface.noc_sentinel_nic.id,
  ]

  admin_ssh_key {
    username   = var.admin_username
    public_key = file(pathexpand(var.ssh_public_key_path))
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 64
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  # Bootstrap: install Docker and clone repo on first boot
  custom_data = base64encode(<<-EOF
    #!/bin/bash
    set -e
    apt-get update -y
    apt-get install -y docker.io docker-compose-plugin git curl jq
    usermod -aG docker ${var.admin_username}
    systemctl enable docker
    systemctl start docker
    mkdir -p /home/${var.admin_username}/noc-sentinel-lab
    chown ${var.admin_username}:${var.admin_username} /home/${var.admin_username}/noc-sentinel-lab
  EOF
  )

  tags = {
    project = "noc-sentinel-lab"
    env     = "lab"
    owner   = "ahmed-marzouki"
  }
}
