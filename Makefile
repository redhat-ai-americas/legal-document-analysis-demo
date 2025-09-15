PY=python3
PIP=pip
VENV=.venv
APP=legal-document-analysis

.PHONY: venv install test ui lint clean run batch analyze verify

venv:
	$(PY) -m venv $(VENV)
	. $(VENV)/bin/activate && $(PIP) install -U pip
	. $(VENV)/bin/activate && $(PIP) install -r requirements.txt

install: venv

test:
	. $(VENV)/bin/activate && pytest -q

ui:
	./start_ui.sh

run:
	. $(VENV)/bin/activate && $(PY) scripts/main.py

batch:
	. $(VENV)/bin/activate && $(PY) scripts/batch_process.py

analyze:
	. $(VENV)/bin/activate && $(PY) scripts/analyze_run.py

verify:
	. $(VENV)/bin/activate && $(PY) scripts/verify_reference_fix.py

lint:
	. $(VENV)/bin/activate && ruff check . || true

clean:
	rm -rf $(VENV) __pycache__ */__pycache__ .pytest_cache

# ==================== OpenShift Deployment ====================

# Check if logged into OpenShift
.PHONY: oc-check
oc-check:
	@oc whoami >/dev/null 2>&1 || (echo "Error: Not logged into OpenShift. Run 'oc login' first." && exit 1)
	@echo "✓ Logged into OpenShift as: $$(oc whoami)"
	@echo "✓ Current project: $$(oc project -q)"

# Deploy prerequisites (Docling service)
.PHONY: deploy-prereq
deploy-prereq: oc-check
	@echo "📦 Checking Docling PDF Processor..."
	@if oc get deployment docling-pdf-processor >/dev/null 2>&1; then \
		echo "✓ Docling PDF Processor already deployed"; \
	else \
		echo "⚠️  Docling PDF Processor not found!"; \
		echo "Please deploy it first from: https://github.com/redhat-ai-americas/docling-service"; \
		exit 1; \
	fi

# Build containers locally
.PHONY: build-containers
build-containers:
	@echo "🔨 Building Backend container..."
	podman build --platform linux/amd64 -t legal-doc-backend:latest -f Containerfile.backend . --no-cache
	@echo "🔨 Building UI container..."
	podman build --platform linux/amd64 -t legal-doc-ui:latest -f Containerfile.ui . --no-cache

# Deploy ConfigMap
.PHONY: deploy-config
deploy-config: oc-check
	@echo "⚙️  Applying ConfigMap..."
	@oc apply -f manifests/base/configmap.yaml || oc apply -f manifests/configmap.yaml || echo "ConfigMap already exists"

# Deploy backend API
.PHONY: deploy-backend
deploy-backend: oc-check deploy-config
	@echo "🚀 Deploying Backend API..."
	@# Create BuildConfig if it doesn't exist
	@oc get bc legal-doc-backend >/dev/null 2>&1 || oc new-build --binary --name=legal-doc-backend --strategy=docker
	@# Start build from local directory
	@echo "  Building backend image..."
	@oc start-build legal-doc-backend --from-dir=. -F
	@# Apply manifests
	@echo "  Applying backend manifests..."
	@oc apply -f manifests/backend/
	@# Wait for rollout
	@echo "  Waiting for backend deployment..."
	@oc rollout status deployment/legal-doc-backend --timeout=300s
	@echo "✓ Backend API deployed successfully"

# Deploy UI
.PHONY: deploy-ui
deploy-ui: oc-check deploy-config
	@echo "🚀 Deploying Web UI..."
	@# Create BuildConfig if it doesn't exist
	@oc get bc legal-doc-ui >/dev/null 2>&1 || oc new-build --binary --name=legal-doc-ui --strategy=docker
	@# Start build from local directory
	@echo "  Building UI image..."
	@oc start-build legal-doc-ui --from-dir=. -F
	@# Apply manifests
	@echo "  Applying UI manifests..."
	@oc apply -f manifests/ui/
	@# Wait for rollout
	@echo "  Waiting for UI deployment..."
	@oc rollout status deployment/legal-doc-ui --timeout=300s
	@echo "✓ Web UI deployed successfully"

# Deploy everything
.PHONY: deploy
deploy: deploy-prereq deploy-backend deploy-ui
	@echo "✅ All components deployed successfully!"
	@echo ""
	@echo "Access URLs:"
	@echo "  UI:      https://$$(oc get route legal-doc-ui -o jsonpath='{.spec.host}')"
	@echo "  API:     https://$$(oc get route legal-doc-api -o jsonpath='{.spec.host}')"
	@echo "  Docling: https://$$(oc get route docling-pdf-processor -o jsonpath='{.spec.host}')"

# Check deployment status
.PHONY: status
status: oc-check
	@echo "📊 Deployment Status:"
	@echo ""
	@echo "Pods:"
	@oc get pods -l app=legal-doc-analysis
	@oc get pods -l app=docling-pdf-processor 2>/dev/null || true
	@echo ""
	@echo "Services:"
	@oc get svc -l app=legal-doc-analysis
	@oc get svc docling-pdf-processor 2>/dev/null || true
	@echo ""
	@echo "Routes:"
	@oc get routes -l app=legal-doc-analysis
	@oc get route docling-pdf-processor 2>/dev/null || true

# View logs
.PHONY: logs
logs: oc-check
	@echo "Select component to view logs:"
	@echo "  1) Backend API"
	@echo "  2) Web UI"
	@echo "  3) Docling Processor"
	@read -p "Enter choice [1-3]: " choice; \
	case $$choice in \
		1) oc logs -f deployment/legal-doc-backend ;; \
		2) oc logs -f deployment/legal-doc-ui ;; \
		3) oc logs -f deployment/docling-pdf-processor ;; \
		*) echo "Invalid choice" ;; \
	esac

# Clean up deployment
.PHONY: clean-deployment
clean-deployment: oc-check
	@echo "🧹 Cleaning up deployment..."
	@# Delete deployments
	@oc delete deployment legal-doc-backend legal-doc-ui --ignore-not-found=true
	@# Delete services
	@oc delete service legal-doc-backend legal-doc-ui --ignore-not-found=true
	@# Delete routes
	@oc delete route legal-doc-api legal-doc-ui --ignore-not-found=true
	@# Delete build configs
	@oc delete bc legal-doc-backend legal-doc-ui --ignore-not-found=true
	@# Delete image streams
	@oc delete is legal-doc-backend legal-doc-ui --ignore-not-found=true
	@echo "✓ Deployment cleaned up (Docling processor preserved)"

# Restart services
.PHONY: restart
restart: oc-check
	@echo "🔄 Restarting services..."
	@oc rollout restart deployment/legal-doc-backend
	@oc rollout restart deployment/legal-doc-ui
	@echo "✓ Services restarted"

# Port forward for local testing
.PHONY: port-forward
port-forward: oc-check
	@echo "Setting up port forwarding..."
	@echo "  Backend API: http://localhost:8080"
	@echo "  Web UI: http://localhost:8501"
	@echo "Press Ctrl+C to stop"
	@oc port-forward service/legal-doc-backend 8080:8080 &
	@oc port-forward service/legal-doc-ui 8501:8501

# Quick redeploy (for development)
.PHONY: redeploy
redeploy: oc-check
	@echo "🔄 Quick redeploy..."
	@oc start-build legal-doc-backend --from-dir=. --wait
	@oc start-build legal-doc-ui --from-dir=. --wait
	@oc rollout restart deployment/legal-doc-backend
	@oc rollout restart deployment/legal-doc-ui
	@echo "✓ Redeployed successfully"
