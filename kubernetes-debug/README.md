# Домашнее задание: отладка в Kubernetes (kubectl debug)

Выполнено с помощью minikube

---

## 1. Pod с distroless-образом nginx

**Манифест:** [nginx-distroless-pod.yaml](nginx-distroless-pod.yaml)

Применение в кластере:

```bash
cd kubernetes-debug
```

```bash
kubectl apply -f nginx-distroless-pod.yaml
```

Поле `shareProcessNamespace: true` в манифесте нужно для доступа эфемерного отладочного контейнера к PID namespace основного контейнера.

---

## 2. Эфемерный контейнер с доступом к PID namespace

Запуск отладки с эфемерным контейнером и привязкой к контейнеру `nginx` (общий PID namespace):

```bash
kubectl debug -it nginx-distroless --image=nicolaka/netshoot --target=nginx --profile=general -- sh
```

Параметр `--target=nginx` подключает отладочный контейнер к namespaces, в том числе PID, контейнера `nginx`. Параметр `--profile=general` даёт доступ к файловой системе (далее - ФС) целевого контейнера через `/proc/1/root`. Образ `nicolaka/netshoot` содержит shell, tcpdump и другие утилиты.

Выход из отладочной оболочки: `exit` или Ctrl+D.

---

## 3. Доступ к файловой системе контейнера nginx из эфемерного

В поде **два контейнера**: основной **nginx** (distroless) и **эфемерный отладочный** (например, netshoot). Это разные контейнеры со своими корневыми ФС. **Hostname совпадает** у обоих, потому что в Kubernetes hostname задаётся на уровне **Pod** (имя пода — `nginx-distroless`), а не отдельно для каждого контейнера.

- **`/etc`** в оболочке отладочного контейнера — это своя файловая система (у `nicolaka/netshoot` — Alpine).
- **`/proc/1/root/etc`** — корневая ФС целевого контейнера (`nginx`). У `kyos0109/nginx-distroless` там только hostname, hosts, mtab, resolv.conf.

Чтобы смотреть именно ФС nginx, нужно использовать путь через `/proc/1/root/...`.

В оболочке эфемерного контейнера (после `kubectl debug -it nginx-distroless --image=nicolaka/netshoot --target=nginx --profile=general -- sh`) общий PID даёт доступ к корню ФС целевого контейнера через `/proc/<pid>/root`. Обычно процесс nginx в контейнере имеет PID 1. Одной командой (без входа в sh):

```bash
kubectl debug -it nginx-distroless --image=nicolaka/netshoot --target=nginx --profile=general -- ls -la /proc/1/root/etc/nginx
```

**Вывод:**

```bash
ls: /proc/1/root/etc/nginx: No such file or directory
```

**Примечание:** образ `kyos0109/nginx-distroless` минимальный и не содержит каталога `/etc/nginx`. Смотрим корень и `/etc` целевого контейнера:

```bash
kubectl debug -it nginx-distroless --image=nicolaka/netshoot --target=nginx --profile=general -- ls -la /proc/1/root/etc
```

**Вывод для kyos0109/nginx-distroless (каталог /etc целевого контейнера):**

```bash
total 20
drwxr-xr-x    2 root     root          4096 Feb 14 10:59 .
drwxr-xr-x    1 root     root          4096 Feb 14 10:59 ..
-rw-r--r--    1 root     root            17 Feb 14 10:59 hostname
-rw-r--r--    1 root     root           148 Feb 14 10:59 hosts
lrwxrwxrwx    1 root     root            12 Feb 14 10:59 mtab -> /proc/mounts
-rw-r--r--    1 root     root           103 Feb 14 10:59 resolv.conf
```

---

## 4. tcpdump в отладочном контейнере

В той же сессии эфемерного контейнера (или в новой `kubectl debug -it nginx-distroless --image=nicolaka/netshoot --target=nginx --profile=general -- ls -la /proc/1/root/etc`) запускаем tcpdump:

```bash
tcpdump -nn -i any -e port 80
```

Оставляем tcpdump работающим. В другом терминале выполняем обращения к nginx.

---

## 5. Сетевые обращения к nginx и проверка tcpdump

В другом терминале:

**Вариант первый: port-forward и curl с хоста:**

```bash
kubectl port-forward pod/nginx-distroless 8080:80
# в другом терминале или после фона:
curl -sS http://127.0.0.1:8080/
```

**Вариант второй: curl из другого пода в кластере:**

```bash
kubectl run curl --rm -it --restart=Never --image=curlimages/curl -- curl -s http://nginx-distroless.default.svc.cluster.local/
```

**Пример вывода tcpdump:**

