#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

HELM_NS_NETAPP = "trident"
HELM_APP_NETAPP = "netapp-storage"
HELM_CHART_NETAPP = "netapp-trident"
FLUXCD_HELMRELEASE_NETAPP = "netapp-trident"
HELM_CHART_NETAPP_PROVISIONER = "netapp-trident-provisioner"
FLUXCD_HELMRELEASE_NETAPP_PROVISIONER = "netapp-trident-provisioner"
VALID_DRIVERS_NETAPP = ('ontap-nas', 'ontap-nas-economy',
                        'ontap-san', 'ontap-san-economy')
VALID_DELETION_POLICIES_NETAPP = ('Delete', 'Retain')
VALID_PROTOCOLS_NETAPP = ("nfs", "iscsi", "fcp", "nvme")
