###############################################################################
# AUTHOR: Ian Downard
#
# DESCRIPTION: This twitter bot will look for mentions of TW_USERNAME. If that tweet includes an image, then it will
#   attempt to detect explicit content such as adult or violent content within the image using Safe Search Detection
#   [1]. If the image is considered safe, it will try to detect a nose in the image using a Haar Cascade image
#   classifier [2] in OpenCV. If a nose is detected, it will apply an image mask to draw a mustache below the nose
#   region. The resulting image will be attached to a twitter reply to the original tweet.
#
#   You can monitor logs at
#
# REFERENCES:
#   [1] Safe Search Detection: https://cloud.google.com/vision/docs/detecting-safe-search#vision-safe-search-detection-python
#   [2] Nose detection and mustache mask: https://sublimerobots.com/2015/02/dancing-mustaches/
#
# PRECONDITIONS: The following environment variables must be set (sample
# values shown below, but don't use the keys and secrets, they won't work.
# I just put them here so you know how the format looks):
#
#   TW_USERNAME=stashorizer
#   TW_CONSUMER_KEY=23e0d55913808d0b813c8dc08
#   TW_CONSUMER_SECRET=08d0b81323e0d55913808d0b813c8dc0808d0b81308d0b8132
#   TW_ACCESS_TOKEN=ad838460bfd641ab7f5-460bfd641ab7f5d76ed5adb91ADADX
#   TW_ACCESS_TOKEN_SECRET=36530de11f9f657f0821356652448ce536530de11f9f6
#   ROLLBAR_ACCESS_KEY=36530de11f9f657f0821356652448ce5
#   GOOGLE_APPLICATION_CREDENTIALS=/root/certs/my-project-98793e12f.json
#   DEBUG=False
#   KAFKA_REST_URL='http://nodea:8082/topics/%2Fapps%2Fstashorizer%3Amentions'
#
# USAGE:
#   Save environment variables to a env-file, then run this command:
#   `eval $(egrep -v '^#' .env | xargs) python streaming_mustache_bot.py`
###############################################################################

import mustache_maker
import rollbar, logging
import os, wget, json, time, base64, requests
from tweepy.streaming import StreamListener
from tweepy import API
from tweepy import OAuthHandler
from tweepy import Stream
from google.cloud import vision

# Setup logger
FORMAT = '%(asctime)-15s %(message)s'
if os.environ.get('DEBUG') == 'True':
    print("DEBUG logging enabled")
    logging.basicConfig(format=FORMAT, level=logging.DEBUG)
else:
    logging.basicConfig(format=FORMAT, level=logging.INFO)
logger = logging.getLogger()

# Validate that the required environment variables are present
def validate_env():
    keys = [
        'TW_USERNAME',
        'TW_CONSUMER_KEY',
        'TW_CONSUMER_SECRET',
        'TW_ACCESS_TOKEN',
        'TW_ACCESS_TOKEN_SECRET',
    ]
    # Log success
    logger.debug("validate_env ok")

    # Check for missing env vars
    for key in keys:
        v = os.environ.get(key)
        if not v:
            logger.error("validate_env failed")
            raise ValueError("Missing environment variable: {0}".format(key))

