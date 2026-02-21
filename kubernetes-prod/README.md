# Развёртывание кластера Kubernetes (kubeadm) и обновление

## Окружение

| Узел      | IP-адрес       | Роль          |
|-----------|----------------|---------------|
| master    | 192.168.177.56 | control-plane |
| worker-1  | 192.168.177.44 | worker        |
| worker-2  | 192.168.177.70 | worker        |
| worker-3  | 192.168.177.51 | worker        |

**Версии Kubernetes:**  

- Установка: на одну минорную версию ниже актуальной (см. [Releases | Kubernetes](https://kubernetes.io/releases/)).  
  Пример: если актуальная — 1.34.x, ставим **1.33.x** (например, 1.33.8).  
- После обновления: на одну версию выше установленной (например, 1.34.4).

Предполагается: **swap отключён** на всех узлах; маршрутизация при необходимости настраивается отдельно.

---

## Часть 1. Подготовка узлов (на каждой VM)

Выполнять **на всех четырёх узлах** (master, worker-1, worker-2, worker-3).

### 1.1. Отключение swap (если ещё включён)

```bash
sudo swapoff -a
sudo sed -i '/[[:space:]]swap[[:space:]]/ s/^\(.*\)$/#\1/' /etc/fstab
```

### 1.2. Загрузка модулей ядра

**overlay** — нужен containerd для хранения слоёв образов контейнеров.  
**br_netfilter** — чтобы трафик через bridge обрабатывался iptables (иначе параметры `net.bridge.bridge-nf-call-*` из п. 1.3 не сработают); требуется для сети Kubernetes и kube-proxy.

```bash
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
sudo modprobe overlay
sudo modprobe br_netfilter
```

### 1.3. Параметры sysctl для Kubernetes

```bash
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sudo sysctl --system
```

---

## Часть 2. Установка containerd, kubeadm, kubelet, kubectl (на всех узлах)

Команды ниже — **на каждой из четырёх VM**.

### 2.1. Установка containerd

```bash
# Ubuntu/Debian: обновление и установка зависимостей
sudo apt-get update
sudo apt-get install -y ca-certificates curl gpg

# Ключ и репозиторий containerd (официальный)
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y containerd.io

# Конфигурация containerd для Kubernetes
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml > /dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd
```

### 2.2. Репозиторий Kubernetes (APT)

```bash
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.33/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.33/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
```

> **Важно:** для установки «на одну ниже» используется v1.33 (обновление затем до 1.34). Актуальные пути: https://pkgs.k8s.io/

### 2.3. Установка kubeadm, kubelet, kubectl

```bash
sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
sudo systemctl enable kubelet
```

---

## Часть 3. Инициализация кластера (только на master)

Выполнять **только на master** (192.168.177.56).

### 3.1. Инициализация control-plane

Подставьте свою версию вместо `1.33.8` при необходимости:

```bash
sudo kubeadm init --pod-network-cidr=10.244.0.0/16 --kubernetes-version=1.33.8
```

### 3.2. Настройка kubectl для текущего пользователя

```bash
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

### 3.3. Сохранение команды join для worker-нод

В выводе `kubeadm init` будет блок вида:

```text
kubeadm join 192.168.177.56:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>
```

Сохраните эту команду целиком — она понадобится для worker-нод. При необходимости позже можно сгенерировать новый токен:

```bash
kubeadm token create --print-join-command
```

---

## Часть 4. Установка Flannel (только на master)

```bash
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml
```

Проверка:

```bash
kubectl get pods -n kube-flannel -o wide
```

---

## Часть 5. Присоединение worker-нод

На **каждой** worker-ноде (worker-1, worker-2, worker-3) выполнить команду `kubeadm join`, полученную на шаге 3.3:

```bash
sudo kubeadm join 192.168.177.56:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>
```

---

## Часть 6. Проверка кластера после установки

На **master**:

```bash
kubectl get nodes -o wide
```

```text
NAME          STATUS   ROLES           AGE     VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION     CONTAINER-RUNTIME
master-node   Ready    control-plane   4m23s   v1.33.8   192.168.177.56   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-1      Ready    <none>          84s     v1.33.8   192.168.177.44   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-2      Ready    <none>          39s     v1.33.8   192.168.177.70   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-3      Ready    <none>          34s     v1.33.8   192.168.177.51   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
```

---

## Часть 7. Обновление кластера до последней актуальной версии

Целевая версия после обновления — 1.34.x (например, 1.34.4). Актуальные патчи: https://kubernetes.io/releases/

### 7.1. Обновление master-ноды

На **master** сначала подключите репозиторий целевой версии (v1.34) и выполните `apt-get update` — иначе пакеты 1.34.x не найдутся. `apt-cache madison` показывает только версии из **уже подключённых** репозиториев (при одном лишь v1.33 будут видны только 1.33.x).

**Подключить репозиторий v1.34**:

```bash
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.34/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.34/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
```

#### Обновить индекс пакетов (после добавления репозитория)

```bash
sudo apt-get update
```

#### Снять hold с kubeadm

```bash
sudo apt-mark unhold kubeadm
```

#### Проверить, что обновление возможно

```bash
sudo kubeadm upgrade plan
```

#### Из вывода понимаем, что обновление доступно. При этом, так как нельзя обновляться сразу на последнюю версию, обновляемся сначала на предпоследнюю 1.34.x

```text
[preflight] Running pre-flight checks.
[upgrade/config] Reading configuration from the "kubeadm-config" ConfigMap in namespace "kube-system"...
[upgrade/config] Use 'kubeadm init phase upload-config --config your-config-file' to re-upload it.
[upgrade] Running cluster health checks
[upgrade] Fetching available versions to upgrade to
[upgrade/versions] Cluster version: 1.33.8
[upgrade/versions] kubeadm version: v1.33.8
I0220 22:36:50.983187   17441 version.go:261] remote version is much newer: v1.35.1; falling back to: stable-1.33
[upgrade/versions] Target version: v1.33.8
[upgrade/versions] Latest version in the v1.33 series: v1.33.8
```

#### Выявить версию kubeadm

```bash
apt-cache madison kubeadm
```

```text
kubeadm | 1.34.4-1.1 | https://pkgs.k8s.io/core:/stable:/v1.34/deb  Packages
kubeadm | 1.34.3-1.1 | https://pkgs.k8s.io/core:/stable:/v1.34/deb  Packages
kubeadm | 1.34.2-1.1 | https://pkgs.k8s.io/core:/stable:/v1.34/deb  Packages
kubeadm | 1.34.1-1.1 | https://pkgs.k8s.io/core:/stable:/v1.34/deb  Packages
kubeadm | 1.34.0-1.1 | https://pkgs.k8s.io/core:/stable:/v1.34/deb  Packages
```

#### Установить kubeadm целевой версии (1.34.4-1.1)

```bash
sudo apt-get install -y kubeadm=1.34.4-1.1
sudo apt-mark hold kubeadm
```

#### Применить обновление control-plane (подставьте целевую версию, например 1.34.4)

```bash
sudo kubeadm upgrade plan
sudo kubeadm upgrade apply v1.34.4
```

#### Обновить kubelet и kubectl

```bash
sudo apt-get install -y kubelet=1.34.4-1.1 kubectl=1.34.4-1.1
sudo apt-mark hold kubelet kubectl
sudo systemctl daemon-reload
sudo systemctl restart kubelet
```

Проверка:

```bash
kubectl get nodes -o wide
```

```text
NAME          STATUS   ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION     CONTAINER-RUNTIME
master-node   Ready    control-plane   48m   v1.34.4   192.168.177.56   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-1      Ready    <none>          45m   v1.33.8   192.168.177.44   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-2      Ready    <none>          44m   v1.33.8   192.168.177.70   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-3      Ready    <none>          44m   v1.33.8   192.168.177.51   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
```

### 7.2. Обновление worker-нод по одной (на master)

Для **каждой** worker-ноды (worker-1 → worker-2 → worker-3):

**Шаг 1.** На **master** вывести узлы из планирования и проверить:

```bash
kubectl cordon worker-1 worker-2 worker-3
kubectl get nodes -o wide
```

```text
NAME          STATUS                     ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION     CONTAINER-RUNTIME
master-node   Ready                      control-plane   52m   v1.34.4   192.168.177.56   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-1      Ready,SchedulingDisabled   <none>          49m   v1.33.8   192.168.177.44   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-2      Ready,SchedulingDisabled   <none>          48m   v1.33.8   192.168.177.70   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-3      Ready,SchedulingDisabled   <none>          48m   v1.33.8   192.168.177.51   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
```

**Шаг 2.** На **worker-1, worker-2, worker-3** обновить kubeadm, конфиг kubelet и пакеты 1.34.x. На worker по умолчанию только репозиторий v1.33 — сначала добавить репозиторий v1.34. **kubeadm на worker тоже нужно обновить** до целевой версии перед `kubeadm upgrade node`: он обновляет конфиг kubelet (в т.ч. kubeadm-flags.env), и старый kubeadm может записать флаги, удалённые в новой версии (например `--pod-infra-container-image` в 1.35).

```bash
# На worker-1, worker-2, worker-3
# Репозиторий v1.34 на worker — иначе пакеты 1.34.x не найдутся (apt увидит только v1.33)
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.34/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.34/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list

sudo apt-get update
sudo apt-mark unhold kubeadm kubelet kubectl
sudo apt-get install -y kubeadm=1.34.4-1.1
sudo apt-mark hold kubeadm

sudo kubeadm upgrade node

sudo apt-get install -y kubelet=1.34.4-1.1 kubectl=1.34.4-1.1
sudo apt-mark hold kubelet kubectl
sudo systemctl daemon-reload
sudo systemctl restart kubelet
```

**Шаг 3.** Снова на **master** вернуть узлы в планирование:

```bash
kubectl uncordon worker-1 worker-2 worker-3
kubectl get nodes -o wide
```

```text
NAME          STATUS   ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION     CONTAINER-RUNTIME
master-node   Ready    control-plane   65m   v1.34.4   192.168.177.56   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-1      Ready    <none>          62m   v1.34.4   192.168.177.44   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-2      Ready    <none>          61m   v1.34.4   192.168.177.70   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-3      Ready    <none>          61m   v1.34.4   192.168.177.51   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
```

### 7.3. Обновление до последней версии

**Шаг 1.** На **master**:

**Подключить репозиторий v1.35**:

```bash
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
```

#### Обновить индекс пакетов (после добавления репозитория v1.35)

```bash
sudo apt-get update
```

#### Снять hold с kubeadm (на master)

```bash
sudo apt-mark unhold kubeadm
```

#### Проверить, что обновление возможно (на master)

```bash
sudo kubeadm upgrade plan
```

#### Из вывода понимаем, что обновление доступно

```text
[preflight] Running pre-flight checks.
[upgrade/config] Reading configuration from the "kubeadm-config" ConfigMap in namespace "kube-system"...
[upgrade/config] Use 'kubeadm init phase upload-config kubeadm --config your-config-file' to re-upload it.
[upgrade] Running cluster health checks
[upgrade] Fetching available versions to upgrade to
[upgrade/versions] Cluster version: 1.34.4
[upgrade/versions] kubeadm version: v1.34.4
I0220 23:36:45.613356   35720 version.go:260] remote version is much newer: v1.35.1; falling back to: stable-1.34
[upgrade/versions] Target version: v1.34.4
[upgrade/versions] Latest version in the v1.34 series: v1.34.4
```

#### Выявить версию kubeadm (на master)

```bash
apt-cache madison kubeadm
```

```text
kubeadm | 1.35.1-1.1 | https://pkgs.k8s.io/core:/stable:/v1.35/deb  Packages
kubeadm | 1.35.0-1.1 | https://pkgs.k8s.io/core:/stable:/v1.35/deb  Packages
```

#### Установить kubeadm целевой версии (1.35.1-1.1)

```bash
sudo apt-get install -y kubeadm=1.35.1-1.1
sudo apt-mark hold kubeadm
```

#### Применить обновление control-plane (на master)

```bash
sudo kubeadm upgrade plan
sudo kubeadm upgrade apply v1.35.1
```

#### Обновить kubelet и kubectl (на master)

```bash
sudo apt-mark unhold kubelet kubectl
sudo apt-get install -y kubelet=1.35.1-1.1 kubectl=1.35.1-1.1
sudo apt-mark hold kubelet kubectl
sudo systemctl daemon-reload
sudo systemctl restart kubelet
```

Проверка:

```bash
kubectl get nodes -o wide
```

```text
NAME          STATUS   ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION     CONTAINER-RUNTIME
master-node   Ready    control-plane   82m   v1.35.1   192.168.177.56   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-1      Ready    <none>          79m   v1.34.4   192.168.177.44   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-2      Ready    <none>          78m   v1.34.4   192.168.177.70   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-3      Ready    <none>          78m   v1.34.4   192.168.177.51   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
```

### 7.4. Обновление worker-нод по одной (master)

Для **каждой** worker-ноды (worker-1 → worker-2 → worker-3):

**Шаг 1.** На **master** вывести узлы из планирования и проверить:

```bash
kubectl cordon worker-1 worker-2 worker-3
kubectl get nodes -o wide
```

```text
NAME          STATUS                     ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION     CONTAINER-RUNTIME
master-node   Ready                      control-plane   82m   v1.35.1   192.168.177.56   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-1      Ready,SchedulingDisabled   <none>          79m   v1.34.4   192.168.177.44   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-2      Ready,SchedulingDisabled   <none>          78m   v1.34.4   192.168.177.70   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-3      Ready,SchedulingDisabled   <none>          78m   v1.34.4   192.168.177.51   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
```

**Шаг 2.** На **worker-1, worker-2, worker-3** обновить kubeadm, конфиг kubelet и пакеты 1.35.x. На worker по умолчанию только репозиторий v1.34 — сначала добавить репозиторий v1.35. **kubeadm на worker тоже обновить** до 1.35.x перед `kubeadm upgrade node`, иначе старый kubeadm запишет в kubeadm-flags.env удалённые в 1.35 флаги (например `--pod-infra-container-image`) и kubelet будет падать с "unknown flag".

```bash
# На worker-1, worker-2, worker-3
# Репозиторий v1.35 на worker — иначе пакеты 1.35.x не найдутся (apt увидит только v1.34)
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list

