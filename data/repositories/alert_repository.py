# data/repositories/alert_repository.py
"""
Alert and system log repository
Manages trading alerts and system events
"""

from typing import List, Optional
from sqlalchemy import desc, and_
from datetime import datetime, timedelta

from .base_repository import BaseRepository
from database.models import AlertStates, SystemLog


class AlertRepository(BaseRepository[AlertStates]):
    """Repository for trading alerts and system logs"""

    def __init__(self, db_manager):
        super().__init__(db_manager, AlertStates)

    def get_active_alerts(self, symbol: Optional[str] = None) -> List[AlertStates]:
        """Get all active alerts, optionally filtered by symbol"""
        with self.get_session() as session:
            query = session.query(AlertStates).filter(AlertStates.status == "active")

            if symbol:
                query = query.filter(AlertStates.symbol == symbol)

            return query.order_by(desc(AlertStates.created_at)).all()

    def expire_alerts_before(self, cutoff_time: datetime) -> int:
        """Expire alerts created before cutoff time"""
        with self.get_session() as session:
            expired = (
                session.query(AlertStates)
                .filter(
                    and_(
                        AlertStates.status == "active",
                        AlertStates.start_time < cutoff_time,
                    )
                )
                .update({AlertStates.status: "expired"}, synchronize_session=False)
            )

            return expired

    def get_alert_history(self, symbol: str, days: int = 30) -> List[AlertStates]:
        """Get alert history for a symbol"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        with self.get_session() as session:
            return (
                session.query(AlertStates)
                .filter(
                    and_(
                        AlertStates.symbol == symbol,
                        AlertStates.start_time >= cutoff_date,
                    )
                )
                .order_by(desc(AlertStates.start_time))
                .all()
            )

    def create_log_entry(self, log_entry: SystemLog) -> SystemLog:
        """Create system log entry"""
        return self.create(log_entry)

    def get_recent_logs(
        self, symbol: Optional[str] = None, hours: int = 24
    ) -> List[SystemLog]:
        """Get recent system logs"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        with self.get_session() as session:
            query = session.query(SystemLog).filter(SystemLog.timestamp >= cutoff_time)

            if symbol:
                query = query.filter(SystemLog.symbol == symbol)

            return query.order_by(desc(SystemLog.timestamp)).all()
