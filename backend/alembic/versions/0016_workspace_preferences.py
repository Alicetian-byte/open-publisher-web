"""Writing preferences and model capabilities."""
from alembic import op
import sqlalchemy as sa
revision = "0016_workspace_preferences"
down_revision = "0015_app_secrets"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("model_profiles", sa.Column("capabilities", sa.JSON(), nullable=True))
    op.create_table("workspace_preferences", sa.Column("id", sa.String(80), primary_key=True), sa.Column("value", sa.JSON(), nullable=False))

def downgrade():
    raise RuntimeError("保留用户设置数据，请使用备份恢复数据库")
