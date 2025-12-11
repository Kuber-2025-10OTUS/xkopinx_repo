# Helmfile для установки Kafka

Этот helmfile описывает установку Apache Kafka из Bitnami Helm chart в двух окружениях: production и development.

## Структура

- `helmfile.yaml` - основной файл конфигурации helmfile с двумя релизами Kafka

## Конфигурация

### Production (kafka-prod)

- **Namespace**: `prod`
- **Количество брокеров**: 5
- **Версия Kafka**: 3.5.2
- **Протокол**: SASL_PLAINTEXT
- **Авторизация**: Включена (SASL/PLAIN)
- **Пользователи**:
  - `kafka` / `kafka-prod-password`
  - `admin` / `admin-prod-password`

### Development (kafka-dev)

- **Namespace**: `dev`
- **Количество брокеров**: 1
- **Версия Kafka**: Последняя доступная (пустой tag)
- **Протокол**: PLAINTEXT
- **Авторизация**: Отключена

## Использование

### Предварительные требования

1. Установите Helm:
   ```bash
   # macOS
   brew install helm
   
   # Linux
   curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
   ```

2. Установите Helmfile:
   ```bash
   # macOS
   brew install helmfile
   
   # Linux
   wget https://github.com/helmfile/helmfile/releases/download/v0.156.0/helmfile_0.156.0_linux_amd64.tar.gz
   tar -xzf helmfile_0.156.0_linux_amd64.tar.gz
   sudo mv helmfile /usr/local/bin/
   ```

3. Добавьте репозиторий Bitnami:
   ```bash
   helm repo add bitnami https://charts.bitnami.com/bitnami
   helm repo update
   ```

### Установка

Установить оба релиза (prod и dev):
```bash
helmfile apply
```

Установить только production:
```bash
helmfile -l name=kafka-prod apply
```

Установить только development:
```bash
helmfile -l name=kafka-dev apply
```

### Проверка установки

Проверить статус подов в production:
```bash
kubectl get pods -n prod
```

Проверить статус подов в development:
```bash
kubectl get pods -n dev
```

### Удаление

Удалить все релизы:
```bash
helmfile destroy
```

Удалить только production:
```bash
helmfile -l name=kafka-prod destroy
```

Удалить только development:
```bash
helmfile -l name=kafka-dev destroy
```

## Дополнительная информация

- Версия Helm chart: 26.0.0
- Каждый релиз включает встроенный ZooKeeper
- Persistent storage включен для Kafka и ZooKeeper

