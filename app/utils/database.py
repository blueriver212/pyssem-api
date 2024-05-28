from app import db

def commit_to_db():
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e
