# The McGeary et al. (2019) CNN, with its dependencies baked in.
#
# The CNN is TensorFlow 1.13 and Python 3.5, which cannot be installed
# alongside this project's Python 3.13. It therefore runs in its own
# container rather than in the project environment, and the image is
# built once so that every run afterwards is identical and needs no
# network access.
#
# Build (from the repo root, once):
#     docker build -f docker/cnn.Dockerfile -t mirpanel-cnn .
#
# The CNN source itself is NOT copied in. It is mounted at run time, so
# the image stays small and the repository is not duplicated.

FROM tensorflow/tensorflow:1.13.1-py3

# Pinned exactly as the CNN's own requirements.txt specifies. matplotlib
# and seaborn are imported by its utils module at import time even
# though inference never plots anything, so they are required.
RUN pip install --no-cache-dir \
        pandas==0.24.2 \
        scipy==1.2.1 \
        matplotlib==3.0.3 \
        seaborn==0.9.0

# matplotlib writes a font cache on first import; without a writable
# home it fails when the container runs as a non-root user.
# The directory must exist and be world-writable: matplotlib on
# Python 3.5 fails outright rather than creating it, and the container
# runs as the calling user rather than root.
RUN mkdir -p /tmp/mpl && chmod 1777 /tmp/mpl
ENV MPLCONFIGDIR=/tmp/mpl
ENV MPLBACKEND=Agg

WORKDIR /cnn
