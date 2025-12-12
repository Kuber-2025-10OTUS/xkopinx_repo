# План проверки Helm Chart и Helmfile

## Общая информация

## Часть 1: Проверка Helm Chart (homework-chart)

### 1.1. Проверка структуры Chart

- [ ] **Проверить наличие обязательных файлов:**

  ```bash
  cd kubernetes-templating
  ls -lhF Chart.yaml values.yaml templates/
  ```

  Ожидается:
  - `Chart.yaml` - метаданные chart
  - `values.yaml` - значения по умолчанию
  - `templates/` - директория с шаблонами

- [ ] **Проверить структуру Chart.yaml:**

  ```bash
  cat Chart.yaml
  ```

  Ожидается:
  - `apiVersion: v2`
  - `name: homework-chart`
  - `version: 0.1.0`
  - `dependencies` с MySQL chart

- [ ] **Проверить наличие всех шаблонов:**

  ```bash
  ls -lhF templates/
  ```

  Ожидается наличие:
  - `namespace.yaml`
  - `deployment.yaml`
  - `service.yaml`
  - `ingress.yaml`
  - `configmap.yaml`
  - `pvc.yaml`
  - `storageclass.yaml`
  - `_helpers.tpl`
  - `NOTES.txt`

### 1.2. Проверка параметризации

- [ ] **Проверить параметризацию основных параметров в values.yaml:**

  ```bash
  grep -A 5 -E "(replicas|image|container|ingress|service|namespace)" values.yaml
  ```

  Ожидается:
  - `namespace.name` - имя namespace
  - `deployment.replicas` - количество реплик
  - `image.repository` и `image.tag` - раздельно
  - `container.name` - имя контейнера
  - `service.port` - порт сервиса
  - `ingress.host` - хост для ingress
  
- [ ] **Проверить разделение репозитория и тега образа:**

  ```bash
  grep -A 2 "image:" values.yaml
  ```

  Ожидается:
  - `image.repository: python` (отдельно)
  - `image.tag: "3.9-slim"` (отдельно)

- [ ] **Проверить возможность включения/отключения проб:**

  ```bash
  grep -A 5 "probes:" values.yaml
  ```

  Ожидается:
  - `probes.enabled: true/false`
  - `probes.readiness` - настройки readiness probe

- [ ] **Проверить использование переменных в шаблонах:**

  ```bash
  grep -E "\.Values\." templates/deployment.yaml | head -10
  ```

  Ожидается использование переменных из values.yaml

### 1.3. Проверка зависимостей

- [ ] **Добавить репозиторий Bitnami:**

  ```bash
  # Добавить репозиторий Bitnami
  helm repo add bitnami https://charts.bitnami.com/bitnami
  
  # Обновить репозиторий
  helm repo update bitnami
  
  # Проверить список репозиториев
  helm repo list
  ```

  Ожидается: репозиторий добавлен и доступен

- [ ] **Проверить доступные версии chart'а в репозитории:**

  ```bash
  # Показать последнюю версию chart'а
  helm search repo bitnami/mysql
  
  # Показать все доступные версии chart'а
  helm search repo bitnami/mysql --versions
  
  # Показать только последние 10 версий
  helm search repo bitnami/mysql --versions | head -11
  
  # Показать информацию о конкретной версии
  helm show chart bitnami/mysql --version 14.0.3
  
  # Показать все значения по умолчанию для chart'а
  helm show values bitnami/mysql --version 14.0.3
  ```

  Ожидается: список доступных версий MySQL chart в репозитории Bitnami

- [ ] **Проверить наличие зависимости MySQL в Chart.yaml:**

  ```bash
  grep -A 5 "dependencies:" Chart.yaml
  ```

  Ожидается:
  - `name: mysql`
  - `repository: https://charts.bitnami.com/bitnami`
  - `version: <доступная версия>` (например, 14.0.3)
  - `condition: mysql.enabled`

- [ ] **Проверить настройки MySQL в values.yaml:**

  ```bash
  grep -A 10 "mysql:" values.yaml
  ```

  Ожидается:
  - `mysql.enabled: true`
  - Настройки аутентификации MySQL

### 1.4. Проверка NOTES.txt

