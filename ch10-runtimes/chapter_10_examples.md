# Chapter 10 — OpenServerless Runtimes
## Code Listings

> Source: Apache OpenServerless codebase — `runtimes/` and related paths.
> These are the real listings used in Chapter 10 of *Apache OpenServerless: The Complete Guide* (Apress).

---

### Listing 10-1. Common builder image — compiles the ActionLoop Proxy binary

Source: `runtimes/runtime/common/common1.17.1/Dockerfile`

```dockerfile
FROM golang:1.21
ENV HOME=/tmp
USER nobody
RUN CGO_ENABLED=0 go install \
    github.com/apache/openserverless-runtimes@common1.17.1
RUN mv /go/bin/openserverless-runtimes /go/bin/proxy
ENTRYPOINT [ "/go/bin/proxy" ]
```

---

### Listing 10-2. Node.js v21 runtime Dockerfile — multi-stage build pattern

Source: `runtimes/runtime/nodejs/v21/Dockerfile`

```dockerfile
ARG COMMON=missing:missing
FROM ${COMMON} AS builder

FROM node:21.6.2-bookworm
ENV OW_EXECUTION_ENV=apacheopenserverless/nodejs-21.6.2
COPY --from=builder /go/bin/proxy /bin/proxy

ENV OW_COMPILER=/bin/compile
ENV OW_LOG_INIT_ERROR=1
ENV OW_WAIT_FOR_ACK=1

RUN apt-get update && apt-get install -y \
    imagemagick graphicsmagick unzip \
    && rm -rf /var/lib/apt/lists/*

COPY package.json /
RUN npm install && npm cache clean --force

RUN mkdir -p /app/action && chmod -R 0775 /app && chown -R nobody:root /app
ENV HOME=/app
WORKDIR /app
COPY bin/compile /bin/compile
COPY lib/launcher.js /lib/launcher.js

EXPOSE 8080
USER nobody
ENTRYPOINT ["/bin/proxy"]
```

---

### Listing 10-3. The `ActionProxy` struct definition

Source: `runtimes/openwhisk/actionProxy.go`

```go
type ActionProxy struct {
    proxyMode        ProxyMode         // None, Client, or Server
    clientProxyData  *ClientProxyData  // set when mode == Client
    serverProxyData  *ServerProxyData  // set when mode == Server
    initialized      bool
    baseDir          string            // ./action
    compiler         string            // value of OW_COMPILER
    currentDir       int               // highest numbered action slot
    theExecutor      *Executor         // the running action process
    outFile          *os.File
    errFile          *os.File
    env              map[string]string
}
```

---

### Listing 10-4. Proxy mode selection in `proxy.go` `main()`

Source: `runtimes/proxy.go`

```go
proxyMode := openwhisk.ProxyModeNone

useProxyClient := os.Getenv("OW_ACTIVATE_PROXY_CLIENT")
if useProxyClient == "1" {
    openwhisk.Debug("Using runtime as a forward proxy.")
    proxyMode = openwhisk.ProxyModeClient
}

useProxyServer := os.Getenv("OW_ACTIVATE_PROXY_SERVER")
if useProxyServer == "1" {
    openwhisk.Debug("Using runtime as a proxy server.")
    proxyMode = openwhisk.ProxyModeServer
}

ap := openwhisk.NewActionProxy(
    "./action",
    os.Getenv("OW_COMPILER"),
    os.Stdout, os.Stderr,
    proxyMode,
)
```

---

### Listing 10-5. `Executor.Interact()` — writes invocation payload to stdin, reads result from fd 3

Source: `runtimes/openwhisk/executor.go`

```go
func (proc *Executor) Interact(in []byte) ([]byte, error) {
    // send the JSON payload followed by a newline
    proc.input.Write(in)
    proc.input.Write([]byte("\n"))

    chout := make(chan []byte)
    go func() {
        out, err := proc.output.ReadBytes('\n')
        if err == nil {
            chout <- out
        } else {
            chout <- []byte{}
        }
    }()

    var err error
    var out []byte
    select {
    case out = <-chout:
        if len(out) == 0 {
            err = errors.New("no answer from the action")
        }
    case <-proc.exited:
        err = errors.New("command exited")
    }

    // write the output guard to both stdout and stderr
    proc.cmd.Stdout.Write([]byte(OutputGuard))
    proc.cmd.Stderr.Write([]byte(OutputGuard))
    return out, err
}
```

---

### Listing 10-6. `initBodyRequest` struct and `doInit()` in `openwhisk/initHandler.go`

Source: `runtimes/openwhisk/initHandler.go`

