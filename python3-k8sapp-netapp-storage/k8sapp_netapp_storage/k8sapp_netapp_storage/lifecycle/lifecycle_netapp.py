#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import yaml

from oslo_log import log as logging
from sysinv.common import constants
from sysinv.common.kube_utils import KubeUtils
from sysinv.common.kube_utils import KubeResourceType
from sysinv.helm import lifecycle_base as base
from sysinv.helm.lifecycle_constants import LifecycleConstants

from k8sapp_netapp_storage.common import constants as app_constants

LOG = logging.getLogger(__name__)


class NetappAppLifecycleOperator(base.AppLifecycleOperator):
    def app_lifecycle_actions(self, context, conductor_obj, app_op, app, hook_info):
        """ Perform lifecycle actions for an operation

        :param context: request context
        :param conductor_obj: conductor object
        :param app_op: AppOperator object
        :param app: AppOperator.Application object
        :param hook_info: LifecycleHookInfo object

        """

        self.kube_utils = KubeUtils()

        # Fluxcd request
        if hook_info.lifecycle_type == LifecycleConstants.APP_LIFECYCLE_TYPE_FLUXCD_REQUEST and \
                hook_info.relative_timing == LifecycleConstants.APP_LIFECYCLE_TIMING_PRE and \
                hook_info.operation == constants.APP_REMOVE_OP:
            return self.pre_remove(context, conductor_obj, app)

        # Semantic Check
        if hook_info.lifecycle_type == LifecycleConstants.APP_LIFECYCLE_TYPE_SEMANTIC_CHECK and \
                hook_info.relative_timing == LifecycleConstants.APP_LIFECYCLE_TIMING_PRE and \
                hook_info.operation == constants.APP_APPLY_OP:
            return self.pre_apply_semantic_checks(app_op, app)

        super(NetappAppLifecycleOperator, self).app_lifecycle_actions(
            context, conductor_obj, app_op, app, hook_info)

    def pre_apply_semantic_checks(self, app_op, app):
        LOG.info("Running pre-apply semantic checks for NetApp Storage")

        dbapi = app_op._dbapi
        user_overrides = self._get_user_overrides(app, dbapi)
        if not user_overrides:
            raise Exception("Cannot apply application: missing user-overrides")

        secrets = user_overrides.get('secret', [])
        backends = user_overrides.get('backends', [])
        storage_classes = user_overrides.get('storageClasses', [])
        snapshot_classes = user_overrides.get('snapshotClasses', [])

        if not backends:
            raise ValueError("Cannot apply application: "
                             "at least one backend is required.")

        secret_names = set()
        for secret in secrets:
            self._pre_check_secret(secret)
            secret_names.add(secret['metadata']['name'])

        for backend in backends:
            self._pre_check_backend(backend, secret_names)

        for sc in storage_classes:
            self._pre_check_storageclass(sc)

        for snap in snapshot_classes:
            self._pre_check_snapshotclass(snap)

        LOG.info("Pre-apply semantic checks for NetApp Storage passed")

    def _pre_check_secret(self, secret):
        name = secret.get('metadata', {}).get('name')
        if not name:
            raise ValueError("Cannot apply application: "
                             "secret is missing metadata.name.")

        string_data = secret.get('stringData', {})
        if not string_data.get('username') or not string_data.get('password'):
            raise ValueError(f"Cannot apply application: "
                             f"secret '{name}' must have "
                             f"username and password in stringData.")

    def _pre_check_backend(self, backend, secret_names):
        name = backend.get('name')
        if not name:
            raise ValueError("Cannot apply application: "
                             "backend is missing 'name'.")

        protocol = backend.get('protocol')
        if not protocol or protocol not in app_constants.VALID_PROTOCOLS_NETAPP:
            raise ValueError(f"Cannot apply application: "
                             f"backend '{name}' has invalid protocol "
                             f"'{protocol}'. Must be one of: "
                             f"{app_constants.VALID_PROTOCOLS_NETAPP}")

        if not backend.get('managementLIF'):
            raise ValueError(f"Cannot apply application: "
                             f"backend '{name}' is missing 'managementLIF'.")

        if not backend.get('svm'):
            raise ValueError(f"Cannot apply application: "
                             f"backend '{name}' is missing 'svm'.")

        secret_name = backend.get('credentials', {}).get('secret_name')
        if not secret_name:
            raise ValueError(f"Cannot apply application: "
                             f"backend '{name}' is missing "
                             f"'credentials.secret_name'.")

        if secret_name not in secret_names:
            raise ValueError(f"Cannot apply application: "
                             f"backend '{name}' references secret "
                             f"'{secret_name}' which is not defined "
                             f"in the 'secret' section.")

    def _pre_check_storageclass(self, storageclass):
        name = storageclass.get('name')
        if not name:
            raise ValueError("Cannot apply application: "
                             "storageClass is missing 'name'.")

        backend_type = storageclass.get('parameters', {}).get('backendType')
        if backend_type and \
           backend_type not in app_constants.VALID_DRIVERS_NETAPP:
            raise ValueError(f"Cannot apply application: "
                             f"storageClass '{name}' has invalid backendType "
                             f"'{backend_type}'.")

    def _pre_check_snapshotclass(self, snapshotclass):
        name = snapshotclass.get('name')
        if not name:
            raise ValueError("Cannot apply application: "
                             "snapshotClass is missing 'name'.")

        deletion_policy = snapshotclass.get('deletionPolicy')
        if deletion_policy and \
           deletion_policy not in app_constants.VALID_DELETION_POLICIES_NETAPP:
            raise ValueError(f"Cannot apply application: "
                             f"snapshotClass '{name}' has invalid "
                             f"deletionPolicy '{deletion_policy}'.")

    def pre_remove(self, context, conductor_obj, app):
        LOG.info("Running pre-remove actions for NetApp Storage")

        self._remove_trident_finalizers()

        LOG.info("NetApp Trident pre-remove cleanup complete")

    def _remove_trident_finalizers(self):
        """Remove finalizers from all Trident CRD instances.

        This prevents namespace stuck in Terminating after the
        Trident operator is removed.
        """
        all_crds = []
        try:
            all_crds = self.kube_utils.list_resources(
                resource_type=KubeResourceType.custom_resource_definition)
        except Exception as e:
            LOG.warning(f"Failed to list CRDs: {e}")

        trident_crds = [
            crd for crd in all_crds
            if crd.get("spec", {}).get("group", "").endswith("trident.netapp.io")
        ]

        for crd in trident_crds:
            plural = crd.get("spec", {}).get("names", {}).get("plural")
            group = crd.get("spec", {}).get("group")

            version = None
            for v in crd.get("spec", {}).get("versions", []):
                if v.get("storage"):
                    version = v.get("name")
                    break
            if not version and crd.get("spec", {}).get("versions", []):
                version = crd["spec"]["versions"][0].get("name")

            if not plural or not group or not version:
                continue

            try:
                resources = self.kube_utils.list_resources(
                    resource_type=KubeResourceType.custom_object,
                    namespace=app_constants.HELM_NS_NETAPP,
                    plural=plural,
                    group=group,
                    version=version)
            except Exception as e:
                LOG.warning(f"Failed to list {plural}: {e}")
                continue

            for resource in resources:
                name = resource.get("metadata", {}).get("name")
                finalizers = resource.get("metadata", {}).get("finalizers")
                if name and finalizers:
                    try:
                        self.kube_utils.remove_resource_finalizers(
                            resource_type=KubeResourceType.custom_object,
                            name=name,
                            namespace=app_constants.HELM_NS_NETAPP,
                            plural=plural,
                            group=group,
                            version=version)
                        LOG.info(f"Removed finalizers from {plural}/{name}")
                    except Exception as e:
                        LOG.warning(f"Failed to remove finalizers "
                                    f"from {plural}/{name}: {e}")

    def _get_user_overrides(self, app, dbapi):
        user_overrides = {}

        overrides = dbapi.helm_override_get(
            app.id,
            app_constants.HELM_CHART_NETAPP_PROVISIONER,
            app_constants.HELM_NS_NETAPP)

        if overrides.user_overrides:
            user_overrides = yaml.safe_load(overrides.user_overrides)

        return user_overrides
