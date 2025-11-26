# monger character config container
# Provides the character definition to other services via shared volume

FROM alpine:3.19

WORKDIR /monger

# Copy the character config
COPY monger.json ./

# On startup, copy config to the shared volume and stay alive
# This ensures the volume is populated before dependent services start
CMD cp -v /monger/monger.json /shared/ && echo "monger config deployed" && tail -f /dev/null

