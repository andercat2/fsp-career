from sqlalchemy.orm import Session

from app.core.email import send_email
from app.models import AuditLog, Notification, User


def notify(db: Session, user_id: int, kind: str, title: str, body: str | None = None, link: str | None = None,
           email: bool = False) -> Notification:
    n = Notification(user_id=user_id, kind=kind, title=title, body=body, link=link)
    db.add(n)
    if email:
        user = db.get(User, user_id)
        if user and not user.is_demo:
            send_email(user.email, title, (body or "") + (f"\n\nПодробнее: {link}" if link else ""))
    return n


def audit(db: Session, user_id: int | None, action: str, entity: str | None = None, entity_id: str | int | None = None,
          **meta) -> None:
    db.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=None if entity_id is None else str(entity_id),
                    meta=meta or None))
