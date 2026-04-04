# Import all models here so Alembic can detect them via Base.metadata.
from app.db.models.event import EventModel
from app.db.models.integration import IntegrationModel
from app.db.models.message import MessageModel
from app.db.models.task import TaskModel

__all__ = ["MessageModel", "EventModel", "TaskModel", "IntegrationModel"]
