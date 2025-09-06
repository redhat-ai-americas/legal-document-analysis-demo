# OpenShift Deployment Guide

## Overview

This guide covers deploying the Legal Document Analysis platform to Red Hat OpenShift. The architecture separates the UI (Streamlit) and backend API (FastAPI) into separate pods for scalability and maintainability.

## Architecture

```
┌─────────────────────────────────────────────┐
│           OpenShift Cluster                  │
│                                              │
│  ┌──────────────┐    ┌──────────────┐      │
│  │   UI Pod     │───▶│ Backend Pod  │      │
│  │ (Streamlit)  │    │  (FastAPI)   │      │
│  └──────────────┘    └──────────────┘      │
│         │                    │              │
│         └────────┬───────────┘              │
│                  │                          │
│          ┌───────▼────────┐                │
│          │  Shared PVCs   │                │
│          │ - Data         │                │
│          │ - Logs         │                │
│          │ - Samples      │                │
│          └────────────────┘                │
└─────────────────────────────────────────────┘
                    │
                    ▼
            External Routes
         - UI: https://app.domain
         - API: https://app.domain/api
```

## Prerequisites

1. **OpenShift CLI (oc)**
   ```bash
   # Download from https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
   oc version
   ```

2. **Cluster Access**
   ```bash
   oc login <cluster-url> -u <username>
   ```

3. **Git Repository**
   - Push code to Git repository accessible from OpenShift
   - Update `manifests/base/buildconfig.yaml` with your repo URL

## Quick Deployment

### 1. One-Command Deployment

```bash
# Make deploy script executable
chmod +x deploy.sh

# Deploy to development
./deploy.sh dev

# Deploy to production
./deploy.sh prod
```

### 2. Manual Deployment Steps

```bash
# Create namespace
oc apply -f manifests/base/namespace.yaml

# Deploy all resources
oc apply -k manifests/base/

# Or for specific environment
oc apply -k manifests/overlays/dev/
```

## Configuration

### Update Secrets

```bash
# Edit secret with your API credentials
oc edit secret legal-doc-secrets -n legal-doc-analysis

# Add your actual values:
# GRANITE_INSTRUCT_API_KEY: <base64-encoded-key>
# GRANITE_INSTRUCT_URL: <base64-encoded-url>
```

### Environment-Specific Configuration

#### Development (manifests/overlays/dev/)
- Single replica for each service
- Lower resource limits
- Debug logging enabled
- Namespace: legal-doc-analysis-dev

#### Production (manifests/overlays/prod/)
- Multiple replicas with HPA
- Higher resource limits
- Selective logging
- Namespace: legal-doc-analysis-prod

## Building Images

### Option 1: OpenShift Build (Recommended)

```bash
# Start backend build
oc start-build legal-doc-backend --follow

# Start UI build
oc start-build legal-doc-ui --follow
```

### Option 2: Local Build and Push

```bash
# Build locally with Podman
podman build --platform linux/amd64 -t legal-doc-backend:latest -f Containerfile.backend .
podman build --platform linux/amd64 -t legal-doc-ui:latest -f Containerfile.ui .

# Tag for OpenShift registry
podman tag legal-doc-backend:latest default-route-openshift-image-registry.apps.cluster/legal-doc-analysis/legal-doc-backend:latest
podman tag legal-doc-ui:latest default-route-openshift-image-registry.apps.cluster/legal-doc-analysis/legal-doc-ui:latest

# Push to registry
podman push default-route-openshift-image-registry.apps.cluster/legal-doc-analysis/legal-doc-backend:latest
podman push default-route-openshift-image-registry.apps.cluster/legal-doc-analysis/legal-doc-ui:latest
```

## Persistent Storage

The deployment uses three PVCs:

1. **legal-doc-data** (10Gi, RWX)
   - Analysis outputs
   - Uploaded documents
   - Temporary files

2. **legal-doc-logs** (5Gi, RWX)
   - Application logs
   - Audit trails

3. **legal-doc-samples** (2Gi, ROX)
   - Sample documents
   - Reference templates

### Populate Sample Data

