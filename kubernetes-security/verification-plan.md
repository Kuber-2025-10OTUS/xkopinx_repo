# План проверки работоспособности

## Шаг 1: Применение кластерных ресурсов (требуют права администратора)

```bash
# Перейти в директорию с манифестами
cd kubernetes-security

# Применить StorageClass
kubectl apply -f storageClass.yaml

# Применить ClusterRole для доступа к метрикам
kubectl apply -f clusterrole.yaml

# Применить ClusterRoleBinding
kubectl apply -f clusterrolebinding.yaml

# Применить namespace
kubectl apply -f namespace.yaml

# Применить ServiceAccount monitoring
kubectl apply -f serviceaccount.yaml
```

**Проверка:**

```bash
# Проверить StorageClass
kubectl get storageclass homework-storageclass

# Проверить ClusterRole
kubectl get clusterrole monitoring-metrics-reader

# Проверить ClusterRoleBinding
kubectl get clusterrolebinding monitoring-metrics-reader-binding

# Проверить namespace
kubectl get namespace homework

# Проверить ServiceAccount
kubectl get serviceaccount monitoring -n homework
```

## Шаг 2: Проверка доступа ServiceAccount monitoring к метрикам

```bash
# Проверка через просмотр ClusterRole и ClusterRoleBinding
kubectl describe clusterrole monitoring-metrics-reader
kubectl describe clusterrolebinding monitoring-metrics-reader-binding

# Должно показать правила доступа к nodes/metrics, pods/metrics и metrics.k8s.io API

# Проверка через kubectl auth can-i
kubectl auth can-i get pods --as=system:serviceaccount:homework:monitoring -n homework
# Должно вернуть: yes
```

## Шаг 3: Применение ServiceAccount cd и RBAC

```bash
# Применить ServiceAccount cd
kubectl apply -f serviceaccount-cd.yaml

# Применить RoleBinding для роли admin
kubectl apply -f rolebinding-cd.yaml
```

**Проверка:**

```bash
# Проверить ServiceAccount cd
kubectl get serviceaccount cd -n homework

# Проверить RoleBinding
kubectl get rolebinding cd-admin-binding -n homework

# Проверить права ServiceAccount cd
kubectl auth can-i create deployments --as=system:serviceaccount:homework:cd -n homework
kubectl auth can-i delete pods --as=system:serviceaccount:homework:cd -n homework
# Должно вернуть yes в обоих случаях
```

## Шаг 4: Применение ресурсов namespace для deployment

```bash
# Применить PVC
kubectl apply -f pvc.yaml

# Применить ConfigMap
kubectl apply -f cm.yaml

# Проверить созданные ресурсы
kubectl get pvc -n homework
kubectl get configmap homework-config -n homework
```

## Шаг 5: Применение и проверка Deployment

```bash
# Применить Deployment
kubectl apply -f deployment.yaml

# Проверить статус Deployment
kubectl get deployment homework-deployment -n homework

# Проверить поды
kubectl get pods -n homework -l app=homework

# Проверить логи initContainer metrics-fetcher
kubectl logs <pod-name> -n homework -c metrics-fetcher
# Должно быть сообщение: "Metrics saved to metrics.html"

# Проверить, что поды используют ServiceAccount monitoring
kubectl get pod <pod-name> -n homework -o jsonpath='{.spec.serviceAccountName}'
# Должно вернуть: monitoring
```

## Шаг 6: Применение Service и проверка доступности

```bash
# Применить Service
kubectl apply -f service.yaml

# Проверить Service
kubectl get service homework-service -n homework

# Получить IP адрес Service
SERVICE_IP=$(kubectl get service homework-service -n homework -o jsonpath='{.spec.clusterIP}')
echo "Service IP: ${SERVICE_IP}"
```

## Шаг 7: Создание токена и kubeconfig для ServiceAccount cd

> **Важно:** Kubeconfig создается после применения всех ресурсов и используется для проверок и дальнейшей работы. Все ресурсы уже применены с обычным kubeconfig администратора.

