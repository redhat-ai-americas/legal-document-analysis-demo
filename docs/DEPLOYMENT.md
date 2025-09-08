# Legal Document Analysis - OpenShift Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Legal Document Analysis system to Red Hat OpenShift. The system consists of three main components:

1. **Docling PDF Processor** - Handles PDF to Markdown conversion
2. **Backend API** - Manages document analysis workflows
3. **Web UI** - Streamlit-based user interface

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     OpenShift Cluster                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────┐ │
│  │   Web UI     │────▶│ Backend API  │────▶│ Docling │ │
│  │  (Streamlit) │     │  (FastAPI)   │     │  Service│ │
│  └──────────────┘     └──────────────┘     └─────────┘ │
│                                                          │
│  External Routes:                                        │
│  - UI: https://legal-doc-ui-*.apps.cluster.com          │
│  - API: https://legal-doc-api-*.apps.cluster.com        │
│  - Docling: https://docling-pdf-processor-*.apps.cluster.com │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. OpenShift CLI and Access
```bash
# Install OpenShift CLI (oc)
# macOS:
brew install openshift-cli

# Linux:
wget https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-client-linux.tar.gz
tar xvf openshift-client-linux.tar.gz
sudo mv oc kubectl /usr/local/bin/

# Login to your OpenShift cluster
oc login --token=<your-token> --server=<your-server-url>
```

### 2. Create Project/Namespace
```bash
# Create a new project (or use existing)
oc new-project legal-doc-analysis

# Or switch to existing project
oc project legal-doc-analysis
```

### 3. Deploy Docling PDF Processor Service

The Docling PDF processor is a prerequisite service that must be deployed first.

```bash
# Clone the Docling service repository
git clone https://github.com/redhat-ai-americas/docling-service.git
cd docling-service

# Deploy to OpenShift
oc apply -f manifests/

# Wait for deployment to be ready
oc rollout status deployment/docling-pdf-processor

# Get the service URL
oc get route docling-pdf-processor -o jsonpath='{.spec.host}'
```

**Note:** The Docling service handles PDF to Markdown conversion and must be running before deploying the main application.

## Configuration

### 1. Create ConfigMap with API Keys

Create a ConfigMap with your API keys and configuration:

```yaml
# config/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: legal-doc-config
  labels:
    app: legal-doc-analysis
data:
  # Granite API Configuration
  GRANITE_INSTRUCT_API_KEY: "your-api-key-here"
  GRANITE_INSTRUCT_URL: "https://your-granite-endpoint"
  GRANITE_INSTRUCT_MODEL_NAME: "granite-3-3-8b-instruct"
  
  # Docling Service (internal URL)
  DOCLING_URL: "http://docling-pdf-processor:8080"
  
  # Feature Flags
  RULES_MODE_ENABLED: "true"
  USE_ENHANCED_ATTRIBUTION: "true"
  USE_TEMPLATE_EXCEL: "true"
  FORCE_GRANITE: "true"
  
  # Other settings
  LOG_LEVEL: "INFO"
  PYTHONUNBUFFERED: "1"
```

Apply the ConfigMap:
```bash
oc apply -f config/configmap.yaml
```

### 2. Create Secrets (if needed)

For sensitive data like API keys, use Secrets instead:

```bash
oc create secret generic legal-doc-secrets \
  --from-literal=GRANITE_INSTRUCT_API_KEY=your-api-key-here
```

## Deployment Steps

### Quick Deploy (Make)

For quick deployment of all components:

```bash
# Deploy everything
make deploy

# Check deployment status
make status

# View logs
make logs

# Clean up deployment
make clean
```

### Manual Deployment

#### 1. Build and Deploy Backend API

```bash
# Build the backend container
podman build --platform linux/amd64 -t legal-doc-backend:latest -f Containerfile.backend .

# Push to OpenShift internal registry
oc new-build --binary --name=legal-doc-backend
oc start-build legal-doc-backend --from-dir=. --follow

# Deploy backend
oc apply -f manifests/backend/

# Expose the service
oc expose service legal-doc-backend
```

#### 2. Build and Deploy Web UI

```bash
# Build the UI container
podman build --platform linux/amd64 -t legal-doc-ui:latest -f Containerfile.ui .

# Push to OpenShift internal registry
oc new-build --binary --name=legal-doc-ui
oc start-build legal-doc-ui --from-dir=. --follow

# Deploy UI
oc apply -f manifests/ui/

# Expose the service
oc expose service legal-doc-ui
```

