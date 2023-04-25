FROM ubuntu:jammy
RUN apt update && apt install -y python3
RUN mkdir -p /app/logs

EXPOSE 5000

COPY vulnerable_app/*.py /app
COPY log.txt /app/logs

# Add command here to copy the flag file into the container
# Since the vulnerability allows RCE, a reverse shell can be used to copy the flag
# so the flag can be copied to anywhere in the container readable by the user
# COPY flag.txt /

WORKDIR /app

ENTRYPOINT [ "/usr/bin/python3", "-u", "chatroom.py", "-p", "5000", "-l", "log.txt", "--log-dir", "/app/logs"]
