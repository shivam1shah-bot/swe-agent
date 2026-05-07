"""
Seed data for agents catalogue items.

This file contains seed data for local development environment.
Run this to populate the agents catalogue with sample items.
"""

import logging
import uuid
import time
import sys
import os
from pathlib import Path

# Add the project root to Python path so we can import modules
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from sqlalchemy import text
from src.providers.database.connection import initialize_engine

logger = logging.getLogger(__name__)


def seed_agents_catalogue_items(engine):
    """Seed agents catalogue items for local development."""
    logger.info("Seeding agents catalogue items...")
    
    # Define agents catalogue items to seed
    items = [
        {
            "id": "spinnaker-v3-pipeline-generator",
            "name": "Spinnaker V3 Pipeline Generator",
            "description": "Generate Spinnaker V3 pipelines from templates with GitOps PR creation. Supports multiple deployment strategies including blue-green, canary, and rolling deployments across multiple regions.",
            "type": "micro-frontend",
            "lifecycle": "production",
            "owners": '["nikhilesh.chamarthi@razorpay.com", "nandakishore.b@razorpay.com"]',  # JSON string
            "tags": '["INFRA", "CI"]'  # JSON string
        },
        {
            "id": "repo-context-generator",
            "name": "Repo Context Generator",
            "description": "Scans code repositories to generate docs and context. Enabling AI agents, IDEs to work better with the repository.",
            "type": "micro-frontend",
            "lifecycle": "production",
            "owners": '["nikhilesh.chamarthi@razorpay.com"]',  # JSON string
            "tags": '["DOCS"]'  # JSON string
        },
        {
            "id": "gateway-integrations-common",
            "name": "Gateway Integrations - Common",
            "description": "Automates the integration of new payment gateways, including setup, configuration, and standardized testing procedures.",
            "type": "micro-frontend",
            "lifecycle": "production",
            "owners": '["nikhilesh.chamarthi@razorpay.com"]',  # JSON string
            "tags": '["GATEWAY_INTEGRATION", "CI"]'  # JSON string
        },
        {
            "id": "e2e-onboarding",
            "name": "E2E Onboarding",
            "description": "Automates the complete E2E onboarding process for services by creating PRs sequentially across multiple repositories (Kubemanifest, E2E Orchestrator, End-to-End Tests, ITF, Service Repo).",
            "type": "micro-frontend",
            "lifecycle": "experimental",
            "owners": '["chirag.chiranjib@razorpay.com"]',  # JSON string
            "tags": '["ONBOARDING", "E2E"]'  # JSON string
        },
        {
            "id": "qcc-onboarding",
            "name": "QCC Onboarding",
            "description": "This agent helps users understand and fulfill the necessary conditions for onboarding new services into Quality Code Coverage (QCC)",
            "type": "micro-frontend",
            "lifecycle": "production",
            "owners": '["prem.dhan@razorpay.com", "ajay.ks@razorpay.com"]',  # JSON string
            "tags": '[]'  # JSON string
        },
        {
            "id": "de-agent",
            "name": "DE Agent",
            "description": "A conversational agent for Razorpay's Data Engineering",
            "type": "micro-frontend",
            "lifecycle": "production",
            "owners": '["anuj.j@razorpay.com"]',  # JSON string
            "tags": '["DE"]'  # JSON string with new DE tag
        },
        {
            "id": "genspec-agent",
            "name": "GenSpec Agent",
            "description": "GenSpec Service for generating technical specifications from problem statements, PRDs, and architecture diagrams",
            "type": "micro-frontend",
            "lifecycle": "production",
            "owners": '["b.navya@razorpay.com"]',  # JSON string
            "tags": '["DOCS"]'  # JSON string
        },
        {
            "id": "foundation-onboarding",
            "name": "Foundation Onboarding",
            "description": "Automates end to end foundation onboarding process for a new service.",
            "type": "micro-frontend",
            "lifecycle": "experimental",
            "owners": '["chirag.chiranjib@razorpay.com", "neel.modi@razorpay.com", "nikhilesh.chamarthi@razorpay.com"]',  # JSON string
            "tags": '["ONBOARDING", "FOUNDATION"]'  # JSON string
        },
        # Add more agents catalogue items here as needed
    ]
    
    current_time = int(time.time())
    
    with engine.connect() as conn:
        for item in items:
            # Use provided ID if available, otherwise generate UUID
            item_id = item.get('id', str(uuid.uuid4()))
            
            logger.info(f"Seeding agents catalogue item: {item['name']}")
            
            # Use INSERT ... ON DUPLICATE KEY UPDATE to handle existing items
            conn.execute(text("""
                INSERT INTO agents_catalogue_items (
                    id, 
                    name, 
                    description, 
                    type, 
                    lifecycle, 
                    owners, 
                    tags, 
                    created_at, 
                    updated_at
                ) VALUES (
                    :id,
                    :name,
                    :description,
                    :type,
                    :lifecycle,
                    :owners,
                    :tags,
                    :created_at,
                    :updated_at
                )
                ON DUPLICATE KEY UPDATE
                    description = VALUES(description),
                    type = VALUES(type),
                    lifecycle = VALUES(lifecycle),
                    owners = VALUES(owners),
                    tags = VALUES(tags),
                    updated_at = VALUES(updated_at)
            """), {
                "id": item_id,
                "name": item["name"],
                "description": item["description"],
                "type": item["type"],
                "lifecycle": item["lifecycle"],
                "owners": item["owners"],
                "tags": item["tags"],
                "created_at": current_time,
                "updated_at": current_time
            })
        
        conn.commit()
        logger.info("Successfully seeded agents catalogue items")


if __name__ == "__main__":
    # This allows the script to be run standalone for testing
    logging.basicConfig(level=logging.INFO)
    
    try:
        from src.providers.config_loader.env_loader import load_config
        config = load_config()
        
        engine = initialize_engine(config)
        seed_agents_catalogue_items(engine)
        
        print("Agents catalogue items seeded successfully!")
        
    except Exception as e:
        print(f"Error seeding agents catalogue items: {e}")
        sys.exit(1) 