- [ ] **Проверить наличие NOTES.txt:**

  ```bash
  cat templates/NOTES.txt
  ```

  Ожидается:
  - Информация о доступе к сервису
  - Адрес через Ingress (если включен)
  - Инструкции для разных типов сервисов

### 1.5. Валидация Chart

- [ ] **Проверить синтаксис chart:**

  ```bash
  helm lint .
  ```

  Ожидается: `1 chart(s) linted, 0 chart(s) failed`

- [ ] **Проверить рендеринг шаблонов:**

  ```bash
  # Загрузить зависимости
  helm dependency update
  
  # Проверить рендеринг шаблонов
  helm template test-release . | head -50
  ```

  Ожидается: успешный рендеринг шаблонов

- [ ] **Проверить рендеринг с кастомными значениями:**

  ```bash
  helm template test-release . --set deployment.replicas=5 --set image.tag=3.10-slim
  ```

  Ожидается: значения должны переопределяться

### 1.6. Проверка установки Chart

- [ ] **Установить chart в тестовый namespace:**

  ```bash
  helm install test-homework . -n homework --create-namespace
  ```

  Ожидается: успешная установка

- [ ] **Проверить созданные ресурсы:**

  ```bash
  kubectl get all -n homework
  kubectl get ingress -n homework
  kubectl get pvc -n homework
  kubectl get configmap -n homework
  ```

  Ожидается:
  - Deployment с правильным количеством реплик
  - Service
  - Ingress
  - PVC
  - ConfigMap

- [ ] **Проверить статус подов:**

  ```bash
  kubectl get pods -n homework
  kubectl describe pod -n homework -l app=homework
  ```

  Ожидается: все поды в статусе `Running`

- [ ] **Проверить логи:**

  ```bash
  kubectl logs -n homework -l app=homework --tail=50
  ```

  Ожидается: отсутствие критических ошибок

- [ ] **Проверить доступность сервиса:**

  ```bash
  # Вариант 1: Через port-forward ingress controller
  kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80
  # В другом терминале:
  curl -H "Host: homework.otus" http://localhost:8080/homepage
  # Ожидается: HTTP/1.1 200 OK с содержимым index.html

  # Вариант 2: Изнутри кластера (для проверки работы ingress)
  kubectl run test-curl --image=curlimages/curl --rm -it --restart=Never -- \
    curl -H "Host: homework.otus" http://ingress-nginx-controller.ingress-nginx.svc.cluster.local/homepage
  
  # Вариант 3: Прямой доступ к сервису (для проверки работы приложения)
  kubectl port-forward -n homework svc/homework-service 8080:8000
  curl http://localhost:8080/index.html
  ```
  
  Ожидается: успешный ответ от сервиса (HTTP 200 OK)
  
- [ ] **Проверить NOTES после установки:**

  ```bash
  helm get notes test-homework -n homework
  ```

  Ожидается: отображение информации о доступе к сервису

- [ ] **Просмотреть созданные объекты через Helm:**

  ```bash
  # Список всех установленных релизов
  helm list -A
  helm list -n homework
  
  # Статус релиза
  helm status test-homework -n homework
  
  # Манифесты релиза
  helm get manifest test-homework -n homework

  # История релиза
  helm history test-homework -n homework
  ```

  Ожидается: информация о релизе и созданных ресурсах

- [ ] **Удалить тестовый релиз:**

  ```bash
  helm uninstall test-homework -n homework
  ```

### 1.7. Справочная информация: дополнительные команды Helm

**Основные команды для просмотра объектов** (используются в пункте 1.6):

- `helm list -A` - список всех релизов
- `helm status <release>` - статус релиза
- `helm get manifest <release>` - манифесты релиза
- `helm get values <release>` - значения переменных
- `helm get notes <release>` - заметки после установки
- `helm history <release>` - история релиза

**Дополнительные команды:**

- `helm get hooks <release>` - просмотр хуков релиза
- `helm get values <release> --all` - все значения (включая дефолтные)
- `helm get values <release> --revision N` - значения конкретной ревизии
- `helm status <release> -o yaml/json` - статус в разных форматах
- `kubectl get all -n <ns> -l app.kubernetes.io/managed-by=Helm` - ресурсы через kubectl

## Часть 2: Проверка Helmfile конфигурации

