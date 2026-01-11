from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    users = User.query.all()
    print(f"用户总数: {len(users)}")
    for user in users:
        print(f"用户ID: {user.id}, 用户名: {user.username}, 邮箱: {user.email}")