```go
type initBodyRequest struct {
    Code   string                 `json:"code,omitempty"`
    Binary bool                   `json:"binary,omitempty"`
    Main   string                 `json:"main,omitempty"`
    Env    map[string]interface{} `json:"env,omitempty"`
}

func (ap *ActionProxy) doInit(request initRequest, w http.ResponseWriter) error {
    // set environment from the init payload
    ap.SetEnv(request.Value.Env)

    main := request.Value.Main
    if main == "" { main = "main" }

    var buf []byte
    if request.Value.Binary {
        b, err := base64.StdEncoding.DecodeString(request.Value.Code)
        if err != nil { /* ... */ }
        buf = b
    } else {
        buf = []byte(request.Value.Code)
    }

    _, err := ap.ExtractAndCompile(&buf, main)
    if err != nil { /* write to log if OW_LOG_INIT_ERROR */ return err }

    err = ap.StartLatestAction()
    if err != nil { /* ... */ return err }
    ap.initialized = true
    return nil
}
```

---

### Listing 10-7. Waiting for the action acknowledgement in `Executor.Start()`

Source: `runtimes/openwhisk/executor.go`

```go
// wait for acknowledgement
ack := make(chan error)
go func() {
    out, err := proc.output.ReadBytes('\n')
    if err != nil { ack <- err; return }

    var ackData ActionAck
    err = json.Unmarshal(out, &ackData)
    if err != nil { ack <- err; return }

    if !ackData.Ok {
        ack <- fmt.Errorf("The action did not initialize properly.")
        return
    }
    ack <- nil
}()

select {
case err = <-ack:
    return err
case <-proc.exited:
    return fmt.Errorf("Command exited abruptly during initialization.")
}
```

---

### Listing 10-8. Python ActionLoop run loop in `lib/launcher.py`

Source: `runtimes/runtime/python/v3.12/lib/launcher.py`

```python
out = fdopen(3, "wb")

# send the ready acknowledgement
if os.getenv("__OW_WAIT_FOR_ACK", "") != "":
    out.write(json.dumps({"ok": True}).encode('utf-8'))
    out.write(b'\n')
    out.flush()

env = os.environ
while True:
    line = stdin.readline()
    if not line: break
    args = json.loads(line)
    payload = {}
    for key in args:
        if key == "value":
            payload = args["value"]
        else:
            # store metadata as __OW_<KEY> environment variables
            env["__OW_%s" % key.upper()] = args[key]
    res = {}
    try:
        res = main(payload)
    except Exception as ex:
        print(traceback.format_exc(), file=stderr)
        res = {"error": str(ex)}
    out.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
    out.write(b'\n')
    stdout.flush()
    stderr.flush()
    out.flush()
```

---

### Listing 10-9. Python v3.12 runtime Dockerfile

Source: `runtimes/runtime/python/v3.12/Dockerfile`

```dockerfile
ARG COMMON=missing:missing
FROM ${COMMON} AS builder

FROM python:3.12.2-bookworm
ENV OW_EXECUTION_ENV=apacheopenserverless/runtime-python-v3.12.2
COPY --from=builder /go/bin/proxy /bin/proxy

RUN apt-get update && apt-get install -y \
    python3-lxml python3-psycopg2 zip xpdf \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip3 install --upgrade pip six wheel virtualenv
RUN pip3 install --no-cache-dir -r requirements.txt

RUN mkdir -p /action
WORKDIR /

ADD bin/compile /bin/compile
ADD lib/launcher.py /lib/launcher.py

ENV OW_LOG_INIT_ERROR=1
ENV OW_WAIT_FOR_ACK=1
ENV OW_COMPILER=/bin/compile
ENV HOME=/tmp

WORKDIR /action
RUN chown nobody:root /action ; chmod 0775 /action
USER nobody
ENTRYPOINT ["/bin/proxy"]
```

---

### Listing 10-10. Minimal Go action function

```go
package main

import "fmt"

// Main is the entry point for the OpenServerless action.
// The --main flag determines the function name; the compile
// script generates a wrapper that calls it with a map argument.
func Main(event map[string]interface{}) map[string]interface{} {
    name, ok := event["name"].(string)
    if !ok { name = "world" }
    msg := fmt.Sprintf("Hello, %s!", name)
    return map[string]interface{}{"message": msg}
}
```

---

### Listing 10-11. PHP v8.3 Dockerfile — extension installation, Composer, proxy setup

Source: `runtimes/runtime/php/v8.3/Dockerfile`

```dockerfile
ARG COMMON=missing:missing
FROM ${COMMON} AS builder

FROM php:8.3-cli-bookworm
ADD --chmod=0755 \
    https://github.com/mlocati/docker-php-extension-installer/.../install-php-extensions \
    /usr/local/bin/

RUN apt-get -y update && apt-get install -y --no-install-recommends \
      unzip libssl3 libssl-dev libxml2 libzip4 libpq5 zip \
    && install-php-extensions \
      bcmath gd intl mysqli mongodb opcache pgsql \
      pdo_mysql pdo_pgsql redis soap zip \
    && apt-get autoremove -y && apt-get clean -y

# install Composer and pre-fetch default dependencies
RUN curl -f -L -o /tmp/installer.php https://getcomposer.org/installer \
    && php /tmp/installer.php --install-dir=/usr/bin --filename=composer
COPY composer.json /phpAction/composer
RUN cd /phpAction/composer && /usr/bin/composer install \
    --no-plugins --no-scripts --prefer-dist --no-dev -o

COPY --from=builder /go/bin/proxy /bin/proxy
ADD compile.php /bin/compile.php
ADD runner.php  /bin/runner.php
ENV OW_COMPILER=/bin/compile.php
ENV OW_EXECUTION_ENV=apacheopenserverless/action-php-v8.3
ENTRYPOINT ["/bin/proxy", "-debug"]
```

