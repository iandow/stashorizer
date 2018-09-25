Stashorizer is a bot that automatically downloads images from tweets in
which its name is "mentioned" in. If the image passes a safety check for 
adult content, violence, etc. then the bot will attempt to find faces in
the image and draw mustaches on each face. The both will then reply to the
original tweet with that mustache annotated image.

# BUILD

```
docker build -t stashorizer .
```

# USAGE:

Define the following environment variables in `./env-file`:

```
TW_USERNAME=
TW_CONSUMER_KEY=
TW_CONSUMER_SECRET=
TW_ACCESS_TOKEN=
TW_ACCESS_TOKEN_SECRET=
DEBUG=False
ROLLBAR_ACCESS_KEY=
GOOGLE_APPLICATION_CREDENTIALS=
```

You'll need to link your Google Cloud certificate to container. I do that by coping my json cert file to `~/certs/` and mapping directory that to the container as a docker volume, like this:

```
docker run --rm --env-file ./env-file --name stashorizer -v ~/certs/:/root/certs/ stashorizer:latest 
```