```bash
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on any, link-type LINUX_SLL2 (Linux cooked v2), snapshot length 262144 bytes
15:24:52.090511 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 80: 127.0.0.1.34586 > 127.0.0.1.80: Flags [S], seq 1202002200, win 65495, options [mss 65495,sackOK,TS val 4115671916 ecr 0,nop,wscale 7], length 0
15:24:52.090527 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 80: 127.0.0.1.80 > 127.0.0.1.34586: Flags [S.], seq 4068992010, ack 1202002201, win 65483, options [mss 65495,sackOK,TS val 4115671916 ecr 4115671916,nop,wscale 7], length 0
15:24:52.090534 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 72: 127.0.0.1.34586 > 127.0.0.1.80: Flags [.], ack 1, win 512, options [nop,nop,TS val 4115671916 ecr 4115671916], length 0
15:24:52.090586 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 149: 127.0.0.1.34586 > 127.0.0.1.80: Flags [P.], seq 1:78, ack 1, win 512, options [nop,nop,TS val 4115671916 ecr 4115671916], length 77: HTTP: GET / HTTP/1.1
15:24:52.090588 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 72: 127.0.0.1.80 > 127.0.0.1.34586: Flags [.], ack 78, win 511, options [nop,nop,TS val 4115671916 ecr 4115671916], length 0
15:24:52.090894 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 310: 127.0.0.1.80 > 127.0.0.1.34586: Flags [P.], seq 1:239, ack 78, win 512, options [nop,nop,TS val 4115671916 ecr 4115671916], length 238: HTTP: HTTP/1.1 200 OK
15:24:52.090905 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 72: 127.0.0.1.34586 > 127.0.0.1.80: Flags [.], ack 239, win 511, options [nop,nop,TS val 4115671916 ecr 4115671916], length 0
15:24:52.090920 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 684: 127.0.0.1.80 > 127.0.0.1.34586: Flags [P.], seq 239:851, ack 78, win 512, options [nop,nop,TS val 4115671916 ecr 4115671916], length 612: HTTP
15:24:52.090922 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 72: 127.0.0.1.34586 > 127.0.0.1.80: Flags [.], ack 851, win 507, options [nop,nop,TS val 4115671916 ecr 4115671916], length 0
15:24:52.092358 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 72: 127.0.0.1.34586 > 127.0.0.1.80: Flags [F.], seq 78, ack 851, win 507, options [nop,nop,TS val 4115671918 ecr 4115671916], length 0
15:24:52.092435 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 72: 127.0.0.1.80 > 127.0.0.1.34586: Flags [F.], seq 851, ack 79, win 512, options [nop,nop,TS val 4115671918 ecr 4115671918], length 0
15:24:52.092448 lo    In  ifindex 1 00:00:00:00:00:00 ethertype IPv4 (0x0800), length 72: 127.0.0.1.34586 > 127.0.0.1.80: Flags [.], ack 852, win 507, options [nop,nop,TS val 4115671918 ecr 4115671918], length 0
15:25:03.028337 eth0  In  ifindex 11 5e:43:11:56:d5:e5 ethertype IPv4 (0x0800), length 80: 10.244.0.14.47584 > 10.244.0.12.80: Flags [S], seq 1245060137, win 64240, options [mss 1460,sackOK,TS val 612131784 ecr 0,nop,wscale 7], length 0
15:25:03.028350 eth0  Out ifindex 11 5a:f6:24:4b:74:0c ethertype IPv4 (0x0800), length 80: 10.244.0.12.80 > 10.244.0.14.47584: Flags [S.], seq 3279640480, ack 1245060138, win 65160, options [mss 1460,sackOK,TS val 3620449594 ecr 612131784,nop,wscale 7], length 0
15:25:03.028358 eth0  In  ifindex 11 5e:43:11:56:d5:e5 ethertype IPv4 (0x0800), length 72: 10.244.0.14.47584 > 10.244.0.12.80: Flags [.], ack 1, win 502, options [nop,nop,TS val 612131784 ecr 3620449594], length 0
15:25:03.028389 eth0  In  ifindex 11 5e:43:11:56:d5:e5 ethertype IPv4 (0x0800), length 178: 10.244.0.14.47584 > 10.244.0.12.80: Flags [P.], seq 1:107, ack 1, win 502, options [nop,nop,TS val 612131784 ecr 3620449594], length 106: HTTP: GET / HTTP/1.1
15:25:03.028390 eth0  Out ifindex 11 5a:f6:24:4b:74:0c ethertype IPv4 (0x0800), length 72: 10.244.0.12.80 > 10.244.0.14.47584: Flags [.], ack 107, win 509, options [nop,nop,TS val 3620449594 ecr 612131784], length 0
15:25:03.028487 eth0  Out ifindex 11 5a:f6:24:4b:74:0c ethertype IPv4 (0x0800), length 310: 10.244.0.12.80 > 10.244.0.14.47584: Flags [P.], seq 1:239, ack 107, win 509, options [nop,nop,TS val 3620449594 ecr 612131784], length 238: HTTP: HTTP/1.1 200 OK
15:25:03.028501 eth0  In  ifindex 11 5e:43:11:56:d5:e5 ethertype IPv4 (0x0800), length 72: 10.244.0.14.47584 > 10.244.0.12.80: Flags [.], ack 239, win 501, options [nop,nop,TS val 612131784 ecr 3620449594], length 0
15:25:03.028508 eth0  Out ifindex 11 5a:f6:24:4b:74:0c ethertype IPv4 (0x0800), length 684: 10.244.0.12.80 > 10.244.0.14.47584: Flags [P.], seq 239:851, ack 107, win 509, options [nop,nop,TS val 3620449594 ecr 612131784], length 612: HTTP
15:25:03.028512 eth0  In  ifindex 11 5e:43:11:56:d5:e5 ethertype IPv4 (0x0800), length 72: 10.244.0.14.47584 > 10.244.0.12.80: Flags [.], ack 851, win 497, options [nop,nop,TS val 612131784 ecr 3620449594], length 0
15:25:03.028560 eth0  In  ifindex 11 5e:43:11:56:d5:e5 ethertype IPv4 (0x0800), length 72: 10.244.0.14.47584 > 10.244.0.12.80: Flags [F.], seq 107, ack 851, win 497, options [nop,nop,TS val 612131784 ecr 3620449594], length 0
15:25:03.028597 eth0  Out ifindex 11 5a:f6:24:4b:74:0c ethertype IPv4 (0x0800), length 72: 10.244.0.12.80 > 10.244.0.14.47584: Flags [F.], seq 851, ack 108, win 509, options [nop,nop,TS val 3620449594 ecr 612131784], length 0
15:25:03.028616 eth0  In  ifindex 11 5e:43:11:56:d5:e5 ethertype IPv4 (0x0800), length 72: 10.244.0.14.47584 > 10.244.0.12.80: Flags [.], ack 852, win 497, options [nop,nop,TS val 612131784 ecr 3620449594], length 0
^C
24 packets captured
36 packets received by filter
0 packets dropped by kernel
```