**Предварительные требования:**

```bash
# Добавить репозиторий Bitnami
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
```

### 2.1. Проверка структуры helmfile.yaml

- [ ] **Проверить наличие helmfile.yaml:**

  ```bash
  cd kubernetes-templating
  cat helmfile.yaml
  ```

  Ожидается:
  - Секция `repositories` с Bitnami
  - Секция `releases` с двумя релизами

- [ ] **Проверить синтаксис helmfile:**

  ```bash
  # Проверка синтаксиса YAML
  yamllint helmfile.yaml
  
  # Проверка через helmfile lint
  helmfile lint
  ```

  Ожидается: отсутствие ошибок

### 2.2. Проверка конфигурации Production Kafka (kafka-prod)

- [ ] **Проверить параметры kafka-prod:**

  ```bash
  grep -A 30 "kafka-prod" helmfile.yaml
  ```

  Ожидается:
  - `namespace: prod`
  - `replicaCount: 5` - 5 брокеров
  - `image.tag: "3.5.2"` - версия Kafka 3.5.2
  - `auth.enabled: true` - авторизация включена
  - `auth.clientProtocol: sasl` - протокол для клиентов
  - `auth.interBrokerProtocol: sasl` - протокол для межброкерного обмена
  - Настроены пользователи SASL

- [ ] **Проверить параметры конфигурации kafka-prod:**

  ```bash
  echo "Проверка параметров kafka-prod"
  echo "Namespace:"
  grep -A 35 "kafka-prod" helmfile.yaml | grep "namespace:" | head -1
  echo "ReplicaCount:"
  grep -A 35 "kafka-prod" helmfile.yaml | grep "replicaCount:" | head -1
  echo "Kafka version:"
  grep -A 35 "kafka-prod" helmfile.yaml | grep "tag:" | head -1
  echo "Auth enabled:"
  grep -A 35 "kafka-prod" helmfile.yaml | grep "auth:" -A 2 | grep "enabled:" | head -1
  echo "Client Protocol:"
  grep -A 35 "kafka-prod" helmfile.yaml | grep "clientProtocol:" | head -1
  echo "InterBroker Protocol:"
  grep -A 35 "kafka-prod" helmfile.yaml | grep "interBrokerProtocol:" | head -1
  ```

  Ожидается:
  - `namespace: prod`
  - `replicaCount: 5`
  - `tag: "3.5.2"`
  - `auth.enabled: true`
  - `clientProtocol: sasl`
  - `interBrokerProtocol: sasl`

### 2.3. Проверка конфигурации Development Kafka (kafka-dev)

- [ ] **Проверить параметры kafka-dev:**

  ```bash
  grep -A 25 "kafka-dev" helmfile.yaml
  ```

  Ожидается:
  - `namespace: dev`
  - `replicaCount: 1` - 1 брокер
  - `auth.enabled: false` - авторизация отключена

- [ ] **Проверить параметры конфигурации kafka-dev:**

  ```bash
  echo "Проверка параметров kafka-dev"
  echo "Namespace:"
  grep -A 25 "kafka-dev" helmfile.yaml | grep "namespace:" | head -1
  echo "ReplicaCount:"
  grep -A 25 "kafka-dev" helmfile.yaml | grep "replicaCount:" | head -1
  echo "Kafka version:"
  grep -A 25 "kafka-dev" helmfile.yaml | grep "tag:" | head -1
  echo "Auth enabled:"
  grep -A 25 "kafka-dev" helmfile.yaml | grep "auth:" -A 2 | grep "enabled:" | head -1
  ```

  Ожидается:
  - `namespace: dev`
  - `replicaCount: 1`
  - `auth.enabled: false`

### 2.4. Проверка различий между окружениями

- [ ] **Проверить основные различия между конфигурациями:**

  ```bash
  # Просмотр конфигурации kafka-prod
  grep -A 35 "kafka-prod" helmfile.yaml
  
  # Просмотр конфигурации kafka-dev
  grep -A 30 "kafka-dev" helmfile.yaml
  ```

  Ожидается:
  - **kafka-prod:** namespace=prod, replicaCount=5, auth=true, clientProtocol=sasl, interBrokerProtocol=sasl, zookeeper.enabled=true
  - **kafka-dev:** namespace=dev, replicaCount=1, auth=false, zookeeper.enabled=true

