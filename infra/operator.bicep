targetScope = 'resourceGroup'

param location string
param foundationResourceGroupName string
param vmSize string
@secure()
param adminPublicKey string
param imageVersion string
param adminUsername string = 'aicgoperator'

var tags = {
  workload: 'ai-command-gateway'
  purpose: 'temporary-private-operator'
  cleanup: 'after-pilot-verification'
  managedBy: 'bicep'
}
var nameStem = 'aicg-operator'
var operatorPrefix = '10.43.0.0/26'
var bastionPrefix = '10.43.0.64/26'
var privateEndpointPrefix = '10.42.2.0/24'

resource foundationVnet 'Microsoft.Network/virtualNetworks@2024-07-01' existing = {
  name: 'vnet-aicg-sn5edmznrgh7s'
  scope: resourceGroup(foundationResourceGroupName)
}

resource operatorNsg 'Microsoft.Network/networkSecurityGroups@2024-07-01' = {
  name: 'nsg-${nameStem}'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowBastionSsh'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: bastionPrefix
          sourcePortRange: '*'
          destinationAddressPrefix: operatorPrefix
          destinationPortRange: '22'
        }
      }
      {
        name: 'DenyOtherInbound'
        properties: {
          priority: 4000
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
      {
        name: 'AllowPrivateServiceHttps'
        properties: {
          priority: 100
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: operatorPrefix
          sourcePortRange: '*'
          destinationAddressPrefix: privateEndpointPrefix
          destinationPortRange: '443'
        }
      }
      // Azure DNS and IMDS are platform exceptions to ordinary NSG evaluation.
      // Their service tags support explicit Deny rules only, not Allow rules.
      // Preserve the default platform access; HTTPS egress below stays bounded.
      {
        name: 'AllowVmAgentPlatform'
        properties: {
          priority: 130
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: operatorPrefix
          sourcePortRange: '*'
          destinationAddressPrefix: '168.63.129.16'
          destinationPortRanges: ['80', '32526']
        }
      }
      {
        name: 'DenyOtherOutbound'
        properties: {
          priority: 4000
          direction: 'Outbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

// All eight Bastion platform rules are required by Microsoft. Workload VM SSH
// is separately limited to this Bastion subnet; no VM public IP is created.
var bastionRules = [
  { name: 'AllowHttpsInbound', priority: 100, direction: 'Inbound', protocol: 'Tcp', source: 'Internet', destination: '*', ports: ['443'] }
  { name: 'AllowGatewayManagerInbound', priority: 110, direction: 'Inbound', protocol: 'Tcp', source: 'GatewayManager', destination: '*', ports: ['443'] }
  { name: 'AllowAzureLoadBalancerInbound', priority: 120, direction: 'Inbound', protocol: 'Tcp', source: 'AzureLoadBalancer', destination: '*', ports: ['443'] }
  { name: 'AllowBastionCommunicationInbound', priority: 130, direction: 'Inbound', protocol: '*', source: 'VirtualNetwork', destination: 'VirtualNetwork', ports: ['8080', '5701'] }
  { name: 'AllowSshRdpOutbound', priority: 100, direction: 'Outbound', protocol: '*', source: '*', destination: 'VirtualNetwork', ports: ['22', '3389'] }
  { name: 'AllowAzureCloudOutbound', priority: 110, direction: 'Outbound', protocol: 'Tcp', source: '*', destination: 'AzureCloud', ports: ['443'] }
  { name: 'AllowBastionCommunicationOutbound', priority: 120, direction: 'Outbound', protocol: '*', source: 'VirtualNetwork', destination: 'VirtualNetwork', ports: ['8080', '5701'] }
  { name: 'AllowHttpOutbound', priority: 130, direction: 'Outbound', protocol: '*', source: '*', destination: 'Internet', ports: ['80'] }
]
resource bastionNsg 'Microsoft.Network/networkSecurityGroups@2024-07-01' = {
  name: 'nsg-${nameStem}-bastion'
  location: location
  tags: tags
  properties: {
    securityRules: [for rule in bastionRules: {
      name: rule.name
      properties: {
        priority: rule.priority
        direction: rule.direction
        access: 'Allow'
        protocol: rule.protocol
        sourceAddressPrefix: rule.source
        sourcePortRange: '*'
        destinationAddressPrefix: rule.destination
        destinationPortRanges: rule.ports
      }
    }]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-07-01' = {
  name: 'vnet-${nameStem}'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.43.0.0/24'] }
    subnets: [
      {
        name: 'snet-operator'
        properties: {
          addressPrefix: operatorPrefix
          defaultOutboundAccess: false
          networkSecurityGroup: { id: operatorNsg.id }
        }
      }
      {
        name: 'AzureBastionSubnet'
        properties: {
          addressPrefix: bastionPrefix
          networkSecurityGroup: { id: bastionNsg.id }
        }
      }
    ]
  }
}
resource peering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-07-01' = {
  parent: vnet
  name: 'to-aicg-foundation'
  properties: {
    remoteVirtualNetwork: { id: foundationVnet.id }
    allowVirtualNetworkAccess: true
    allowForwardedTraffic: false
    allowGatewayTransit: false
    useRemoteGateways: false
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-${nameStem}'
  location: location
  tags: tags
}
resource nic 'Microsoft.Network/networkInterfaces@2024-07-01' = {
  name: 'nic-${nameStem}'
  location: location
  tags: tags
  properties: {
    enableIPForwarding: false
    ipConfigurations: [{
      name: 'private'
      properties: {
        primary: true
        privateIPAllocationMethod: 'Dynamic'
        subnet: { id: '${vnet.id}/subnets/snet-operator' }
      }
    }]
  }
}
resource vm 'Microsoft.Compute/virtualMachines@2024-11-01' = {
  name: 'vm-${nameStem}'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    hardwareProfile: { vmSize: vmSize }
    securityProfile: {
      securityType: 'TrustedLaunch'
      encryptionAtHost: true
      uefiSettings: { secureBootEnabled: true, vTpmEnabled: true }
    }
    storageProfile: {
      imageReference: { publisher: 'Canonical', offer: 'ubuntu-24_04-lts', sku: 'server', version: imageVersion }
      osDisk: {
        name: 'osdisk-${nameStem}'
        createOption: 'FromImage'
        caching: 'ReadWrite'
        diskSizeGB: 32
        managedDisk: { storageAccountType: 'StandardSSD_LRS' }
        deleteOption: 'Delete'
      }
    }
    osProfile: {
      computerName: 'aicg-operator'
      adminUsername: adminUsername
      allowExtensionOperations: false
      linuxConfiguration: {
        disablePasswordAuthentication: true
        provisionVMAgent: true
        ssh: { publicKeys: [{ path: '/home/${adminUsername}/.ssh/authorized_keys', keyData: adminPublicKey }] }
        patchSettings: { patchMode: 'ImageDefault', assessmentMode: 'ImageDefault' }
      }
    }
    networkProfile: { networkInterfaces: [{ id: nic.id, properties: { primary: true, deleteOption: 'Delete' } }] }
    diagnosticsProfile: { bootDiagnostics: { enabled: true } }
  }
}

resource publicIp 'Microsoft.Network/publicIPAddresses@2024-07-01' = {
  name: 'pip-${nameStem}-bastion'
  location: location
  tags: tags
  sku: { name: 'Standard', tier: 'Regional' }
  properties: { publicIPAllocationMethod: 'Static', publicIPAddressVersion: 'IPv4', idleTimeoutInMinutes: 4 }
}
resource bastion 'Microsoft.Network/bastionHosts@2024-07-01' = {
  name: 'bas-${nameStem}'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: {
    scaleUnits: 2
    enableTunneling: true
    enableFileCopy: true
    enableIpConnect: false
    enableShareableLink: false
    disableCopyPaste: true
    ipConfigurations: [{
      name: 'private-operator'
      properties: {
        publicIPAddress: { id: publicIp.id }
        subnet: { id: '${vnet.id}/subnets/AzureBastionSubnet' }
      }
    }]
  }
}

module integration './operator-foundation-links.bicep' = {
  name: 'aicg-operator-integration'
  scope: resourceGroup(foundationResourceGroupName)
  params: {
    operatorVnetId: vnet.id
    operatorIdentityId: identity.id
    operatorPrincipalId: identity.properties.principalId
  }
}

output vmResourceId string = vm.id
output bastionName string = bastion.name
output identityClientId string = identity.properties.clientId
output operatorVnetId string = vnet.id
output foundationCleanupResourceIds array = integration.outputs.cleanupResourceIds
