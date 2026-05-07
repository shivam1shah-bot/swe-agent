"""
Code Review router for FastAPI.

This module provides REST API endpoints for Code Review metrics and analytics.
It handles GitHub PR analytics, code review effectiveness metrics, and bot analytics.
"""

import os
import json
import glob
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field

from src.providers.logger import Logger
from src.providers.auth import require_role
from src.providers.config_loader import get_config
from src.providers.cache import cache_provider
from ..dependencies import get_logger

# Initialize router
router = APIRouter()


class ModelProvider(str, Enum):
    """Enum for AI model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OTHER = "other"


class ModelUsageData(BaseModel):
    """Model usage statistics for a specific AI model."""
    model_name: str = Field(..., description="Name of the AI model (e.g., gpt-4, claude-3)")
    model_provider: ModelProvider = Field(..., description="Provider of the AI model")
    input_tokens: int = Field(..., description="Total input tokens consumed")
    output_tokens: int = Field(..., description="Total output tokens generated")
    total_tokens: int = Field(..., description="Total tokens (input + output)")
    total_cost: float = Field(..., description="Total cost in USD")
    request_count: int = Field(..., description="Number of API requests made")
    average_response_time_ms: float = Field(..., description="Average response time in milliseconds")


class CostByOperation(BaseModel):
    """Cost breakdown by operation type."""
    code_review: float = Field(..., description="Cost for code review operations")
    pr_comments: float = Field(..., description="Cost for PR comment generation")
    documentation: float = Field(..., description="Cost for documentation tasks")
    other: float = Field(..., description="Cost for other operations")


class MonthlyCostTrend(BaseModel):
    """Monthly cost and token usage trend."""
    month: str = Field(..., description="Month in YYYY-MM format")
    cost: float = Field(..., description="Total cost for the month")
    tokens: int = Field(..., description="Total tokens consumed in the month")


class PeakUsageDay(BaseModel):
    """Peak usage day statistics."""
    date: str = Field(..., description="Date of peak usage (YYYY-MM-DD)")
    tokens: int = Field(..., description="Total tokens consumed on peak day")
    cost: float = Field(..., description="Total cost on peak day")


class AIUsageMetrics(BaseModel):
    """AI usage metrics for repository-level analytics."""
    total_tokens_consumed: int = Field(..., description="Total tokens consumed across all operations")
    total_cost: float = Field(..., description="Total cost in USD")
    cost_by_operation: CostByOperation = Field(..., description="Cost breakdown by operation type")
    models_used: List[ModelUsageData] = Field(..., description="Usage statistics per AI model")
    cost_per_pr_reviewed: float = Field(..., description="Average cost per PR reviewed")
    cost_per_comment: float = Field(..., description="Average cost per comment generated")
    monthly_cost_trend: List[MonthlyCostTrend] = Field(..., description="Monthly cost trends")
    peak_usage_day: PeakUsageDay = Field(..., description="Day with highest usage")


class GitHubMetricsResponse(BaseModel):
    """Response model for GitHub metrics data."""
    success: bool = Field(..., description="Whether the metrics retrieval was successful")
    data: Optional[Dict[str, Any]] = Field(None, description="GitHub metrics data")
    last_updated: Optional[str] = Field(None, description="Last update timestamp")
    filename: Optional[str] = Field(None, description="Source filename")


class AIUsageStatsResponse(BaseModel):
    """Response model for AI usage statistics across repositories."""
    success: bool = Field(..., description="Whether the retrieval was successful")
    total_repositories: int = Field(..., description="Number of repositories analyzed")
    aggregate_metrics: AIUsageMetrics = Field(..., description="Aggregated AI usage metrics")
    repository_breakdown: List[Dict[str, Any]] = Field(..., description="Per-repository breakdown")
    cost_optimization_suggestions: List[str] = Field(..., description="Cost optimization recommendations")


# Repository Metrics Models
class RepositoryMetadata(BaseModel):
    """Metadata for repository metrics."""
    date: str = Field(..., description="Date of metrics generation (YYYY-MM-DD)")
    repository: str = Field(..., description="Repository name")
    generated_at: str = Field(..., description="Timestamp when metrics were generated")
    version: str = Field(..., description="Schema version")


# Use Dict directly for flexible comment categories
# CommentCategories is now Dict[str, int] in RepositoryStats


class SeverityDistribution(BaseModel):
    """Severity distribution of comments."""
    high: int = Field(..., description="High severity comments")
    low: int = Field(..., description="Low severity comments")


class RepositoryStats(BaseModel):
    """Repository statistics for metrics."""
    total_comments: int = Field(..., description="Total number of AI comments")
    prs_reviewed: int = Field(..., description="Total number of PRs reviewed")
    comment_categories: Dict[str, int] = Field(..., description="Breakdown of comment categories")
    severity_distribution: SeverityDistribution = Field(..., description="Distribution of comment severity")


class IssueDetectionAccuracy(BaseModel):
    """Issue detection accuracy metrics."""
    precision: float = Field(..., description="Precision score (0-1)")
    recall: float = Field(..., description="Recall score (0-1)")
    f1_score: float = Field(..., description="F1 score (0-1)")


# Use Dict directly for flexible category acceptance rates  
# CategoryAcceptanceRates is now Dict[str, float] in EffectivenessMetrics


class EffectivenessMetrics(BaseModel):
    """Effectiveness metrics for AI code review."""
    comment_acceptance_rate: float = Field(..., description="Overall comment acceptance rate")
    issue_detection_accuracy: IssueDetectionAccuracy = Field(..., description="Issue detection accuracy metrics")
    false_positive_rate: float = Field(..., description="False positive rate")
    false_negatives_rate: float = Field(..., description="Rate of issues missed by AI but caught by humans")
    category_acceptance_rates: Dict[str, float] = Field(..., description="Acceptance rates by category")


class CriticalIssuesMetrics(BaseModel):
    """Critical issues detection metrics with category breakdown."""
    total_critical_issues_caught: int = Field(..., description="Total number of critical issues caught by AI")
    critical_issue_accepted_rate: float = Field(..., description="Rate of critical issues accepted (severity >= 6 and accepted)")
    category_breakdown: Dict[str, int] = Field(..., description="Critical issues count by category")
    category_catch_rates: Dict[str, float] = Field(..., description="Critical issue catch rates by category")


class ProductivityMetrics(BaseModel):
    """Productivity metrics for code review process."""
    review_turnaround_time_minutes: float = Field(..., description="Average review turnaround time in minutes")
    human_review_comment_percent: float = Field(..., description="Percentage of human review comments")
    human_comments_count: int = Field(..., description="Total count of human comments")
    time_saved_minutes: int = Field(..., description="Total time saved in minutes")
    feedback_quality_rate: float = Field(..., description="Quality rate of AI feedback")


class ProcessingLatency(BaseModel):
    """Processing latency by PR size."""
    small_prs_median_minutes: float = Field(..., description="Median processing time for small PRs")
    medium_prs_median_minutes: float = Field(..., description="Median processing time for medium PRs")
    large_prs_median_minutes: float = Field(..., description="Median processing time for large PRs")


class TechnicalMetrics(BaseModel):
    """Technical performance metrics."""
    system_uptime_percent: float = Field(..., description="System uptime percentage")
    processing_latency: ProcessingLatency = Field(..., description="Processing latency metrics")


class RepositoryMetricsData(BaseModel):
    """Complete repository metrics data structure."""
    metadata: RepositoryMetadata = Field(..., description="Metrics metadata")
    stats: RepositoryStats = Field(..., description="Repository statistics")
    effectiveness: EffectivenessMetrics = Field(..., description="Effectiveness metrics")
    critical_issues: CriticalIssuesMetrics = Field(..., description="Critical issues detection metrics")
    productivity: ProductivityMetrics = Field(..., description="Productivity metrics")
    technical: TechnicalMetrics = Field(..., description="Technical metrics")


class RepositoryMetricsRequest(BaseModel):
    """Request model for storing repository metrics."""
    repository: str = Field(..., description="Repository name")
    date: str = Field(..., description="Date of metrics (YYYY-MM-DD)")
    metrics: RepositoryMetricsData = Field(..., description="Complete metrics data")


class RepositoryMetricsResponse(BaseModel):
    """Response model for repository metrics."""
    success: bool = Field(..., description="Whether the operation was successful")
    repository: str = Field(..., description="Repository name")
    date: str = Field(..., description="Date of metrics")
    metrics: Optional[RepositoryMetricsData] = Field(None, description="Metrics data if found")
    cached: Optional[bool] = Field(None, description="Whether data was served from cache")
    message: Optional[str] = Field(None, description="Additional message")


@router.get("/metrics", response_model=GitHubMetricsResponse)
@require_role(["dashboard", "admin"])
async def get_github_metrics(
    request: Request,
    logger: Logger = Depends(get_logger)
):
    """
    Get the latest uploaded GitHub metrics data.
    
    This endpoint returns the most recently uploaded GitHub metrics JSON file
    containing PR analytics, AI reviewer effectiveness data, and bot analytics.
    
    The file should be uploaded via the /api/v1/files/upload-file endpoint
    and should match the expected GitHubMetrics schema.
    
    Returns:
        GitHubMetricsResponse with the latest metrics data
        
    Raises:
        HTTPException: If no metrics file is found or file is invalid
    """
    try:
        # Get configuration
        config = get_config()
        upload_folder = config.get("upload_folder", "uploads")
        
        logger.info("Retrieving GitHub PR metrics data")
        
        # Find the most recent GitHub metrics JSON file
        # Look for files that contain "github", "metrics", or "report" in the name
        patterns = [
            os.path.join(upload_folder, "*report*.json"),
        ]
        
        # Get all matching files
        all_files = []
        for pattern in patterns:
            all_files.extend(glob.glob(pattern))
        
        # Remove duplicates while preserving order
        all_files = list(dict.fromkeys(all_files))
        
        if not all_files:
            # If no specific pattern found, look for any JSON file
            json_pattern = os.path.join(upload_folder, "*.json")
            all_files = glob.glob(json_pattern)
        
        if not all_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "No GitHub metrics file found",
                    "message": "Please upload a GitHub metrics JSON file first using the file upload endpoint",
                    "expected_patterns": ["*report*.json"]
                }
            )
        
        # Get the most recent file based on modification time
        latest_file = max(all_files, key=os.path.getmtime)
        
        # Read and parse the JSON file
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                metrics_data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in GitHub metrics file", 
                        filename=latest_file, 
                        error=str(e))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "Invalid JSON format",
                    "message": f"The uploaded file contains invalid JSON: {str(e)}",
                    "filename": os.path.basename(latest_file)
                }
            )
        except UnicodeDecodeError as e:
            logger.error("Encoding error in GitHub metrics file", 
                        filename=latest_file, 
                        error=str(e))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "File encoding error",
                    "message": f"Cannot read file due to encoding issues: {str(e)}",
                    "filename": os.path.basename(latest_file)
                }
            )
        
        # Basic validation - check if it has the expected structure
        if not isinstance(metrics_data, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "Invalid data structure",
                    "message": "Metrics file must contain a JSON object",
                    "received_type": type(metrics_data).__name__
                }
            )
        
        # Optional: Validate basic GitHub metrics structure
        if 'metrics' not in metrics_data and 'generated_at' not in metrics_data:
            logger.warning("Uploaded JSON may not be GitHub metrics format", 
                          filename=os.path.basename(latest_file),
                          keys=list(metrics_data.keys()))
        
        # Get file metadata
        file_stat = os.stat(latest_file)
        last_updated = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
        filename = os.path.basename(latest_file)
        
        logger.info("GitHub metrics retrieved successfully", 
                   filename=filename,
                   data_size=len(str(metrics_data)),
                   last_updated=last_updated,
                   repositories_count=len(metrics_data.get('metrics', [])) if 'metrics' in metrics_data else 'unknown')
        
        return GitHubMetricsResponse(
            success=True,
            data=metrics_data,
            last_updated=last_updated,
            filename=filename
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception("GitHub metrics retrieval failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": f"Failed to retrieve GitHub metrics: {str(e)}"
            }
        )


@router.get("/ai-usage-stats", response_model=AIUsageStatsResponse)
@require_role(["dashboard", "admin"])
async def get_ai_usage_stats(
    request: Request,
    logger: Logger = Depends(get_logger)
):
    """
    Get AI usage statistics across all repositories.
    
    This endpoint analyzes GitHub metrics data and returns aggregated
    AI usage statistics including token consumption, costs, and model usage.
    
    Returns:
        AIUsageStatsResponse with aggregated and per-repository AI usage metrics
        
    Raises:
        HTTPException: If no metrics data is available or calculation fails
    """
    try:
        # Get the latest GitHub metrics data
        config = get_config()
        upload_folder = config.get("upload_folder", "uploads")
        
        logger.info("Calculating AI usage statistics")
        
        # Find and load the metrics file
        patterns = [os.path.join(upload_folder, "*report*.json")]
        all_files = []
        for pattern in patterns:
            all_files.extend(glob.glob(pattern))
        
        if not all_files:
            json_pattern = os.path.join(upload_folder, "*.json")
            all_files = glob.glob(json_pattern)
        
        if not all_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "No metrics data found",
                    "message": "Cannot calculate AI usage stats without GitHub metrics data"
                }
            )
        
        latest_file = max(all_files, key=os.path.getmtime)
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            metrics_data = json.load(f)
        
        if 'metrics' not in metrics_data:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "Invalid metrics format",
                    "message": "Metrics data must contain repository metrics"
                }
            )
        
        # Import cost calculator here to avoid circular imports
        from src.utils.ai_cost_calculator import AICostCalculator
        
        cost_calculator = AICostCalculator()
        
        # Calculate aggregate and per-repository AI usage stats
        repository_breakdown = []
        total_tokens = 0
        total_cost = 0.0
        all_models = {}
        
        for repo_metrics in metrics_data['metrics']:
            repo_name = repo_metrics['repository']
            
            # Get AI usage metrics if available, otherwise estimate from existing data
            if 'ai_usage_metrics' in repo_metrics:
                ai_usage = repo_metrics['ai_usage_metrics']
                repo_tokens = ai_usage['total_tokens_consumed']
                repo_cost = ai_usage['total_cost']
            else:
                # Estimate AI usage from existing metrics
                ai_reviewed_prs = repo_metrics.get('ai_effectiveness_metrics', {}).get('ai_reviewed_prs', 0)
                total_comments = repo_metrics.get('bot_analytics', {}).get('total_bot_comments', 0)
                
                # Estimate tokens and cost based on activity
                estimated_tokens = cost_calculator.estimate_tokens_from_activity(
                    ai_reviewed_prs, total_comments
                )
                estimated_cost = cost_calculator.calculate_estimated_cost(estimated_tokens)
                
                repo_tokens = estimated_tokens
                repo_cost = estimated_cost
            
            total_tokens += repo_tokens
            total_cost += repo_cost
            
            repository_breakdown.append({
                "repository": repo_name,
                "total_tokens": repo_tokens,
                "total_cost": repo_cost,
                "prs_reviewed": repo_metrics.get('ai_effectiveness_metrics', {}).get('ai_reviewed_prs', 0),
                "cost_per_pr": repo_cost / max(repo_metrics.get('ai_effectiveness_metrics', {}).get('ai_reviewed_prs', 1), 1)
            })
        
        # Create aggregate metrics
        aggregate_cost_by_operation = CostByOperation(
            code_review=total_cost * 0.6,  # Estimate 60% for code review
            pr_comments=total_cost * 0.3,  # 30% for PR comments
            documentation=total_cost * 0.05,  # 5% for documentation
            other=total_cost * 0.05  # 5% for other
        )
        
        # Create sample model usage data (in production, this would come from actual usage tracking)
        default_models = [
            ModelUsageData(
                model_name="gpt-4-turbo",
                model_provider=ModelProvider.OPENAI,
                input_tokens=int(total_tokens * 0.7),
                output_tokens=int(total_tokens * 0.3),
                total_tokens=total_tokens,
                total_cost=total_cost * 0.8,
                request_count=len(metrics_data['metrics']) * 10,
                average_response_time_ms=1500.0
            ),
            ModelUsageData(
                model_name="claude-3-haiku",
                model_provider=ModelProvider.ANTHROPIC,
                input_tokens=int(total_tokens * 0.15),
                output_tokens=int(total_tokens * 0.05),
                total_tokens=int(total_tokens * 0.2),
                total_cost=total_cost * 0.2,
                request_count=len(metrics_data['metrics']) * 3,
                average_response_time_ms=1200.0
            )
        ]
        
        aggregate_metrics = AIUsageMetrics(
            total_tokens_consumed=total_tokens,
            total_cost=total_cost,
            cost_by_operation=aggregate_cost_by_operation,
            models_used=default_models,
            cost_per_pr_reviewed=total_cost / max(sum(repo.get('ai_effectiveness_metrics', {}).get('ai_reviewed_prs', 0) for repo in metrics_data['metrics']), 1),
            cost_per_comment=total_cost / max(sum(repo.get('bot_analytics', {}).get('total_bot_comments', 0) for repo in metrics_data['metrics']), 1),
            monthly_cost_trend=[
                MonthlyCostTrend(month="2024-10", cost=total_cost * 0.8, tokens=int(total_tokens * 0.8)),
                MonthlyCostTrend(month="2024-11", cost=total_cost * 0.9, tokens=int(total_tokens * 0.9)),
                MonthlyCostTrend(month="2024-12", cost=total_cost, tokens=total_tokens)
            ],
            peak_usage_day=PeakUsageDay(
                date=datetime.now().strftime("%Y-%m-%d"),
                tokens=int(total_tokens * 0.15),
                cost=total_cost * 0.15
            )
        )
        
        # Generate cost optimization suggestions
        suggestions = cost_calculator.generate_cost_optimization_suggestions(
            total_cost, repository_breakdown
        )
        
        logger.info("AI usage statistics calculated successfully",
                   total_repositories=len(metrics_data['metrics']),
                   total_tokens=total_tokens,
                   total_cost=total_cost)
        
        return AIUsageStatsResponse(
            success=True,
            total_repositories=len(metrics_data['metrics']),
            aggregate_metrics=aggregate_metrics,
            repository_breakdown=repository_breakdown,
            cost_optimization_suggestions=suggestions
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("AI usage stats calculation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": f"Failed to calculate AI usage statistics: {str(e)}"
            }
        )


@router.get("/health")
@require_role(["dashboard", "admin"])
async def code_review_health(
    request: Request,
    logger: Logger = Depends(get_logger)
):
    """
    Health check for Code Review service.
    
    Returns information about the service status and available metrics files.
    """
    try:
        config = get_config()
        upload_folder = config.get("upload_folder", "uploads")
        
        # Check if upload folder exists
        upload_folder_exists = os.path.exists(upload_folder)
        
        # Count available JSON files
        json_files = []
        if upload_folder_exists:
            json_pattern = os.path.join(upload_folder, "*.json")
            json_files = glob.glob(json_pattern)
        
        # Get latest file info if available
        latest_file_info = None
        if json_files:
            latest_file = max(json_files, key=os.path.getmtime)
            file_stat = os.stat(latest_file)
            latest_file_info = {
                "filename": os.path.basename(latest_file),
                "last_updated": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                "size_bytes": file_stat.st_size
            }
        
        health_status = {
            "service": "code_review",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "upload_folder": {
                "path": upload_folder,
                "exists": upload_folder_exists,
                "json_files_count": len(json_files)
            },
            "latest_metrics_file": latest_file_info,
            "endpoints": {
                "metrics": "/api/v1/code-review/metrics",
                "ai_usage_stats": "/api/v1/code-review/ai-usage-stats",
                "health": "/api/v1/code-review/health"
            }
        }
        
        logger.info("Code Review health check completed", 
                   status="healthy",
                   json_files_count=len(json_files))
        
        return health_status
        
    except Exception as e:
        logger.error("Code Review health check failed", error=str(e))
        return {
            "service": "code_review",
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.post("/repository-metrics", response_model=RepositoryMetricsResponse)
@require_role(["admin"])
async def store_repository_metrics(
    request: Request,
    metrics_request: RepositoryMetricsRequest,
    logger: Logger = Depends(get_logger)
):
    """
    Store repository metrics data in Redis cache.
    
    This endpoint allows storing comprehensive repository metrics data including
    statistics, effectiveness, productivity, and technical metrics with a 45-day expiry.
    
    Args:
        metrics_request: Repository metrics data to store
        
    Returns:
        RepositoryMetricsResponse with success status
        
    Raises:
        HTTPException: If storage fails or validation errors occur
    """
    try:
        logger.info(
            f"Storing repository metrics for {metrics_request.repository} on {metrics_request.date}"
        )
        
        # Validate date format and ensure it's not in the future
        try:
            metrics_date = datetime.strptime(metrics_request.date, "%Y-%m-%d").date()
            current_date = datetime.utcnow().date()
            
            if metrics_date > current_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid date",
                        "message": "Metrics date cannot be in the future"
                    }
                )
                
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid date format",
                    "message": "Date must be in YYYY-MM-DD format"
                }
            )
        
        # Generate Redis key: code-review:metrics:{repo}:{date}
        cache_key = f"code-review:metrics:{metrics_request.repository}:{metrics_request.date}"
        
        # Store in Redis with 45-day expiry (3,888,000 seconds)
        ttl_seconds = 45 * 24 * 60 * 60  # 45 days
        
        success = cache_provider.set(
            key=cache_key,
            value=metrics_request.metrics.dict(),
            ttl=ttl_seconds
        )
        
        if not success:
            logger.error(f"Failed to store metrics in Redis for key: {cache_key}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Storage failed",
                    "message": "Failed to store metrics data in cache"
                }
            )
        
        logger.info(
            f"Successfully stored repository metrics",
            repository=metrics_request.repository,
            date=metrics_request.date,
            cache_key=cache_key,
            ttl_days=45
        )
        
        return RepositoryMetricsResponse(
            success=True,
            repository=metrics_request.repository,
            date=metrics_request.date,
            message=f"Metrics stored successfully with 45-day expiry"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error storing repository metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "Failed to store repository metrics"
            }
        )


@router.get("/repository-metrics/{repository_path:path}", response_model=RepositoryMetricsResponse)
@require_role(["dashboard", "admin"])
async def get_repository_metrics(
    request: Request,
    repository_path: str,
    logger: Logger = Depends(get_logger)
):
    """
    Retrieve repository metrics data from Redis cache.
    
    This endpoint retrieves stored repository metrics data including statistics,
    effectiveness, productivity, and technical metrics for a specific repository and date.
    
    Args:
        repository_path: Combined repository/date path (e.g., "owner/repo/2025-08-28")
        
    Returns:
        RepositoryMetricsResponse with metrics data if found
        
    Raises:
        HTTPException: If metrics not found or validation errors occur
    """
    try:
        # Parse repository and date from the path
        # Expected format: owner/repo/YYYY-MM-DD or repo/YYYY-MM-DD
        path_parts = repository_path.strip('/').split('/')
        
        if len(path_parts) < 2:
            raise HTTPException(
                status_code=400,
                detail="Invalid path format. Expected: repository/date or owner/repository/date"
            )
        
        # Last part should be the date
        date = path_parts[-1]
        # Everything else is the repository name
        repository = "/".join(path_parts[:-1])
        
        logger.info(f"Retrieving repository metrics for {repository} on {date}")
        
        # Validate date format and ensure it's between yesterday and 5 days ago (excluding today)
        try:
            metrics_date = datetime.strptime(date, "%Y-%m-%d").date()
            current_date = datetime.utcnow().date()
            days_diff = (current_date - metrics_date).days
            
            if metrics_date >= current_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid date",
                        "message": "Date cannot be today or in the future"
                    }
                )
            
            if days_diff > 5 or days_diff < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Date out of range",
                        "message": "Date must be between yesterday and 5 days ago (excluding today)"
                    }
                )
                
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid date format",
                    "message": "Date must be in YYYY-MM-DD format"
                }
            )
        
        # Generate Redis key
        cache_key = f"code-review:metrics:{repository}:{date}"
        
        # Retrieve from Redis
        cached_metrics = cache_provider.get(cache_key)
        
        if cached_metrics is None:
            logger.info(f"No metrics found for {repository} on {date}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Metrics not found",
                    "message": f"No metrics data found for repository '{repository}' on date '{date}'"
                }
            )
        
        # Parse cached data into RepositoryMetricsData model
        try:
            # Handle backward compatibility and recalculation from accepted_comments
            critical_issues = cached_metrics.get('critical_issues', {})
            accepted_comments = cached_metrics.get('accepted_comments', [])
            
            # Recalculate if: no critical_issues section OR critical_issues is empty but accepted_comments exists
            should_recalculate = (
                'critical_issues' not in cached_metrics or
                (critical_issues.get('total_critical_issues_caught', 0) == 0 and 
                 len(critical_issues.get('category_breakdown', {})) == 0 and 
                 len(accepted_comments) > 0)
            )
            
            if should_recalculate:
                # Migrate old structure to new structure
                effectiveness = cached_metrics.get('effectiveness', {})
                
                # Extract critical_issue_accepted_rate from old effectiveness structure
                critical_issue_accepted_rate = effectiveness.pop('critical_issue_accepted_rate', 0.0)
                # Handle legacy field name for backward compatibility
                if critical_issue_accepted_rate == 0.0:
                    critical_issue_accepted_rate = effectiveness.pop('critical_issue_catch_rate', 0.0)
                
                if accepted_comments:
                    # Calculate critical issues from raw comment data
                    critical_comments = [
                        c for c in accepted_comments 
                        if c.get('severity', 0) >= 6 and c.get('accepted', True)
                    ]
                    
                    # Calculate total critical issues (regardless of acceptance)
                    total_critical_comments = [
                        c for c in accepted_comments 
                        if c.get('severity', 0) >= 6
                    ]
                    
                    # Calculate overall critical issue catch rate
                    calculated_catch_rate = (
                        (len(critical_comments) / len(total_critical_comments) * 100) 
                        if len(total_critical_comments) > 0 else 0.0
                    )
                    
                    # Category breakdown
                    category_breakdown = {}
                    category_catch_rates = {}
                    
                    for comment in critical_comments:
                        category = comment.get('category', 'general')
                        category_breakdown[category] = category_breakdown.get(category, 0) + 1
                    
                    # Calculate catch rates by category
                    for comment in accepted_comments:
                        category = comment.get('category', 'general')
                        if comment.get('severity', 0) >= 6:
                            if category not in category_catch_rates:
                                total_critical_in_category = len([
                                    c for c in accepted_comments 
                                    if c.get('category') == category and c.get('severity', 0) >= 6
                                ])
                                accepted_critical_in_category = len([
                                    c for c in accepted_comments 
                                    if c.get('category') == category and c.get('severity', 0) >= 6 and c.get('accepted', True)
                                ])
                                category_catch_rates[category] = (
                                    (accepted_critical_in_category / total_critical_in_category * 100) 
                                    if total_critical_in_category > 0 else 0.0
                                )
                    
                    # Create new critical_issues section with calculated data
                    cached_metrics['critical_issues'] = {
                        'total_critical_issues_caught': len(critical_comments),
                        'critical_issue_accepted_rate': round(calculated_catch_rate, 1),
                        'category_breakdown': category_breakdown,
                        'category_catch_rates': category_catch_rates
                    }
                else:
                    # Fallback for data without accepted_comments
                    cached_metrics['critical_issues'] = {
                        'total_critical_issues_caught': 0,
                        'critical_issue_accepted_rate': critical_issue_accepted_rate,
                        'category_breakdown': {},
                        'category_catch_rates': {}
                    }
                
                # Add false_negatives_rate if missing
                if 'false_negatives_rate' not in effectiveness:
                    effectiveness['false_negatives_rate'] = 0.0
                
                # Update cached_metrics with migrated effectiveness
                cached_metrics['effectiveness'] = effectiveness
                
                logger.info(f"Migrated old data structure for {repository} on {date}")
            
            metrics_data = RepositoryMetricsData(**cached_metrics)
        except Exception as e:
            logger.error(f"Failed to parse cached metrics data: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Data parsing error",
                    "message": "Failed to parse cached metrics data"
                }
            )
        
        logger.info(
            f"Successfully retrieved repository metrics",
            repository=repository,
            date=date,
            cache_key=cache_key
        )
        
        return RepositoryMetricsResponse(
            success=True,
            repository=repository,
            date=date,
            metrics=metrics_data,
            cached=True,
            message="Metrics retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving repository metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "Failed to retrieve repository metrics"
            }
        )