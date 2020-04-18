FROM python:3-alpine
# nftables in alpine 3.11 was built without json support
RUN apk add --no-cache --repository http://nl.alpinelinux.org/alpine/edge/main nftables
WORKDIR /app
COPY ./main.py ./bin/prometheus-nftables-exporter
COPY ./requirements.txt .
RUN pip install -r ./requirements.txt && rm ./requirements.txt
USER nobody:nogroup
ENV PATH /app/bin:$PATH
ENTRYPOINT ["prometheus-nftables-exporter"]

