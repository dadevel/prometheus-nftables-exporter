FROM python:3-alpine
WORKDIR /app
COPY ./main.py ./bin/nftables-exporter
COPY ./requirements.txt .
RUN apk add --no-cache nftables
RUN pip install -r ./requirements.txt && rm ./requirements.txt
ENV PATH /app/bin:$PATH
ENTRYPOINT ["nftables-exporter"]
EXPOSE 9630/tcp

