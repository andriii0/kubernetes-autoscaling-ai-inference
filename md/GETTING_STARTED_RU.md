# Как сделать проект по масштабированию AI inference с нуля

Это инструкция для твоего Windows и папки `C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference`. Выполняй шаги по порядку. Команды предназначены для PowerShell, а не для терминала Linux. Блоки YAML, JavaScript и Python нужно сохранять в указанные файлы, а не вставлять в PowerShell.

Проверено 4 октября 2026: Docker и сохранённый кластер `ai-lab` работают. Одна копия Ollama с моделью `qwen2.5:0.5b` запущена на CPU и отвечает через Kubernetes Service. Добавлен `bench/inference.js`: минутная проверка k6 при двух запросах за 10 секунд дала 13 корректных ответов без ошибок и пропущенных итераций. Настройки находятся в `deploy/ollama.yaml`, результаты — в `results/smoke-2026-10-04/` и `results/k6-smoke-2026-10-04/`. Это первые проверки стенда: предел одной копии, порог допустимой задержки и основной эксперимент ещё не определены.

## Что в итоге будет работать

Ты запускаешь небольшую языковую модель, отправляешь ей много запросов и наблюдаешь, как Kubernetes добавляет её копии. Затем сравниваешь результаты с режимами, в которых число копий постоянно.

Рабочий кандидат для первого стенда — Docker Desktop, Minikube, Ollama, модель `qwen2.5:0.5b` и k6. Minikube запускает Kubernetes на твоём компьютере; Ollama запускает модель; k6 создаёт нагрузку. Основной эксперимент выполняется на CPU. Твоя RTX 5070 для этих шагов не требуется.

