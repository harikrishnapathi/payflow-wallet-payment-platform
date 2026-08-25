from sqlalchemy import text


def test_database_connection(db):
    result = db.execute(
        text("SELECT current_database()")
    ).scalar_one()

    assert result == "payflow_test_db"