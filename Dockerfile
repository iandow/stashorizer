FROM dymat/opencv:latest

WORKDIR /root/
RUN apt-get update && \
	apt-get upgrade -y && \
	apt-get install -y --no-install-recommends git python-setuptools && \
    git clone https://github.com/iandow/stashorizer && \
    pip install -r stashorizer/requirements.txt

ENTRYPOINT ["python", "/root/stashorizer/streaming_mustache_bot.py"]

#WORKDIR stashorizer
#RUN pip install -r requirements.txt