# Detects unsafe features in an image file located on the Web.
def detect_safe_search_uri(uri):
    logger.debug("authenticating to google cloud")
    # Instantiates GCP client
    client = vision.ImageAnnotatorClient()
    image = vision.types.Image()
    image.source.image_uri = uri

    # Performs label detection on the image file
    response = client.safe_search_detection(image=image)
    safe = response.safe_search_annotation

    # Names of likelihood from google.cloud.vision.enums
    likelihood_name = ('UNKNOWN', 'VERY_UNLIKELY', 'UNLIKELY', 'POSSIBLE',
                       'LIKELY', 'VERY_LIKELY')

    logger.debug('Safe search:')
    logger.debug('adult: {}'.format(likelihood_name[safe.adult]))
    logger.debug('medical: {}'.format(likelihood_name[safe.medical]))
    logger.debug('spoofed: {}'.format(likelihood_name[safe.spoof]))
    logger.debug('violence: {}'.format(likelihood_name[safe.violence]))
    logger.debug('racy: {}'.format(likelihood_name[safe.racy]))

    if safe.adult > 2 | safe.medical > 2 | safe.spoof > 2 | safe.violence > 2 | safe.racy > 2:
        logger.error("Detected unsafe image " + uri)
        rollbar.report_message("Detected unsafe image " + uri, 'error')
        rollbar.report_message('image uri: {}'.format(uri), 'error')
        rollbar.report_message('adult: {}'.format(likelihood_name[safe.adult]), 'error')
        rollbar.report_message('medical: {}'.format(likelihood_name[safe.medical]), 'error')
        rollbar.report_message('spoofed: {}'.format(likelihood_name[safe.spoof]), 'error')
        rollbar.report_message('violence: {}'.format(likelihood_name[safe.violence]), 'error')
        rollbar.report_message('racy: {}'.format(likelihood_name[safe.racy]), 'error')
        return False
    else:
        return True


class SListener(StreamListener):
    """ A listener handles tweets that are received from the stream.
    This listener downloads images in received tweets, checks for image safety, then applies a
    mustache mask below the nose on every detected face.
    """

    def init(self, api):
        self.api = api

    def on_status(self, status):
        logging.info(status.text)

        kafka_rest_url = os.environ.get('KAFKA_REST_URL')
        if kafka_rest_url:
            # Persist all the metadata in the @mention to MapR-ES
            #url = 'http://nodea:8082/topics/%2Fapps%2Fstashorizer%3Amentions'
            payload = '{"records":[{"value":"' + base64.b64encode(json.dumps(status._json)) + '"}]}'
            headers = {'content-type': 'application/vnd.kafka.v1+json'}
            try:
                r = requests.post(kafka_rest_url, data=payload, headers=headers)
            except requests.exceptions.Timeout:
                logging.error("Kafka REST request timeout.")
            except requests.exceptions.TooManyRedirects:
                logging.error("Kafka REST URL is bad.")
            except requests.exceptions.RequestException as e:
                # catastrophic error. bail.
                logging.error("Kafka REST request failed. " + e)

            logging.debug("Kafka REST response status code " + str(r.status_code) + ": " + str(r.text))
        else:
            logging.warning("KAFKA_REST_URL undefined. Tweet won't be archived to stream.")

        # ignore retweets
        if hasattr(status, 'quoted_status') | hasattr(status, 'retweeted_status'):
            logger.debug("ignoring retweet")
            return

        # save tweet data to log
        logger.info("Found mention in tweet id " + str(status.id) + " from " + status.user.screen_name + " created at " + str(status.created_at), 'info')
        rollbar.report_message("Found mention in tweet id " + str(status.id) + " from " + status.user.screen_name + " created at " + str(status.created_at), 'info')
        media = status.entities.get('media', [])
        received_tweet = {}
        received_tweet["id_str"] = status.id_str
        received_tweet["text"] = status.text
        received_tweet["favorite_count"] = status.favorite_count
        received_tweet["user_screen_name"] = status.user.screen_name
        received_tweet["user_statuses_count"] = status.user.statuses_count
        received_tweet["user_location"] = status.user.location
        received_tweet["followers_count"] = status.user.followers_count
        rollbar.report_message(json.dumps(received_tweet), 'info')

        if (len(media) > 0):
            logger.debug("Checking for unsafe features in image " + media[0]['media_url'])
            if detect_safe_search_uri(media[0]['media_url']) == False:
                logger.error("Ignoring tweet with unsafe image " + media[0]['media_url'])
                return
            logger.info("Downloading image " + media[0]['media_url'])
            media_url = media[0]['media_url']
            wget.download(media_url, '/root/stashorizer/image_raw.jpg')
            raw_image_exists = os.path.isfile('/root/stashorizer/image_raw.jpg')
            if raw_image_exists:
                logger.info("Applying mustache to image")

                # Use this docker run instead of mustache_make.main() in order to run this on a mac.
                # This is the easiest way to run cv2 libraries on mac. --Ian
                # os.system('docker run --rm -e ./.env -e DISPLAY=$DISPLAY -v /Users/idownard/development/stashorizer:/data dymat/opencv python /data/mustache_maker.py')

                # Use this command if you're on linux, where `pip install cv2` actually works (unlike mac)!
                mustache_maker.main()

                annotated_image_exists = os.path.isfile('/root/stashorizer/image_annotated.jpg')
                if annotated_image_exists:
                    reply_message = ".@%s %s" % (status.user.screen_name, "Nice stache. Please help me support men's mental health by donating to #Movember, https://mobro.co/iandownard. Thanks!")
                    logger.info("Sending tweet: \"" + reply_message + "\"")
                    try:
                        self.api.update_with_media('/root/stashorizer/image_annotated.jpg', status=reply_message, in_reply_to_status_id=status.id)
                    except:
                        logger.error("Failed to tweet mustache image")
                        rollbar.report_message("Failed to tweet mustache image.", 'error')
                        raise
                    finally:
                        os.remove('/root/stashorizer/image_raw.jpg')
                        os.remove('/root/stashorizer/image_annotated.jpg')
                else:
                    logger.info("No nose detected.")
                    reply_message = "@%s %s" % (status.user.screen_name, "I can't find a face in your image! Please help me support mental health for men by donating to Movember > https://mobro.co/iandownard")
                    logger.info("Sending tweet: \"" + reply_message + "\"")
                    try:
                        self.api.update_status(status=reply_message, in_reply_to_status_id=status.id)
                    except:
                        logger.error("Failed to tweet mustache image")
                        rollbar.report_message("Failed to tweet mustache image.", 'error')
                        raise
                    finally:
                        os.remove('/root/stashorizer/image_raw.jpg')
            else:
                logger.error("Failed to download image.")
                rollbar.report_message("Failed to download image.", 'error')

    def on_error(self, status_code):
        logger.error("Stream listener threw error code " + str(status_code))
        rollbar.report_message("Stream listener threw error code " + str(status_code))
        if status_code == 420:
            logger.error("Stream listener is rate limited. Try restarting again.")
            rollbar.report_message("Stream listener is rate limited. Try restarting again.")
            return False

    def on_timeout(self):
        logger.error("Stream listener timeout.")
        rollbar.report_message("Stream listener timeout.", 'error')
        logger.debug("Sleeping for 60 seconds...\n")
        time.sleep(60)
        return