---

### Listing 10-12. `nodejs:21` entry in `runtimes.json` — full kind descriptor with `stemCells`

Source: `runtimes/runtimes.json`

```json
{
    "kind": "nodejs:21",
    "default": true,
    "image": {
        "prefix": "apache",
        "name": "openserverless-runtime-nodejs",
        "tag": "v21-cf0e986"
    },
    "deprecated": false,
    "attached": {
        "attachmentName": "codefile",
        "attachmentType": "text/plain"
    },
    "stemCells": [
        {
            "initialCount": 1,
            "memory": "256 MB",
            "reactive": {
                "minCount": 1,
                "maxCount": 4,
                "ttl": "2 minutes",
                "threshold": 1,
                "increment": 1
            }
        }
    ]
}
```

---

### Listing 10-13. `python:3` entry in `runtimes.json.tpl` — `envsubst`-style variable placeholders

Source: `runtimes/runtimes.json.tpl`

```json
{
    "kind": "python:3",
    "default": true,
    "image": {
        "prefix": "$OPS_RUNTIME_PREFIX",
        "name": "openserverless-runtime-python",
        "tag": "$OPS_RUNTIME_TAG_PYTHON_V3_12"
    },
    "deprecated": false,
    "attached": {
        "attachmentName": "codefile",
        "attachmentType": "text/plain"
    },
    "stemCells": [{
        "initialCount": 1,
        "memory": "256 MB",
        "reactive": {
            "minCount": 1, "maxCount": 4,
            "ttl": "2 minutes",
            "threshold": 1, "increment": 1
        }
    }]
}
```

---

### Listing 10-14. `runtimes.env` — generated by `task render-runtimes`

```bash
OPS_RUNTIME_PREFIX=apache
OPS_RUNTIME_TAG_GO_V1_20=v1.20-cf0e986
OPS_RUNTIME_TAG_GO_V1_21=v1.21-cf0e986
OPS_RUNTIME_TAG_GO_V1_22=v1.22-cf0e986
OPS_RUNTIME_TAG_GO_V1_22PROXY=v1.22proxy-cf0e986
OPS_RUNTIME_TAG_NODEJS_V18=v18-cf0e986
OPS_RUNTIME_TAG_NODEJS_V20=v20-cf0e986
OPS_RUNTIME_TAG_NODEJS_V21=v21-cf0e986
OPS_RUNTIME_TAG_PYTHON_V3_11=v3.11-cf0e986
OPS_RUNTIME_TAG_PYTHON_V3_12=v3.12-cf0e986
OPS_RUNTIME_TAG_PYTHON_V3_13=v3.13-cf0e986
OPS_RUNTIME_TAG_JAVA_V8=v8-cf0e986
OPS_RUNTIME_TAG_JAVA_V11=v11-cf0e986
OPS_RUNTIME_TAG_JAVA_V17=v17-cf0e986
OPS_RUNTIME_TAG_JAVA_V21=v21-cf0e986
```

---

### Listing 10-15. `generate-runtimes` task in `runtimes/Taskfile.yml`

Source: `runtimes/Taskfile.yml`

```yaml
generate-runtimes:
  silent: true
  dotenv:
    - runtimes.env
  cmds:
    - cat runtimes.json.tpl | envsubst > runtimes.json
```

---

### Listing 10-16. `go:1.22proxy` Dockerfile — activates `ProxyModeClient`

Source: `runtimes/runtime/go/v1.22proxy/Dockerfile`

```dockerfile
# Only difference from the standard go:1.22 Dockerfile:
# this image pins to the experimental common base (common1.18.4)
# and activates forward proxy client mode.
FROM apache/openserverless-runtime-common:common1.18.4 AS builder

FROM golang:1.22-bookworm
ENV OW_EXECUTION_ENV=apacheopenserverless/runtime-golang-v1.22
COPY --from=builder /go/bin/proxy /bin/proxy

# ... same apt-get and ADD steps as go:1.22 ...

ENV OW_COMPILER=/bin/compile
ENV OW_LOG_INIT_ERROR=1
ENV OW_WAIT_FOR_ACK=1
ENV OW_ACTIVATE_PROXY_CLIENT=1   # <-- activates ProxyModeClient

ENTRYPOINT [ "/bin/proxy" ]
```
