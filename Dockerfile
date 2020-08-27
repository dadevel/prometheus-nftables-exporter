FROM python:3-alpine
WORKDIR /app
COPY ./main.py ./bin/nftables-exporter
COPY ./requirements.txt .
RUN apk add --no-cache libcap nftables && \
setcap -q cap_net_admin+ep /usr/sbin/nft && \
apk del --purge --rdepends libcap && \
rm -rf /etc/nftables*
RUN pip install -r ./requirements.txt && rm ./requirements.txt
RUN mkdir ./data && chown -R nobody:nobody ./data
ENV PATH /app/bin:$PATH
ENTRYPOINT ["nftables-exporter"]
USER nobody:nobody
VOLUME /app/data
EXPOSE 9630/tcp