---

## 6. Отладочный под для ноды (node debug)

Узнать ноду, на которой запущен под:

```bash
kubectl get pod nginx-distroless -o wide
```

**Вывод**:

```bash
nginx-distroless   1/1     Running   0          8m56s   10.244.0.12   minikube   <none>           <none>
```

Создать отладочный под на этой ноде с доступом к её файловой системе:

```bash
kubectl debug -it node/<NODE_NAME> --image=ubuntu -- chroot /host
```

Вместо `<NODE_NAME>` подставляем имя ноды из вывода выше (в моём случае это `minikube`). Для однократного выполнения команды на ноде без входа в shell:

```bash
kubectl debug -it node/minikube --image=ubuntu -- chroot /host sh -c 'команда'
```

В отладочном поде мы находимся в корне файловой системы ноды (`/host` в образе — это корень ноды).

---

## 7. Доступ к логам пода с distroless nginx с ноды

Из отладочного пода ноды (после `chroot /host`) логи контейнеров лежат в каталоге ноды:

```bash
/var/log/pods/<namespace>_<pod-name>_<pod-uid>/<container-name>/
```

Имя каталога пода можно найти, выполнив внутри chroot на ноде:

```bash
# В chroot на ноде (/host):
ls -lahF /var/log/pods/
# или найти по имени пода:
ls -lahF /var/log/pods/ | grep nginx-distroless
```

**Вывод:**

```bash
drwxr-xr-x  7 root root 4.0K Feb 14 15:24 default_nginx-distroless_84d58bd0-ac6b-4cb7-98a3-9b6726cd27ab/
```

Путь к логам контейнера `nginx`: `/var/log/pods/default_nginx-distroless_<POD_UID>/nginx/*.log`. UID пода: `kubectl get pod nginx-distroless -o jsonpath='{.metadata.uid}'`.

**Команда для получения логов (приложить к результатам ДЗ):**

С хоста (подставить свой UID вместо `<POD_UID>`; UID: `kubectl get pod nginx-distroless -o jsonpath='{.metadata.uid}'`):

```bash
kubectl debug --profile=general -it node/minikube --image=ubuntu -- chroot /host sh -c 'cat /var/log/pods/default_nginx-distroless_<POD_UID>/nginx/*.log'
```

```bash
kubectl debug --profile=general -it node/minikube --image=ubuntu -- chroot /host sh -c 'cat /var/log/pods/default_nginx-distroless_84d58bd0-ac6b-4cb7-98a3-9b6726cd27ab/nginx/*.log'
```

**Вывод:**