sudo apt-get update
sudo apt-mark unhold kubeadm kubelet kubectl
sudo apt-get install -y kubeadm=1.35.1-1.1
sudo apt-mark hold kubeadm

sudo kubeadm upgrade node

sudo apt-get install -y kubelet=1.35.1-1.1 kubectl=1.35.1-1.1
sudo apt-mark hold kubelet kubectl
sudo systemctl daemon-reload
sudo systemctl restart kubelet
```

**Шаг 3.** Снова на **master** вернуть узлы в планирование:

```bash
kubectl uncordon worker-1 worker-2 worker-3
kubectl get nodes -o wide
```

```text
NAME          STATUS   ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION     CONTAINER-RUNTIME
master-node   Ready    control-plane   121m   v1.35.1   192.168.177.56   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic    containerd://2.2.1
worker-1      Ready    <none>          118m   v1.35.1   192.168.177.44   <none>        Ubuntu 24.04.3 LTS   6.8.0-100-generic   containerd://2.2.1
worker-2      Ready    <none>          117m   v1.35.1   192.168.177.70   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic    containerd://2.2.1
worker-3      Ready    <none>          117m   v1.35.1   192.168.177.51   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic    containerd://2.2.1
```

---

## Задание со звёздочкой: отказоустойчивый кластер с Kubespray

Развернуть отказоустойчивый кластер Kubernetes с помощью **Kubespray**: 3 master-ноды, минимум 2 worker-ноды.

**К результатам приложить:** inventory-файл, использованный для создания кластера, и вывод команды `kubectl get nodes -o wide`.

---

## Окружение (HA-кластер)

| Узел          | IP-адрес        | Роль                |
|---------------|-----------------|---------------------|
| master-node-1 | 192.168.177.56  | control-plane, etcd |
| master-node-2 | 192.168.177.51  | control-plane, etcd |
| master-node-3 | 192.168.177.136 | control-plane, etcd |
| worker-1      | 192.168.177.44  | worker              |
| worker-2      | 192.168.177.69  | worker              |

Требования к узлам: отключён swap, SSH по ключу с deploy-машины, **sudo без пароля** для пользователя, под которым запускается Ansible, иначе playbook завершается с ошибкой `Missing sudo password`).

**Вариант 1 — passwordless sudo :** на **каждом** узле (master-node-1, master-node-2, master-node-3, worker-1, worker-2), в моём случае это `user1`:

```bash
echo 'user1 ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/user1
sudo chmod 440 /etc/sudoers.d/user1
```

**Вариант 2 — запрос пароля sudo при запуске:** если NOPASSWD настроить нельзя, запускать playbook с флагом `-K`, Ansible запросит BECOME password:

```bash
ansible-playbook -i inventory/mycluster/inventory.ini cluster.yml -b -u user1 -K
```

---

### 1. Подготовка машины с Ansible

Kubespray запускается с отдельной машины (ноутбук, CI-сервер или одна из VM), с которой есть SSH-доступ ко всем узлам кластера.

#### 1.1. Клонирование Kubespray и установка зависимостей

```bash
# Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate
# Клонирование Kubespray
git clone https://github.com/kubernetes-sigs/kubespray.git
# Установка Kubespray
cd kubespray
# Переключение на релиз 2.30 (https://github.com/kubernetes-sigs/kubespray/tree/release-2.30)
git checkout v2.30.0
# Установка зависимостей
pip install -r requirements.txt
```

#### 1.2. Создание inventory

В [release-2.30](https://github.com/kubernetes-sigs/kubespray/tree/release-2.30) в качестве образца используется формат **inventory.ini** (INI). Копируем пример и правим inventory:

```bash
cp -r inventory/sample inventory/mycluster
```

Редактируем `inventory/mycluster/inventory.ini`. Пример для 3 master (stacked etcd) и 2 worker с нашими IP:

```ini
[kube_control_plane]
master-node-1 ansible_host=192.168.177.56 ip=192.168.177.56 etcd_member_name=etcd1
master-node-2 ansible_host=192.168.177.51 ip=192.168.177.51 etcd_member_name=etcd2
master-node-3 ansible_host=192.168.177.136 ip=192.168.177.136 etcd_member_name=etcd3

