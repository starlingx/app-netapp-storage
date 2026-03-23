#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from sysinv.common import exception
from sysinv.helm import base

from k8sapp_netapp_storage.common import constants as app_constants


class NetappHelm(base.FluxCDBaseHelm):
    """Class to encapsulate helm operations for the netapp chart"""

    SUPPORTED_NAMESPACES = base.BaseHelm.SUPPORTED_NAMESPACES + \
        [app_constants.HELM_NS_NETAPP]
    SUPPORTED_APP_NAMESPACES = {
        app_constants.HELM_APP_NETAPP: SUPPORTED_NAMESPACES
    }

    CHART = app_constants.HELM_CHART_NETAPP
    HELM_RELEASE = app_constants.FLUXCD_HELMRELEASE_NETAPP

    def get_namespaces(self):
        return self.SUPPORTED_NAMESPACES

    def get_overrides(self, namespace=None):

        overrides = {
            app_constants.HELM_NS_NETAPP: {
                'trident': {
                    'namespace': app_constants.HELM_NS_NETAPP
                }
            }
        }

        if namespace in self.SUPPORTED_NAMESPACES:
            return overrides[namespace]
        elif namespace:
            raise exception.InvalidHelmNamespace(chart=self.CHART,
                                                 namespace=namespace)
        else:
            return overrides