```bash
Creating debugging pod node-debugger-minikube-n47p5 with container debugger on node minikube.
{"log":"127.0.0.1 - - [14/Feb/2026:23:22:26 +0800] \"GET / HTTP/1.1\" 200 612 \"-\" \"curl/8.7.1\" \"-\"\n","stream":"stdout","time":"2026-02-14T15:22:26.515224136Z"}
{"log":"10.244.0.13 - - [14/Feb/2026:23:22:48 +0800] \"GET / HTTP/1.1\" 200 612 \"-\" \"curl/8.18.0\" \"-\"\n","stream":"stdout","time":"2026-02-14T15:22:48.258951049Z"}
{"log":"127.0.0.1 - - [14/Feb/2026:23:24:19 +0800] \"GET / HTTP/1.1\" 200 612 \"-\" \"curl/8.7.1\" \"-\"\n","stream":"stdout","time":"2026-02-14T15:24:19.583621508Z"}
{"log":"127.0.0.1 - - [14/Feb/2026:23:24:52 +0800] \"GET / HTTP/1.1\" 200 612 \"-\" \"curl/8.7.1\" \"-\"\n","stream":"stdout","time":"2026-02-14T15:24:52.091101926Z"}
{"log":"10.244.0.14 - - [14/Feb/2026:23:25:03 +0800] \"GET / HTTP/1.1\" 200 612 \"-\" \"curl/8.18.0\" \"-\"\n","stream":"stdout","time":"2026-02-14T15:25:03.028577292Z"}
```

Либо из отладочного пода ноды после `chroot /host`: `cat /var/log/pods/default_nginx-distroless_*/nginx/*.log`

---

## Задание со звёздочкой: strace для корневого процесса nginx

### Операции, необходимые для успешного выполнения

1. **Общий PID namespace**
   В поде должно быть `shareProcessNamespace: true` (уже есть в [nginx-distroless-pod.yaml](nginx-distroless-pod.yaml)). В эфемерном контейнере с `--target=nginx` видны процессы целевого контейнера. **Важно:** в части окружений, как оказалось, PID 1 — это процесс `/pause`, а nginx имеет другой PID; тогда нужно трассировать именно процесс nginx.

2. **Права на ptrace**
   Для прикрепления к чужому процессу (`strace -p 1`) контейнеру нужна возможность **ptrace** (как правило, capability `CAP_SYS_PTRACE`). В `kubectl debug` это даёт профиль **`--profile=general`** — без него будет ошибка вида `strace: ptrace(PTRACE_SEIZE, 1): Operation not permitted`.

3. **Образ с strace**
   Использовать образ отладочного контейнера, в котором есть **strace**, например **`nicolaka/netshoot`**.

4. **Запуск strace**
   Запускать strace **из эфемерного контейнера**, привязанного к контейнеру `nginx` (`--target=nginx`), чтобы видеть тот же PID namespace и процесс.

### Команда для выполнения

Сначала заходим в shell, затем вручную запускаем strace:

```bash
kubectl debug -it nginx-distroless --image=nicolaka/netshoot --target=nginx --profile=general -- sh
```

Затем выясняем PID процесса nginx:

```bash
ps axu | grep nginx
```

В моём случае PID_NGINX = 13

**Вывод:**

```bash
    7 root      0:00 {nginx} /run/rosetta/rosetta /usr/sbin/nginx nginx -g daemon off;
   13 101       0:00 {nginx} /run/rosetta/rosetta /usr/sbin/nginx nginx -g daemon off;
```

Внутри контейнера запускаем strace:

```bash
strace -p <PID_NGINX> -e trace=accept4,read,write -f
```

```bash
strace -p 13 -e trace=accept4,read,write -f
```

В другом терминале делаем запросы к nginx:

```bash
curl -sS http://127.0.0.1:8080/
```

Либо к сервису изнутри другого контейнера:

```bash
kubectl debug -it nginx-distroless --image=nicolaka/netshoot --target=nginx --profile=general -- sh
```

```bash
curl -sS http://nginx-distroless.default.svc.cluster.local/
```

**Наблюдаем вывод strace:**

```bash
accept4(9, {sa_family=AF_INET, sin_port=htons(33154), sin_addr=inet_addr("127.0.0.1")}, [112 => 16], SOCK_NONBLOCK) = 6
write(8, "127.0.0.1 - - [14/Feb/2026:23:35"..., 89) = 89
accept4(9, {sa_family=AF_INET, sin_port=htons(63842), sin_addr=inet_addr("10.244.0.1")}, [112 => 16], SOCK_NONBLOCK) = 6
write(8, "10.244.0.1 - - [14/Feb/2026:23:3"..., 91) = 91
```

Видно приём соединений `accept4`, клиентов `127.0.0.1` и `10.244.0.1`.