[etcd:children]
kube_control_plane

[kube_node]
worker-1 ansible_host=192.168.177.44 ip=192.168.177.44
worker-2 ansible_host=192.168.177.69 ip=192.168.177.69
```

Либо готовый файл для этого окружения: `kubernetes-prod/kubespray-inventory.ini` в репозитории — скопировать в `inventory/mycluster/inventory.ini`.

#### 1.3. Проверка доступности узлов

```bash
ansible -i inventory/mycluster/inventory.ini all -m ping -u user1
```

---

### 2. Запуск развёртывания кластера

При настроенном passwordless sudo для `user1` на всех узлах:

```bash
ansible-playbook -i inventory/mycluster/inventory.ini cluster.yml -b -u user1 -K
```

---

### 3. Доступ к кластеру и проверка, например, на master-node-1

```bash
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

Вывод команды `kubectl get nodes -o wide` на master-node-1:

```text
NAME            STATUS   ROLES           AGE     VERSION   INTERNAL-IP       EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION     CONTAINER-RUNTIME
master-node-1   Ready    control-plane   6m22s   v1.34.3   192.168.177.56    <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
master-node-2   Ready    control-plane   6m6s    v1.34.3   192.168.177.51    <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
master-node-3   Ready    control-plane   6m1s    v1.34.3   192.168.177.136   <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-1        Ready    <none>          5m35s   v1.34.3   192.168.177.44    <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
worker-2        Ready    <none>          5m35s   v1.34.3   192.168.177.69    <none>        Ubuntu 24.04.3 LTS   6.8.0-90-generic   containerd://2.2.1
```

Файл inventory, который использовался для создания кластера, `kubernetes-prod/kubespray-inventory.ini` в репозитории.
