# trading/alerts/alert_manager.py
"""
Alert Management System
Handles alert lifecycle, notifications, and state management
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging

from data.repositories.alert_repository import AlertRepository
from database.models import AlertStates, SystemLog


class AlertType(Enum):
    BUY = "buy"
    SELL = "sell"


class AlertStatus(Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"


class AlertManager:
    """Manages trading alerts and notifications"""

    def __init__(self, alert_repo: AlertRepository, logger: logging.Logger):
        self.alert_repo = alert_repo
        self.logger = logger

    def create_alert(
        self,
        symbol: str,
        alert_type: AlertType,
        confidence: str,
        reasoning: List[str],
        metadata: Dict[str, Any],
    ) -> AlertStates:
        """Create a new trading alert"""
        alert = AlertStates(
            symbol=symbol,
            alert_type=alert_type.value,
            status=AlertStatus.ACTIVE.value,
            rsi_trigger_level=metadata.get("rsi_15m", 0),
            initial_rsi=metadata.get("rsi_15m", 0),
            start_time=datetime.utcnow(),
        )

        saved_alert = self.alert_repo.create(alert)
        self.logger.info(
            f"Created {alert_type.value} alert for {symbol} with {confidence} confidence"
        )

        return saved_alert

    def get_active_alerts(self, symbol: Optional[str] = None) -> List[AlertStates]:
        """Get all active alerts, optionally filtered by symbol"""
        return self.alert_repo.get_active_alerts(symbol)

    def expire_old_alerts(self, hours: int = 12) -> int:
        """Expire alerts older than specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        expired_count = self.alert_repo.expire_alerts_before(cutoff_time)

        if expired_count > 0:
            self.logger.info(f"Expired {expired_count} old alerts")

        return expired_count

    def trigger_alert(self, alert_id: int, trigger_price: float) -> bool:
        """Mark an alert as triggered"""
        try:
            alert = self.alert_repo.get_by_id(alert_id)
            if alert and alert.status == AlertStatus.ACTIVE.value:
                alert.status = AlertStatus.TRIGGERED.value

                self.alert_repo.update(alert)
                self.logger.info(
                    f"Triggered {alert.alert_type} alert for {alert.symbol} at ${trigger_price}"
                )
                return True
        except Exception as e:
            self.logger.error(f"Error triggering alert {alert_id}: {e}")

        return False

    def log_event(
        self,
        symbol: str,
        event_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log system events"""
        log_entry = SystemLog(
            symbol=symbol,
            event_type=event_type,
            message=message,
            timestamp=datetime.utcnow(),
        )

        try:
            self.alert_repo.create_log_entry(log_entry)
        except Exception as e:
            self.logger.error(f"Error logging event: {e}")
