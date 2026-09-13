FROM python:3.13-slim-trixie

WORKDIR /app

# R + RNAhybrid
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        r-base-core \
        rnahybrid \
        ca-certificates \
        wget \
    && rm -rf /var/lib/apt/lists/*

# R/Bioconductor packages required by enrichment
RUN R -e "install.packages('BiocManager', repos='https://cloud.r-project.org')" \
    && R -e "BiocManager::install(c('clusterProfiler', 'org.Hs.eg.db'), ask=FALSE, update=FALSE)"

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src /app/src
COPY scripts /app/scripts
COPY web /app/web
COPY R /app/R
COPY data /app/data

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