### 2.5. Проверка рендеринга релизов через helmfile

- [ ] **Проверить рендеринг kafka-prod:**

  ```bash
  # Обновить репозитории перед рендерингом
  helmfile repos
  
  # Рендеринг kafka-prod
  helmfile -l name=kafka-prod template
  ```

  Ожидается: успешный рендеринг манифестов для kafka-prod

- [ ] **Проверить рендеринг kafka-dev:**

  ```bash
  # Рендеринг kafka-dev
  helmfile -l name=kafka-dev template
  ```

  Ожидается: успешный рендеринг манифестов для kafka-dev

- [ ] **Проверить рендеринг всех релизов:**

  ```bash
  # Рендеринг всех релизов
  helmfile template
  ```

  Ожидается: успешный рендеринг всех манифестов

### 2.6. Проверка установки релизов через helmfile

**Примечание:** Для работы `helmfile apply` требуется плагин `helm-diff`. Если плагин не установлен, установите его:

```bash
helm plugin install https://github.com/databus23/helm-diff --version v3.8.1 --verify=false
```

Проверить установку плагина:

```bash
helm diff version
```

- [ ] **Установить kafka-prod:**

  ```bash
  # Создать namespace prod
  kubectl create namespace prod --dry-run=client -o yaml | kubectl apply -f -
  
  # Установить kafka-prod
  helmfile -l name=kafka-prod apply
  ```

  Ожидается: успешная установка kafka-prod в namespace prod

- [ ] **Проверить статус kafka-prod:**

  ```bash
  # Проверить статус подов
  kubectl get pods -n prod
  
  # Проверить статус StatefulSet
  kubectl get statefulset -n prod
  
  # Проверить статус релиза
  helm list -n prod
  ```

  Ожидается:
  - 5 подов Kafka в статусе Running
  - 1 под ZooKeeper в статусе Running
  - StatefulSet kafka-prod-kafka с 5 репликами

- [ ] **Установить kafka-dev:**

  ```bash
  # Создать namespace dev
  kubectl create namespace dev --dry-run=client -o yaml | kubectl apply -f -
  
  # Установить kafka-dev
  helmfile -l name=kafka-dev apply
  ```

  Ожидается: успешная установка kafka-dev в namespace dev

- [ ] **Проверить статус kafka-dev:**

  ```bash
  # Проверить статус подов
  kubectl get pods -n dev
  
  # Проверить статус StatefulSet
  kubectl get statefulset -n dev
  
  # Проверить статус релиза
  helm list -n dev
  ```

  Ожидается:
  - 1 под Kafka в статусе Running
  - 1 под ZooKeeper в статусе Running
  - StatefulSet kafka-dev-kafka с 1 репликой

- [ ] **Установить все релизы:**

  ```bash
  # Установить все релизы из helmfile
  helmfile apply
  ```

  Ожидается: успешная установка всех релизов

- [ ] **Проверить различия в конфигурации между окружениями:**

  ```bash
  # Проверить конфигурацию kafka-prod
  kubectl get statefulset kafka-prod-broker -n prod -o yaml | grep -A 5 "replicas:"
  kubectl get statefulset kafka-prod-zookeeper -n prod -o yaml | grep -A 2 "image:"
  
  # Проверить конфигурацию kafka-dev
  kubectl get statefulset kafka-dev-broker -n dev -o yaml | grep -A 5 "replicas:"
  kubectl get statefulset kafka-dev-zookeeper -n dev -o yaml | grep -A 2 "image:"
  ```

- [ ] **Удалить тестовые релизы (опционально):**

  ```bash
  # Удалить все релизы из helmfile
  helmfile destroy
  
  # Или удалить по отдельности
  helmfile -l name=kafka-prod destroy
  helmfile -l name=kafka-dev destroy
  ```

  Ожидается: успешное удаление релизов

---

## Часть 3: Дополнительные проверки Helm Chart

### 3.1. Проверка переопределения значений

- [ ] **Проверить переопределение через --set:**

  ```bash
  helm install test . --set deployment.replicas=10 --set image.tag=3.10-slim -n homework --create-namespace
  kubectl get deployment -n homework -o jsonpath='{.items[0].spec.replicas}'  # Должно быть 10
  helm uninstall test -n homework
  ```

