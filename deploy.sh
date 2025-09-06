#!/bin/bash

# OpenShift Deployment Script for Legal Document Analysis Platform

set -e

# Configuration
PROJECT_NAME="legal-doc-analysis"
GIT_REPO="https://github.com/your-org/legal-document-analysis.git"
ENVIRONMENT="${1:-dev}"  # dev, staging, or prod

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Legal Document Analysis Platform - OpenShift Deployment${NC}"
echo "Environment: $ENVIRONMENT"
echo "==========================================="

# Function to check if logged into OpenShift
check_login() {
    if ! oc whoami &> /dev/null; then
        echo -e "${RED}Error: Not logged into OpenShift${NC}"
        echo "Please run: oc login <cluster-url>"
        exit 1
    fi
    echo -e "${GREEN}✓ Logged in as: $(oc whoami)${NC}"
}

# Function to create/switch to project
setup_project() {
    local project_name="${PROJECT_NAME}-${ENVIRONMENT}"
    if [ "$ENVIRONMENT" == "base" ]; then
        project_name="${PROJECT_NAME}"
    fi
    
    if oc project "$project_name" &> /dev/null; then
        echo -e "${GREEN}✓ Switched to project: $project_name${NC}"
    else
        echo -e "${YELLOW}Creating project: $project_name${NC}"
        oc new-project "$project_name"
    fi
}

# Function to update secrets
update_secrets() {
    echo -e "${YELLOW}Updating secrets...${NC}"
    
    # Check if secrets exist
    if oc get secret legal-doc-secrets &> /dev/null; then
        echo "Secret exists. Update with your API credentials:"
        echo "oc edit secret legal-doc-secrets"
    else
        echo -e "${YELLOW}Creating placeholder secret. Please update with actual values.${NC}"
    fi
}

# Function to build images
build_images() {
    echo -e "${YELLOW}Building container images...${NC}"
    
    # Trigger builds
    if oc get bc legal-doc-backend &> /dev/null; then
        oc start-build legal-doc-backend --follow
    fi
    
    if oc get bc legal-doc-ui &> /dev/null; then
        oc start-build legal-doc-ui --follow
    fi
}

# Function to deploy using Kustomize
deploy_kustomize() {
    echo -e "${YELLOW}Deploying with Kustomize...${NC}"
    
    if [ "$ENVIRONMENT" == "base" ]; then
        oc apply -k manifests/base/
    else
        oc apply -k manifests/overlays/${ENVIRONMENT}/
    fi
    
    echo -e "${GREEN}✓ Resources deployed${NC}"
}

# Function to wait for rollout
wait_for_rollout() {
    echo -e "${YELLOW}Waiting for deployments to be ready...${NC}"
    
    local prefix=""
    if [ "$ENVIRONMENT" != "base" ]; then
        prefix="${ENVIRONMENT}-"
    fi
    
    oc rollout status deployment/${prefix}legal-doc-backend -w
    oc rollout status deployment/${prefix}legal-doc-ui -w
    
    echo -e "${GREEN}✓ All deployments ready${NC}"
}

# Function to get routes
get_routes() {
    echo -e "${GREEN}Application URLs:${NC}"
    echo "==========================================="
    
    local ui_route=$(oc get route legal-doc-ui -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not found")
    local api_route=$(oc get route legal-doc-api -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not found")
    
    echo -e "UI: ${GREEN}https://${ui_route}${NC}"
    echo -e "API: ${GREEN}https://${api_route}/api${NC}"
}

# Function to setup sample data PVC
setup_sample_data() {
    echo -e "${YELLOW}Setting up sample data...${NC}"
    
    # Create a job to copy sample data to PVC
    cat <<EOF | oc apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: sample-data-loader
spec:
  template:
    spec:
      containers:
      - name: loader
        image: registry.redhat.io/ubi9/ubi-minimal
        command: ["/bin/sh", "-c"]
        args:
          - |
            echo "Sample data would be copied here"
            # In production, you would copy actual sample documents
        volumeMounts:
        - name: samples
          mountPath: /data
      volumes:
      - name: samples
        persistentVolumeClaim:
          claimName: legal-doc-samples
      restartPolicy: Never
EOF
}

# Main deployment flow
main() {
    echo -e "${GREEN}Starting deployment...${NC}"
    
    # Check prerequisites
    check_login
    
    # Setup project
    setup_project
    
    # Deploy resources
    deploy_kustomize
    
    # Update secrets reminder
    update_secrets
    
    # Build images if BuildConfigs exist
    if oc get bc &> /dev/null; then
        build_images
    fi
    
    # Setup sample data
    if [ "$ENVIRONMENT" == "dev" ]; then
        setup_sample_data
    fi
    
    # Wait for rollout
    wait_for_rollout
    
    # Display routes
    get_routes
    
    echo ""
    echo -e "${GREEN}Deployment complete!${NC}"
    echo "==========================================="
    echo "Next steps:"
    echo "1. Update secrets with actual API credentials:"
    echo "   oc edit secret legal-doc-secrets"
    echo "2. Verify the application is working by visiting the UI URL"
    echo "3. Check pod logs if needed:"
    echo "   oc logs -f deployment/legal-doc-backend"
    echo "   oc logs -f deployment/legal-doc-ui"
}

# Run main function
main

# Additional helper commands
echo ""
echo "Useful commands:"
echo "---------------"
echo "View pods:        oc get pods"
echo "View logs:        oc logs -f <pod-name>"
echo "Port forward UI:  oc port-forward svc/legal-doc-ui 8501:8501"
echo "Port forward API: oc port-forward svc/legal-doc-backend 8080:8080"
echo "Scale deployment: oc scale deployment/legal-doc-backend --replicas=3"