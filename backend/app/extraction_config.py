from sqlalchemy.orm import Session

from app import models
from app.config import KNOWN_GOOD_EXTRACTION_MODEL

CONFIG_ID = "default"


def get_or_create_extraction_config(db: Session) -> models.ExtractionConfig:
    config = db.query(models.ExtractionConfig).filter(models.ExtractionConfig.id == CONFIG_ID).first()
    if config is None:
        config = models.ExtractionConfig(
            id=CONFIG_ID,
            active_model=KNOWN_GOOD_EXTRACTION_MODEL,
            known_good_model=KNOWN_GOOD_EXTRACTION_MODEL,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config
