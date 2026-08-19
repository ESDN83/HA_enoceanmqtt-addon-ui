ARG BUILD_FROM
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install requirements
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-setuptools \
    py3-wheel \
    gcc \
    musl-dev \
    python3-dev \
    libxml2-dev \
    libxslt-dev

# Copy application files
COPY rootfs /

# Copy the add-on manifest so the app can read its version at runtime
# (single source of truth for the UI/API version, see app_version.py)
COPY config.yaml /app/config.yaml

# Install Python dependencies, from PyPI first.
#
# The base image's /etc/pip.conf adds wheels.home-assistant.io as an extra
# index, and pip will happily fetch a pure-python wheel from there. That mirror
# is periodically unusable: measured at 1.5 kB/s, 87 seconds for a 133 kB file,
# with stalls long enough to blow any read timeout. It failed the build at
# --timeout=120 and again at --timeout=300, so raising the limits is not a fix.
#
# PIP_CONFIG_FILE=/dev/null drops that config, --index-url pins PyPI, and
# --prefer-binary is carried over from the config we just discarded. The same
# requirements install in 17 seconds this way, with only paho-mqtt built from
# its sdist (pure python, no compiler needed).
#
# The fallback keeps the mirror for what it is actually for: an architecture
# where PyPI has no musllinux wheel, armv7 lxml being the likely case. It then
# either finds one there or compiles, which is why the toolchain above stays.
RUN PIP_CONFIG_FILE=/dev/null pip3 install --no-cache-dir \
      --index-url https://pypi.org/simple --prefer-binary \
      --timeout=120 --retries=5 -r /app/requirements.txt \
 || pip3 install --no-cache-dir --timeout=300 --retries=10 -r /app/requirements.txt

# Set working directory
WORKDIR /app

# Make run script executable
RUN chmod a+x /run.sh

# Run
CMD ["/run.sh"]
