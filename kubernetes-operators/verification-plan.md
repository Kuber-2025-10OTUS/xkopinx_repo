# Цель

Применить все манифесты и проверить, что:

- CRD `mysqls.otus.homework` создан.
- Оператор работает (Deployment в статусе Ready).
- При создании `kind: MySQL` оператор создаёт связанные ресурсы: Deployment + Service + PVC (+ PV при необходимости).
- При удалении `MySQL` удаляются созданные для него ресурсы.

## Применение манифестов

### Сборка образа собственного оператора (minikube)

Перейти в директорию оператора:

```bash
cd kubernetes-operators/custom-operator
```

Для minikube с docker driver существует возможность собрать образ прямо в Docker minikube:

```bash
eval $(minikube -p minikube docker-env)
docker build -t mysql-operator-custom:0.1.0 .
```

Альтернатива: собрать локально и загрузить в minikube (зависит от драйвера):

```bash
docker build -t mysql-operator-custom:0.1.0 .
minikube image load mysql-operator-custom:0.1.0
```

Вернуться в корень репозитория:

```bash
cd -
```

### Применение манифестов (из корня репозитория)

```bash
kubectl apply -f kubernetes-operators/namespace.yaml
kubectl apply -f kubernetes-operators/crd-mysql.yaml
kubectl apply -f kubernetes-operators/custom-operator/rbac.yaml
kubectl apply -f kubernetes-operators/custom-operator/deployment.yaml
```

## Проверка CRD

```bash
kubectl get crd mysqls.otus.homework
kubectl describe crd mysqls.otus.homework
kubectl api-resources --api-group=otus.homework
```

## Проверка оператора

```bash
kubectl -n mysql-operator get deploy,pods
kubectl -n mysql-operator rollout status deploy/mysql-operator-custom
kubectl -n mysql-operator logs deploy/mysql-operator-custom --tail=200
```

## Создание MySQL (кастомный ресурс)

```bash
kubectl apply -f kubernetes-operators/mysql-sample.yaml
kubectl -n mysql-operator get mysql
kubectl -n mysql-operator describe mysql mysql-sample
```

## Проверка созданных оператором ресурсов

Список ресурсов в namespace:

```bash
kubectl -n mysql-operator get deploy,svc,pvc,pods
```

Ресурсы, связанные MySQL:

```bash
kubectl -n mysql-operator get all -o wide
```

Если в кластере используется dynamic provisioner, PV может появиться автоматически:

```bash
kubectl get pv | head
```

## Проверка удаления (garbage collection)

```bash
kubectl delete -f kubernetes-operators/mysql-sample.yaml
kubectl -n mysql-operator get deploy,svc,pvc,pods
```
