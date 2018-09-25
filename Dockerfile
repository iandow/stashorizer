FROM dymat/opencv:latest

RUN git clone https://github.com/iandow/stashorizer \
    pip install -r requirements.txt --user --upgrade

ENTRYPOINT ["sh", "-c", "python streaming_mustache_bot.py"]