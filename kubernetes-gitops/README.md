# Kubernetes GitOps с ArgoCD

Данный модуль содержит конфигурацию для установки ArgoCD в Kubernetes кластер Yandex Cloud с использованием инфраструктурных нод.

## Описание задания

Установка ArgoCD в managed Kubernetes кластер Yandex Cloud с разделением на:

- **Пул рабочей нагрузки** - для основных приложений
- **Пул инфраструктурных сервисов** - для ArgoCD с taint `node-role=infra:NoSchedule`

Компоненты ArgoCD должны устанавливаться **исключительно** на infra-ноды.

## Файлы для задания

- [argocd-values.yaml](./argocd-values.yaml) - конфигурация Helm chart для ArgoCD
- [argocd-project.yaml](./argocd-project.yaml) - манифест ArgoCD Project "Otus"
- [argocd-app-networks.yaml](./argocd-app-networks.yaml) - манифест ArgoCD Application для kubernetes-networks (manual sync)
- [argocd-app-templating.yaml](./argocd-app-templating.yaml) - манифест ArgoCD Application для kubernetes-templating (auto sync)

## Создание кластера в Yandex Cloud

1. Перейдите в раздел **Managed Service for Kubernetes**
2. Нажмите **Создать кластер**
3. Заполните параметры кластера
4. Создайте два пула нод:
   - **workload-pool** - для рабочей нагрузки (1 нода)
   - **infra-pool** - для инфраструктурных сервисов (1 нода)
     - Добавьте label: `node-role=infra`
     - Добавьте taint: `node-role=infra:NoSchedule`

## Подключение к кластеру

```bash
# Получение credentials для kubectl
yc managed-kubernetes cluster get-credentials <идентификатор кластера> --external # по имени кластера не работает

# Проверка подключения и нод
kubectl get nodes -o wide
```

## Проверка конфигурации нод

### Проверка labels и taints

```bash
# Просмотр нод с labels
kubectl get nodes --show-labels

# Просмотр taints
kubectl get nodes -o custom-columns=NAME:metadata.name,TAINTS:.spec.taints
```

Ожидаемый результат:

- Одна нода из infra-pool должна иметь label `node-role=infra`
- Та же нода должна иметь taint `node-role=infra:NoSchedule`

## Установка ArgoCD

### 1. Создание namespace

```bash
kubectl create namespace argocd
```

### 2. Добавление Helm репозитория

```bash
# Добавление репозитория
helm repo add argo https://argoproj.github.io/argo-helm

# Обновление репозиториев
helm repo update
```

### 3. Установка ArgoCD через Helm

**Команда установки:**

```bash
helm install argocd argo/argo-cd \
  --namespace argocd \
  --values argocd-values.yaml \
  --create-namespace
```

