"""empty message

Revision ID: 4571de123acb
Revises: 0576b1d76579
Create Date: 2026-09-02 11:00:16.165640

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4571de123acb'
down_revision: Union[str, Sequence[str], None] = '0576b1d76579'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
