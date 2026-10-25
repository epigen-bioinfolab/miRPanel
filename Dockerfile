# miRPanel, with everything it needs already built.
#
# Build (takes 40-70 minutes, once):
#   docker build -t ghcr.io/epigen-bioinfolab/mirpanel:v0.1.0 .
#
# Run:
#   docker run -d --name mirpanel -p 8000:8000 \
#     ghcr.io/epigen-bioinfolab/mirpanel:v0.1.0
#
# The reference database is baked in, so there is nothing to download
# afterwards and nothing to configure.

FROM r-base:4.5.3

# Everything the R packages compile against. These were worked out the hard
# way: a missing libuv or libcairo takes down a dozen packages that depend
# on them, and the errors name the dependants rather than the cause.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip \
      rnahybrid sqlite3 ca-certificates \
      build-essential cmake \
      libcurl4-openssl-dev libssl-dev libxml2-dev \
      libfontconfig1-dev libharfbuzz-dev libfribidi-dev libfreetype6-dev \
      libpng-dev libtiff5-dev libjpeg-dev \
      libglpk-dev libuv1-dev libcairo2-dev \
 && rm -rf /var/lib/apt/lists/*

# Bioconductor pinned to 3.22. Left to choose, an older release installs
# scanMiR 1.4.0 instead of 1.16.0 and gives different numbers.
RUN R -q -e 'install.packages("BiocManager", repos="https://cloud.r-project.org")' \
 && R -q -e 'BiocManager::install(version="3.22", ask=FALSE, update=FALSE)' \
 && R -q -e 'BiocManager::install(c("scanMiR","scanMiRData","miRBaseConverter",\
      "AnnotationHub","clusterProfiler","org.Hs.eg.db","org.Mm.eg.db",\
      "org.Rn.eg.db","org.Dm.eg.db"), version="3.22", ask=FALSE, update=FALSE)' \
 && R -q -e 'q(status = length(setdiff(c("scanMiR","scanMiRData","miRBaseConverter",\
      "AnnotationHub","clusterProfiler","org.Hs.eg.db","org.Mm.eg.db",\
      "org.Rn.eg.db","org.Dm.eg.db"), rownames(installed.packages()))))'

WORKDIR /app

# Python packages before the application code, so editing the code does not
# rebuild this layer.
COPY requirements.txt .
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY web/ /app/web/
COPY R/ /app/R/
COPY docker-entrypoint.sh /app/

# ADD unpacks a local tar.gz by itself. This is the 2 GB database, so it
# goes last: every layer above it stays cached when it changes.
RUN mkdir -p /app/data/processed /app/data/raw /app/data/uploads /app/data/tmp
ADD dist/mirpanel-data-v0.1.0.tar.gz /app/data/

RUN chmod +x /app/docker-entrypoint.sh \
 && python3 /app/scripts/check_env.py

EXPOSE 8000
CMD ["/app/docker-entrypoint.sh"]
