# CSI S3 в Yandex Cloud (Managed Kubernetes)

Развёртывание [k8s-csi-s3](https://github.com/yandex-cloud/k8s-csi-s3): монтирование S3 (Object Storage) как PersistentVolume в поды. Бакет при auto-provisioning создаётся автоматически при создании PVC.

**Предварительно:** [YC CLI](https://yandex.cloud/en/docs/cli/quickstart), `yc init`, доступ к кластеру (`yc managed-kubernetes cluster get-credentials <CLUSTER_ID> --external`). В кластере должна быть группа узлов (хотя бы один worker в состоянии Ready).

---

## 1. Service Account и ключи доступа

```bash
export FOLDER_ID=$(yc config get folder-id)

yc iam service-account create --name csi-s3-sa --description "Service Account for CSI S3"
export SA_ID=$(yc iam service-account get csi-s3-sa --format json | jq -r .id)
yc resource-manager folder add-access-binding $FOLDER_ID \
  --role storage.editor --subject serviceAccount:$SA_ID
yc iam access-key create --service-account-name csi-s3-sa --description "Access Key for CSI S3"
```

Из вывода последней команды: **key_id** → `accessKeyID`, **secret** → `secretAccessKey` в `secret.yaml`.

---

## 2. Secret

Вписать в `secret.yaml` свои `accessKeyID` и `secretAccessKey`, затем:

```bash
kubectl apply -f kubernetes-csi/secret.yaml
```

---

## 3. CSI driver

```bash
kubectl apply -f kubernetes-csi/deploy/provisioner.yaml
kubectl apply -f kubernetes-csi/deploy/driver.yaml
kubectl apply -f kubernetes-csi/deploy/csi-s3.yaml
```

---

## 4. StorageClass и PVC

```bash
kubectl apply -f kubernetes-csi/storageclass.yaml
kubectl apply -f kubernetes-csi/pvc.yaml
```

---

## 5. Deployment

```bash
kubectl apply -f kubernetes-csi/deployment.yaml
```

Проверка записи в volume:

```bash
kubectl exec -it deployment/csi-s3-app -- cat /data/s3-otus/hello.txt
watch kubectl exec -it deployment/csi-s3-app -- cat /data/s3-otus/heartbeat.log
```

Данные в Object Storage: консоль Yandex Cloud → Object Storage → бакет с именем PV (например `pvc-<uuid>`).

---

## Манифесты для проверки ДЗ

| Файл | Назначение |
| ----- | ---------- |
| [secret.yaml](secret.yaml) | Secret с ключами доступа к Object Storage |
| [storageclass.yaml](storageclass.yaml) | StorageClass для CSI S3 |
| [pvc.yaml](pvc.yaml) | PVC с autoProvisioning |
| [deployment.yaml](deployment.yaml) | Deployment с volume и записью в `/data/s3-otus` |
| [deploy/](deploy/) | Манифесты CSI driver (provisioner, driver, csi-s3) |
