# Мониторинг NGINX с Prometheus Operator

Этот проект настраивает мониторинг NGINX с использованием Prometheus Operator, включая кастомный образ NGINX с модулем stub_status и nginx-prometheus-exporter.

## Структура проекта

- `Dockerfile` - Dockerfile для сборки кастомного образа NGINX
- `nginx.conf` - Основная конфигурация NGINX
- `default.conf` - Конфигурация виртуального хоста с endpoint `/basic_status` для метрик
- `namespace.yaml` - Namespace для мониторинга
- `nginx-configmap.yaml` - ConfigMap с конфигурацией NGINX
- `nginx-deployment.yaml` - Deployment для NGINX
- `nginx-service.yaml` - Service для NGINX
- `nginx-exporter-deployment.yaml` - Deployment для nginx-prometheus-exporter
- `nginx-exporter-service.yaml` - Service для nginx-prometheus-exporter
- `servicemonitor.yaml` - ServiceMonitor для Prometheus Operator

## Предварительные требования

- Kubernetes кластер версии >= 1.25.0 (для Prometheus Operator >= v0.84.0)
- kubectl настроен для работы с кластером
- Docker для сборки образа (опционально, можно использовать готовый образ)

## Установка Prometheus Operator

### Вариант 1: Установка через официальные манифесты

```bash
# Установка CRDs и оператора
LATEST=$(curl -s https://api.github.com/repos/prometheus-operator/prometheus-operator/releases/latest | jq -cr .tag_name)
curl -sL https://github.com/prometheus-operator/prometheus-operator/releases/download/${LATEST}/bundle.yaml | kubectl create -f -

# Проверка готовности оператора
kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=prometheus-operator -n default --timeout=300s
```

### Вариант 2: Установка через Helm

```bash
# Добавление репозитория
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Установка kube-prometheus-stack
helm install prometheus-operator prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace
```

### Вариант 3: Установка через kube-prometheus

```bash
# Клонирование репозитория
git clone https://github.com/prometheus-operator/kube-prometheus.git
cd kube-prometheus

# Установка
kubectl create -f manifests/setup
until kubectl get servicemonitors --all-namespaces ; do date; sleep 1; echo ""; done
kubectl create -f manifests/
```

## Сборка кастомного образа NGINX (опционально)

Если вы хотите использовать кастомный образ NGINX:

```bash
# Сборка образа
docker build -t your-registry/nginx-custom:latest .

# Загрузка образа в registry (если требуется)
docker push your-registry/nginx-custom:latest
```

**Примечание:** Стандартный образ `nginx:stable-alpine` уже включает модуль `stub_status`, поэтому можно использовать его. В этом случае конфигурация будет загружаться через ConfigMap.

## Развёртывание компонентов мониторинга

### 1. Создание namespace

```bash
cd kubernetes-monitoring
```

```bash
kubectl apply -f namespace.yaml
```

### 2. Создание ConfigMap с конфигурацией NGINX

```bash
kubectl apply -f nginx-configmap.yaml
```

### 3. Развёртывание NGINX

```bash
kubectl apply -f nginx-deployment.yaml
kubectl apply -f nginx-service.yaml
```

### 4. Развёртывание nginx-prometheus-exporter

```bash
kubectl apply -f nginx-exporter-deployment.yaml
kubectl apply -f nginx-exporter-service.yaml
```

### 5. Создание ServiceMonitor

```bash
kubectl apply -f servicemonitor.yaml
```

## Проверка работы

### Проверка метрик stub_status

```bash
# Порт-форвардинг для доступа к NGINX
kubectl port-forward -n monitoring svc/nginx 8080:80

# В другом терминале проверка метрик
curl http://localhost:8080/basic_status
```

Вы должны увидеть вывод вида:

```text
Active connections: 1
server accepts handled requests
 1 1 1
Reading: 0 Writing: 1 Waiting: 0
```

### Проверка метрик Prometheus

```bash
# Порт-форвардинг для доступа к exporter
kubectl port-forward -n monitoring svc/nginx-prometheus-exporter 9113:9113

# В другом терминале проверка метрик Prometheus
curl http://localhost:9113/metrics
```

### Проверка ServiceMonitor

```bash
# Проверка создания ServiceMonitor
kubectl get servicemonitor -n monitoring

# Проверка деталей ServiceMonitor
kubectl describe servicemonitor nginx-metrics -n monitoring
```

### Проверка подов

```bash
# Проверка статуса подов
kubectl get pods -n monitoring

# Проверка логов NGINX
kubectl logs -n monitoring -l app=nginx

# Проверка логов exporter
kubectl logs -n monitoring -l app=nginx-prometheus-exporter
```

## Настройка Prometheus для сбора метрик

После создания ServiceMonitor, Prometheus Operator автоматически обнаружит его и настроит Prometheus для сбора метрик.

Если вы используете kube-prometheus или kube-prometheus-stack, Prometheus должен автоматически начать собирать метрики из ServiceMonitor.

Для проверки targets в Prometheus:

```bash
# Порт-форвардинг для доступа к Prometheus (если установлен через kube-prometheus)
kubectl port-forward -n monitoring svc/prometheus-k8s 9090:9090
```

Затем откройте в браузере `http://localhost:9090` и перейдите в раздел Status -> Targets. Вы должны увидеть `nginx-prometheus-exporter` в списке targets.

## Важные замечания

1. **Модуль stub_status**: Стандартный образ NGINX уже включает модуль `stub_status`, поэтому дополнительная сборка не требуется, если используется ConfigMap для конфигурации.

2. **Сетевое взаимодействие**: nginx-prometheus-exporter должен иметь доступ к сервису NGINX. В конфигурации используется FQDN `nginx.monitoring.svc.cluster.local:80`.

3. **ServiceMonitor labels**: Убедитесь, что labels в ServiceMonitor соответствуют labels в Service для nginx-prometheus-exporter.

4. **Prometheus Operator**: ServiceMonitor будет работать только если Prometheus Operator установлен и настроен для мониторинга namespace `monitoring`.

## Удаление

Удаление компонентов:

```bash
kubectl delete -f servicemonitor.yaml
kubectl delete -f nginx-exporter-service.yaml
kubectl delete -f nginx-exporter-deployment.yaml
kubectl delete -f nginx-service.yaml
kubectl delete -f nginx-deployment.yaml
kubectl delete -f nginx-configmap.yaml
kubectl delete -f namespace.yaml
```

Либо можно удалить сразу namespace:

```bash
kubectl delete -f namespace.yaml
```

## Ссылки

- [NGINX stub_status модуль](https://nginx.org/ru/docs/http/ngx_http_stub_status_module.html)
- [Prometheus Operator установка](https://github.com/prometheus-operator/prometheus-operator/blob/main/Documentation/getting-started/installation.md)
- [nginx-prometheus-exporter](https://github.com/nginx/nginx-prometheus-exporter)