- [ ] **Проверить переопределение через values файл:**

  ```bash
  echo "deployment:
    replicas: 7" > custom-values.yaml
  helm install test . -f custom-values.yaml -n homework --create-namespace
  kubectl get deployment -n homework -o jsonpath='{.items[0].spec.replicas}'  # Должно быть 7
  helm uninstall test -n homework
  rm custom-values.yaml
  ```

### 3.2. Проверка отключения проб

- [ ] **Проверить отключение проб:**

  ```bash
  # Проверить пробы в основном контейнере web-server
  helm template test . --set probes.enabled=false | grep -A 30 "name: web-server" | grep -E "readinessProbe|livenessProbe|startupProbe"
  ```

  Ожидается: отсутствие проб (readinessProbe, livenessProbe, startupProbe) в контейнере `web-server`
  
### 3.3. Проверка зависимостей

- [ ] **Проверить наличие зависимости в Chart.yaml:**

  ```bash
  grep -A 5 "dependencies:" Chart.yaml
  ```

  Ожидается: наличие MySQL зависимости в Chart.yaml

- [ ] **Проверить загрузку зависимостей:**

  ```bash
  helm dependency update
  ls charts/
  ```

  Ожидается: наличие MySQL chart в директории `charts/`

- [ ] **Проверить установку с зависимостью:**

  ```bash
  helm install test . --set mysql.enabled=true -n homework --create-namespace
  kubectl get pods -n homework | grep mysql
  helm uninstall test -n homework
  ```

### 3.4. Проверка cleanup

- [ ] **Удалить тестовые релизы (если были установлены):**
  
  ```bash
  helm uninstall test-homework -n homework
  helm list -A
  ```

  Ожидается: отсутствие тестовых релизов

---

## Чеклист итоговой проверки

### Helm Chart (Задание 1)

- [ ] Структура chart соответствует стандарту Helm
- [ ] Все основные параметры параметризованы
- [ ] Репозиторий и тег образа разделены
- [ ] Пробы можно включать/отключать
- [ ] NOTES.txt содержит информацию о доступе
- [ ] Добавлена зависимость MySQL
- [ ] Chart проходит lint-проверку
- [ ] Chart успешно устанавливается
- [ ] Приложение работает после установки

### Helmfile (Задание 2)

- [ ] helmfile.yaml корректен синтаксически
- [ ] Настроен kafka-prod: 5 брокеров, версия 3.5.2, SASL_PLAINTEXT
- [ ] Настроен kafka-dev: 1 брокер, PLAINTEXT без авторизации
- [ ] Репозитории успешно добавляются и обновляются
- [ ] Оба релиза успешно рендерятся через helmfile
- [ ] Оба релиза успешно устанавливаются через helmfile
- [ ] Конфигурации различаются между окружениями
- [ ] Ресурсы создаются корректно в соответствующих namespace

## Команды для быстрой проверки

```bash
# Добавить репозиторий Bitnami
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Проверка доступных версий chart'ов
helm search repo bitnami/mysql                    # Последняя версия
helm search repo bitnami/mysql --versions         # Все версии
helm show chart bitnami/mysql --version 14.0.3    # Информация о версии

# Проверка Helm chart
cd kubernetes-templating
helm lint .
helm template test . --debug

# Проверка helmfile
helmfile lint
helmfile -l name=kafka-prod template
helmfile -l name=kafka-dev template

# Установка (если есть доступ к кластеру)
helm install test-homework . -n homework --create-namespace
helmfile apply

# Проверка статуса
kubectl get all -n homework
kubectl get all -n prod
kubectl get all -n dev

# Просмотр объектов через Helm
helm list -A                                    # Все релизы во всех namespace
helm status test-homework -n homework           # Статус конкретного релиза
helm get manifest test-homework -n homework     # Манифесты релиза
helm get notes test-homework -n homework        # Заметки после установки
helm history test-homework -n homework          # История релиза

# Просмотр ресурсов с фильтрацией по Helm меткам
kubectl get all -n homework -l app.kubernetes.io/managed-by=Helm
kubectl get all -n homework -l app.kubernetes.io/instance=test-homework
```
