# Chapter 11 — Development Workflow
## Code Listings

> Source: Apache OpenServerless codebase — `testing/tasks/ide/deploy/` and related paths.
> These are the real listings used in Chapter 11 of *Apache OpenServerless: The Complete Guide* (Apress).

---

### Listing 11-1. Canonical OpenServerless project layout

```
my-app/
├── package.json          # optional openserverless config
├── .env                  # API host, credentials
├── .devcontainer/
│   └── devcontainer.json
├── web/
│   └── index.html
└── packages/
    ├── mypkg.args        # extra ops package flags
    ├── mypkg/
    │   ├── hello.py              ← single-file action
    │   ├── greet/                ← multi-file (zip) action
    │   │   ├── __main__.py
    │   │   └── requirements.txt  ← triggers zip build
    │   └── services.yaml         ← wskdeploy manifest
    └── packages/.env     # shared package env vars
```

---

### Listing 11-2. `scan.js` — the `scan()` function

Source: `testing/tasks/ide/deploy/scan.js`

```javascript
export async function scan() {
  const deployments = new Set();
  const packages    = new Set();

  // 1. Requirements → zip actions
  const reqGlobs = await getOpenServerlessConfig('requirements', [
    'packages/*/*/requirements.txt',
    'packages/*/*/package.json',
    'packages/*/*/composer.json',
    'packages/*/*/go.mod',
  ]);
  for (const glob of reqGlobs) {
    for (const item of await glob(glob)) {
      const [, pkg, act] = item.split('/');
      deployments.add(await buildZip(pkg, act));
      packages.add(pkg);
    }
  }

  // 2. Main entry points → zip actions
  const mainGlobs = await getOpenServerlessConfig('mains', [
    'packages/*/*/index.js', 'packages/*/*/__main__.py',
    'packages/*/*/index.php', 'packages/*/*/main.go',
  ]);
  // ... same loop ...

  // 3. Single-file actions
  const singleGlobs = await getOpenServerlessConfig('singles', [
    'packages/*/*.py', 'packages/*/*.js',
    'packages/*/*.php', 'packages/*/*.go',
  ]);
  // ... same loop ...

  // 4. Deploy packages then actions
  for (const pkg of packages) await deployPackage(pkg);
  for (const action of deployments) await deployAction(action);

  // 5. YAML manifests
  const manifestGlobs = ['packages/*.yaml', 'packages/*/*.yaml'];
  for (const manifest of await glob(...manifestGlobs))
    await deployProject(manifest);

  syncDeployInfo(packages, deployments);
}
```

---

### Listing 11-3. `deploy.js` — `extractArgs()` reads inline comment flags

Source: `testing/tasks/ide/deploy/deploy.js`

```javascript
async function extractArgs(files) {
  const res = [];
  for (const file of files) {
    if (await fs.exists(file)) {
      const lines = (await fs.readFile(file, 'utf-8')).split('\n');
      for (const line of lines) {
        // Python-style:  # --web true
        if (line.match(/^#[ ]?-{1,2}[^\s-].+/))
          res.push(line.trim().substring(1).trim());
        // JS-style:  // --timeout 60000
        if (line.match(/^\/\/[ ]?-{1,2}[^\s-].+/))
          res.push(line.trim().substring(2).trim());
      }
    }
  }
  return res;
}
```

---

### Listing 11-4. Python action with inline arg annotations

```python
# packages/mypkg/hello.py
#
# Inline action flags consumed by extractArgs() in deploy.js:
# --web true
# --timeout 30000
# --memory 256

def main(args):
    name = args.get('name', 'World')
    return {'body': f'Hello, {name}!'}
```

---

### Listing 11-5. `deploy.js` — `deployAction()` with concurrency guard

Source: `testing/tasks/ide/deploy/deploy.js`

```javascript
export async function deployAction(artifact) {
  // Guard against concurrent deploys of the same artifact
  if (activeDeployments.has(artifact)) {
    queue.push(artifact);
    return;
  }
  activeDeployments.set(artifact, true);

  const sp       = artifact.split('/');
  const spData   = sp[sp.length - 1].split('.');
  const name     = spData[0];
  const typ      = spData[1];
  const pkg      = sp[1];

  await deployPackage(pkg);

  // For zip artifacts inspect all possible mains for inline args
  const toInspect = typ === 'zip'
    ? MAINS.map(m => `${artifact.slice(0,-4)}/${m}`)
    : [artifact];

  const args       = (await extractArgs(toInspect)).join(' ');
  const actionName = `${pkg}/${name}`;
  await exec(`ops action update ${actionName} ${artifact} ${args}`);

  activeDeployments.delete(artifact);
  if (queue.length > 0) await deploy(queue.shift());
}
```

