# Infrastructure

Stage 0 infrastructure consists of the root `docker-compose.yml`, which starts
a local PostgreSQL service with a named volume and health check.

The FastAPI Dockerfile and API Compose service will be added in Stage 1.
Production container and deployment guidance belong to Stage 7. Kubernetes,
Kafka, and microservice infrastructure are deliberately outside the current
scope.
