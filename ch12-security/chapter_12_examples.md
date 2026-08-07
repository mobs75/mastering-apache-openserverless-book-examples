# Chapter 12 — Security in OpenServerless — Code Listings
> Source: Apache OpenServerless codebase — security, authentication, and operator RBAC paths.
> These are the real listings used in Chapter 12 of *Apache OpenServerless: The Complete Guide* (Apress).
---
### Listing 12-1. openwhisk_authorize.py — the core OpenWhisk token validation path
```python
# admin-api/openserverless/common/openwhisk_authorize.py (excerpts)
class OpenwhiskAuthorize:

    def encode(self, username, password):
        """Build Basic <b64(uuid:key)> header value."""
        username_password = f'{quote(username)}:{quote(password)}'
        return f'Basic {b64encode(username_password.encode()).decode()}'

    def fetch_subject(self, uuid: str, key: str):
        """Query CouchDB subjects DB for matching uuid+key."""
        selector = {
            'selector': {'namespaces': {'$elemMatch': {'uuid': uuid, 'key': key}}}
        }
        response = self._db.find_doc(SUBJECT_META_DBN, json.dumps(selector))
        if response['docs']:
            return list(response['docs'])[0]
        return None

    def login(self, authorization: str):
        uuid, key = self.decode(authorization)
        subject   = self.fetch_subject(uuid, key)
        if not subject:
            raise AuthorizationError('Openwhisk subject not found.')
        user_data = self.fetch_user_data(subject['subject'])
        if user_data:
            return user_data
        raise AuthorizationError('Could not retrieve user metadata.')
```
---
### Listing 12-2. ow_authorize.py — decorator that gates an endpoint on OW namespace credentials
```python
# admin-api/openserverless/security/ow_authorize.py
def ow_authorize(pass_user_data=False, kwargs_field_name='ow-auth-user'):
    def decorator(func, **kwargs):
        @wraps(func)
        def decorated(*args, **kwargs):
            if 'authorization' not in request.headers:
                return res_builder.build_error_message(
                    'No valid authorization headers found', 401
                )
            ow_auth = OpenwhiskAuthorize()
            try:
                user_data = ow_auth.login(request.headers['authorization'])
                if not user_data:
                    return res_builder.build_error_message(
                        'Invalid authorization header. Access denied.', 401
                    )
                if pass_user_data:
                    kwargs[kwargs_field_name] = user_data
                return func(*args, **kwargs)
            except Exception as ex:
                return res_builder.build_error_message(
                    f'Could not validate authorization headers. Reason {ex}', 401
                )
        return decorated
    return decorator
```
---
### Listing 12-3. auth_service.py and bcrypt_util.py — password authentication and hashing
```python
# admin-api/openserverless/impl/auth/auth_service.py (excerpts)
import openserverless.couchdb.bcrypt_util as bu

class AuthService:

    def login(self, login, password):
        user_data = self.fetch_user_data(login)
        if user_data:
            if bu.verify_password(password, user_data['password']):
                return res_builder.build_response_with_data(self.map_data(user_data))
            else:
                return res_builder.build_error_message('Invalid credentials', 401)
        return res_builder.build_error_message('Invalid credentials', 401)

    def update_password(self, login, old_password, new_password):
        user_data = self.fetch_user_data(login)
        if user_data and bu.verify_password(old_password, user_data['password']):
            whisk_user = self.kube_client.get_whisk_user(user_data['login'])
            whisk_user['spec']['password'] = new_password
            self.kube_client.update_whisk_user(whisk_user)
            return res_builder.build_response_with_data(
                {'status': 'ok', 'message': 'Password updated'}
            )
        return res_builder.build_error_message('password mismatch', 401)

# admin-api/openserverless/couchdb/bcrypt_util.py
import bcrypt

def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
```
---
### Listing 12-4. login.go — the CLI login flow, schema enforcement, and config.json persistence
```go
# cli/auth/login.go (excerpts)
const whiskLoginPath = "/api/v1/web/whisk-system/nuv/login"

func LoginCmd() (*LoginResult, error) {
    // ... flag parsing ...
    apihost = ensureSchema(apihost)  // forces https:// for non-localhost
    url := apihost + whiskLoginPath

    password := os.Getenv("OPS_PASSWORD")
    if password == "" {
        fmt.Print("Enter Password: ")
        pwd, err := AskPassword()   // reads from terminal without echo
        password = pwd
    }
    creds, err := doLogin(url, user, password)
    // creds map contains AUTH token returned by the login action
    for k, v := range creds {
        configMap.Insert(k, v)      // persisted to OPS_HOME/config.json
    }
    return &LoginResult{Login: user, Auth: creds["AUTH"], ApiHost: apihost}, nil
}

func ensureSchema(apihost string) string {
    if apihost == "localhost" {
        return "http://" + apihost
    }
    return "https://" + apihost  // always TLS for remote hosts
}
```
---
### Listing 12-5. user-crd.yaml — the WhiskUser CRD template with all optional service credentials
```yaml
# olaris/admin/user-crd.yaml template
apiVersion: nuvolaris.org/v1
kind: WhiskUser
metadata:
  name: ${USERNAME}
  namespace: nuvolaris
spec:
  email:     ${EMAIL}
  password:  ${PASSWORD}        # bcrypt-hashed at operator level
  namespace: ${USERNAME}        # dedicated OW namespace
  auth:      ${SECRET_USER_AUTH} # uuid4:random64 OW token
  redis:
    enabled:  ${REDIS_ENABLED}
    prefix:   ${USERNAME}
    password: ${USER_SECRET_REDIS}
  mongodb:
    enabled:  ${MONGODB_ENABLED}
    database: ${USERNAME}
    password: ${USER_SECRET_MONGODB}
  postgres:
    enabled:  ${POSTGRES_ENABLED}
    database: ${USERNAME}
    password: ${USER_SECRET_POSTGRES}
  object-storage:
    password: ${USER_SECRET_MINIO}
    quota:    ${MINIO_STORAGE_QUOTA:-auto}
    data:  { enabled: ${MINIO_DATA_ENABLED},   bucket: ${USERNAME}-data }
    route: { enabled: ${MINIO_STATIC_ENABLED}, bucket: ${USERNAME}-web  }
  milvus:
    enabled:  ${MILVUS_ENABLED}
    database: ${USERNAME}
    password: ${USER_SECRET_MILVUS}
```
---
### Listing 12-6. opsfile.yml — system secret generation and per-user secret generation tasks
```yaml
# olaris/util/opsfile.yml â task: secrets (system-level generation)
secrets:
  cmds:
    - config SECRET_OPENWHISK_SYSTEM='$(random --uuid):$(random --str 64)'
    - config SECRET_OPENWHISK_NUVOLARIS='$(random --uuid):$(random --str 64)'
    - config SECRET_COUCHDB_ADMIN='$(random --str 12)'
    - config SECRET_COUCHDB_CONTROLLER='$(random --str 12)'
    - config SECRET_COUCHDB_INVOKER='$(random --str 12)'
    - config SECRET_REDIS_DEFAULT='$(random --str 12)'
    - config SECRET_REDIS_NUVOLARIS='$(random --str 12)'
    - config SECRET_MONGODB_ADMIN='$(random --str 12)'
    - config SECRET_MINIO_ADMIN='$(random --str 40)'
    - config SECRET_MINIO_NUVOLARIS='$(random --str 40)'
    - config SECRET_POSTGRES_ADMIN='$(random --str 12)'
    - config SECRET_ETCD_ROOT='$(random --str 12)'
    - config SECRET_MILVUS_ROOT='$(random --str 12)'
    - config SECRET_NUVOLARIS_METADATA='$(random --str 12)'

# task: user-secrets (per-user generation inside ops admin adduser)
user-secrets:
  cmds:
    - config '${USR}_SECRET_OPENWHISK'='$(random --uuid):$(random --str 64)'
    - config '${USR}_SECRET_REDIS'='$(random --str 12)'
    - config '${USR}_SECRET_MONGODB'='$(random --str 12)'
    - config '${USR}_SECRET_MINIO'='$(random --str 40)'
    - config '${USR}_SECRET_POSTGRES'='$(random --str 12)'
```
---
### Listing 12-7. secrets.lib.ts and secrets/__main__.py — the env-secrets add/remove/list pipeline
```typescript
# olaris/env/secrets/src/secrets.lib.ts (requestSecrets excerpt)
public static async requestSecrets(
    operation: string,
    username: string,
    apihost: string,
    secrets?: Record<string, string>
): Promise<SecretResponse> {
    const apiUrl = `${apihost}/api/v1/web/whisk-system/nuv/secrets`;
    const AUTH   = process.env['AUTH'] || '';
    const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `${AUTH}`   // OW token, not password
        },
        body: JSON.stringify({ login: username, env: secrets })
    });
    return response.json();
}

# olaris-op/actions/secrets/__main__.py (merge logic excerpt)
def handle_additional_env(user_data, env):
    old_env = env_to_dict(user_data, 'userenv')
    added_keys   = [k for k in env if k not in old_env and env[k]]
    changed_keys = [k for k in env if k in old_env and old_env[k] != env[k] and env[k]]
    new_env = {
        **{k: v for k, v in old_env.items() if k not in env or env[k]},
        **{k: v for k, v in env.items()     if v}
    }
    removed_keys = [k for k in old_env if k not in new_env]
    return new_env, added_keys, changed_keys, removed_keys
```
---
### Listing 12-8. operator-clusterroles.yaml — ClusterRole for infrastructure and TLS management
```yaml
# olaris/setup/kubernetes/roles/operator-clusterroles.yaml (condensed)
kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: nuvolaris-operator-cr
rules:
  # Read-only cluster discovery
  - apiGroups: ['']
    resources: ['nodes', 'namespaces']
    verbs: ['get', 'list', 'watch']

  # Manage CRDs and RBAC (includes 'escalate' to bind higher roles)
  - apiGroups: ['apiextensions.k8s.io']
    resources: ['customresourcedefinitions']
    verbs: ['get', 'list', 'watch', 'create', 'update', 'patch', 'delete']
  - apiGroups: ['rbac.authorization.k8s.io']
    resources: ['clusterroles', 'clusterrolebindings', 'rolebindings', 'roles']
    verbs: ['get', 'list', 'watch', 'create', 'update', 'patch',
            'delete', 'escalate', 'bind']

  # TLS: full control over cert-manager issuers and clusterissuers
  - apiGroups: ['cert-manager.io']
    resources: ['issuers', 'clusterissuers', 'certificates']
    verbs: ['get', 'list', 'watch', 'create', 'update', 'patch', 'delete']

  # Ingress management (nginx + traefik)
  - apiGroups: ['networking.k8s.io']
    resources: ['ingresses', 'ingresses/status', 'ingressclasses']
    verbs: ['get', 'list', 'watch', 'create', 'update', 'patch', 'delete']
```
---
### Listing 12-9. Operational security commands — certificates, secrets retrieval, and docx validation
```bash
# Verify TLS resources in a running cluster
kubectl -n nuvolaris get ClusterIssuers,Certificates,CertificateRequests,Orders,Challenges

# Monitor cert-manager logs
kubectl -n cert-manager logs -l app=cert-manager

# Verify fonts and image types in the generated docx
unzip -p chapter.docx word/styles.xml | grep -o 'w:ascii="[^"]*"' | sort -u
unzip -l chapter.docx | grep media   # must show .png, not .undefined
unzip -p chapter.docx '[Content_Types].xml' | grep -o '<Default[^/]*/>'

# Retrieve live secrets from a running cluster (useful after cluster rebuild)
ops update secrets

# Validate all section headings start with numeric prefix
# (run against generated XML after unzipping .docx)
unzip -p chapter.docx word/document.xml \
  | grep -oP '(?<=<w:t>)[^<]+' \
  | grep -E '^1[0-9]\.' | head -30
```
---