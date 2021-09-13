FROM ubuntu:20.04

ENV APPDIR /usr/src/app
WORKDIR $APPDIR

COPY src/istio_job_cleaner.py $APPDIR
COPY requirements.txt $APPDIR

RUN apt update && apt upgrade -y && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 install -r requirements.txt && \
    rm $APPDIR/requirements.txt

RUN useradd cleaner && groupadd cleaner
USER cleaner:cleaner

ENTRYPOINT [ "python3", "-m", "istio_job_cleaner" ]