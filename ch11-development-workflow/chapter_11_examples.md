# Chapter 11 — Development Workflow
## Code Listings

> These are the listings used in Chapter 11 of *Mastering Apache OpenServerless* (Apress),
> aligned with the Apache OpenServerless 0.9.0-incubating release.

---

### Listing 11-1. Canonical OpenServerless project layout showing single-file actions, multi-file zip actions, and manifest-based deployments

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

### Listing 11-2. scan.js — the scan() function that discovers and deploys all action types in order

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

  // 5. YAML manifests (glob list also configurable)
  const manifestGlobs = await getOpenServerlessConfig('manifests',
    ['packages/*.yaml', 'packages/*/*.yaml']);
  // ... collect and sort the manifests, load packages/.env ...
  for (const manifest of manifests)
    await deployProject(manifest);

  syncDeployInfo(packages, deployments);
}
```

---

### Listing 11-3. deploy.js — extractArgs() reads # -- and // -- comment lines and converts them to CLI flags

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

### Listing 11-4. Python action using inline arg annotations for web exposure and resource limits

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

### Listing 11-5. deploy.js — deployAction() with concurrency guard, inline-arg extraction, and queue processing

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

### Listing 11-6. deploy.js — deployProject() deploys a wskdeploy YAML manifest via ops -wsk project deploy

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

### Listing 11-7. testing/test-runtimes/manifest.yaml — multi-package manifest with shared service inputs

```yaml
packages:
  javascript:
    inputs:
      redis_url: ${REDIS_URL}
      redis_prefix: ${REDIS_PREFIX}
      mongodb_url: ${MONGODB_URL}
      postgres_url: ${POSTGRES_URL}
      s3_access: ${S3_ACCESS_KEY}
      s3_secret: ${S3_SECRET_KEY}
      s3_host: ${S3_HOST}
      s3_port: ${S3_PORT}
      s3_data: ${S3_BUCKET_DATA}
    actions:
      hello:
        function: javascript/hello.js
      redis:
        function: javascript/redis.js
      mongodb:
        function: javascript/mongodb.js
      postgres:
        function: javascript/postgres.js
      seaweed:
        function: javascript/seaweed.js
  python:
    inputs:
      redis_url: ${REDIS_URL}
      mongodb_db: ${MONGODB_DB}
      # ... same service credentials ...
    actions:
      hello:
        function: python/hello.py
      # ... redis, mongodb, postgres, seaweed ...
```

---

### Listing 11-8. ide/python/build-venv.sh in the ops task bundle — creates a virtualenv and packages it into the action zip

```bash
#!/bin/bash
# ide/python/build-venv.sh (license header omitted)
DIR="${1:?directory}"
ZIP="${2:?zip file}"
cd "$DIR"
if ! test -d virtualenv
then uv venv virtualenv --python=/usr/bin/python3
fi
uv pip install --python=virtualenv/bin/python -r requirements.txt
if test -f "$ZIP"
  then rm "$ZIP"
fi
7zz a "$ZIP" -tzip virtualenv >/dev/null
ls -l $ZIP
date >virtualenv/date
```

---

### Listing 11-9. ide/nodejs/build-node.sh in the ops task bundle — installs the dependencies with Bun and packages them into the action zip

```bash
#!/bin/bash
# ide/nodejs/build-node.sh (license header omitted)
DIR="${1:?directory}"
ZIP="${2:?zip file}"
cd "$DIR"
bun install
if test -f "$ZIP"
then rm "$ZIP"
fi
7zz a "$ZIP" -tzip node_modules >/dev/null
ls -l $ZIP
```

---

### Listing 11-10. syncDeployInfo.js — writes and resets the .ops/deployment.json state file

```javascript
// ide/deploy/syncDeployInfo.js (excerpt)

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

### Listing 11-11. watch.js — chokidar watcher with SKIPDIR exclusions and write-stability detection

```javascript
// ide/deploy/watch.js (excerpt)
const SKIPDIR = ["virtualenv", "node_modules", "__pycache__"];

export const watcherOptions = {
  persistent: true,
  ignoreInitial: true,
  recursive: true,
  // wait until a file has been stable for 500 ms
  awaitWriteFinish: { stabilityThreshold: 500, pollInterval: 100 },
  atomic: 250,
  ignored: (file) => shouldIgnoreFile(file), // *.zip, *.tmp
};

export async function checkAndDeploy(changeType, path) {
  path = resolve(path);
  const src = path.slice(process.cwd().length + 1);
  if (changeType !== 'change' || !src) return;
  for (const dir of src.split('/').slice(0, -1)) {
    if (SKIPDIR.includes(dir)) return;
  }
  await deploy(src);
}

export async function watchAndDeploy() {
  await serve(); // ops ide serve, or the "devel" command
  await logs();  // ops activation poll, or the "logs" command
  globalWatcher = watch('packages', watcherOptions);
  globalWatcher.on('all', async (event, path) => {
    try { await checkAndDeploy(event, path); }
    catch (error) { console.error(error); }
  });
}
```

---

### Listing 11-12. serve.js — static file serving with ETag caching and proxy fallback to the remote OpenServerless host

```javascript
// ide/deploy/serve.js (excerpt)

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

### Listing 11-13. devcontainer.json — VS Code devcontainer configuration created by ops ide devcontainer (ide/devcontainer.json in the ops task bundle)

```json
{
  "name": "Agent41",
  "image": "ghcr.io/mastrogpt/agent41-starter:2506201530",
  "remoteUser": "node",
  "containerEnv": {
    "OPS_BRANCH": "main",
    "DEVCONTAINER": "1"
  },
  "runArgs": [ "--network=host" ],
  "remoteEnv": {
    "OPS_BRANCH": "main",
    "REMOTE_CONTAINERS": "1"
  },
  "postCreateCommand": "ops -update",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-vscode.test-adapter-converter",
        "pamaron.pytest-runner"
        // ... more extensions ...
      ]
    }
  }
}
```

---

### Listing 11-14. undeploy.js — full project teardown by reading .ops/deployment.json and issuing delete commands

```javascript
// ide/deploy/undeploy.js (excerpt)

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

### Listing 11-15. .github/workflows/tests.yaml — the three-stage CI pipeline triggered on platform-identifying tags

```yaml
# .github/workflows/tests.yaml (excerpt)
name: AllTests
on:
  push:
    tags:
      - '*-*'          # e.g. k3s-0.1.2, aks-0.2.0
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
