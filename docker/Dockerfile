# syntax=docker/dockerfile:1
FROM debian:bookworm-slim
ARG APT_MIRROR=
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 HOME=/home/agent USER=agent \
    XDG_RUNTIME_DIR=/tmp/runtime-agent \
    GTK_MODULES=gail:atk-bridge QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 \
    NO_AT_BRIDGE=0 MOZ_ACCESSIBILITY_AT_ENABLED=1 \
    LANG=C.UTF-8 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then cp /run/secrets/proxy_ca /usr/local/share/ca-certificates/session.crt; fi; \
    if [ -n "$APT_MIRROR" ]; then sed -i "s|deb.debian.org|$APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources; fi; \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates python3 python3-venv python3-pyatspi python3-gi \
    gir1.2-gtk-3.0 at-spi2-core dbus-x11 xvfb xfce4 xfce4-terminal mousepad \
    firefox-esr x11vnc novnc websockify supervisor xdotool xclip wmctrl x11-utils \
    fonts-noto-cjk curl tini procps \
    && update-ca-certificates \
    && rm -f /usr/local/share/ca-certificates/session.crt \
    && update-ca-certificates --fresh \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 -s /bin/bash agent \
    && mkdir -p /workspace /tmp/runtime-agent \
    && chown agent:agent /workspace /tmp/runtime-agent \
    && chmod 700 /tmp/runtime-agent \
    && python3 -m venv --system-site-packages /opt/venv
WORKDIR /opt/nekoworker
COPY pyproject.toml README.md requirements.lock ./
COPY src ./src
RUN --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    /opt/venv/bin/pip install --no-cache-dir --index-url "$PIP_INDEX_URL" -r requirements.lock \
    && /opt/venv/bin/pip install --no-cache-dir --no-deps .
COPY docker/firefox/policies.json /usr/lib/firefox-esr/distribution/policies.json
COPY docker/entrypoint.sh /usr/local/bin/nekoworker-entrypoint
COPY docker/supervisord.conf /etc/nekoworker-supervisord.conf
ENV PATH=/opt/venv/bin:$PATH
USER agent
WORKDIR /workspace
EXPOSE 8080 6080
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=4 \
    CMD curl -fsS http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/nekoworker-entrypoint"]
