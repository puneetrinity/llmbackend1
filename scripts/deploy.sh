#!/bin/bash

set -e

# Configuration
NAMESPACE="llm-search-backend"
IMAGE_NAME="ghcr.io/yourusername/llm-search-backend"
ENVIRONMENT=${1:-staging}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# Function to check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        error "kubectl is not installed or not in PATH"
        exit 1
    fi
}

# Function to check if cluster is accessible
check_cluster() {
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    log "Connected to Kubernetes cluster"
}

# Function to create namespace if it doesn't exist
create_namespace() {
    if ! kubectl get namespace $NAMESPACE &> /dev/null; then
        log "Creating namespace: $NAMESPACE"
        kubectl apply -f kubernetes/namespace.yaml
    else
        log "Namespace $NAMESPACE already exists"
    fi
}

# Function to apply configurations
apply_configs() {
    log "Applying ConfigMaps..."
    kubectl apply -f kubernetes/configmap.yaml

    log "Applying PersistentVolumeClaims..."
    kubectl apply -f kubernetes/pvc.yaml
}

# Function to deploy application
deploy_app() {
    log "Deploying application..."
    
    # Update image tag if provided
    if [ -n "$2" ]; then
        IMAGE_TAG=$2
        log "Using image tag: $IMAGE_TAG"
        sed -i "s|image: $IMAGE_NAME:.*|image: $IMAGE_NAME:$IMAGE_TAG|g" kubernetes/deployment.yaml
    fi
    
    kubectl apply -f kubernetes/deployment.yaml
    kubectl apply -f kubernetes/service.yaml
    
    if [ "$ENVIRONMENT" = "production" ]; then
        log "Applying ingress for production..."
        kubectl apply -f kubernetes/ingress.yaml
    fi
}

# Function to wait for deployment
wait_for_deployment() {
    log "Waiting for deployment to be ready..."
    kubectl rollout status deployment/llm-search-api -n $NAMESPACE --timeout=300s
    
    if [ $? -eq 0 ]; then
        log "Deployment successful!"
    else
        error "Deployment failed or timed out"
        exit 1
    fi
}

# Function to run post-deployment tasks
post_deploy() {
    log "Running post-deployment tasks..."
    
    # Run database migrations
    POD_NAME=$(kubectl get pods -n $NAMESPACE -l app=llm-search-api -o jsonpath='{.items[0].metadata.name}')
    if [ -n "$POD_NAME" ]; then
        log "Running database migrations..."
        kubectl exec -n $NAMESPACE $POD_NAME -- python scripts/manage_migrations.py upgrade
    else
        warn "Could not find pod to run migrations"
    fi
}

# Function to show deployment status
show_status() {
    log "Deployment Status:"
    kubectl get pods -n $NAMESPACE
    kubectl get services -n $NAMESPACE
    
    if [ "$ENVIRONMENT" = "production" ]; then
        kubectl get ingress -n $NAMESPACE
    fi
}

# Main deployment function
main() {
    log "Starting deployment to $ENVIRONMENT environment..."
    
    check_kubectl
    check_cluster
    create_namespace
    apply_configs
    deploy_app $ENVIRONMENT $2
    wait_for_deployment
    post_deploy
    show_status
    
    log "Deployment completed successfully!"
    
    if [ "$ENVIRONMENT" = "production" ]; then
        log "Production deployment complete. Check your domain for the live application."
    else
        log "To access the application locally, run:"
        log "kubectl port-forward service/llm-search-api-service 8000:80 -n $NAMESPACE"
    fi
}

# Show usage if no arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <environment> [image-tag]"
    echo "Environments: staging, production"
    echo "Example: $0 staging v1.0.0"
    exit 1
fi

main "$@"