---

### Listing 11-6. `deploy.js` — `deployProject()` for wskdeploy manifests

Source: `testing/tasks/ide/deploy/deploy.js`

```javascript
export async function deployProject(artifact) {
  if (await fs.exists(artifact)) {
    const content = await Bun.file(artifact).text();
    if (content.indexOf('packages:') !== -1) {
      await exec(
        `ops -wsk project deploy --manifest ${artifact}`
      );
    } else {
      console.log(`⚠️ Not a valid manifest: ${artifact}. Skipping`);
    }
  }
}
```

---

### Listing 11-7. `testing/test-runtimes/manifest.yaml` — multi-package wskdeploy manifest

Source: `testing/test-runtimes/manifest.yaml`

```yaml
packages:
  javascript:
    inputs:
      redis_url:   ${REDIS_URL}
      mongodb_url: ${MONGODB_URL}
      postgres_url: ${POSTGRES_URL}
      s3_access:   ${S3_ACCESS_KEY}
      s3_secret:   ${S3_SECRET_KEY}
      s3_host:     ${S3_HOST}
      s3_port:     ${S3_PORT}
      s3_data:     ${S3_BUCKET_DATA}
    actions:
      hello:
        function: javascript/hello.js
      redis:
        function: javascript/redis.js
      minio:
        function: javascript/minio.js
  python:
    inputs:
      redis_url:    ${REDIS_URL}
      mongodb_url:  ${MONGODB_URL}
      mongodb_db:   ${MONGODB_DB}
      postgres_url: ${POSTGRES_URL}
      # ... same service credentials ...
    actions:
      hello:
        function: python/hello.py
      redis:
        function: python/redis.py
      minio:
        function: python/minio.py
```

---

### Listing 11-8. `build-venv.sh` — Python virtualenv build script

Source: `testing/tasks/ide/python/build-venv.sh`

```bash
#!/bin/bash
# Creates a Python virtualenv and packages it as a zip artifact.

PKG=$1
ACT=$2
DIR="packages/$PKG/$ACT"

cd "$DIR"
virtualenv virtualenv
source virtualenv/bin/activate
pip install -r requirements.txt
deactivate

# Package source files + virtualenv into a zip
cd ..
7zz a -r "${ACT}.zip" "$ACT"
echo "Built: packages/${PKG}/${ACT}.zip"
```

---

### Listing 11-9. `build-node.sh` — Node.js dependency bundle script

Source: `testing/tasks/ide/nodejs/build-node.sh`

```bash
#!/bin/bash
# Installs npm/bun dependencies and packages the action as a zip.

PKG=$1
ACT=$2
DIR="packages/$PKG/$ACT"

cd "$DIR"
# Use bun for fast installs; falls back to npm
if command -v bun &>/dev/null; then
  bun install
else
  npm install
fi

cd ..
7zz a -r "${ACT}.zip" "$ACT"
echo "Built: packages/${PKG}/${ACT}.zip"
```

---

### Listing 11-10. `syncDeployInfo.js` — deployment state file management

Source: `testing/tasks/ide/deploy/syncDeployInfo.js`

```javascript
export function syncDeployInfo(packages, deployments) {
  if (!existsSync('.ops')) mkdirSync('.ops', { recursive: true });

  const packageActions = {};
  for (const pkg of packages) packageActions[pkg] = [];

  for (const dep of deployments) {
    const sp   = dep.split('/');
    const name = sp[sp.length - 1].split('.')[0];
    const pkg  = sp[1];
    if (packageActions[pkg]) packageActions[pkg].push(name);
  }

  const info = {
    packages: Array.from(packages),
    packageActions,
  };
  writeFileSync('.ops/deployment.json', JSON.stringify(info, null, 2));
  console.log('> Saved deployment information to .ops/deployment.json');
}

export function cleanupDeployInfo() {
  syncDeployInfo(new Set(), new Set());
}
```

---

### Listing 11-11. `watch.js` — chokidar watcher with SKIPDIR and debounce

Source: `testing/tasks/ide/deploy/watch.js`

