# Домашнее задание: Vault в Yandex Cloud Managed Kubernetes

## Содержание

1. [Установка Consul](#1-установка-consul)
2. [Установка Vault](#2-установка-vault)
3. [Инициализация и распечатывание Vault](#3-инициализация-и-распечатывание-vault)
4. [Создание секретов в Vault](#4-создание-секретов-в-vault)
5. [Настройка Kubernetes авторизации](#5-настройка-kubernetes-авторизации)
6. [Установка External Secrets Operator](#6-установка-external-secrets-operator)
7. [Создание SecretStore и ExternalSecret](#7-создание-secretstore-и-externalsecret)
8. [Проверка результата](#8-проверка-результата)

## Подключение к кластеру

```bash
yc managed-kubernetes cluster get-credentials <идентификатор кластера> --external
```

## 1. Установка Consul

### 1.1. Создание namespaces

Создаём необходимые namespaces:

```bash
kubectl apply -f namespaces.yaml
```

Проверяем создание:

```bash
kubectl get namespaces consul vault
```

### 1.2. Добавление Helm репозитория Consul

```bash
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo update
```

### 1.3. Установка Consul

Устанавливаем Consul с 3 репликами сервера:

```bash
helm install consul hashicorp/consul \
  --namespace consul \
  --values consul-values.yaml \
  --version 1.5.3
```

**Параметры установки:**

- `--namespace consul` - установка в namespace consul
- `--values consul-values.yaml` - файл с параметрами (3 реплики сервера)
- `--version 1.5.3` - версия чарта

### 1.4. Проверка установки Consul

Ожидаем запуск всех подов:

```bash
kubectl get pods -n consul -w
```

Проверяем статус:

```bash
kubectl get pods -n consul
kubectl get svc -n consul
```

## 2. Установка Vault

### 2.1. Установка Vault с Consul backend

Устанавливаем Vault в HA режиме с использованием Consul:

```bash
helm install vault hashicorp/vault \
  --namespace vault \
  --values vault-values.yaml \
  --version 0.28.1
```

**Параметры установки:**

- `--namespace vault` - установка в namespace vault
- `--values vault-values.yaml` - файл с параметрами (HA режим, Consul backend)
- `--version 0.28.1` - версия чарта

### 2.2. Проверка установки Vault

```bash
kubectl get pods -n vault
kubectl get svc -n vault
```

Видим 3 пода vault в статусе `0/1 Running` - это нормально, они требуют инициализации и распечатывания.

## 3. Инициализация и распечатывание Vault

### 3.1. Инициализация Vault

Инициализируем первый под Vault:

```bash
kubectl exec -n vault vault-0 -- vault operator init \
  -key-shares=1 \
  -key-threshold=1 \
  -format=json > vault-init-keys.json
```

Извлекаем ключи:

```bash
VAULT_UNSEAL_KEY=$(cat vault-init-keys.json | jq -r '.unseal_keys_b64[0]')
VAULT_ROOT_TOKEN=$(cat vault-init-keys.json | jq -r '.root_token')

echo "Unseal Key: $VAULT_UNSEAL_KEY"
echo "Root Token: $VAULT_ROOT_TOKEN"
```

### 3.2. Распечатывание (Unseal) всех подов Vault

Распечатываем каждый под Vault:

```bash
# Unseal vault-0
kubectl exec -n vault vault-0 -- vault operator unseal $VAULT_UNSEAL_KEY

# Unseal vault-1
kubectl exec -n vault vault-1 -- vault operator unseal $VAULT_UNSEAL_KEY

# Unseal vault-2
kubectl exec -n vault vault-2 -- vault operator unseal $VAULT_UNSEAL_KEY
```

### 3.3. Проверка статуса

```bash
kubectl get pods -n vault
```

Все поды должны быть в статусе `1/1 Running`.

Проверяем статус Vault:

```bash
kubectl exec -n vault vault-0 -- vault status
```

## 4. Создание секретов в Vault

### 4.1. Авторизация в Vault

```bash
VAULT_ROOT_TOKEN=$(cat vault-init-keys.json | jq -r '.root_token')

# Выполняем одну команду
kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN vault status

# Или несколько команд, если необходимо
kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN sh -c "vault status && vault secrets list"
```

**Port-forward для работы с локальным Vault CLI (опционально):**

```bash
kubectl port-forward -n vault svc/vault 8200:8200
```

В другом терминале (если используем port-forward):

```bash
export VAULT_ADDR='http://localhost:8200'
vault login $VAULT_ROOT_TOKEN
```

### 4.2. Включение KV v1 Secrets Engine

Создаём хранилище секретов `otus/`:

```bash
kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault secrets enable -path=otus kv
```

Проверяем:

```bash
kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault secrets list
```

### 4.3. Создание секрета

Создаём секрет `otus/cred`:

```bash
kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault kv put otus/cred username=otus password=asajkjkahs
```

Проверяем созданный секрет:

```bash
kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault kv get otus/cred
```

## 5. Настройка Kubernetes авторизации

### 5.1. Создание ServiceAccount

Применяем манифест для создания ServiceAccount и ClusterRoleBinding:

```bash
kubectl apply -f vault-auth-sa.yaml
```

Проверяем:

```bash
kubectl get sa -n vault vault-auth
kubectl get clusterrolebinding vault-auth-delegator
```

**Важно для Kubernetes 1.24+:** Видим `SECRETS 0` - это **нормально** и **правильно**!

```bash
kubectl get sa -n vault vault-auth
```

Начиная с Kubernetes 1.24, ServiceAccount больше не создают автоматически долгоживущие токены, что сделано для улучшения безопасности.

### 5.2. Включение Kubernetes-аутентификации в Vault

```bash
VAULT_ROOT_TOKEN=$(cat vault-init-keys.json | jq -r '.root_token')

kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault auth enable kubernetes
```

### 5.3. Настройка Kubernetes-аутентификации в Vault

**Существует два варианта настройки Kubernetes-аутентификации в Vault:**

#### Вариант 1: Упрощенный подход

Vault будет использовать свой собственный ServiceAccount токен для проверки других подов:

```bash
VAULT_ROOT_TOKEN=$(cat vault-init-keys.json | jq -r '.root_token')

kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault write auth/kubernetes/config \
  kubernetes_host="https://kubernetes.default.svc.cluster.local:443"
```

Пояснение:

- Vault запущен внутри Kubernetes кластера
- У Vault есть свой ServiceAccount-токен
- Vault автоматически использует его для TokenReview API
- Проще и работает отлично для большинства случаев

#### Вариант 2: С явным токеном

Используйте этот вариант только если:

- Vault находится вне Kubernetes кластера
- Требуется явный контроль над токеном reviewer'а

**Шаг 2.1:** Создаём токен для ServiceAccount:

```bash
SA_TOKEN=$(kubectl create token vault-auth -n vault --duration=8760h)
```

**Шаг 2.2:** Получаем CA сертификат кластера:

```bash
SA_CA_CRT=$(kubectl config view --raw --minify --flatten -o jsonpath='{.clusters[].cluster.certificate-authority-data}' | base64 -d)
```

**Шаг 2.3:** Получаем адрес Kubernetes API:

```bash
KUBERNETES_HOST=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
echo "Kubernetes API: $KUBERNETES_HOST"
```

**Шаг 2.4:** Настраиваем Vault:

```bash
VAULT_ROOT_TOKEN=$(cat vault-init-keys.json | jq -r '.root_token')

kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault write auth/kubernetes/config \
  token_reviewer_jwt="$SA_TOKEN" \
  kubernetes_host="$KUBERNETES_HOST" \
  kubernetes_ca_cert="$SA_CA_CRT" \
  disable_local_ca_jwt=true
```

### 5.4. Проверка настройки

Проверяем конфигурацию Kubernetes auth:

```bash
kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault read auth/kubernetes/config
```

### 5.5. Создание политики

Загружаем политику в Vault:

```bash
VAULT_ROOT_TOKEN=$(cat vault-init-keys.json | jq -r '.root_token')

kubectl cp otus-policy.hcl vault/vault-0:/tmp/otus-policy.hcl

kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault policy write otus-policy /tmp/otus-policy.hcl
```

Проверяем политику:

```bash
kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault policy read otus-policy
```

### 5.6. Создание роли

Создаём роль `otus`:

```bash
VAULT_ROOT_TOKEN=$(cat vault-init-keys.json | jq -r '.root_token')

kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault write auth/kubernetes/role/otus \
  bound_service_account_names=vault-auth \
  bound_service_account_namespaces=vault \
  policies=otus-policy \
  ttl=24h
```

Проверяем роль:

```bash
kubectl exec -n vault vault-0 -- env VAULT_TOKEN=$VAULT_ROOT_TOKEN \
  vault read auth/kubernetes/role/otus
```

## 6. Установка External Secrets Operator

### 6.1. Добавление Helm репозитория

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update
```

### 6.2. Установка External Secrets Operator

```bash
helm install external-secrets external-secrets/external-secrets \
  --namespace vault \
  --values eso-values.yaml \
  --version 1.3.1
```

**Параметры установки:**

- `--namespace vault` - установка в namespace vault
- `--values eso-values.yaml` - файл с параметрами
- `--version 1.3.1` - версия чарта

### 6.3. Проверка установки

```bash
kubectl get pods -n vault -l app.kubernetes.io/name=external-secrets
kubectl get crd | grep external-secrets
```

Видим установленные CRD:

- `externalsecrets.external-secrets.io`
- `secretstores.external-secrets.io`
- `clustersecretstores.external-secrets.io`

## 7. Создание SecretStore и ExternalSecret

### 7.1. Создание SecretStore

Применяем манифест SecretStore:

```bash
kubectl apply -f secret-store.yaml
```

### 7.2. Проверка подключения SecretStore

```bash
kubectl get secretstore -n vault
kubectl describe secretstore vault-backend -n vault
```

### 7.3. Создание ExternalSecret

Применяем манифест ExternalSecret:

```bash
kubectl apply -f external-secret.yaml
```

### 7.4. Проверка ExternalSecret

```bash
kubectl get externalsecret -n vault
kubectl describe externalsecret otus-external-secret -n vault
```

## 8. Проверка результата

### 8.1. Проверка созданного Secret

```bash
kubectl get secret otus-cred -n vault
```

### 8.2. Проверка содержимого Secret

```bash
kubectl get secret otus-cred -n vault -o yaml
```

### 8.3. Декодирование значений

```bash
# Проверка username
kubectl get secret otus-cred -n vault -o jsonpath='{.data.username}' | base64 -d

# Проверка password
kubectl get secret otus-cred -n vault -o jsonpath='{.data.password}' | base64 -d
```

### 8.4. Более удобный вывод значений

```bash
echo "Username: $(kubectl get secret otus-cred -n vault -o jsonpath='{.data.username}' | base64 -d)"
echo "Password: $(kubectl get secret otus-cred -n vault -o jsonpath='{.data.password}' | base64 -d)"
```

## Очистка ресурсов

Если нужно удалить все созданные ресурсы, выполняем:

```bash
# Удаление External Secrets
kubectl delete -f external-secret.yaml
kubectl delete -f secret-store.yaml

# Удаление External Secrets Operator
helm uninstall external-secrets -n vault

# Удаление Vault
helm uninstall vault -n vault

# Удаление Consul
helm uninstall consul -n consul

# Удаление namespaces
kubectl delete namespace vault
kubectl delete namespace consul
```

## Файлы проекта

### Основные манифесты

- `namespaces.yaml` - манифесты для создания namespace consul и vault
- `consul-values.yaml` - параметры для установки Consul (3 реплики)
- `vault-values.yaml` - параметры для установки Vault (HA режим с Consul)
- `vault-auth-sa.yaml` - ServiceAccount и ClusterRoleBinding для vault-auth
- `otus-policy.hcl` - политика Vault для доступа к секретам otus/cred
- `eso-values.yaml` - параметры для установки External Secrets Operator
- `secret-store.yaml` - манифест SecretStore для подключения к Vault
- `external-secret.yaml` - манифест ExternalSecret для синхронизации секрета