Это конкретный учебный маршрут для одного кандидата. До окончательного выбора платформы прочитай [раздел 14: исследование альтернатив и обоснование решений](#research-alternatives). В нём сравниваются в том числе варианты без Kubernetes и описано, чем проверять выбор. Успешный запуск Kubernetes ещё не доказывает, что он лучше остальных.

## 0. Сначала разберись в нескольких словах

**Контейнер** — запущенная программа с подготовленным окружением. **Образ контейнера** — пакет, из которого запускают такие контейнеры.

**Kubernetes** — система, которой ты говоришь, какие контейнеры и сколько их копий должны работать. Она запускает их и следит за состоянием.

**Кластер** — вся среда Kubernetes. **Нода (node)** — машина внутри этого кластера, на которой могут работать приложения. В нашем случае Minikube создаст одну ноду внутри Docker на твоём ПК. Это не дополнительный физический компьютер.

**Pod** — единица запуска приложения в Kubernetes. Здесь каждый pod содержит один контейнер Ollama. **Реплика** — ещё одна копия такого pod.

**Deployment** — описание приложения и желаемого количества его копий. **Service** — постоянный адрес, который направляет подключения к работающим копиям приложения.

**HPA (Horizontal Pod Autoscaler)** — механизм Kubernetes, который меняет число копий приложения по наблюдаемой нагрузке. В этом эксперименте он смотрит на использование CPU.

**Inference** — применение уже готовой модели: отправил текст, получил ответ. Обучать модель здесь не нужно.

Путь запроса будет таким:

```text
k6 на Windows → адрес Service → один из pod с Ollama → ответ модели
                                      ↑
                         HPA меняет число этих pod
```

Мы увеличиваем число pod на одной ноде. Число физических CPU и объём памяти ПК от этого не увеличиваются.

## 1. Подготовь Docker и терминал

Открой Docker Desktop через меню «Пуск» и дождись состояния работающего engine — движка, который запускает контейнеры. В настройках Docker должен использоваться WSL 2 — механизм запуска Linux внутри Windows. Нужен режим **Linux containers**. Встроенный Kubernetes в Docker Desktop включать для этого маршрута не требуется: кластер создаст Minikube.

Открой PowerShell и перейди в проект:

```powershell
Set-Location 'C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference'
docker info --format '{{.OSType}}'
docker info --format 'CPUs={{.NCPU}} RAM_BYTES={{.MemTotal}}'
```

Первая проверка должна вывести `linux`. Вторая показывает ресурсы, доступные Docker, а не только характеристики компьютера. Для следующих команд Docker должен видеть хотя бы 8 CPU и больше 12 ГиБ RAM.

Если Docker сообщает, что WSL отсутствует, открой PowerShell **от имени администратора**, выполни следующую команду и перезагрузи компьютер, если Windows этого попросит:

```powershell
wsl --install
```

Это условный шаг: если Docker уже работает, устанавливать WSL повторно не нужно. Если ресурсов Docker недостаточно, сначала проверь его настройки и существующие ограничения WSL; не заменяй весь файл `.wslconfig`, если там уже есть твои настройки.

**Проверка этапа:** `docker info` работает без ошибки подключения. Дальше пока не переходи, если движок Docker недоступен.

Источник: [Docker Desktop и WSL 2](https://docs.docker.com/desktop/features/wsl/).

## 2. Установи инструменты и создай Kubernetes

На твоём ПК Minikube и k6 уже установлены: пропусти установку и начни с проверки версий в новом окне PowerShell. Для повторения на другой машине команды установки такие:

```powershell
winget install --id Kubernetes.minikube --exact --source winget
winget install --id GrafanaLabs.k6 --exact --source winget
```

Minikube нужен для локального кластера. k6 — готовый генератор запросов: с ним сначала проверишь сам эксперимент, прежде чем писать собственный инструмент нагрузки.

После установки закрой и снова открой PowerShell, затем вернись в папку проекта:

```powershell
Set-Location 'C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference'
minikube version
k6 version
kubectl version --client
```

`kubectl` — программа, через которую ты отдаёшь команды Kubernetes. На твоей машине она уже была установлена вместе с Docker. Если команда сейчас не находится, установи её:

```powershell
winget install --id Kubernetes.kubectl --exact --source winget
```

Создай кластер с именем `ai-lab`, выделив ему 8 CPU и 12 ГиБ RAM:

```powershell
minikube start -p ai-lab --driver=docker --cpus=8 --memory=12288
kubectl --context ai-lab get nodes
```

Первый запуск скачивает необходимые образы и может занять несколько минут. В выводе второй команды должна появиться нода со статусом `Ready` — она готова запускать приложения. CPU здесь означает доступную вычислительную ёмкость, а не закрепление конкретных физических ядер i7.

Во всех следующих командах `--context ai-lab` явно выбирает наш локальный кластер. Это помогает не отправить команду в другой кластер, который может быть настроен у тебя на компьютере.

Создай `namespace` — отдельную группу ресурсов для нашего приложения — и включи сбор CPU и памяти:

```powershell
kubectl --context ai-lab create namespace inference
minikube -p ai-lab addons enable metrics-server
kubectl --context ai-lab top nodes
```

`metrics-server` — компонент, который передаёт Kubernetes данные об использовании ресурсов. Сразу после установки `top nodes` может ещё не показать данные: подожди минуту и повтори команду. Если namespace уже существует при повторном прохождении, создавать его снова не надо.

**Проверка этапа:** нода `Ready`, а `top nodes` показывает CPU и память.

Источники: [установка Minikube](https://minikube.sigs.k8s.io/docs/start/), [Docker driver](https://minikube.sigs.k8s.io/docs/drivers/docker/), [установка k6](https://grafana.com/docs/k6/latest/set-up/install-k6/).

## 3. Скачай модель и получи первый ответ

Берём **`qwen2.5:0.5b`**: это небольшая готовая языковая модель примерно на 0,5 миллиарда параметров. Её файл в каталоге Ollama занимает около 398 МБ; память во время работы будет больше размера файла. Для изучения масштабирования маленькая модель позволяет запустить несколько копий на CPU.

На твоём ПК модель уже скачана в контейнер `ai-lab-model`. Если ты его не удалял, выполни этот блок и переходи к шагу 4:

```powershell
docker start ai-lab-model
$ollamaImageId = docker inspect ai-lab-model --format '{{.Image}}'
$ollamaBaseImage = docker image inspect $ollamaImageId --format '{{index .RepoDigests 0}}'
docker exec ai-lab-model ollama list
```

Модель уже проверена коротким запросом на CPU. Контейнер ограничен 2 CPU и 2 ГиБ памяти; скачанные файлы сохраняются при остановке.

Следующий блок нужен только при подготовке с нуля, если контейнера `ai-lab-model` ещё нет. Ollama запустим во временном контейнере. Команды выполняй в одном окне PowerShell, чтобы сохранялась переменная `$ollamaBaseImage`:

```powershell
docker pull ollama/ollama:latest
$ollamaBaseImage = docker image inspect ollama/ollama:latest --format '{{index .RepoDigests 0}}'
docker run -d --name ai-lab-model $ollamaBaseImage
docker exec ai-lab-model ollama list
docker exec ai-lab-model ollama pull qwen2.5:0.5b
docker exec ai-lab-model ollama run qwen2.5:0.5b 'Explain what a container is in three short sentences.'
```

Если сразу после запуска `ollama list` сообщает, что сервер ещё недоступен, подожди несколько секунд и повтори её. Когда `pull` завершится, последняя команда должна напечатать ответ модели. Здесь GPU контейнеру не передаётся.

Переменная `$ollamaBaseImage` хранит идентификатор именно скачанной версии Ollama. Дальше используем его, чтобы все копии приложения запускались из одной версии.

**Проверка этапа:** модель отвечает на запрос ещё до подключения Kubernetes.

Источники: [Ollama в Docker](https://docs.ollama.com/docker), [модель qwen2.5:0.5b](https://ollama.com/library/qwen2.5:0.5b).

## 4. Подготовь образ с моделью внутри

Новые копии приложения не должны каждый раз скачивать модель из интернета: иначе ты будешь измерять ещё и скорость скачивания. Скопируй файлы модели и создай Dockerfile — короткую инструкцию сборки образа:

```powershell
New-Item -ItemType Directory -Force .\app\models | Out-Null
docker cp ai-lab-model:/root/.ollama/models/. .\app\models
@("FROM $ollamaBaseImage", 'COPY models/ /root/.ollama/models/') | Set-Content -Encoding ascii .\app\Dockerfile
docker build -t ai-inference:0.1 .\app
minikube -p ai-lab image load ai-inference:0.1
```

`ai-inference:0.1` — имя нашей собранной версии. Последняя команда передаёт образ в Minikube: образ, доступный обычному Docker, не обязательно уже доступен Kubernetes.

После успешной сборки и загрузки образа временный контейнер больше не нужен. Следующие команды остановят и удалят **только его**, скопированная модель останется в проекте:

```powershell
docker stop ai-lab-model
docker rm ai-lab-model
```

В корневой `.gitignore` добавь строку `/app/models/`, чтобы впоследствии случайно не загрузить сотни мегабайт весов модели в Git. Сам Dockerfile сохраняй вместе с проектом. На протяжении основной серии экспериментов не пересобирай образ под тем же именем.

**Проверка этапа:** обе команды сборки и загрузки образа завершились успешно.

## 5. Запусти одну копию модели в Kubernetes

В PyCharm создай файл `deploy/ollama.yaml` и вставь следующее. YAML — текстовый формат настроек; отступы здесь имеют значение, используй пробелы.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama
  namespace: inference
spec:
  replicas: 1
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 0
      maxUnavailable: 1
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      terminationGracePeriodSeconds: 60
      containers:
        - name: ollama
          image: ai-inference:0.1
          imagePullPolicy: Never
          ports:
            - containerPort: 11434
          env:
            - name: OLLAMA_HOST
              value: "0.0.0.0:11434"
            - name: OLLAMA_NUM_PARALLEL
              value: "1"
            - name: OLLAMA_CONTEXT_LENGTH
              value: "1024"
            - name: OLLAMA_KEEP_ALIVE
              value: "-1"
          resources:
            requests:
              cpu: "2"
              memory: "1Gi"
            limits:
              cpu: "2"
              memory: "2Gi"
          readinessProbe:
            httpGet:
              path: /api/tags
              port: 11434
            periodSeconds: 5
            timeoutSeconds: 5
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sleep", "35"]
---
apiVersion: v1
kind: Service
metadata:
  name: ollama
  namespace: inference
spec:
  type: NodePort
  selector:
    app: ollama
  ports:
    - port: 11434
      targetPort: 11434
      nodePort: 30080
```

Здесь `replicas: 1` просит одну копию. `requests` указывает ресурсы, которые Kubernetes должен учитывать при её размещении, а `limits` ограничивает потребление. Для каждой копии CPU ограничен двумя единицами: три копии смогут использовать до шести из восьми выделенных кластеру CPU.

`readinessProbe` — проверка готовности сервера принимать запросы. Она проверяет работу Ollama, но не означает, что модель уже загружена в RAM. Пауза `preStop` при остановке даёт уже начатым запросам время завершиться; возможные ошибки при удалении копий всё равно нужно измерять. Настройка `strategy` позволяет при перезапуске заменять копии по одной, не требуя ресурсов для четвёртой копии; перезапуски будем делать между измерениями.

`Service` выбирает pod по метке `app: ollama`. `NodePort` открывает порт приложения на ноде, а Windows получит доступ к нему на следующем шаге.

Примени файл:

```powershell
kubectl --context ai-lab apply -f .\deploy\ollama.yaml
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
kubectl --context ai-lab -n inference get pods
```

**Проверка этапа:** один pod показывает `Running` и `READY 1/1`. До этого момента генератор нагрузки не запускай.

## 6. Отправь запрос через адрес приложения

Открой **второе окно PowerShell** и выполни:

```powershell
minikube -p ai-lab service ollama -n inference --url
```

На Windows команда создаёт туннель — соединение между твоим компьютером и сервисом внутри Minikube. Она напечатает адрес вроде `http://127.0.0.1:54321`. **Оставь это окно открытым.** Порт может отличаться при каждом запуске.

В первом окне выполни следующую команду и вставь выданный адрес, без кавычек:

```powershell
$env:BASE_URL = (Read-Host 'Вставь адрес из окна minikube service').Trim().TrimEnd('/')
$body = @{
    model = 'qwen2.5:0.5b'
    prompt = 'Explain what a container is in three short sentences.'
    stream = $false
    keep_alive = -1
    options = @{ num_predict = 64; num_ctx = 1024; num_thread = 2; temperature = 0; seed = 42 }
} | ConvertTo-Json -Depth 3
Invoke-RestMethod -Uri "$env:BASE_URL/api/generate" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 60
```

`stream = false` означает, что получаем ответ целиком. `num_predict = 64` ограничивает ответ 64 токенами — небольшими фрагментами текста, из которых модель собирает ответ; фактический ответ может быть короче. `num_thread = 2` задаёт число вычислительных потоков. `keep_alive = -1` оставляет модель в памяти между запросами.

**Проверка этапа:** поле `response` содержит ответ, а `done` равно `true`.

Для нагрузочных тестов используй именно этот адрес Service. `kubectl port-forward deployment/ollama` выбирает отдельный pod и не подходит для проверки распределения нагрузки между всеми копиями.

Источники: [доступ к сервису Minikube с Windows](https://minikube.sigs.k8s.io/docs/handbook/accessing/), [Ollama generate API](https://docs.ollama.com/api/generate), [параметры Ollama](https://docs.ollama.com/faq).

## 7. Добавь нагрузочный сценарий

Создай файл `bench/inference.js`. Это сценарий для k6 на JavaScript. Он посылает новые запросы по расписанию, даже когда предыдущие ещё не закончились: так замедление модели не уменьшает нагрузку незаметно для нас.

```javascript
import http from 'k6/http';
import { Rate, Trend } from 'k6/metrics';

const requestLatency = new Trend('request_latency_ms', true);
const successfulLatency = new Trend('successful_latency_ms', true);
const inferenceErrors = new Rate('inference_errors');
const outputTokens = new Trend('output_tokens');
const modelLoad = new Trend('model_load_ms', true);
const baseUrl = __ENV.BASE_URL;
if (!baseUrl) throw new Error('BASE_URL is required');

const low = Number(__ENV.LOW_RATE || 2);
const peak = Number(__ENV.RATE || 10);
const common = { timeUnit: '10s', preAllocatedVUs: 50, maxVUs: 100, gracefulStop: '35s' };
const load = __ENV.PROFILE === 'burst'
  ? {
      ...common,
      executor: 'ramping-arrival-rate',
      startRate: low,
      stages: [
        { duration: '2m', target: low },
        { duration: '1s', target: peak },
        { duration: '5m', target: peak },
        { duration: '1s', target: low },
        { duration: '6m', target: low },
      ],
    }
  : { ...common, executor: 'constant-arrival-rate', rate: peak, duration: __ENV.DURATION || '13m2s' };

export const options = {
  scenarios: { load },
  noConnectionReuse: true,
  thresholds: {
    dropped_iterations: ['count==0'],
    inference_errors: ['rate<=0.01'],
    ...(__ENV.SLO_MS ? { successful_latency_ms: [`p(95)<=${Number(__ENV.SLO_MS)}`] } : {}),
  },
};

const payload = JSON.stringify({
  model: 'qwen2.5:0.5b',
  prompt: 'Explain what a container is in three short sentences.',
  stream: false,
  keep_alive: -1,
  options: { num_predict: 64, num_ctx: 1024, num_thread: 2, temperature: 0, seed: 42 },
});

export default function () {
  const started = Date.now();
  const response = http.post(`${baseUrl}/api/generate`, payload, {
    headers: { 'Content-Type': 'application/json' },
    timeout: '30s',
  });
  const elapsed = Date.now() - started;
  requestLatency.add(elapsed);
  let body;
  try {
    body = response.json();
  } catch (_) {
    body = null;
  }
  const ok = response.status === 200 && body && body.done === true && typeof body.response === 'string' && body.response.trim().length > 0;
  inferenceErrors.add(!ok);
  if (ok) {
    successfulLatency.add(elapsed);
    outputTokens.add(body.eval_count || 0);
    modelLoad.add((body.load_duration || 0) / 1e6);
  }
}
```

`noConnectionReuse` создаёт новые подключения: долго живущие соединения могут привязать запросы к старым копиям сервиса. `preAllocatedVUs` и `maxVUs` задают доступное число одновременно работающих исполнителей запросов в k6. Это не число пользователей твоего приложения и не число pod.

В первом окне PowerShell, где уже задан `BASE_URL`, запусти короткую пробу:

```powershell
k6 run -e RATE=2 -e DURATION=1m .\bench\inference.js
```

`RATE=2` здесь означает **два запроса за 10 секунд**, не два в секунду. Ожидается примерно 12 запросов за минуту.

Читай результат так:

- `successful_latency_ms`: время полного корректного ответа; `p(95)` — время, в которое уложились 95% успешных запросов.
- `inference_errors`: доля ошибок, включая неверные ответы API и таймауты — запросы, которые не завершились за 30 секунд.
- `request_latency_ms`: задержки всех отправленных запросов, включая неуспешные.
- `http_reqs`: число выполненных HTTP-запросов и их средняя частота.
- `dropped_iterations`: сколько запланированных запросов k6 не смог начать; если значение больше нуля, заданная нагрузка не была полностью создана.
- `output_tokens`: фактическая длина ответов; фиксированный лимит 64 не гарантирует ровно 64 токена.

Красная проверка k6 может означать нарушение критерия эксперимента, а не поломку скрипта. Например, более 1% ошибок нарушит заданный начальный критерий. Допуск ошибок и порог задержки нужно окончательно зафиксировать до основных прогонов.

**Проверка этапа:** короткий тест завершился, ответы корректные, `dropped_iterations` равен нулю.

Источники: [подача запросов независимо от времени ответа](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/), [constant arrival rate](https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/constant-arrival-rate/).

## 8. Найди предел одной копии

Пока HPA не создан, число копий фиксировано. Открой третье окно PowerShell и периодически проверяй:

```powershell
kubectl --context ai-lab -n inference top pods
```

Значение CPU `1000m` примерно соответствует одной единице CPU; у нас лимит одной копии `2000m`. Программа должна иметь возможность занять заметную часть своих двух CPU.

В первом окне запускай пробы **по одной**, сохраняя данные каждой. Например:

```powershell
k6 run -e RATE=2 -e DURATION=2m --out json=results/pilot-rate-2.json --summary-export results/pilot-rate-2-summary.json .\bench\inference.js
k6 run -e RATE=5 -e DURATION=2m --out json=results/pilot-rate-5.json --summary-export results/pilot-rate-5-summary.json .\bench\inference.js
k6 run -e RATE=10 -e DURATION=2m --out json=results/pilot-rate-10.json --summary-export results/pilot-rate-10-summary.json .\bench\inference.js
```

Между пробами дождись, чтобы оставшиеся запросы завершились, а CPU вернулся к низкому уровню. Не продолжай повышать нагрузку автоматически, если уже появились большие задержки и ошибки. Если все эти значения слишком лёгкие, попробуй 20, затем 40 запросов за 10 секунд. Если даже 2 слишком тяжёлые, начни с 1.

По пилоту выбери две частоты: низкую, при которой одна копия работает спокойно, и пиковую, при которой она уже заметно замедляется. Порог приемлемой задержки определи после пилота и запиши **до** сравнения режимов. Например, «95% корректных ответов не дольше 5 секунд и не более 1% ошибок» — это пример, а не уже измеренная характеристика твоего ПК.

Создай `md/plans/experiment-protocol.md` и запиши выбранные частоты, порог задержки, длительности сценариев и почему такой результат приемлем для выбранной задачи. Также укажи, что запросы одинаковые: это контролируемый простой сценарий, и его результаты не описывают все возможные пользовательские запросы.

## 9. Сначала увеличь число копий вручную

Выполни:

```powershell
kubectl --context ai-lab -n inference scale deployment/ollama --replicas=3
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
kubectl --context ai-lab -n inference get pods
```

Теперь должно быть три pod со статусом `Running` и готовностью `1/1`. Это и есть горизонтальное масштабирование — добавление копий приложения.

Проведи минуту небольшой нагрузки тем же скриптом, чтобы модели загрузились в память, затем проверь каждую копию:

```powershell
k6 run -e RATE=5 -e DURATION=1m .\bench\inference.js
$pods = (kubectl --context ai-lab -n inference get pods -l app=ollama -o json | ConvertFrom-Json).items
foreach ($pod in $pods) {
    $pod.metadata.name
    kubectl --context ai-lab -n inference exec $pod.metadata.name -- ollama ps
}
```

У всех копий должна отображаться загруженная модель и CPU-режим. Если какая-то ещё не получила запрос, продли прогрев. По `top pods` во время нагрузки убедись, что CPU используется несколькими копиями, а не только одной.

Повтори выбранную пиковую пробу. Если три копии не улучшают ситуацию, сначала проверь распределение запросов, доступные ресурсы и настройки нагрузки. Наличие трёх pod само по себе ещё не означает прирост производительности.

## 10. Включи автоматическое масштабирование

Верни одну копию и дождись её готовности:

```powershell
kubectl --context ai-lab -n inference scale deployment/ollama --replicas=1
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
kubectl --context ai-lab -n inference get pods
```

Создай `deploy/hpa.yaml`:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ollama
  namespace: inference
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ollama
  minReplicas: 1
  maxReplicas: 3
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
```

Примени:

```powershell
kubectl --context ai-lab apply -f .\deploy\hpa.yaml
kubectl --context ai-lab -n inference get hpa
```

HPA старается удержать среднюю загрузку около 60% от `requests.cpu`. Здесь запрос ресурсов равен 2 CPU, поэтому целевой уровень — примерно 1,2 CPU на копию, **не 60% всего процессора компьютера**. При устойчивой нагрузке выше цели он может добавить копии, но не больше трёх.

В отдельном окне наблюдай изменения:

```powershell
kubectl --context ai-lab -n inference get hpa --watch
```

В первом окне запусти сценарий со всплеском. Следующие значения — стартовый пример; замени их числами, выбранными по пилоту:

```powershell
k6 run -e PROFILE=burst -e LOW_RATE=2 -e RATE=10 .\bench\inference.js
```

Сценарий даёт две минуты небольшой нагрузки, за секунду повышает её, держит пять минут и возвращается к небольшой нагрузке ещё на шесть минут. Ты должен проверить, появляются ли дополнительные копии и уменьшается ли их число после спада. Масштабирование не мгновенное: нужно получить метрики, принять решение, запустить контейнер и загрузить модель.

После спада HPA учитывает пятиминутное окно стабилизации — период ожидания, который уменьшает постоянные добавления и удаления копий. Поэтому подожди; при очереди незавершённых запросов уменьшение может произойти ещё позже. Чтобы отдельно проверить возврат к одной копии, закончи тест и наблюдай ещё несколько минут без запросов.

Если в `TARGETS` долго остаётся `<unknown>`, HPA не получает метрику: сначала исправь это, не интерпретируй такой прогон как результат работы autoscaling.

Источник: [как работает HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/).

## 11. Начни сохранять состояние кластера

Смотреть на терминал достаточно для знакомства. Для отчёта нужны данные, которые останутся после теста.

Сборщик уже реализован в `bench/observe.py`. Он читает состояние pod, Deployment, HPA и нод, отдельно сохраняет сигнал metrics-server и прямые измерения CPU/памяти kubelet (компонента Kubernetes на ноде).

В новой вкладке PowerShell выполни:

```powershell
Set-Location 'C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference'
python .\bench\observe.py .\results\my-run\cluster.jsonl --duration 150
```

Это сохраняет примерно 150 секунд наблюдений с целевым интервалом 5 секунд. Для непрерывного сбора убери `--duration` и останови его `Ctrl+C`. Текущий опрос завершается перед проверкой длительности, поэтому остановка может произойти немного позже.

JSONL — текст, где каждая строка содержит отдельную запись JSON. Путь должен быть новым: существующий файл не перезаписывается. Все отметки времени сохраняются в UTC. Вместе с данными записываются фактическое время каждого чтения и ошибки; пропуски не заменяются нулями. Код завершения 0 означает отсутствие ошибок сбора, 1 — ошибки сбора, 2 — ошибку аргументов или создания файла.

CPU рассчитывается по приросту процессорного времени между исходными метками времени kubelet. Первая точка и повторившаяся метка времени дают `null`, а не ноль. Значение 2 означает среднее использование двух единиц CPU. Память сохраняется в байтах как working set (показатель используемой памяти). Метрики ноды относятся к Minikube, а не ко всему компьютеру Windows.

Отсутствие HPA до его настройки — нормальное состояние. При сбое отдельного источника сохраняются ошибка и остальные доступные данные. Проверка готовности pod не подтверждает завершение загрузки модели: прогрев остаётся отдельным этапом.

Проверить обработку ошибок и расчёты:

```powershell
python -m unittest discover -s bench -p test_observe.py -v
```

Формат данных, единицы и ограничения описаны в [bench/OBSERVATION.md](OBSERVATION.md). Первая проверка на работающем кластере сохранена в [results/observation-check-2026-10-16-verified/README.md](../results/observation-check-2026-10-16-verified/README.md).

## 12. Проведи одинаковые тесты в трёх режимах

Теперь сравнивай три режима. Переключай их **между** прогонами, а не во время измерения.

**Одна постоянная копия:**

```powershell
kubectl --context ai-lab -n inference delete hpa ollama --ignore-not-found
kubectl --context ai-lab -n inference scale deployment/ollama --replicas=1
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
```

**Три постоянные копии:**

```powershell
kubectl --context ai-lab -n inference delete hpa ollama --ignore-not-found
kubectl --context ai-lab -n inference scale deployment/ollama --replicas=3
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
```

**От одной до трёх копий автоматически:**

```powershell
kubectl --context ai-lab -n inference delete hpa ollama --ignore-not-found
kubectl --context ai-lab -n inference scale deployment/ollama --replicas=1
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
```

Для автоматического режима HPA применишь после прогрева, непосредственно перед измерением. Удаление и повторное создание только этого HPA сбрасывает историю предыдущего прогона.

Перед каждым прогоном проверь `get pods`: должно остаться ровно нужное число готовых копий и не должно быть завершающихся `Terminating`. Для чистого старта перезапусти приложение без HPA и прогрей начальные копии минутным тестом из шага 9:

```powershell
kubectl --context ai-lab -n inference rollout restart deployment/ollama
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
k6 run -e RATE=5 -e DURATION=1m .\bench\inference.js
```

Проверь `ollama ps` для каждой копии, как в шаге 9, и дождись обработки оставшихся запросов. Прогрев не включай в измерения. В автоматическом режиме прогрета только начальная копия; загрузка модели в новых копиях во время теста — часть измеряемой реакции масштабирования.

### Подготовка конкретного прогона

В первом окне задай имя режима и профиль нагрузки. Каждый повтор получает новую папку с временем запуска:

```powershell
$mode = 'fixed-1'
$profile = 'burst'
$runDir = Join-Path 'results' ("{0}-{1}-{2}" -f $mode, $profile, (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $runDir | Out-Null
$env:LOW_RATE = Read-Host 'Низкая частота из пилота: запросов за 10 секунд'
$env:RATE = Read-Host 'Пиковая частота из пилота: запросов за 10 секунд'
$env:SLO_MS = Read-Host 'Выбранный порог p95 в миллисекундах'
```

`$mode` меняет **только подпись результатов**. Реальный режим переключается командами выше. Используй имена `fixed-1`, `fixed-3`, `autoscaling`; для профиля — `steady` или `burst`.

Запиши конфигурацию:

```powershell
@{
    mode = $mode
    profile = $profile
    low_rate_per_10s = [int]$env:LOW_RATE
    peak_rate_per_10s = [int]$env:RATE
    p95_limit_ms = [int]$env:SLO_MS
    error_rate_limit = 0.01
    model = 'qwen2.5:0.5b'
    model_options = @{ num_predict = 64; num_ctx = 1024; num_thread = 2; temperature = 0; seed = 42 }
} | ConvertTo-Json -Depth 3 | Set-Content -Encoding utf8 "$runDir\settings.json"
minikube version | Set-Content -Encoding utf8 "$runDir\minikube-version.txt"
kubectl --context ai-lab version -o json | Set-Content -Encoding utf8 "$runDir\kubernetes-version.json"
k6 version | Set-Content -Encoding utf8 "$runDir\k6-version.txt"
docker image inspect ai-inference:0.1 | Set-Content -Encoding utf8 "$runDir\image.json"
kubectl --context ai-lab -n inference exec deployment/ollama -- ollama list | Set-Content -Encoding utf8 "$runDir\model-version.txt"
```

Для режима `autoscaling` сейчас включи HPA, дождись появления числовых метрик и убедись, что перед стартом осталась одна копия:

```powershell
kubectl --context ai-lab apply -f .\deploy\hpa.yaml
kubectl --context ai-lab -n inference get hpa
```

В режимах `fixed-1` и `fixed-3` этот блок пропусти. После выбора режима сохрани его настройки:

```powershell
kubectl --context ai-lab -n inference get deployment,service,hpa -o yaml | Set-Content -Encoding utf8 "$runDir\cluster-config.yaml"
$runDir
```

В окне наблюдения перейди в проект и вставь напечатанный путь папки:

```powershell
Set-Location 'C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference'
$observationDir = Read-Host 'Вставь путь папки текущего прогона'
python .\bench\observe.py "$observationDir\cluster.jsonl"
```

В первом окне запусти измерение:

```powershell
(Get-Date).ToUniversalTime().ToString('o') | Set-Content -Encoding utf8 "$runDir\started-at.txt"
k6 run -e "PROFILE=$profile" --out "json=$runDir/requests.json" --summary-export "$runDir/summary.json" .\bench\inference.js 2>&1 | Tee-Object -FilePath "$runDir\console.txt"
$LASTEXITCODE | Set-Content -Encoding ascii "$runDir\exit-code.txt"
(Get-Date).ToUniversalTime().ToString('o') | Set-Content -Encoding utf8 "$runDir\ended-at.txt"
```

После окончания дай наблюдателю записать последнее состояние и останови его через `Ctrl+C`. Если копии после всплеска ещё не уменьшились, можешь продолжить наблюдение без нагрузки, отметив этот дополнительный период в отчёте.

`steady` создаёт пиковую частоту постоянно 13 минут 2 секунды. `burst` использует низкую и пиковую частоты по расписанию из шага 10. К этому времени может добавиться завершение последних запросов.

Для каждого из трёх режимов выполни оба профиля и повтори каждый минимум три раза: получится 18 основных прогонов. Чередуй порядок режимов между повторами. Частоты, модель и её настройки, пороги, число CPU и длительности должны оставаться одинаковыми. Не запускай одновременно другие тяжёлые задачи на ПК.

Если `dropped_iterations > 0`, сам генератор не выдержал расписание. Сначала исправь это на пилоте: увеличь число исполнителей k6 или уменьши выбранную нагрузку для всей серии. Не включай такой прогон в сравнение как будто полная нагрузка была создана.

Источник: [сохранение исходных измерений k6](https://grafana.com/docs/k6/latest/results-output/real-time/json/).

## 13. Преврати результаты в вывод

Сначала открой `console.txt` каждого прогона и перенеси значения в таблицу в `report/results.md`:

| Режим | Профиль | Повтор | p95 успешного ответа | Ошибки | Выполнено запросов | Пропущено генератором | Максимум готовых копий |
|---|---|---|---|---|---|---|---|
| fixed-1 | burst | 1 | | | | | |
| fixed-3 | burst | 1 | | | | | |
| autoscaling | burst | 1 | | | | | |

`requests.json` содержит исходные точки измерений, по одной записи JSON на строку. `cluster.jsonl` содержит состояние кластера. По ним можно проверить цифры и построить графики, даже если терминал уже закрыт.

В `bench/analyze.py` следующим небольшим шагом реализуй чтение этих двух файлов: оставляй из k6 записи `type == "Point"`; для задержки используй `successful_latency_ms`, для ошибок — `inference_errors`. Сгруппируй данные по 30-секундным интервалам и сохрани таблицу с временем, p95, долей ошибок и числом готовых pod. Готовым считай pod без `deletionTimestamp` и с условием `Ready=True` в `status.conditions`. Если метрики в интервале нет, оставляй пропуск, а не ноль.

Для ресурсов используй записи `resources.items[].containers[].usage` из наблюдателя и суммируй значения всех контейнеров Ollama в одном замере. CPU может быть указан в `n` (миллиардная доля CPU), `u` (миллионная) или `m` (тысячная); память — в `Ki`, `Mi`, `Gi`. Перед суммированием приведи CPU к числу CPU, память к МиБ. Сохраняй пропуски измерений, если они возникли, и не приравнивай их к нулевому потреблению.

**Ограничение источника:** эти значения приходят из metrics-server и подходят для предварительного графика и наблюдения сигнала HPA. Разработчики не рекомендуют metrics-server для точного мониторинга ресурсов. Для итоговых выводов об их потреблении нужен отдельный источник измерений; сравнение вариантов приведено в пункте 14.13 [раздела исследования](#research-alternatives).

Из этой таблицы сделай три графика с общей осью времени: задержка и её допустимый порог; количество готовых копий; суммарный CPU. Для первой версии достаточно сохранить таблицу в CSV — обычную таблицу в текстовом файле — и построить графики в Excel через «Вставка → График». Ось времени синхронизируй по UTC — единому времени без местного часового сдвига — и отметь на графике начало и конец всплеска.

Не складывай p95 трёх повторов и не называй их среднее общим p95. Покажи p95 каждого повтора и разброс; общий p95 при необходимости считай заново из объединённых исходных задержек. Порог задержки считай выполненным только вместе с условием на долю ошибок: исчезновение медленных запросов из-за таймаутов не является улучшением.

В итоговом тексте ответь на конкретные вопросы:

1. При какой частоте одна копия переставала укладываться в выбранную задержку?
2. Что изменилось при трёх постоянных копиях?
3. Через сколько секунд после начала всплеска появилась первая дополнительная готовая копия?
4. Сколько времени autoscaling нарушал порог задержки во время всплеска?
5. Когда число копий уменьшилось после спада, были ли при этом ошибки?
6. Сколько ресурсов использовал каждый режим и какую задержку он обеспечивал?

Отдельно запиши ограничения: одна физическая машина, CPU вместо GPU, одинаковый короткий запрос, прогретые начальные копии и загрузка модели в новых копиях во время масштабирования. Из этого опыта можно сделать вывод о работе стенда и выбранной политики масштабирования; он не измеряет производительность большого GPU-кластера.

`app/inference.py` для первого маршрута заполнять не требуется: готовый сервер уже предоставляет Ollama. `bench/load_test.py` тоже может остаться заготовкой, пока нагрузку создаёт k6. Собственный Python-генератор имеет смысл добавлять, когда сможешь объяснить, какой возможности готового инструмента не хватает.

## Если что-то не работает

| Что видишь | Что проверить |
|---|---|
| Docker daemon недоступен | Запущен ли Docker Desktop; проходит ли `docker info`. |
| `minikube` или `k6` не найден | Перезапусти PowerShell после установки. |
| `ErrImageNeverPull` | Успешна ли сборка `ai-inference:0.1` и команда `minikube -p ai-lab image load ai-inference:0.1`. |
| Pod остаётся `Pending` | Хватает ли свободных CPU и памяти для его `requests`; посмотри `describe pod`. |
| `OOMKilled` | Контейнер превысил лимит памяти. Измени лимит на пилоте и повтори всю сопоставляемую серию с одинаковой конфигурацией. |
| Адрес приложения не отвечает | Открыто ли окно `minikube service`; не изменился ли порт после перезапуска. |
| HPA показывает `<unknown>` | Работает ли `metrics-server` и команда `top pods`. |
| Копии не добавляются | Есть ли достаточная CPU-нагрузка относительно `requests.cpu`; числовые ли метрики; не достигнут ли максимум 3. |
| Копии есть, ускорения нет | Доходят ли запросы до всех копий; не упёрлась ли вся машина в общий лимит CPU/памяти; одинакова ли длина ответов. |
| Несовместимость версии kubectl | Используй клиент, который скачает Minikube: вместо начального `kubectl --context ai-lab` в команде поставь `minikube -p ai-lab kubectl --`. |

Для диагностики узнай имя проблемного pod:

```powershell
kubectl --context ai-lab -n inference get pods
$podName = Read-Host 'Вставь имя проблемного pod'
kubectl --context ai-lab -n inference describe pod $podName
kubectl --context ai-lab -n inference logs $podName
kubectl --context ai-lab -n inference describe hpa ollama
```

`describe` показывает состояние и события; `logs` — вывод программы внутри контейнера. Не переходи к большому тесту, пока одиночный запрос и короткая проба не работают.

## Как закончить работу и продолжить завтра

Останови генератор и наблюдатель, закрой туннель через `Ctrl+C`, затем:

```powershell
minikube stop -p ai-lab
```

Остановка сохраняет окружение. В следующий раз открой Docker Desktop и выполни:

```powershell
minikube start -p ai-lab
kubectl --context ai-lab -n inference get pods
```

Заново открой туннель из шага 6 и задай его новый адрес в `BASE_URL`. Для измерений снова выполни подготовку нужного режима и прогрев из шага 12.

<a id="research-alternatives"></a>

## 14. Исследование альтернатив и обоснование решений

Этот раздел нужно прочитать **до выбора окончательной архитектуры**. Шаги 1–13 описывают один рабочий кандидат для прототипа. Они не означают, что Kubernetes, Ollama или CPU уже признаны лучшим решением.

Обзор документации подготовлен 27 сентября 2026 года. Ниже отдельно указаны возможности инструментов, предварительные рекомендации для проекта и проверки, которые ещё предстоит провести. Сравнительные эксперименты не выполнены. Ранее подтверждённый запуск одной модели на CPU доказывает только возможность такого запуска.

### 14.1. Что именно исследуется

Основной вопрос: **насколько эффективно выбранная платформа автоматически меняет число копий AI inference при изменении нагрузки, сохраняя приемлемую задержку?** Inference — получение результата от уже обученной модели. Сначала сравниваются платформы и выбирается кандидат; затем его поведение проверяется экспериментом.

Для проекта есть несколько возможных задач:

| Вариант | Что позволяет исследовать | Ограничение и предварительное решение |
|---|---|---|
| Генерация текста небольшой языковой моделью | Очереди запросов, время загрузки модели, изменение задержки при длинных ответах | Основной кандидат. Длину входа и выхода нужно контролировать. |
| Embeddings — преобразование текста в числовое представление | Масштабирование более коротких запросов, обработку групп текстов | Полноценная альтернатива, если генерация окажется слишком медленной для достаточного числа измерений. |
| Классификация текста | Более простой и короткий цикл запроса | Позволяет исследовать платформу, но выводы будут относиться к классификации, а не генерации. |
| Искусственная CPU-нагрузка без модели | Проверку механизма масштабирования до подключения inference | Полезна для диагностики; не заменяет основной AI-эксперимент. |
| Обучение модели или агент с несколькими внешними вызовами | Другую исследовательскую задачу | Обучение требует другой организации работ; агент добавляет внешние задержки. В текущий эксперимент не включать без пересмотра вопроса. |

Не требуется обучать собственную модель, чтобы исследовать инфраструктуру. Качество её ответов и качество масштабирования — разные измеряемые свойства. Если качество текста становится требованием продукта, потребуется отдельный набор заданий с ожидаемыми результатами.

### 14.2. Нужен ли вообще Kubernetes

**Оркестратор** — система, которая размещает приложения, поддерживает нужное число копий и восстанавливает их после остановки. Наличие оркестратора само по себе не гарантирует автоматического изменения числа копий по нагрузке.

| Вариант | Почему его стоит рассмотреть | Что усложняется | Как проверить пригодность |
|---|---|---|---|
| Kubernetes + HPA | Есть механизм изменения числа pod по метрикам; подходят CPU и дополнительные метрики | Нужно разобраться с ресурсами, сетью, готовностью приложений и сбором метрик | Запустить тот же образ, проверить восстановление копии и увеличение/уменьшение их числа при нагрузке. |
| Nomad + Nomad Autoscaler | Альтернатива для запуска контейнеров с отдельным компонентом автоматического масштабирования | Автомасштабирование требует своей настройки и источника метрик; меньшая сложность именно нашего стенда пока не доказана | Проверить тот же сценарий с одинаковыми лимитами ресурсов, отдельно записать время настройки и необходимые компоненты. |
| Docker Swarm | Позволяет управлять сервисами и числом их копий средствами Docker | Документированная команда изменения числа копий не является политикой масштабирования по метрикам; для неё потребуется дополнительное решение | Установить, какой контроллер будет принимать решения и можно ли воспроизводимо поддерживать его в рамках семестра. |
| Docker Compose | Простой запуск нескольких контейнеров; удобно получить результат с фиксированным числом копий | `--scale` задаёт количество вручную. Автоматический цикл наблюдения и изменения числа копий придётся добавлять | Использовать как исходный вариант без автомасштабирования. Для нескольких копий предусмотреть общий адрес и распределение запросов. |
| Собственный процесс или скрипт без оркестратора | Минимум инфраструктуры для одного сервера модели | Восстановление процессов, распределение запросов и масштабирование становятся собственным кодом | Оценить, не превращается ли исследование платформ в разработку платформы. |

Предварительный короткий список: **Kubernetes и Nomad для сравнения платформ; Compose как простой вариант с постоянной мощностью**. Swarm имеет смысл оставить в обзоре и переходить к его прототипу, если найден подходящий механизм автоматического масштабирования. Это предложение по объёму исследования, а не объявление победителя.

Отдельные альтернативы находятся на другом уровне. **Ray Serve** управляет обслуживанием моделей и может менять число обработчиков по числу незавершённых запросов; он может работать поверх Kubernetes, поэтому эти технологии не всегда заменяют друг друга. **Cloud Run** предоставляет управляемый облачный запуск с автомасштабированием: часть инфраструктурных решений принимает провайдер. Его стоит сравнить, если допустимы облако, расходы и меньший контроль над средой. У Cloud Run существуют и GPU-варианты, но доступность и условия нужно проверять отдельно.

Источники: [Kubernetes HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/), [Nomad Autoscaler](https://developer.hashicorp.com/nomad/tools/autoscaling), [масштабирование Swarm](https://docs.docker.com/engine/swarm/swarm-tutorial/scale-service/), [Compose up и scale](https://docs.docker.com/reference/cli/docker/compose/up/), [Ray Serve](https://docs.ray.io/en/latest/serve/autoscaling-guide.html), [Cloud Run autoscaling](https://docs.cloud.google.com/run/docs/about-instance-autoscaling), [GPU в Cloud Run](https://docs.cloud.google.com/run/docs/configuring/services/gpu).

### 14.3. Где выполнять эксперимент

| Среда | Преимущество для исследования | Ограничение | Предварительное решение |
|---|---|---|---|
| Локальный CPU | Можно повторять эксперименты без почасовой аренды и запускать несколько небольших копий | Все копии конкурируют за один процессор; фоновые задачи Windows влияют на результат | Начать пилот — короткую пробную серию — здесь. Это не доказательство пригодности для большого GPU-сервиса. |
| Локальная RTX 5070 | Позволяет исследовать GPU-inference | Одна видеокарта не превращается в несколько независимых GPU при добавлении pod. Нужно проверить поддержку оборудования и способ совместного доступа | Отдельный этап после CPU. Не смешивать его результаты с основной CPU-серией. |
| Облачная виртуальная машина или несколько машин | Можно отделить генератор нагрузки и проверить разные физические ресурсы | Стоимость, сетевые задержки, квоты и подготовка среды | Только при необходимости проверить вывод, недоступный локально; до запуска определить бюджет и условия остановки. |
| Kaggle Notebook | Может подойти для отдельных проб модели на доступном ускорителе | Сессии, квоты и управление средой отличаются от постоянного стенда | Дополнительная среда для модели, пока возможность полного воспроизводимого стенда не проверена. |

Упомянутые ранее **100 часов Kaggle в неделю не подтверждены**. Перед включением Kaggle в план нужно проверить квоту конкретного аккаунта, длительность сессии, доступный GPU, доступ к сети и возможность нужного окружения. Публичная страница документации в этой проверке не позволила подтвердить текущие условия. Источник для дальнейшей проверки: [Kaggle Notebooks](https://www.kaggle.com/docs/notebooks).

Для любой среды записываются фактически доступные ресурсы, а не только характеристики компьютера. В локальной серии также учитывается, что генератор запросов, виртуализация и модель используют одну машину. Затраты локального ПК нельзя автоматически называть нулевыми: можно отдельно обсуждать электричество и оборудование, но без измерений это будут оценки.

### 14.4. Windows, контейнеры и локальный кластер

| Решение | Альтернативы и различия | Что выбрать предварительно и как проверить |
|---|---|---|
| Среда контейнеров | Docker Desktop + WSL 2; Podman с Linux-машиной; Docker Engine на отдельной Linux-системе или виртуальной машине | Сохранить уже работающий Docker Desktop для пилота. Проверить потребление памяти без нагрузки, доступные CPU и воспроизводимость перезапуска. Podman на Windows тоже использует виртуализированную Linux-среду. |
| Локальный Kubernetes | Minikube; kind; k3d; встроенный Kubernetes Docker Desktop | Minikube уже установлен и описан в инструкции. kind запускает ноды в контейнерах; k3d запускает K3s, облегчённый вариант Kubernetes. Сравнить настройку, доступ к сервису, загрузку локального образа и работу метрик. |
| Число нод | Одна виртуальная нода; несколько нод на том же ПК; несколько отдельных машин | Одной ноды достаточно для первого исследования числа pod. Несколько виртуальных нод полезны для проверки размещения, но не добавляют физических ресурсов и не доказывают устойчивость к отказу компьютера. |

Minikube, kind и k3d — способы организовать Kubernetes, **не альтернативы самой платформе Kubernetes**. Сравнение «Kubernetes против Minikube» было бы некорректным. Переход на другую среду следует оценивать по ожидаемой пользе, а не только по тому, что она существует.

Источники: [Docker и WSL](https://docs.docker.com/desktop/features/wsl/), [Podman machine](https://docs.podman.io/en/latest/markdown/podman-machine.1.html), [Minikube](https://minikube.sigs.k8s.io/docs/start/), [kind](https://kind.sigs.k8s.io/), [k3d](https://k3d.io/stable/).

### 14.5. Чем запускать модель

**Сервер inference** принимает запросы, запускает вычисления модели и возвращает ответ. Он не обязан быть написан в этом проекте.

| Вариант | Причина включить в сравнение | Цена выбора и проверка |
|---|---|---|
| Ollama | Готовый HTTP-сервер и удобное управление моделями; одиночный CPU-запуск уже проверен | Удобство не доказывает лучшую производительность. Измерить задержку, память, запуск новой копии и доступность необходимых метрик. |
| llama.cpp server | CPU/GPU-выполнение и управление моделями в формате GGUF — формате хранения весов и параметров модели | Проверить совместимость модели, параметры сервера и эквивалентность настроек Ollama. |
| vLLM | Возможности обслуживания одновременно поступающих запросов, включая их совместную обработку | Проверить поддержку выбранного оборудования и модели, память и сложность установки. vLLM нельзя описывать как исключительно GPU-инструмент: у него есть разные аппаратные реализации. |
| Transformers + собственный API, например FastAPI | Больше контроля над обработкой входа и поведением модели | Появляется собственный серверный код: очередь, ограничения параллелизма, ошибки и метрики. Обосновать, зачем это нужно готовому прототипу. |

Для CPU-пилота разумно сравнить Ollama и llama.cpp. vLLM добавить при переходе к подходящему GPU-эксперименту либо при конкретном требовании к обслуживанию запросов. Один и тот же текст запроса не гарантирует равные условия: должны совпадать веса, представление чисел, шаблон запроса, ограничения длины, потоки CPU и прогрев. Если идентичность невозможна, различие явно записывается.

Источники: [Ollama FAQ](https://docs.ollama.com/faq), [llama.cpp](https://github.com/ggml-org/llama.cpp), [vLLM](https://docs.vllm.ai/en/latest/), [установка vLLM для GPU](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/), [Transformers pipelines](https://huggingface.co/docs/transformers/main/en/pipeline_tutorial).

### 14.6. Модель и параметры вычисления

Текущий кандидат `qwen2.5:0.5b` выбран из-за небольшого размера, позволяющего пробовать несколько CPU-копий. Альтернатива той же семьи — `qwen2.5:1.5b`: она меняет требования к ресурсам и может изменить качество ответов. Предпочтение по качеству нельзя установить только по числу параметров. Альтернативы по типу задачи рассмотрены в 14.1.

**Квантизация** — хранение чисел модели с меньшей точностью для уменьшения размера и требований к памяти. В каталоге вариант 0.5b указан с Q4_K_M. Сравнение такого варианта с моделью большей точности одновременно меняет инфраструктуру и вычисления: нельзя приписывать всю разницу серверу или оркестратору.

| Параметр | Текущий кандидат | Альтернативы и проверка |
|---|---|---|
| Одновременная обработка | `OLLAMA_NUM_PARALLEL=1` | Сравнить одну копию с большим параллелизмом и несколько копий при сопоставимом общем бюджете ресурсов. |
| Потоки CPU | `num_thread=2` | Проверить меньшее и большее число на пилоте; больше потоков не гарантирует меньшую задержку. |
| Длина | Контекст 1024, максимум 64 выходных токена — частей текста, которыми оперирует модель | Позже добавить короткие и длинные входы. Сохранять реальную длину ответа: максимум 64 не означает, что каждый ответ содержит ровно 64 токена. |
| Случайность ответа | Температура 0, фиксированный seed — начальное значение генератора случайности | Помогает контролировать условия, но не гарантирует побитово одинаковый результат на разных реализациях и оборудовании. |
| Прогрев | Начальные копии заранее получают запрос | Отдельно измерить холодный запуск, когда модель ещё не готова к вычислению. Новые копии при масштабировании тоже проходят загрузку. |

До основной серии фиксируются точная версия модели или идентификатор её содержимого, настройки и версия сервера. Сначала меняется один фактор: например, размер модели при неизменном сервере. Полный перебор всех комбинаций для этого семестра не требуется.

Источники: [Qwen 0.5b](https://ollama.com/library/qwen2.5:0.5b), [Qwen 1.5b](https://ollama.com/library/qwen2.5:1.5b), [параметры Ollama](https://docs.ollama.com/modelfile).

### 14.7. API и путь запроса

**API** — согласованный способ отправить запрос программе. Текущий вариант — HTTP-запрос прямо в Ollama, без собственного промежуточного сервера.

| Выбор | Альтернативы | Критерий решения |
|---|---|---|
| Полный ответ или поток | `stream=false` возвращает результат целиком; потоковая выдача передаёт его по частям | Для первого опыта измерять время полного ответа. Для интерактивного продукта добавить время до первого токена и темп последующей выдачи. Сравнивать эти показатели как разные величины. |
| Прямой вызов или собственный API | Ollama напрямую; Python/FastAPI с проверкой запросов; отдельный сервис с очередью заданий | Добавлять собственный API при конкретной обязанности: например, авторизация или единый формат ответа разных серверов. Иначе он добавляет код и задержку без необходимой функции. |
| Синхронная обработка или очередь | Клиент ждёт ответ; клиент получает номер задания и проверяет результат позже | Очередь подходит для фоновых задач. Измерять время от отправки до готового результата, включая ожидание, а не только быстрое подтверждение приёма задания. |

gRPC — ещё один протокол взаимодействия программ — имеет смысл при требованиях интеграции, а не как обязательная замена HTTP. Пока такие требования не установлены. Источник о текущем контракте: [Ollama Generate API](https://docs.ollama.com/api/generate).

### 14.8. Где хранить модель и как доставлять приложение

| Вариант | Преимущество | Недостаток и проверка |
|---|---|---|
| Модель внутри образа контейнера | При старте приложения не требуется скачивание весов из интернета | Большой образ дольше передавать. Измерять отдельно доставку образа и запуск pod с уже доступным образом. Текущий кандидат для локальной серии. |
| Отдельное постоянное хранилище | Веса сохраняются отдельно от контейнера | Нужно настроить доступ и режим использования несколькими копиями; сетевое хранилище может стать ограничением. |
| Загрузка при запуске | Небольшой исходный образ, модель можно выбирать отдельно | Старт зависит от сети, доступности источника и кеша. Эти задержки нельзя молча исключать, если так устроен выбранный продукт. |

Локальная загрузка образа в Minikube удобна для одной машины. Для нескольких машин альтернатива — **registry**, сервер хранения образов, откуда их скачивают ноды. Его настройка для текущего пилота не обязательна.

Тег `latest` может измениться. Для повторяемой серии фиксируется **digest** — идентификатор конкретного содержимого образа — и отдельно идентификатор модели. Установленная версия инструмента не является доказательством, что именно она использована внутри контейнера.

Источники: [образы Kubernetes](https://kubernetes.io/docs/concepts/containers/images/), [постоянное хранилище](https://kubernetes.io/docs/concepts/storage/persistent-volumes/).

### 14.9. Что именно масштабировать

| Способ | Что меняется | Применимость к проекту |
|---|---|---|
| Горизонтальное масштабирование | Число копий приложения | Основной кандидат: 1–3 pod. У каждой копии свои расходы памяти и запуска. |
| Вертикальное масштабирование | CPU и память одной копии | Альтернатива, которую важно проверить вручную: возможно, одна более мощная копия решает задачу проще. Нужно согласованно настроить число потоков и параллельных запросов. |
| Масштабирование нод | Число машин, доступных кластеру | Другой уровень. Добавление pod на локальном ПК не исследует автоматическое добавление физических машин. |
| Совместная обработка запросов | Число запросов, вычисляемых сервером вместе | Может улучшить использование оборудования без добавления копий; требует отдельного сравнения задержки и пропускной способности. |

Серия «одна копия по 2 CPU против трёх по 2 CPU» показывает эффект доступа к большей суммарной мощности. Она сама по себе не доказывает преимущество нескольких копий над одной при одинаковом бюджете. Для такого вывода нужен дополнительный опыт: одна копия с суммарным бюджетом до 6 CPU против трёх по 2 CPU, с подходящими настройками обработки и учётом памяти.

### 14.10. По какому сигналу принимать решение

**Политика масштабирования** — правило, которое по измерению выбирает нужное число копий.

| Политика | Что показывает сигнал | Ограничение и проверка |
|---|---|---|
| HPA по CPU | Насколько заняты выделенные CPU | Простой кандидат для CPU-модели. Проверить, растёт ли CPU до того, как задержка становится неприемлемой. Для GPU-модели CPU может плохо отражать занятость основного вычислителя. |
| HPA по дополнительной метрике | Например, число активных запросов или очередь | Нужны корректная метрика и способ передать её в Kubernetes. Проверить связь сигнала с задержкой и способность новых копий снять перегрузку. |
| KEDA | Сигнал от источника событий или метрик, например очереди | Это дополнение к Kubernetes, взаимодействующее с его механизмами масштабирования. Имеет смысл при подходящем источнике нагрузки. |
| Ray Serve autoscaling | Число незавершённых запросов внутри сервиса моделей | Подходит при выборе Ray Serve; нужно учитывать управление его обработчиками и ресурсами среды. |
| Собственное правило или прогноз нагрузки | Любые доступные измерения либо прогноз | Потребуется реализовать и проверить управляющий код. Оставить для конкретной исследовательской гипотезы, которую не покрывают готовые механизмы. |
| Постоянное число копий | Никакого автоматического решения | Обязательные исходные режимы сравнения: фиксированные 1 и 3 копии. |

В текущем варианте HPA цель 60% считается от `requests.cpu`, поэтому при запросе 2 CPU это примерно 1,2 CPU на копию. Это **параметр для проверки**, а не оптимальное значение. На пилоте можно сравнить несколько порогов, сохраняя остальные условия. Затем выбранный порог фиксируется до основной серии.

Аналогично обосновываются диапазон 1–3, окно стабилизации уменьшения 300 секунд и ограничения скорости изменения числа копий. Более быстрое уменьшение может снизить занятые ресурсы, но привести к частым повторным запускам; длительное ожидание удерживает запас. Не запускать независимые контроллеры, одновременно задающие число копий одного Deployment.

Источники: [HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/), [KEDA](https://keda.sh/docs/2.21/), [Ray Serve autoscaling](https://docs.ray.io/en/latest/serve/autoscaling-guide.html).

### 14.11. Ресурсы, готовность и остановка копий

Текущие 2 CPU и 1 ГиБ запрашиваемой памяти, лимиты 2 CPU и 2 ГиБ — начальные настройки. **Requests** влияют на размещение приложения, **limits** ограничивают потребление. Альтернативы: иной размер копии, иной запас памяти и другая конфигурация CPU-лимита. На пилоте проверяются фактическая память, завершения из-за нехватки памяти, задержки и ограничение CPU. Снятие лимитов без учёта общей ёмкости машины не является доказанным улучшением.

Готовность HTTP-сервера и готовность модели отвечать — разные события. Текущая проверка `/api/tags` не доказывает, что модель уже загружена для inference. Альтернатива — сигнал готовности после явной загрузки модели. **Startup probe** проверяет успешное начало работы, **readiness probe** — можно ли направлять трафик, **liveness probe** — нужно ли перезапустить зависшее приложение. Не следует выполнять дорогую генерацию слишком часто в таких проверках: она сама меняет нагрузку.

Текущие ожидание перед остановкой 35 секунд и общий срок завершения 60 секунд требуют проверки на реальной длительности запросов. Альтернатива — перестать принимать новые запросы и завершить уже начатые с измеримым пределом ожидания. Отдельно проверить ошибки при уменьшении числа копий. Повторные попытки клиента, если они добавлены, нужно учитывать вместе с исходными ошибками и общим временем ожидания.

Для обновления приложения текущий вариант допускает недоступность единственной копии. Если требуется непрерывная доступность, нужно сравнить обновление с временной дополнительной копией, которое требует свободных ресурсов. Это отдельный выбор от автомасштабирования под нагрузкой.

Источники: [requests и limits](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/), [проверки состояния](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/), [обновления Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).

### 14.12. Сеть и распределение запросов

Текущий путь — k6 на Windows, туннель Minikube и Kubernetes Service типа NodePort. Альтернативы: генератор внутри кластера; отдельная машина генератора; **Ingress или gateway**, входной компонент с правилами маршрутизации; сервис типа LoadBalancer с подходящей реализацией.

Для пилота оставить описанный путь и проверить распределение запросов между копиями. Для вывода о предельной производительности выяснить, не ограничивает ли результат туннель или сам генератор. Перенос генератора внутрь кластера убирает часть внешнего пути, но добавляет потребление ресурсов кластера; ему тоже нужен учитываемый бюджет.

`kubectl port-forward deployment/...` выбирает pod и не заменяет общий путь распределения нагрузки между всеми копиями. В текущем сценарии k6 отключено повторное использование соединений: это помогает проверить распределение новых подключений, но добавляет расходы установления соединения. Альтернатива — сохранять соединения, как это делает целевой клиент, и проверить получившееся распределение. По одному графику суммарного CPU нельзя доказать равномерность обработки запросов.

Источники: [доступ к сервисам Minikube](https://minikube.sigs.k8s.io/docs/handbook/accessing/), [port-forward](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/).

### 14.13. Чем собирать метрики

**Метрика** — числовое измерение, например загрузка CPU или задержка. Для управления копиями и для точного анализа ресурсов могут требоваться разные источники.

| Вариант | Назначение | Решение для проекта |
|---|---|---|
| metrics-server и `kubectl top` | Данные ресурсов для автомасштабирования и быстрой проверки | Оставить для HPA. Сохранённые значения использовать как наблюдение его входного сигнала, а не как точный учёт потребления. |
| Прямые метрики kubelet | Накопленное процессорное время и working set памяти контейнера/ноды | Выбраны и проверены для локального наблюдателя; сохраняются исходные значения и метки времени. |
| Prometheus | Хранение временных рядов — значений метрик с отметками времени — и запросы к ним | Альтернатива файловому сбору, если потребуются долговременное хранение и запросы. |
| Grafana | Визуализация данных из источников вроде Prometheus | Удобна для наблюдения, но не заменяет сбор и хранение исходных данных. Не обязательна для первых графиков. |
| OpenTelemetry | Сбор метрик, логов и трасс — последовательностей действий внутри запроса | Полезна при нескольких сервисах и поиске источника задержки. Для одного Ollama-сервера может быть избыточна; сама по себе не заменяет хранилище измерений. |

Разработчики metrics-server прямо предупреждают, что он предназначен для автомасштабирования и не рекомендуется как источник точных метрик мониторинга. Поэтому поле `resources` наблюдателя используется для объяснения сигнала HPA. Для анализа ресурсов отдельно сохраняются прямые данные `/metrics/resource` kubelet в полях `kubelet` и `resource_usage`. Их единицы, область измерения и ограничения описаны в `md/OBSERVATION.md`; выбранный источник не измеряет потребление энергии или денежную экономию.

Наблюдатель из шага 11 написан на Python и вызывает `kubectl`; PowerShell только запускает его. Альтернативы — официальный Python-клиент Kubernetes или запросы к Prometheus. У текущего подхода меньше кода для API, но каждый опрос запускает внешние команды. Реализованный сборщик учитывает длительность чтений в целевом интервале 5 секунд, но долгий опрос может превысить его. Для анализа использовать фактические отметки времени, сохранять пропуски и не превращать их в нули.

Источники: [назначение и ограничения metrics-server](https://github.com/kubernetes-sigs/metrics-server), [Prometheus](https://prometheus.io/docs/introduction/overview/), [OpenTelemetry](https://opentelemetry.io/docs/what-is-opentelemetry/), [Python-клиент Kubernetes](https://github.com/kubernetes-client/python).

### 14.14. Чем создавать нагрузку

| Вариант | Причина рассмотреть | Что проверить |
|---|---|---|
| k6 | Готовые сценарии нагрузки, показатели ошибок и задержек; уже установлен | Способен ли генератор поддерживать заданный поток, хватает ли рабочих исполнителей, корректно ли учитываются ответы модели. |
| Locust | Сценарии на Python, удобно описывать действия пользователей | Как задаётся частота запросов и зависит ли она от времени ответа. Одинаковое число пользователей не означает одинаковую нагрузку. |
| JMeter | Готовые планы тестирования и широкий набор протоколов | Объём настройки и воспроизводимость запуска без ручной правки интерфейса. |
| Собственный Python-генератор | Полный контроль над запросами и форматом данных | Придётся корректно реализовать планирование, параллельность, таймауты и учёт ошибок. Нужен только при конкретной нехватке готовых средств. |

Отдельное решение — **модель поступления запросов**. В открытой модели новые запросы запланированы независимо от завершения предыдущих. В закрытой модели фиксированное число пользователей обычно ждёт ответа перед следующим запросом; при замедлении сервера создаваемая частота может уменьшаться. Для исследования реакции на внешний всплеск текущий кандидат — открытая модель k6.

Фиксировать нужно запланированные, реально начатые, успешно завершённые запросы и ошибки. **Dropped iterations** в k6 — запланированные итерации, которые не удалось начать. Это не HTTP-ошибка сервера, но и не успешно обслуженная нагрузка; рост этого показателя требует выяснить причину и пересмотреть достоверность прогона.

Источники: [открытая и закрытая модели k6](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/), [dropped iterations](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/dropped-iterations/), [Locust](https://docs.locust.io/en/stable/what-is-locust.html), [JMeter](https://jmeter.apache.org/).

### 14.15. Какие сценарии и показатели сравнивать

Текущие профили — постоянная нагрузка и резкий всплеск. Альтернативы: плавный рост, несколько повторных всплесков, длительный высокий уровень и воспроизведение обезличенной записи реального трафика. Сначала достаточно первых двух; дополнительные выбираются по исследовательскому вопросу.

Одинаковый короткий запрос удобен для контроля условий, но не представляет все пользовательские задачи. Альтернатива — зафиксированный набор коротких и длинных текстов с воспроизводимым порядком. Повторяющиеся входы могут взаимодействовать с кешированием — повторным использованием уже вычисленного результата или его частей. Поэтому настройки и характер повторов надо записывать, а результаты одного текста не обобщать на любой трафик.

Основные показатели: задержка успешных ответов, доля ошибок, фактически обслуженная частота, время появления работоспособной дополнительной копии, время нарушения выбранного порога, поведение при уменьшении числа копий и потребление ресурсов. **p95** — значение, не превышенное примерно 95% наблюдений; это не максимум. При малом числе запросов p95 в 30-секундном окне нестабилен: сохранять число наблюдений и при необходимости увеличить окно до основной серии.

Порог допустимой задержки выбирается после пилота с объяснением требований задачи, затем фиксируется. Нельзя менять его после получения неудобных результатов. Три повтора каждого режима — начальный план, а не гарантия статистической надёжности. Если разброс мешает выводу, потребуются дополнительные повторы или вывод о недостаточности данных.

Для честного сравнения сохраняются одинаковые запросы и ресурсы, чередуется порядок режимов, исключаются посторонние тяжёлые задачи, между прогонами завершаются оставшиеся запросы. Основную серию по политике масштабирования выполнять на одной выбранной платформе. Сравнение платформ проводить отдельной серией, чтобы изменение сервера или модели не выдавало себя за эффект оркестратора.

### 14.16. Хранение данных и анализ

| Решение | Альтернативы | Предварительный выбор |
|---|---|---|
| Исходные результаты | JSONL — отдельная JSON-запись в каждой строке; CSV; Parquet — компактный табличный формат; база SQLite | JSONL оставить для сырых событий и изменений состояния, CSV — для итоговых таблиц. Parquet или SQLite нужны при объёме или запросах, которые неудобно обслуживать файлами. |
| Обработка результатов | Python с pandas и графиками; Excel; R; Jupyter Notebook — документ с кодом и его выводом | Excel допустим для первой ручной проверки. Итоговое преобразование данных лучше сохранять в повторяемом скрипте; ноутбук удобен для исследования, если порядок выполнения воспроизводим. |
| Интерфейс продукта | Только команды и отчёт; Grafana; собственный веб-интерфейс | Для исследовательского прототипа достаточно команд, результатов и графиков. Собственный интерфейс добавлять только при отдельном требовании. |

Для каждого прогона хранить идентификатор, время UTC, версии, модель, конфигурацию ресурсов, параметры нагрузки и политики, исходные измерения, ошибки и коды завершения. Значение, которого нет, остаётся отсутствующим. Сводная таблица не должна заменять исходные результаты.

Измеренный CPU, запрошенный CPU и лимит CPU — разные величины. Число копий или время их работы можно использовать как показатель удерживаемой мощности, но нельзя автоматически называть денежной экономией. Для оценки стоимости нужны явно указанные тарифы или модель затрат; для энергии — отдельное измерение либо честно обозначенная оценка. Источник по форматам данных: [pandas IO](https://pandas.pydata.org/docs/user_guide/io.html).

### 14.17. Конфигурация, язык и документация

| Решение | Альтернативы и критерий | Кандидат для первого прототипа |
|---|---|---|
| Описание развёртывания | Обычные YAML-файлы; Kustomize для вариантов конфигурации; Helm для пакетов с шаблонами | YAML проще просмотреть для одного стенда. Kustomize рассмотреть при нескольких окружениях; Helm — при необходимости повторно распространять настраиваемый набор компонентов. |
| Подготовка инфраструктуры | Ручные документированные команды; скрипт; инструмент вроде Terraform для управления инфраструктурными ресурсами | Сначала воспроизводимые команды. Автоматизацию добавлять для реально повторяющегося шага. Terraform не заменяет сервер модели или политику масштабирования. |
| Язык вспомогательного кода | Python; JavaScript; Go; PowerShell | Python соответствует существующим заготовкам и анализу данных, JavaScript уже используется k6, PowerShell — запуску на Windows. Переписывание всего на один язык не является самоцелью. |
| Структура проекта | Один скрипт; отдельные `app`, `bench`, `deploy`, `research`, `results`, `report`; несколько сервисов и репозиториев | Сохранить существующие папки по обязанностям. `app` может оставаться заготовкой, пока Ollama сам предоставляет API. |
| Редактор и история | PyCharm или VS Code; локальный Git с подходящим удалённым хранилищем | Выбирать по удобству и требованиям курса. Это не фактор производительности inference и не требует нагрузочного эксперимента. Секреты и большие веса модели не добавлять в Git. |
| Архитектурные схемы | C4 C1/C2; UML; диаграмма последовательности; FigJam или текстовое описание схемы | C1 показывает систему и окружение, C2 — основные исполняемые части и связи. Сценарий масштабирования при необходимости объясняется отдельно последовательностью событий. C4-container означает исполняемую часть системы, а не обязательно Docker-контейнер. |
| Доступ к стенду | Только локальный доступ; доступ из локальной сети; публичный сервис | Для пилота локальный доступ. Публичный вариант требует отдельного решения об аутентификации, шифровании и ограничении запросов; исследование не требует автоматически открывать сервис в интернет. |

Для небольших решений достаточно короткого объяснения и ссылки на требования. Не нужно искусственно проводить эксперимент «PyCharm против VS Code», если вопрос исследования касается масштабирования.

Источники по развёртыванию: [Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/), [Helm charts](https://helm.sh/docs/topics/charts/).

### 14.18. Как провести исследование по шагам

**Шаг A — зафиксировать требования.** Описать тип задачи, допустимые среды, доступные ресурсы, бюджет и срок. Разделить обязательное, например воспроизводимый запуск и сохранение результатов, и желательное, например удобный интерфейс. Ограничения записать до сравнения.

**Шаг B — составить таблицу кандидатов по документации.** Для каждого решения указать альтернативы из этого раздела, официальный источник, дату проверки и применимость к требованиям. Отметка «не подходит» должна иметь конкретную причину. Если совместимость ещё не проверена, записать «неизвестно», а не ноль баллов.

**Шаг C — проверить самые рискованные предположения.** У короткого списка платформ проверить запуск одинакового контейнера, общий адрес, восстановление после остановки и возможность автоматического изменения числа копий. У короткого списка серверов модели — одиночный запрос, ограничение ресурсов и старт новой копии. Записывать время настройки и необходимые ручные исправления. Прежний опыт с Kubernetes влияет на это время и должен быть указан.

**Шаг D — принять предварительные решения.** Выбрать платформу и сервер по требованиям и результатам проб. Только после этого утверждать основной маршрут. Если выигрывает другая платформа, шаги 2 и 5–12 потребуют адаптации; существующие команды Kubernetes не становятся обязательными из-за того, что они уже написаны.

**Шаг E — подготовить измерения и пилот.** Проверить источники метрик и единицы, подобрать нагрузку и порог задержки, подтвердить распределение запросов и готовность новых копий. Параметры подбирать на пилоте, а не незаметно менять между основными прогонами.

**Шаг F — выполнить зафиксированную серию.** Сравнить постоянные 1 и 3 копии с автоматическим изменением 1–3. Провести оба выбранных профиля и минимум три повтора, сохранив исходные результаты. Дополнительное сравнение с одной более мощной копией отвечает на отдельный вопрос о равном бюджете ресурсов.

**Шаг G — оформить вывод и границы.** Показать, какие требования выполнены, где результаты неоднозначны и что не проверялось. Допустимый результат исследования — отсутствие преимущества автомасштабирования при данной нагрузке или вывод, что простого решения достаточно. Не требуется заранее доказывать пользу Kubernetes.

Для выбора платформ можно использовать такую таблицу; сейчас она намеренно не содержит выдуманных оценок:

| Критерий | Способ проверки | Kubernetes | Nomad | Compose |
|---|---|---|---|---|
| Поддержка выбранной среды и образа | Успешный запуск в заданном бюджете ресурсов | Не измерено | Не измерено | Не измерено |
| Автоматическое увеличение и уменьшение | Управляемый всплеск, наблюдение решений | Проверить HPA | Проверить Autoscaler | Нужен дополнительный контроллер |
| Задержка и ошибки | Одинаковая модель, конфигурация и нагрузка | Не измерено | Не измерено | Не измерено |
| Расход ресурсов среды | Измерение без нагрузки и во время прогона | Не измерено | Не измерено | Не измерено |
| Сложность и повторяемость | Время подготовки, число ручных шагов, повторный запуск | Не измерено | Не измерено | Не измерено |
| Восстановление копии | Контролируемая остановка одной копии | Не измерено | Не измерено | Проверить выбранную настройку |

Сначала проверяются обязательные ограничения. Затем допустимо назначить критериям веса — относительную важность — до выставления оценок. Если небольшая смена весов меняет победителя, вывод зависит от приоритетов, и это нужно явно написать. Не сводить измеренные секунды, субъективное удобство и непроверенные предположения в один «объективный» балл без объяснения.

### 14.19. Как записывать принятое решение

Для существенных выборов можно вести `md/DECISIONS.md`. **ADR** — короткая запись об архитектурном решении: какие варианты были и на каком основании выбран один. Файл создавать по мере появления решений; этот раздел пока содержит обзор и план проверок.

```text
Решение: выбор платформы запуска и масштабирования
Статус: кандидат / принято после проверки / пересмотрено
Дата и автор:
Требование или вопрос:
Рассмотренные варианты:
Обязательные ограничения и критерии:
Что известно из документации: ссылки и дата
Что проверено локально: команды, конфигурация, файлы результатов
Что пока является предположением:
Выбранный вариант и причина:
Недостатки выбранного варианта:
Почему остальные варианты не выбраны:
При каком изменении условий решение нужно пересмотреть:
```

Итог исследования должен позволять проследить цепочку **требование → альтернативы → свидетельства → решение → экспериментальный результат**. По состоянию на дату этого обзора стек Docker Desktop / Minikube / Ollama / Qwen 0.5b / k6 остаётся кандидатом для первого CPU-прототипа. Преимущество Kubernetes над другими платформами и преимущество автоматического масштабирования над постоянным числом копий ещё предстоит установить.
