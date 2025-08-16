"""merge_multiple_heads

Revision ID: 8d474fc2857f
Revises: add_dropoff_location, b735851e31e6
Create Date: 2025-08-16 09:32:10.538035

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8d474fc2857f'
down_revision = ('add_dropoff_location', 'b735851e31e6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