**Репозиторий:** `argo` (https://argoproj.github.io/argo-helm)  
**Chart:** `argo-cd`  
**Файл конфигурации:** [argocd-values.yaml](./argocd-values.yaml)

### 4. Проверка установки

```bash
# Проверка статуса подов ArgoCD
kubectl get pods -n argocd -o wide

# Убеждаемся, что все поды запущены на infra-ноде
kubectl get pods -n argocd -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName

# Проверка tolerations и nodeSelector у подов
kubectl get pod -n argocd -l app.kubernetes.io/name=argocd-server -o yaml | grep -A 10 "tolerations\|nodeSelector"
```

Все поды ArgoCD должны быть размещены на ноде из infra-pool.

### 5. Получение пароля администратора

```bash
# Получение начального пароля для пользователя admin
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d && echo
```

### 6. Доступ к UI ArgoCD

```bash
# Port-forward для доступа к UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Откройте браузер и перейдите по адресу: `https://localhost:8080`

**Логин:** `admin`  
**Пароль:** (получен на шаге 5)

## Создание ArgoCD Project

### Описание

ArgoCD Project (AppProject) - это логическая группа приложений в ArgoCD, которая определяет:

- Из каких source-репозиториев можно деплоить
- В какие кластеры и namespaces можно деплоить
- Какие ресурсы разрешено создавать
- Политики доступа и роли

### Манифест Project

Файл: [argocd-project.yaml](./argocd-project.yaml)

### Применение манифеста

```bash
# Применить манифест Project
kubectl apply -f argocd-project.yaml

# Проверить создание проекта
kubectl get appproject -n argocd

# Посмотреть детали проекта
kubectl describe appproject otus -n argocd
```

### Проверка через UI

1. Откройте ArgoCD UI (`https://localhost:8080`)
2. Перейдите в **Settings** → **Projects**
3. Должен появиться проект **otus**
4. Нажмите на проект для просмотра конфигурации

### Ключевые параметры Project

**Source репозитории:**

```yaml
sourceRepos:
  - https://github.com/Kuber-2025-10OTUS/xkopinx_repo.git
  - https://charts.bitnami.com/bitnami  # Для Helm dependencies
```

**Примечание**: Bitnami репозиторий может быть недоступен из России. Если возникает ошибка доступа, есть несколько решений:
1. Удалить зависимость MySQL из `Chart.yaml` (или использовать `Chart.lock`)
2. Использовать альтернативный репозиторий (например, `bitnamilegacy`)
3. Разрешить все репозитории в Project: `sourceRepos: ['*']` (не рекомендуется для production)

**Destination кластер:**
```yaml
destinations:
  - namespace: '*'
    server: https://kubernetes.default.svc
```

Это означает:
- `namespace: '*'` - разрешено деплоить в любые namespaces
- `server: https://kubernetes.default.svc` - in-cluster (кластер, где установлен ArgoCD)

**Разрешения для ресурсов:**
```yaml
clusterResourceWhitelist:
  - group: '*'
    kind: '*'
```

Разрешены все типы Kubernetes ресурсов.

## Создание ArgoCD Applications

### Приложение 1: kubernetes-networks (Manual Sync)

Манифест: [argocd-app-networks.yaml](./argocd-app-networks.yaml)

#### Описание

Приложение для деплоя манифестов из директории `kubernetes-networks`:
- **Sync Policy**: Manual - требуется ручная синхронизация
- **Namespace**: homework
- **Project**: otus
- **Source**: https://github.com/Kuber-2025-10OTUS/xkopinx_repo.git (path: kubernetes-networks)

#### Ключевые параметры

```yaml
spec:
  project: otus
  source:
    repoURL: https://github.com/Kuber-2025-10OTUS/xkopinx_repo.git
    targetRevision: main
    path: kubernetes-networks
  destination:
    server: https://kubernetes.default.svc
    namespace: homework
  syncPolicy:
    # Ручная синхронизация (automated закомментирован)
    syncOptions:
      - CreateNamespace=true
```

#### Применение

```bash
# Применить манифест
kubectl apply -f argocd-app-networks.yaml

# Проверить приложение
kubectl get application -n argocd kubernetes-networks

# Посмотреть статус
kubectl describe application -n argocd kubernetes-networks
```

#### Синхронизация через CLI

```bash
# Синхронизировать приложение (так как sync policy - manual)
argocd app sync kubernetes-networks

# Или через kubectl
kubectl patch application kubernetes-networks -n argocd \
  --type merge \
  --patch '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"HEAD"}}}'
```

#### Синхронизация через UI

1. Откройте ArgoCD UI
2. Найдите приложение **kubernetes-networks**
3. Нажмите **SYNC** → **SYNCHRONIZE**

#### Проверка nodeSelector

В deployment из kubernetes-networks указан nodeSelector:

```yaml
nodeSelector:
  homework: "true"
```

**Важно**: Убедитесь, что хотя бы одна нода в кластере имеет label `homework=true`:

```bash
# Проверить labels нод
kubectl get nodes --show-labels | grep homework

# Добавить label на ноду (если нужно)
kubectl label nodes <node-name> homework=true
```

Для Yandex Cloud можно добавить label через node pool или вручную на существующие ноды.

---

### Приложение 2: kubernetes-templating (Auto Sync)

Манифест: [argocd-app-templating.yaml](./argocd-app-templating.yaml)

#### Описание

Приложение для деплоя Helm chart из директории `kubernetes-templating`:

- **Sync Policy**: Auto (Prune=true, SelfHeal=true)
- **Namespace**: homeworkhelm
- **Project**: otus
- **Source**: https://github.com/Kuber-2025-10OTUS/xkopinx_repo.git (path: kubernetes-templating)
- **Replicas**: переопределено на 2 (вместо 3 по умолчанию)

#### Ключевые параметры

```yaml
spec:
  project: otus
  source:
    repoURL: https://github.com/Kuber-2025-10OTUS/xkopinx_repo.git
    targetRevision: main
    path: kubernetes-templating
    helm:
      values: |
        namespace:
          name: homeworkhelm
          create: true
        deployment:
          replicas: 2  # Переопределено
        mysql:
          enabled: false  # Отключено для упрощения
      parameters:
        - name: deployment.replicas
          value: "2"
  destination:
    server: https://kubernetes.default.svc
    namespace: homeworkhelm
  syncPolicy:
    automated:
      prune: true      # Удалять лишние ресурсы
      selfHeal: true   # Автовосстановление
    syncOptions:
      - CreateNamespace=true
```

#### Применение

```bash
# Применить манифест
kubectl apply -f argocd-app-templating.yaml

# Проверить приложение
kubectl get application -n argocd kubernetes-templating

# Посмотреть статус
kubectl describe application -n argocd kubernetes-templating
```

После применения манифеста ArgoCD **автоматически** начнет синхронизацию (Auto Sync).

**Важно**: Если возникает ошибка `helm repos https://charts.bitnami.com/bitnami are not permitted`, это означает, что:
1. Bitnami репозиторий не добавлен в `sourceRepos` проекта (уже исправлено в манифесте)
2. Bitnami может быть недоступен из России - в этом случае приложение не будет работать

Решения проблемы с Bitnami:
```bash
# Вариант 1: Обновить Project с разрешением Bitnami репозитория
kubectl apply -f argocd-project.yaml

# Вариант 2: Разрешить все репозитории (временное решение)
kubectl patch appproject otus -n argocd --type=json \
  -p='[{"op": "replace", "path": "/spec/sourceRepos", "value": ["*"]}]'

# Вариант 3: Удалить dependency из Chart.yaml вручную перед деплоем
# (требует изменения в Git репозитории)
```

#### Переопределение параметров

В манифесте переопределены следующие параметры:

1. **Количество реплик**: `deployment.replicas: 2` (вместо 3)
2. **Namespace**: `homeworkhelm` (вместо homework)
3. **MySQL**: отключен (`mysql.enabled: false`)
4. **StorageClass**: настроен для Yandex Cloud (`disk.csi.cloud.yandex.ru`)
5. **NodeSelector**: отключен (`nodeSelector.enabled: false`)

#### Проверка деплоя

```bash
# Проверить namespace
kubectl get ns homeworkhelm

# Проверить поды
kubectl get pods -n homeworkhelm

# Проверить количество реплик
kubectl get deployment -n homeworkhelm -o wide

# Должно быть 2 реплики
kubectl get deployment -n homeworkhelm -o jsonpath='{.items[0].spec.replicas}'
```

#### Auto-sync и Self-heal

**Auto-sync (prune: true)**:
- ArgoCD автоматически синхронизирует изменения из Git
- Удаляет ресурсы, которых нет в Git

**Self-heal (selfHeal: true)**:
- Автоматически восстанавливает ресурсы при изменениях в кластере
- Например, если вручную изменить replicas, ArgoCD вернет значение из Git

Проверка self-heal:

```bash
# Изменить replicas вручную
kubectl scale deployment -n homeworkhelm homework-helm-homework-chart --replicas=5

# Проверить - через несколько секунд ArgoCD вернет replicas=2
kubectl get deployment -n homeworkhelm -w
```

---

### Проверка обоих приложений

```bash
# Список приложений ArgoCD
kubectl get applications -n argocd

# Статус приложений
argocd app list

# Детальная информация
argocd app get kubernetes-networks
argocd app get kubernetes-templating

# Проверка через UI
# Откройте https://localhost:8080 и просмотрите оба приложения
```

### Различия между приложениями

| Параметр | kubernetes-networks | kubernetes-templating |
|----------|---------------------|----------------------|
| **Sync Policy** | Manual | Auto |
| **Prune** | - | true |
| **Self-heal** | - | true |
| **Namespace** | homework | homeworkhelm |
| **Source Type** | Plain YAML | Helm Chart |
| **Replicas** | 3 (из манифеста) | 2 (переопределено) |
| **Node Selector** | homework=true | отключен |

## Ключевые моменты конфигурации

Конфигурация в `argocd-values.yaml` включает три механизма для гарантированного размещения подов на infra-нодах:

### 1. nodeSelector

```yaml
nodeSelector:
  node-role: infra
```

Выбирает только ноды с label `node-role=infra`.

### 2. tolerations

```yaml
tolerations:
  - key: "node-role"
    operator: "Equal"
    value: "infra"
    effect: "NoSchedule"
```

Обходит taint `node-role=infra:NoSchedule`, установленный на infra-нодах.

### 3. nodeAffinity

```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: node-role
              operator: In
              values:
                - infra
```

Более строгий контроль размещения подов (requiredDuringScheduling).

### Компоненты ArgoCD с конфигурацией

Все компоненты настроены на работу исключительно на инфраструктурных нодах:

- **controller** - основной контроллер ArgoCD
- **dex** - OIDC provider для аутентификации
- **redis** - кеш и очередь задач
- **server** - API и UI сервер
- **repoServer** - работа с Git репозиториями
- **applicationSet** - контроллер ApplicationSet
- **notifications** - контроллер уведомлений

## Проверка работоспособности

После установки проверьте:

```bash
# 1. Все поды ArgoCD запущены
kubectl get pods -n argocd

# 2. Поды размещены на infra-нодах
kubectl get pods -n argocd -o wide

# 3. Проверка сервисов
kubectl get svc -n argocd

# 4. Проверка логов (если есть проблемы)
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server
```

Ожидаемый результат:

- Все поды в статусе `Running`
- Все поды размещены на ноде из infra-pool
- ArgoCD UI доступен через port-forward
- Успешная аутентификация под пользователем admin

## Удаление (при необходимости)

```bash
# Удаление ArgoCD
helm uninstall argocd -n argocd

# Удаление namespace
kubectl delete namespace argocd

# Удаление кластера (ОСТОРОЖНО!)
yc managed-kubernetes cluster delete <идентификатор кластера>
```
