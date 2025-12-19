import os
from typing import Tuple

import kopf
import kubernetes
from kubernetes.client import ApiException


OPERATOR_NS = os.getenv("OPERATOR_NAMESPACE", "mysql-operator")


def _ns_name(body) -> Tuple[str, str]:
    meta = body.get("metadata", {})
    return meta.get("namespace", "default"), meta["name"]


def _labels(name: str) -> dict:
    return {"app": name, "app.kubernetes.io/managed-by": "mysql-operator-custom"}


def _ownerref(body) -> dict:
    meta = body["metadata"]
    return {
        "apiVersion": body["apiVersion"],
        "kind": body["kind"],
        "name": meta["name"],
        "uid": meta["uid"],
        "controller": True,
        "blockOwnerDeletion": True,
    }


def build_pv(name: str, storage_size: str, owner_ref: dict) -> dict:
    # NOTE: hostPath is for учебный minikube; in real clusters you would use a StorageClass.
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolume",
        "metadata": {"name": f"{name}-pv", "labels": _labels(name)},
        "spec": {
            "capacity": {"storage": storage_size},
            "accessModes": ["ReadWriteOnce"],
            "persistentVolumeReclaimPolicy": "Delete",
            "storageClassName": "standard",
            "hostPath": {"path": f"/data/mysql/{name}"},
            # bind to our PVC explicitly (avoid matching issues)
            "claimRef": {
                "namespace": owner_ref.get("namespace", "default"),  # will be overwritten in handler
                "name": f"{name}-pvc",
            },
        },
    }


def build_pvc(namespace: str, name: str, storage_size: str, owner_ref: dict) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": f"{name}-pvc",
            "namespace": namespace,
            "labels": _labels(name),
            "ownerReferences": [owner_ref],
        },
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "storageClassName": "standard",
            "resources": {"requests": {"storage": storage_size}},
            "volumeName": f"{name}-pv",
        },
    }


def build_service(namespace: str, name: str, owner_ref: dict) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": _labels(name),
            "ownerReferences": [owner_ref],
        },
        "spec": {
            "type": "ClusterIP",
            "selector": {"app": name},
            "ports": [{"name": "mysql", "port": 3306, "targetPort": 3306}],
        },
    }


def build_deployment(namespace: str, name: str, image: str, password: str, database: str, owner_ref: dict) -> dict:
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": _labels(name),
            "ownerReferences": [owner_ref],
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {
                    "containers": [
                        {
                            "name": "mysql",
                            "image": image,
                            "ports": [{"containerPort": 3306, "name": "mysql"}],
                            "env": [
                                {"name": "MYSQL_ROOT_PASSWORD", "value": password},
                                {"name": "MYSQL_DATABASE", "value": database},
                            ],
                            "volumeMounts": [{"name": "data", "mountPath": "/var/lib/mysql"}],
                            # Keep it simple: don't block the operator on readiness quirks.
                        }
                    ],
                    "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": f"{name}-pvc"}}],
                },
            },
        },
    }


def _ensure_created(create_fn, *args, **kwargs):
    try:
        return create_fn(*args, **kwargs)
    except ApiException as e:
        if e.status == 409:  # AlreadyExists
            return None
        raise


@kopf.on.startup()
def _configure(settings: kopf.OperatorSettings, **_):
    kubernetes.config.load_incluster_config()


@kopf.on.create("otus.homework", "v1", "mysqls")
def on_mysql_create(body, spec, logger, **_):
    namespace, name = _ns_name(body)
    owner_ref = _ownerref(body)
    owner_ref["namespace"] = namespace  # for PV claimRef filling

    image = spec["image"]
    password = spec["password"]
    database = spec["database"]
    storage_size = spec["storage_size"]

    core = kubernetes.client.CoreV1Api()
    apps = kubernetes.client.AppsV1Api()

    logger.info(f"[{namespace}/{name}] creating PV/PVC/Service/Deployment")

    pv = build_pv(name, storage_size, owner_ref)
    pvc = build_pvc(namespace, name, storage_size, owner_ref)
    svc = build_service(namespace, name, owner_ref)
    dep = build_deployment(namespace, name, image, password, database, owner_ref)

    # PV is cluster-scoped: we delete it explicitly on CR delete via finalizer.
    _ensure_created(core.create_persistent_volume, pv)
    _ensure_created(core.create_namespaced_persistent_volume_claim, namespace, pvc)
    _ensure_created(core.create_namespaced_service, namespace, svc)
    _ensure_created(apps.create_namespaced_deployment, namespace, dep)

    return {"created": True}


@kopf.on.delete("otus.homework", "v1", "mysqls")
def on_mysql_delete(body, logger, **_):
    namespace, name = _ns_name(body)
    core = kubernetes.client.CoreV1Api()
    logger.info(f"[{namespace}/{name}] deleting PV {name}-pv")
    try:
        core.delete_persistent_volume(f"{name}-pv")
    except ApiException as e:
        if e.status != 404:
            raise
    return {"deleted": True}