```javascript
const SKIPDIR = ['virtualenv', 'node_modules', '__pycache__', '.git', '.ops'];

export async function watch(dir, handler) {
  globalWatcher = chokidar.watch(dir, {
    ignored: (p) => {
      const parts = p.split(path.sep);
      return parts.some(part => SKIPDIR.includes(part));
    },
    persistent: true,
    ignoreInitial: true,
  });

  // Debounce: collect rapid changes and fire once
  let debounceTimer;
  const pending = new Set();

  globalWatcher.on('all', (event, changedPath) => {
    pending.add(changedPath);
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      const files = [...pending];
      pending.clear();
      for (const f of files) await handler(f);
    }, 300);
  });
}
```

---

### Listing 11-12. `serve.js` — static asset server with proxy fallback

Source: `testing/tasks/ide/deploy/serve.js`

```javascript
Bun.serve({
  port: serverPort,
  hostname: flags.host,
  async fetch(req) {
    const { pathname } = parse(req.url);
    const filePath = `${assetsDirectory}${pathname === '/' ? '/index.html' : pathname}`;

    try {
      // Try to serve file from local assets directory
      const fileStats = await stat(filePath);
      if (fileStats.isFile()) {
        const mimeType = getMimeType(filePath);
        const etag     = `W/"${fileStats.size}-${fileStats.mtimeMs}"`;
        // ... ETag / conditional-request handling ...
        return new Response(Bun.file(filePath).stream(), {
          headers: { 'Content-Type': mimeType, 'ETag': etag }
        });
      }
    } catch {
      // File not found locally — proxy to OpenServerless host
      if (flags.proxyHost) {
        const destUrl = `${flags.proxyHost}${pathname}`;
        console.log(`[ P ] Proxying ${req.method} → ${destUrl}`);
        return fetch(destUrl, { method: req.method, headers: req.headers });
      }
      return new Response('File not found', { status: 404 });
    }
  },
});
```

---

### Listing 11-13. `devcontainer.json` — VS Code devcontainer configuration

Source: `testing/tasks/ide/devcontainer.json`

```json
{
  "name": "openserverless-devcontainer",
  "image": "ghcr.io/mastrogpt/agent41-starter:2506201530",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "dbaeumer.vscode-eslint"
      ]
    }
  },
  "mounts": [
    "source=${localEnv:HOME}/.wskprops,target=/root/.wskprops,type=bind"
  ],
  "postCreateCommand": "ops ide setup",
  "remoteEnv": {
    "OPS_PWD": "${containerWorkspaceFolder}"
  }
}
```

---

### Listing 11-14. `undeploy.js` — full project teardown

Source: `testing/tasks/ide/deploy/undeploy.js`

```javascript
export function undeploy(specificAction) {
  if (specificAction) return undeployAction(specificAction);

  const deploymentInfo = JSON.parse(
    readFileSync('.ops/deployment.json', 'utf8')
  );
  const { packages, packageActions } = deploymentInfo;

  // Delete actions first, then packages
  for (const pkg of packages) {
    for (const action of packageActions[pkg] || []) {
      exec(`$OPS action delete ${pkg}/${action}`);
    }
  }
  for (const pkg of packages) {
    exec(`$OPS package delete ${pkg}`);
  }

  cleanupDeployInfo();
  console.log('> Undeployment completed successfully.');
}
```

---

### Listing 11-15. `.github/workflows/tests.yaml` — three-stage CI pipeline

Source: `testing/.github/workflows/tests.yaml`

```yaml
# Triggered on tags matching *-* (e.g. k3s-0.1.2, aks-0.2.0, kind-0.3.0)
name: AllTests
on:
  push:
    tags:
      - '*-*'
    branches-ignore: '*'

jobs:
  test-linux:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - name: Install ops
        run: curl -sL bit.ly/get-ops | bash
      - name: Load secrets
        uses: 1password/load-secrets-action@v2
        env:
          OP_SERVICE_ACCOUNT_TOKEN: ${{ secrets.OP_SERVICE_ACCOUNT_TOKEN }}
          K3S_IP:  op://OpenServerless/TESTING/K3S_IP
          MK8S_IP: op://OpenServerless/TESTING/MK8S_IP
          # ... more secrets ...
      - name: Deploy
        run: tests/1-deploy.sh $PLATFORM
      - name: Runtime tests
        run: tests/14-runtime-testing.sh $PLATFORM

  test-windows:
    runs-on: windows-2022
    needs: test-linux
    steps:
      - name: Install ops
        shell: powershell
        run: irm bit.ly/get-ops-exe | iex
      # ... same test steps via bash shell ...

  test-mac:
    runs-on: macOS-14
    needs: test-windows
    steps:
      - name: Install ops
        run: curl -sL bit.ly/get-ops | /bin/bash
      # ... same test steps ...
```