```bash
# Применить Secret для токена
kubectl apply -f secret-cd-token.yaml

# Сгенерировать токен со временем действия 1 день
kubectl create token cd -n homework --duration=24h > token

# Проверить, что токен создан
cat token
# Должен быть виден JWT токен

# Получить данные для kubeconfig
CA_CERT=$(kubectl get secret cd-token -n homework -o jsonpath='{.data.ca\.crt}')
APISERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
CLUSTER_NAME=$(kubectl config view --minify -o jsonpath='{.clusters[0].name}')
TOKEN=$(cat token)

# Заполнить kubeconfig
sed -i.bak "s|PLACEHOLDER_TOKEN|${TOKEN}|g; s|PLACEHOLDER_CA_CERT|${CA_CERT}|g; s|PLACEHOLDER_API_SERVER|${APISERVER}|g; s|PLACEHOLDER_CLUSTER_NAME|${CLUSTER_NAME}|g" kubeconfig-cd.yaml

# Проверить kubeconfig
export KUBECONFIG=kubeconfig-cd.yaml
kubectl get pods -n homework
# Должен показать список подов в namespace homework

# Проверить текущего пользователя (должен быть ServiceAccount cd)
kubectl config view --minify -o jsonpath='{.users[0].name}'
# Должно вернуть: cd
```

**Переключение между kubeconfig'ами при необходимости:**

```bash
# Проверить текущий kubeconfig
echo "KUBECONFIG: ${KUBECONFIG:-~/.kube/config}"
kubectl config view --minify -o jsonpath='{.users[0].name}'

# Переключиться на kubeconfig от ServiceAccount cd
export KUBECONFIG=kubeconfig-cd.yaml

# При необходимости переключиться обратно на обычный kubeconfig администратора
unset KUBECONFIG
# или
export KUBECONFIG=~/.kube/config

# Проверить, что переключение прошло успешно
kubectl config current-context
kubectl config view --minify -o jsonpath='{.users[0].name}'
```

## Шаг 8: Проверка доступа к метрикам через веб-интерфейс

### Вариант A: Доступ из пода в кластере

```bash
# Запустить временный под для проверки
kubectl run test-pod --image=curlimages/curl:latest --rm -it --restart=Never -n homework -- sh

# Внутри пода выполнить:
curl http://homework-service.homework.svc.cluster.local:8000/metrics.html
# Должен вернуть HTML страницу с метриками кластера

# Также проверить главную страницу
curl http://homework-service.homework.svc.cluster.local:8000/index.html
```

### Вариант B: Проброс порта (port-forward)

```bash
# Пробросить порт локально
kubectl port-forward -n homework service/homework-service 8000:8000

# В другом терминале проверить доступность
curl http://localhost:8000/metrics.html
# Должен вернуть HTML страницу с метриками

# Или открыть в браузере
open http://localhost:8000/metrics.html
```

## Шаг 9: Проверка работы ServiceAccount monitoring через API

```bash
# Получить имя пода
POD_NAME=$(kubectl get pods -n homework -l app=homework -o jsonpath='{.items[0].metadata.name}')

# Выполнить команду внутри пода для проверки доступа к метрикам
kubectl exec -n homework ${POD_NAME} -- sh -c '
  TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
  API_SERVER="https://${KUBERNETES_SERVICE_HOST}:${KUBERNETES_SERVICE_PORT}"
  CA_CERT="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
  
  echo "Testing access to node metrics..."
  curl -s --cacert "${CA_CERT}" \
    --header "Authorization: Bearer ${TOKEN}" \
    "${API_SERVER}/apis/metrics.k8s.io/v1beta1/nodes" | head -20
  
  echo -e "\n\nTesting access to pod metrics..."
  curl -s --cacert "${CA_CERT}" \
    --header "Authorization: Bearer ${TOKEN}" \
    "${API_SERVER}/apis/metrics.k8s.io/v1beta1/namespaces/homework/pods" | head -20
'
# Должен вернуть JSON с метриками без ошибок авторизации
```

## Шаг 10: Финальная проверка всех компонентов

```bash
# Проверить все ресурсы в namespace homework
kubectl get all -n homework

# Проверить ServiceAccounts
kubectl get serviceaccount -n homework

# Проверить RBAC
kubectl get rolebinding -n homework

# Проверить, что все поды работают
kubectl get pods -n homework
# Все поды должны быть в статусе Running

# Проверить логи основного контейнера
kubectl logs -n homework -l app=homework --tail=20
# Должен быть виден запуск HTTP сервера на порту 8000
```

## Ожидаемые результаты

ServiceAccount `monitoring` создан и имеет доступ к метрикам кластера  
ServiceAccount `cd` создан и имеет роль admin в namespace homework  
Токен для ServiceAccount `cd` создан и сохранён в файл `token`  
Kubeconfig для ServiceAccount `cd` создан и работает  
Deployment использует ServiceAccount `monitoring`  
InitContainer `metrics-fetcher` успешно получает метрики  
Файл `metrics.html` создан и доступен через веб-сервер  
Метрики доступны по адресу `/metrics.html` через Service  
