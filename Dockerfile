FROM python:3-alpine
RUN apk add --no-cache setpriv nftables
WORKDIR /app
COPY ./main.py ./bin/nftables-exporter
COPY ./requirements.txt .
RUN pip install -r ./requirements.txt && rm ./requirements.txt
ENV PATH /app/bin:$PATH
ENTRYPOINT ["/usr/bin/setpriv", "--reuid", "65534", "--regid", "65534", "--clear-groups", "--no-new-privs", "--bounding-set", "-all,+net_admin", "--ambient-caps", "-all,+net_admin", "--inh-caps", "-all,+net_admin", "nftables-exporter"]

