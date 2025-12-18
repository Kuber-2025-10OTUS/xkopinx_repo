# MySQL custom operator (task **)

## Назначение

Оператор отслеживает создание/удаление кастомных ресурсов:

- **apiVersion**: `otus.homework/v1`
- **kind**: `MySQL` (plural: `mysqls`)

## Поведение при создании `MySQL`

При создании объекта `MySQL` в namespace `N` оператор создаёт **в том же namespace `N`**:

- **Deployment** `metadata.name` (1 реплика) с контейнером MySQL из `spec.image`
- **Service** типа **ClusterIP** с именем `metadata.name` (порт 3306)
- **PVC** `${name}-pvc` размером `spec.storage_size`

А также создаёт **кластерный** ресурс:

- **PV** `${name}-pv` (привязанный к PVC через `volumeName/claimRef`)

Параметры MySQL передаются через переменные окружения контейнера:

- `MYSQL_ROOT_PASSWORD` = `spec.password`
- `MYSQL_DATABASE` = `spec.database`

## Поведение при удалении `MySQL`

- Namespaced-ресурсы (Deployment/Service/PVC) удаляются сборщиком мусора Kubernetes через `ownerReferences`.
- **PV** удаляется явно в delete-хендлере оператора.

## Важные допущения (для лабораторной/minikube)

- PV создаётся как `hostPath` (путь вида `/data/mysql/<name>`) — это удобно для minikube, но не прод-решение.
- `storageClassName` зафиксирован как `standard`.
