# Chapter 10 — OpenServerless Runtimes
## Code Listings

> These are the listings used in Chapter 10 of *Mastering Apache OpenServerless* (Apress),
> aligned with the Apache OpenServerless 0.9.0-incubating release.

---

### Listing 10-1. The openserverless-runtime-common builder image compiles the proxy binary (Dockerfile in the root of the runtimes repository)

```dockerfile
FROM golang:1.21
ENV HOME=/tmp

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY proxy.go ./
COPY openwhisk/ ./openwhisk/
RUN CGO_ENABLED=0 go build -o /go/bin/proxy

USER nobody
COPY DISCLAIMER LICENSE NOTICE /
ENTRYPOINT [ "/go/bin/proxy" ]
```

---

### Listing 10-2. The Node.js v22 runtime Dockerfile, illustrating the multi-stage build pattern (runtime/nodejs/v22/Dockerfile)

```dockerfile
ARG COMMON=missing:missing
FROM ${COMMON} AS builder

FROM node:22.23.2-bookworm
ENV OW_EXECUTION_ENV=apacheopenserverless/nodejs-22.23.2
COPY --from=builder /go/bin/proxy /bin/proxy

ENV OW_COMPILER=/bin/compile
ENV OW_LOG_INIT_ERROR=1
ENV OW_WAIT_FOR_ACK=1

RUN apt-get update && apt-get install -y \
    imagemagick graphicsmagick unzip \
    && rm -rf /var/lib/apt/lists/*

COPY package.json /
RUN npm config set fetch-retry-maxtimeout 60000 -g
RUN cd / && npm install && npm cache clean --force

RUN mkdir -p /app/action && chmod -R 0775 /app && \
    chown -R nobody:root /app
ENV HOME=/app
WORKDIR /app
COPY bin/compile /bin/compile
COPY lib/launcher.js /lib/launcher.js

EXPOSE 8080
USER nobody
COPY DISCLAIMER LICENSE NOTICE /
ENTRYPOINT ["/bin/proxy"]
```

---

### Listing 10-3. The ActionProxy struct definition in openwhisk/actionProxy.go

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

### Listing 10-4. Mode selection in proxy.go main() — three mutually exclusive operating modes

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

### Listing 10-5. The Executor.Interact() method: writing the invocation payload to stdin and reading the result from fd 3

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

### Listing 10-6. The initBodyRequest struct and the start of doInit() in openwhisk/initHandler.go

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

### Listing 10-7. Waiting for the action acknowledgement in Executor.Start() — openwhisk/executor.go

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

### Listing 10-8. The Python ActionLoop run loop in lib/launcher.py — every language launcher implements this same pattern

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

### Listing 10-9. The Python v3.12 runtime Dockerfile — multi-stage build, proxy binary copy, and environment configuration (runtime/python/v3.12/Dockerfile)

```dockerfile
ARG COMMON=missing:missing
FROM ${COMMON} AS builder

FROM python:3.12.14-slim-bookworm
ENV OW_EXECUTION_ENV=apacheopenserverless/runtime-python-v3.12.14
COPY --from=builder /go/bin/proxy /bin/proxy

RUN apt-get update && apt-get install -y python3-lxml zip \
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
COPY DISCLAIMER LICENSE NOTICE /
ENTRYPOINT ["/bin/proxy"]
```

---

### Listing 10-10. A minimal Go action function — the compile script wraps this into a complete Go program and compiles it

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

### Listing 10-11. Key excerpt from the PHP v8.3 Dockerfile — extension installation, Composer, and proxy setup (experimental/php/v8.3/Dockerfile)

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

### Listing 10-12. The nodejs:22 entry in runtimes.json, showing the full kind descriptor including stemCells reactive pre-warming

```json
{
    "kind": "nodejs:22",
    "default": true,
    "image": {
        "prefix": "docker.io/apache",
        "name": "openserverless-runtime-nodejs",
        "tag": "v22-26i22h40-snapshot"
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

### Listing 10-13. The merge.json file of the Node.js v22 runtime — the default flag and the stemCells configuration are merged into the generated kind (runtime/nodejs/v22/merge.json)

```json
{
    "default": true,
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

### Listing 10-14. The render-runtimes task in the runtimes Taskfile.yml and an example run

```yaml
render-runtimes:
  silent: true
  desc: generate a runtimes.json file with all the runtime
        corresponding to the current TAG
  cmds:
    - echo "creating runtimes.json"
    - python3 runtimes.py {{.TAG}} >runtimes.json

$ task tag
Tag all_26i22h40-snapshot, you can now task build
$ task render-runtimes
creating runtimes.json
```

---

### Listing 10-15. Inspecting, customizing, and applying the runtimes manifest with the ops CLI

```bash
# show the runtimes.json deployed in the cluster
ops debug runtimes

# use a customized runtimes.json instead of the default one
ops config runtimes ./my-runtimes.json

# deploy the manifest as the openwhisk-runtimes ConfigMap
ops update runtimes
```

---

### Listing 10-16. A Dockerfile for a forward proxy client runtime, built on top of the standard Go 1.26 runtime image

```dockerfile
# Forward proxy client runtime: the standard Go runtime
# with the client mode of the proxy switched on
FROM apache/openserverless-runtime-go:v1.26-<tag>
ENV OW_ACTIVATE_PROXY_CLIENT=1
```
