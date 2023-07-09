FROM quay.io/unstructured-io/unstructured-api:latest

USER root
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
USER notebook-user

ENTRYPOINT ["/entrypoint.sh"]
