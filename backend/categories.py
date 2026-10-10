"""One stable primary category per review. Shared by API validation and catalog."""
from typing import Literal

TaskCategory = Literal[
    "security", "frontend-ux", "backend-api", "performance", "testing-qa",
    "devops-cloud", "data-ai", "architecture", "general",
]

TASK_CATEGORIES = (
    {"id": "security", "label": "Security"},
    {"id": "frontend-ux", "label": "Frontend & UX"},
    {"id": "backend-api", "label": "Backend & APIs"},
    {"id": "performance", "label": "Performance"},
    {"id": "testing-qa", "label": "Testing & QA"},
    {"id": "devops-cloud", "label": "DevOps & Cloud"},
    {"id": "data-ai", "label": "Data & AI"},
    {"id": "architecture", "label": "Architecture & Refactoring"},
    {"id": "general", "label": "General review"},
)
