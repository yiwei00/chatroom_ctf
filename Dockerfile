FROM ubuntu:jammy
RUN apt update && apt install -y python3
RUN mkdir -p /app/logs

EXPOSE 5000

COPY vulnerable_app/*.py /app
COPY log.txt /app/logs

# Add command here to plant the flag
# Since the vulnerability allows RCE, and a reverse shell with root privelege is possible
# it doesn't matter where the flag is located
# COPY flag.txt /
# RUN echo "flag" >> /etc/shadow

WORKDIR /app

ENTRYPOINT [ "/usr/bin/python3", "-u", "chatroom.py", "-p", "5000", "-l", "log.txt", "--log-dir", "/app/logs"]
