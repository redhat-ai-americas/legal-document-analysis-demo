"""
FastAPI backend service for legal document analysis
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import tempfile
import shutil
from pathlib import Path
import uuid
from datetime import datetime
import json

from workflows.graph_builder import build_graph
from nodes.base_node import ProgressReporter, ProgressUpdate

app = FastAPI(
    title="Legal Document Analysis API",
    description="Backend service for contract analysis and compliance checking",
    version="1.0.0"
)

# Add CORS middleware for UI communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store for tracking analysis jobs
analysis_jobs = {}


class AnalysisRequest(BaseModel):
    """Request model for document analysis"""
    reference_document_path: str
    target_document_paths: List[str]
    rules_path: Optional[str] = None
    options: Dict[str, Any] = {}


class AnalysisResponse(BaseModel):
    """Response model for analysis request"""
    job_id: str
    status: str
    message: str


class JobStatus(BaseModel):
    """Job status model"""
    job_id: str
    status: str  # pending, running, completed, failed
    progress: float
    current_node: Optional[str] = None
    current_message: Optional[str] = None
    llm_output: Optional[str] = None
    progress_history: Optional[List[Dict[str, Any]]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "legal-document-analysis-backend"}


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {
            "disk_space": check_disk_space(),
            "model_connectivity": check_model_connection()
        }
    }


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_documents(
    background_tasks: BackgroundTasks,
    request: AnalysisRequest
):
    """
    Start document analysis job
    """
    job_id = str(uuid.uuid4())
    
    # Initialize job tracking
    analysis_jobs[job_id] = {
        "status": "pending",
        "progress": 0.0,
        "started_at": datetime.now().isoformat()
    }
    
    # Start analysis in background
    background_tasks.add_task(
        run_analysis,
        job_id,
        request.reference_document_path,
        request.target_document_paths,
        request.rules_path,
        request.options
    )
    
    return AnalysisResponse(
        job_id=job_id,
        status="accepted",
        message="Analysis job started"
    )


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document for analysis
    """
    try:
        # Create upload directory
        upload_dir = Path("/app/data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file with unique name
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        file_path = upload_dir / f"{file_id}{file_extension}"
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "file_id": file_id,
            "file_path": str(file_path),
            "original_name": file.filename,
            "size": file_path.stat().st_size
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """
    Get status of analysis job
    """
    if job_id not in analysis_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = analysis_jobs[job_id]
    
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress", 0.0),
        current_node=job.get("current_node"),
        current_message=job.get("current_message"),
        llm_output=job.get("llm_output"),
        progress_history=job.get("progress_history", [])[-10:],  # Last 10 entries
        result=job.get("result"),
        error=job.get("error")
    )


@app.get("/api/jobs/{job_id}/download/{file_type}")
async def download_result(job_id: str, file_type: str):
    """
    Download analysis results
    file_type: excel, yaml, markdown, jsonl
    """
    if job_id not in analysis_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = analysis_jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    
    run_id = job.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="Run ID not found")
    
    # Map file types to actual files
    file_map = {
        "excel": f"/app/data/output/comparisons/contract_analysis_template_master.xlsx",
        "yaml": f"/app/data/output/runs/run_{run_id}/analysis.yaml",
        "markdown": f"/app/data/output/runs/run_{run_id}/analysis.md",
        "jsonl": f"/app/data/output/runs/run_{run_id}/classified_sentences.jsonl",
        "state": f"/app/data/output/runs/run_{run_id}/workflow_state.json"
    }
    
    file_path = file_map.get(file_type)
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename=Path(file_path).name
    )


@app.get("/api/document-sets")
async def get_document_sets():
    """
    Get available document sets
    """
    config_path = Path("/app/config/document_sets.yaml")
    
    if not config_path.exists():
        return {"document_sets": {}}
    
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Validate file existence
    validated_sets = {}
    for set_id, set_config in config.get("document_sets", {}).items():
        ref_path = Path("/app") / set_config.get("reference_document", "")
        if ref_path.exists():
            validated_sets[set_id] = set_config
    
    return {"document_sets": validated_sets}


def run_analysis(
    job_id: str,
    reference_path: str,
    target_paths: List[str],
    rules_path: Optional[str],
    options: Dict[str, Any]
):
    """
    Run the actual analysis workflow
    """
    try:
        # Update job status
        analysis_jobs[job_id]["status"] = "running"
        analysis_jobs[job_id]["progress"] = 0.1
        analysis_jobs[job_id]["progress_history"] = []
        
        # Set up progress reporter callback
        reporter = ProgressReporter()
        reporter.clear_callbacks()
        
        def capture_progress(update: ProgressUpdate):
            """Capture progress updates from workflow"""
            analysis_jobs[job_id]["current_node"] = update.node_name
            analysis_jobs[job_id]["current_message"] = update.message
            if update.progress is not None:
                analysis_jobs[job_id]["progress"] = update.progress
            
            # Store LLM output if present in details
            if update.details and "llm_output" in update.details:
                analysis_jobs[job_id]["llm_output"] = update.details["llm_output"]
            
            # Add to history
            analysis_jobs[job_id]["progress_history"].append({
                "timestamp": update.timestamp.isoformat(),
                "node": update.node_name,
                "message": update.message,
                "progress": update.progress,
                "details": update.details
            })
        
        reporter.register_callback(capture_progress)
        
        # Configure environment
        if rules_path:
            os.environ['RULES_MODE_ENABLED'] = 'true'
        else:
            os.environ['RULES_MODE_ENABLED'] = 'false'
        
        # Build workflow
        app = build_graph()
        
        # Process each target document
        results = []
        for i, target_path in enumerate(target_paths):
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Update progress
            progress = 0.1 + (0.8 * i / len(target_paths))
            analysis_jobs[job_id]["progress"] = progress
            analysis_jobs[job_id]["current_node"] = f"Processing {Path(target_path).name}"
            
            # Create state
            state = {
                "target_document_path": target_path,
                "reference_document_path": reference_path,
                "rules_path": rules_path or "",
                "terminology_path": "/app/config/canonical_labels.yaml",
                "run_id": run_id,
                "processing_start_time": run_id
            }
            
            # Run workflow
            result = app.invoke(state)
            results.append({
                "document": Path(target_path).name,
                "run_id": run_id,
                "status": "completed"
            })
        
        # Update job with results
        analysis_jobs[job_id]["status"] = "completed"
        analysis_jobs[job_id]["progress"] = 1.0
        analysis_jobs[job_id]["result"] = {
            "documents_processed": len(target_paths),
            "results": results,
            "run_id": run_id  # Last run ID for downloads
        }
        analysis_jobs[job_id]["run_id"] = run_id
        
    except Exception as e:
        analysis_jobs[job_id]["status"] = "failed"
        analysis_jobs[job_id]["error"] = str(e)


def check_disk_space():
    """Check available disk space"""
    import shutil
    stat = shutil.disk_usage("/app/data")
    return {
        "total_gb": stat.total / (1024**3),
        "free_gb": stat.free / (1024**3),
        "used_percent": (stat.used / stat.total) * 100
    }


def check_model_connection():
    """Check model API connectivity"""
    try:
        from utils.model_config import model_config
        # Test if we can get the model config
        if model_config and hasattr(model_config, 'model_name'):
            return {"status": "connected", "model": model_config.model_name}
        else:
            return {"status": "connected", "model": "granite"}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)