## Verification

### 1. Check Pod Status
```bash
# View all pods
oc get pods

# Expected output:
NAME                                    READY   STATUS    RESTARTS   AGE
docling-pdf-processor-xxx               1/1     Running   0          10m
legal-doc-backend-xxx                   1/1     Running   0          5m
legal-doc-ui-xxx                        1/1     Running   0          2m
```

### 2. Check Service Endpoints
```bash
# Get all routes
oc get routes

# Test backend health
curl https://legal-doc-api-<namespace>.apps.<cluster-domain>/health

# Test Docling service
curl https://docling-pdf-processor-<namespace>.apps.<cluster-domain>/docs
```

### 3. Access the Web UI
```bash
# Get UI URL
oc get route legal-doc-ui -o jsonpath='{.spec.host}'

# Open in browser
open https://legal-doc-ui-<namespace>.apps.<cluster-domain>
```

## Monitoring and Logs

### View Application Logs
```bash
# Backend logs
oc logs -f deployment/legal-doc-backend

# UI logs
oc logs -f deployment/legal-doc-ui

# Docling processor logs
oc logs -f deployment/docling-pdf-processor
```

### Check Resource Usage
```bash
# Pod resource usage
oc adm top pods

# Node resource usage
oc adm top nodes
```

## Troubleshooting

### Common Issues

#### 1. Pods Not Starting
```bash
# Check pod events
oc describe pod <pod-name>

# Check for resource limits
oc get resourcequota
oc get limitrange
```

#### 2. API Connection Issues
```bash
# Test internal service connectivity
oc exec -it <ui-pod> -- curl http://legal-doc-backend:8080/health

# Check service endpoints
oc get endpoints
```

#### 3. Docling Service Issues
```bash
# Check if Docling is accessible internally
oc exec -it <backend-pod> -- curl http://docling-pdf-processor:8080/docs

# Check Docling logs for errors
oc logs deployment/docling-pdf-processor | grep ERROR
```

### Debug Commands
```bash
# Get into a pod shell
oc exec -it <pod-name> -- /bin/bash

# Port forward for local testing
oc port-forward service/legal-doc-backend 8080:8080

# View recent events
oc get events --sort-by='.lastTimestamp'
```

## Scaling

### Manual Scaling
```bash
# Scale backend
oc scale deployment legal-doc-backend --replicas=3

# Scale UI
oc scale deployment legal-doc-ui --replicas=2
```

### Auto-scaling
```yaml
# Create HorizontalPodAutoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: legal-doc-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: legal-doc-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Security Considerations

1. **Network Policies**: Implement network policies to restrict traffic between pods
2. **RBAC**: Use proper service accounts with minimal permissions
3. **Secrets Management**: Store sensitive data in OpenShift Secrets or external vault
4. **Image Security**: Scan container images for vulnerabilities
5. **TLS/SSL**: Ensure all routes use edge termination with redirect

## Backup and Recovery

### Backup Application Data
```bash
# Backup PVCs
oc get pvc
oc create backup <backup-name> --include-resources=pvc

# Export application configuration
oc get all -o yaml > backup-config.yaml
```

### Restore from Backup
```bash
# Restore configuration
oc apply -f backup-config.yaml

# Restore PVCs
oc restore <backup-name>
```

## Maintenance

### Update Application
```bash
# Update backend
oc start-build legal-doc-backend --from-dir=. --follow
oc rollout restart deployment/legal-doc-backend

# Update UI
oc start-build legal-doc-ui --from-dir=. --follow
oc rollout restart deployment/legal-doc-ui
```

### Clean Up Resources
```bash
# Delete all application resources
make clean

# Or manually
oc delete all -l app=legal-doc-analysis
oc delete configmap legal-doc-config
oc delete secret legal-doc-secrets
```

## Support

For issues or questions:
1. Check application logs: `oc logs -f deployment/<component-name>`
2. Review events: `oc get events`
3. Check pod status: `oc describe pod <pod-name>`
4. Consult the [troubleshooting section](#troubleshooting)

## Related Documentation

- [Docling Service Repository](https://github.com/redhat-ai-americas/docling-service)
- [OpenShift Documentation](https://docs.openshift.com/)
- [Application README](../README.md)