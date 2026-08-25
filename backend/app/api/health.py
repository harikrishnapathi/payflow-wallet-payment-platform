from fastapi import APIRouter
from sqlalchemy import text
from app.db.session import engine
from app.core.config import settings
router=APIRouter(tags=['Operations'])
@router.get('/health')
def health(): return {'status':'healthy','service':'payflow-api','environment':settings.environment}
@router.get('/ready')
def ready():
    with engine.connect() as c: c.execute(text('SELECT 1'))
    return {'status':'ready','database':'ok'}
