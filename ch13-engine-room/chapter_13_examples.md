# Chapter 13 — Engine Room — Code Listings
> Source: Apache OpenWhisk codebase (github.com/apache/openwhisk, `master` branch) — architectural
> reference excerpts, not code developed for this book or for the OpenServerless project itself.
> These are the real listings used in Chapter 13 of *Mastering Apache OpenServerless* (Apress).
> Apache OpenWhisk is licensed under the Apache License 2.0; excerpts are reproduced here for
> educational commentary with source paths noted per listing.

---

### Listing 13-1. A representative activation record written to the activations database
Illustrative document shape (not a verbatim file — assembled from the `WhiskActivation` JSON schema).
```json
{
  "_id": "guest/myAction:2026-04-16T10:00:00.000Z",
  "_rev": "1-cd503abe708f3950bdc8c76c2cfccf12",
  "namespace": "guest",
  "name": "myAction",
  "version": "0.0.1",
  "activationId": "23bc46b171f64ed5",
  "start": 1713261600000,
  "end": 1713261600215,
  "duration": 215,
  "statusCode": 0,
  "response": {
    "status": "success",
    "result": { "hello": "World" }
  },
  "logs": ["2026-04-16T10:00:00.100Z stdout: Hello World"],
  "annotations": [
    { "key": "path", "value": "guest/myAction" },
    { "key": "kind", "value": "python:3.11" },
    { "key": "timeout", "value": false }
  ]
}
```

---

### Listing 13-2. `ArtifactStore.scala` — the storage SPI every backend must implement
Source: `common/scala/src/main/scala/org/apache/openwhisk/core/database/ArtifactStore.scala`
```scala
trait ArtifactStore[DocumentAbstraction] {

  protected[core] implicit val executionContext: ExecutionContext
  implicit val logging: Logging

  /** Puts (saves) a document to the database. */
  protected[database] def put(d: DocumentAbstraction)
    (implicit transid: TransactionId): Future[DocInfo]

  /** Deletes a document (must contain valid id and rev). */
  protected[database] def del(doc: DocInfo)
    (implicit transid: TransactionId): Future[Boolean]

  /** Gets a document from the database by id. */
  protected[database] def get[A <: DocumentAbstraction](
    doc: DocInfo,
    attachmentHandler: Option[(A, Attached) => A] = None)
    (implicit transid: TransactionId, ma: Manifest[A]): Future[A]
}
```

---

### Listing 13-3. `MessagingProvider.scala` — the full messaging SPI
Source: `common/scala/src/main/scala/org/apache/openwhisk/core/connector/MessagingProvider.scala`
```scala
trait MessagingProvider extends Spi {
  def getConsumer(
    config: WhiskConfig,
    groupId: String,
    topic: String,
    maxPeek: Int = Int.MaxValue,
    maxPollInterval: FiniteDuration = 5.minutes)
    (implicit logging: Logging, actorSystem: ActorSystem): MessageConsumer

  def getProducer(config: WhiskConfig, maxRequestSize: Option[ByteSize] = None)
    (implicit logging: Logging, actorSystem: ActorSystem): MessageProducer

  def ensureTopic(config: WhiskConfig, topic: String, topicConfig: String,
    maxMessageBytes: Option[ByteSize] = None)
    (implicit logging: Logging): Try[Unit]
}
```

---

### Listing 13-4. `DockerContainerFactory.scala` — the invoker talking directly to the Docker daemon
Source: `core/invoker/src/main/scala/org/apache/openwhisk/core/containerpool/docker/DockerContainerFactory.scala`
```scala
override def createContainer(
  tid: TransactionId,
  name: String,
  actionImage: ExecManifest.ImageName,
  userProvidedImage: Boolean,
  memory: ByteSize,
  cpuShares: Int,
  cpuLimit: Option[Double])
  (implicit config: WhiskConfig, logging: Logging): Future[Container] = {

  val registryConfig = ContainerFactory.resolveRegistryConfig(
    userProvidedImage, runtimesRegistryConfig, userImagesRegistryConfig)
  val image = if (userProvidedImage) Left(actionImage) else Right(actionImage)

  DockerContainer.create(
    tid,
    image = image,
    registryConfig = Some(registryConfig),
    memory = memory,
    cpuShares = cpuShares,
    cpuLimit = cpuLimit,
    environment = Map("__OW_API_HOST" -> config.wskApiHost)
      ++ containerArgsConfig.extraEnvVarMap,
    network = containerArgsConfig.network,
    name = Some(name),
    useRunc = dockerContainerFactoryConfig.useRunc,
    parameters ++ containerArgsConfig.extraArgs.map {
      case (k, v) => ("--" + k, v)
    })
}
```

---

### Listing 13-5. `ShardingContainerPoolBalancer.scala` — consistent-hashing invoker selection
Source: `core/controller/src/main/scala/org/apache/openwhisk/core/loadBalancer/ShardingContainerPoolBalancer.scala`
```scala
@tailrec
def schedule(
  maxConcurrent: Int,
  fqn: FullyQualifiedEntityName,
  invokers: IndexedSeq[InvokerHealth],
  dispatched: IndexedSeq[NestedSemaphore[FullyQualifiedEntityName]],
  slots: Int,
  index: Int,
  step: Int,
  stepsDone: Int = 0)
  (implicit logging: Logging, transId: TransactionId)
  : Option[(InvokerInstanceId, Boolean)] = {

  val numInvokers = invokers.size
  if (numInvokers > 0) {
    val invoker = invokers(index)
    if (invoker.status.isUsable &&
        dispatched(invoker.id.toInt)
          .tryAcquireConcurrent(fqn, maxConcurrent, slots)) {
      Some(invoker.id, false)
    } else if (stepsDone == numInvokers + 1) {
      // exhausted every invoker: fall back to random assignment
      val healthy = invokers.filter(_.status.isUsable)
      // ... choose randomly among healthy invokers
      None
    } else {
      val newIndex = (index + step) % numInvokers
      schedule(maxConcurrent, fqn, invokers, dispatched,
        slots, newIndex, step, stepsDone + 1)
    }
  } else None
}
```

---

### Listing 13-6. Timing a single invocation end to end
Operational command, not source code.
```bash
$ ops action invoke hello --param name World --blocking --result
{
    "greeting": "Hello World"
}

$ ops activation get --last | jq '{start, end, duration,
    init: .annotations[] | select(.key=="initTime")}'
```

---

### Listing 13-7. Isolating database query latency in the controller logs
Operational command, not source code.
```bash
$ kubectl -n openserverless logs sts/controller --tail=500 \
    | grep -E 'DATABASE_(BATCH_)?(GET|SAVE|QUERY)'

# a healthy warm-path invocation shows three short database markers:
#   DATABASE_GET   subjects   ~2-5 ms
#   DATABASE_GET   whisks     ~2-5 ms
#   DATABASE_SAVE  activations  ~3-8 ms
# a slow or overloaded CouchDB will show these numbers climbing
# into the tens of milliseconds, and that climb tracks directly
# with the total invocation latency you measured above.
```

---

### Listing 13-8. Reproducing a CouchDB MVCC conflict
Operational command, not source code.
```bash
# terminal 1
$ ops action update myAction --param stage v1 &
# terminal 2, fired immediately after
$ ops action update myAction --param stage v2
error: Unable to update action 'myAction':
  Document update conflict.
```