# Authenticate to Twitter and start stream listener
def main():
    # Twitter API authentication
    username = os.environ.get('TW_USERNAME')
    consumer_key = os.environ.get('TW_CONSUMER_KEY')
    consumer_secret = os.environ.get('TW_CONSUMER_SECRET')
    access_key = os.environ.get('TW_ACCESS_TOKEN')
    access_secret = os.environ.get('TW_ACCESS_TOKEN_SECRET')

    logger.debug("authenticating to twitter")
    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_key, access_secret)
    stream_listener = SListener()
    stream_listener.init(API(auth_handler=auth, retry_count=10, retry_delay=5, retry_errors=5))
    stream = Stream(auth=auth, listener=stream_listener)
    stream.filter(track=['@'+username])

# initialize rollbar for logging
if __name__ == '__main__':
    # set up rollbar
    rollbar_configured = False
    rollbar_access_key = os.environ.get('ROLLBAR_ACCESS_KEY')
    rollbar.init(rollbar_access_key, 'production')
    rollbar_configured = True
    rollbar.report_message('Rollbar is configured correctly')

    try:
        main()
    except KeyboardInterrupt:
        logger.debug('keyboard_interrupt')
        quit()
    except:
        if rollbar_configured:
            rollbar.report_exc_info()
        raise