```bash
# Create a pod to upload sample documents
oc run sample-loader --image=registry.redhat.io/ubi9/ubi-minimal \
  --rm -it --restart=Never \
  -- /bin/bash

# Inside the pod, copy your sample documents to /app/sample_documents
```

## Monitoring

### View Logs

```bash
# Backend logs
oc logs -f deployment/legal-doc-backend

# UI logs
oc logs -f deployment/legal-doc-ui

# All pods
oc logs -l app=legal-doc-analysis --tail=100
```

### Check Pod Status

```bash
# View all pods
oc get pods -n legal-doc-analysis

# Describe pod for details
oc describe pod <pod-name>

# Get events
oc get events --sort-by='.lastTimestamp'
```

### Resource Usage

```bash
# View resource usage
oc adm top pods

# Check HPA status (production)
oc get hpa
```

## Scaling

### Manual Scaling

```bash
# Scale backend
oc scale deployment/legal-doc-backend --replicas=3

# Scale UI
oc scale deployment/legal-doc-ui --replicas=2
```

### Auto-Scaling (Production)

HPA automatically scales based on CPU/memory:
- Backend: 2-10 replicas
- UI: 1-5 replicas

## Troubleshooting

### Common Issues

1. **Pods not starting**
   ```bash
   # Check events
   oc describe pod <pod-name>
   
   # Check secrets
   oc get secret legal-doc-secrets -o yaml
   ```

2. **Image pull errors**
   ```bash
   # Check image stream
   oc get is
   
   # Trigger new build
   oc start-build legal-doc-backend
   ```

3. **Storage issues**
   ```bash
   # Check PVC status
   oc get pvc
   
   # Check available storage classes
   oc get storageclass
   ```

4. **Route not accessible**
   ```bash
   # Get route URL
   oc get route legal-doc-ui
   
   # Check service
   oc get svc
   ```

### Port Forwarding (Development)

```bash
# Forward UI locally
oc port-forward svc/legal-doc-ui 8501:8501

# Forward API locally
oc port-forward svc/legal-doc-backend 8080:8080

# Access at http://localhost:8501 and http://localhost:8080
```

## Security Considerations

1. **Network Policies**
   - Restrict pod-to-pod communication
   - Allow only necessary ingress/egress

2. **Secrets Management**
   - Use OpenShift secrets for API keys
   - Consider integrating with HashiCorp Vault

3. **RBAC**
   - Service accounts have minimal permissions
   - Review and adjust as needed

4. **Security Context**
   - Pods run as non-root
   - Capabilities dropped
   - Seccomp profiles enabled

## CI/CD Integration

### GitOps with ArgoCD

```yaml
# argocd-app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: legal-doc-analysis
  namespace: openshift-gitops
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/legal-document-analysis
    targetRevision: main
    path: manifests/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: legal-doc-analysis-prod
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### Tekton Pipeline

```yaml
# Create pipeline for automated builds
oc create -f manifests/tekton/pipeline.yaml
```

## Backup and Recovery

### Backup PVCs

```bash
# Create backup job
oc create job backup-$(date +%Y%m%d) \
  --from=cronjob/backup-job

# Verify backup
oc logs job/backup-$(date +%Y%m%d)
```

### Restore Process

1. Scale down deployments
2. Restore PVC data
3. Scale up deployments

## Performance Tuning

### Backend Optimization
- Increase worker processes for uvicorn
- Adjust connection pool settings
- Enable response caching

### UI Optimization
- Enable Streamlit caching
- Optimize session state management
- Use CDN for static assets

## Maintenance

### Rolling Updates

```bash
# Update image
oc set image deployment/legal-doc-backend \
  backend=image-registry.openshift-image-registry.svc:5000/legal-doc-analysis/legal-doc-backend:v2

# Monitor rollout
oc rollout status deployment/legal-doc-backend
```

### Database Migrations (if applicable)

```bash
# Run migration job
oc create job migrate-$(date +%Y%m%d) \
  --from=cronjob/migration-job
```

## Support

For issues or questions:
1. Check pod logs: `oc logs -f <pod-name>`
2. Review events: `oc get events`
3. Consult OpenShift documentation
4. File issues in the project repository