@description('Azure resource region.')
param location string
@description('Generated resource name stem.')
param nameStem string
@description('Nonproduction resource tags.')
param tags object
@description('VNet address prefix.')
param vnetAddressPrefix string
@description('Dedicated Container Apps subnet prefix.')
param environmentSubnetPrefix string
@description('Separate private endpoint subnet prefix.')
param privateEndpointSubnetPrefix string

// Default NSG rules permit VNet/platform connectivity and deny internet ingress.
// This is not a firewall or an outbound data-exfiltration control.
resource environmentNsg 'Microsoft.Network/networkSecurityGroups@2024-07-01' = {
  name: 'nsg-${nameStem}-environment'
  location: location
  tags: tags
  properties: { securityRules: [] }
}

resource endpointNsg 'Microsoft.Network/networkSecurityGroups@2024-07-01' = {
  name: 'nsg-${nameStem}-endpoints'
  location: location
  tags: tags
  properties: { securityRules: [] }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-07-01' = {
  name: 'vnet-${nameStem}'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: [vnetAddressPrefix] }
    subnets: [
      {
        name: 'snet-environment'
        properties: {
          addressPrefix: environmentSubnetPrefix
          networkSecurityGroup: { id: environmentNsg.id }
          delegations: [{
            name: 'container-apps'
            properties: { serviceName: 'Microsoft.App/environments' }
          }]
        }
      }
      {
        name: 'snet-private-endpoints'
        properties: {
          addressPrefix: privateEndpointSubnetPrefix
          networkSecurityGroup: { id: endpointNsg.id }
          privateEndpointNetworkPolicies: 'Enabled'
        }
      }
    ]
  }
}

var dnsNames = [
  'privatelink.azurecr.io'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.monitor.azure.com'
  'privatelink.oms.opinsights.azure.com'
  'privatelink.ods.opinsights.azure.com'
  'privatelink.agentsvc.azure-automation.net'
]

resource zones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for zoneName in dnsNames: {
  name: zoneName
  location: 'global'
  tags: tags
}]

resource links 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (zoneName, index) in dnsNames: {
  parent: zones[index]
  name: 'link-${nameStem}'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: { id: vnet.id }
  }
}]

output vnetId string = vnet.id
output environmentSubnetId string = resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'snet-environment')
output privateEndpointSubnetId string = resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'snet-private-endpoints')
output registryDnsZoneId string = zones[0].id
output blobDnsZoneId string = zones[1].id
output monitorDnsZoneIds array = [zones[2].id, zones[3].id, zones[4].id, zones[5].id, zones[1].id]

