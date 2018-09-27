Stashorizer is a bot that automatically downloads images from tweets in
which its name is "mentioned" in. If the image passes a safety check for 
adult content, violence, etc. then the bot will attempt to find faces in
the image and draw mustaches on each face. The both will then reply to the
original tweet with that mustache annotated image.

# BUILD

```
git push -u origin master
docker build --no-cache -t iandow/stashorizer .
docker push iandow/stashorizer
```

# USAGE:

Define the following environment variables in `~/env-file`:

*Required:*
```
TW_USERNAME=
TW_CONSUMER_KEY=
TW_CONSUMER_SECRET=
TW_ACCESS_TOKEN=
KAFKA_REST_URL=
ROLLBAR_ACCESS_KEY=
GOOGLE_APPLICATION_CREDENTIALS=
```

*Optional:*
```
TW_ACCESS_TOKEN_SECRET=
DEBUG=False
```

Here's what an example env-file might look like. The keys and secrets shown below are fake.
I just put them here so you know how the format looks:

```
TW_USERNAME=stashorizer
TW_CONSUMER_KEY=23e0d55913808d0b813c8dc08
TW_CONSUMER_SECRET=08d0b81323e0d55913808d0b813c8dc0808d0b81308d0b8132
TW_ACCESS_TOKEN=ad838460bfd641ab7f5-460bfd641ab7f5d76ed5adb91ADADX
TW_ACCESS_TOKEN_SECRET=36530de11f9f657f0821356652448ce536530de11f9f6
ROLLBAR_ACCESS_KEY=36530de11f9f657f0821356652448ce5
GOOGLE_APPLICATION_CREDENTIALS=/root/certs/my-project-98793e12f.json
DEBUG=False
KAFKA_REST_URL='http://nodea:8082/topics/%2Fapps%2Fstashorizer%3Amentions'
```

You'll need to link your Google Cloud certificate to container. I do that by coping my json cert file to `~/certs/` and mapping directory that to the container as a docker volume, like this:

```
docker pull iandow/stashorizer
docker run -it --rm --env-file ~/env-file --name stashorizer -v ~/certs/:/root/certs/ iandow/stashorizer:latest
```

# MapR Streams

The twitter stream listener in streaming_mustache_bot.py will try to persist every received mention to a topic in MapR Streams using a Kafka REST service running on a MapR cluster node. This helps guarantee that we keep all the @stashorizer mentions on twitter even if if people delete their mentions from twitter or if twitter disables the bot account.

Here's how to create the stream on a MapR cluster node, with public write permissions and a TTL of 0 (meaning data is never purged).

```
maprcli stream create -path /apps/stashorizer
maprcli stream edit -path /apps/stashorizer -produceperm p -consumeperm p -topicperm p --ttl 0
maprcli stream topic create -path /apps/stashorizer -topic mentions -partitions 3
```

Once the stream is created you can produce a message like this:

```
echo "hello world" | base64 | xargs -I {} curl -X POST -H "Content-Type: application/vnd.kafka.v1+json" --data '{"records":[{"value":"{}"}]}' "http://nodea:8082/topics/%2Fapps%2Fstashorizer%3Amentions"
```

You can read from the stream using the kafka console consumer, like this:

```
/opt/mapr/kafka/kafka-1.0.1/bin/kafka-console-consumer.sh --topic /apps/stashorizer:mentions --new-consumer --bootstrap-server this.will.be.ignored:9092 --from-beginning
```