FROM dymat/opencv:latest


RUN git clone https://github.com/iandow/stashorizer \
    python streaming_mustache_bot.py